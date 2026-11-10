import re
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from apps.common.access_control.constants import Module
from apps.common.access_control.testing import grant_access

from .import_engine import process_import_job
from .models import ImportJob, Vendor
from .vendor_excel import VENDOR_EXCEL_HEADERS
from .vendor_rules import (
    INVALID_CONTACT,
    INVALID_EMAIL,
    INVALID_GSTIN,
    INVALID_GSTIN_CHECK_DIGIT,
    clean_vendor_text,
    gstin_check_digit,
    normalize_contact,
    normalize_email,
    normalize_gstin,
)

MEDIA_ROOT = tempfile.mkdtemp(prefix="vendor-test-")
URL = "/api/v1/master/vendors/"
VENDOR_ID = re.compile(r"^VEN-\d{6}$")


def gst(first_fourteen: str) -> str:
    """Build a GSTIN with a correct check digit."""
    return first_fourteen + gstin_check_digit(first_fourteen)


GST_A = gst("22AAAAA0000A1Z")
GST_B = gst("21ABCDE1234F1Z")
GST_C = gst("27AAPFU0939F1Z")


def _errors(response) -> dict:
    return response.data["error"]["detail"]


def _workbook(rows: list[list], headers: list[str] | None = None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers or VENDOR_EXCEL_HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class VendorRulesTests(SimpleTestCase):
    def test_gstin_validation(self):
        self.assertEqual(normalize_gstin(f" {GST_A.lower()} "), (GST_A, None))
        self.assertEqual(normalize_gstin("27AAPFU0939F1ZV"), ("27AAPFU0939F1ZV", None))
        self.assertEqual(normalize_gstin(""), ("", None))
        self.assertEqual(normalize_gstin("22AAAAA0000A1Z"), ("", INVALID_GSTIN))
        self.assertEqual(normalize_gstin(gst("00AAAAA0000A1Z")), ("", INVALID_GSTIN))
        wrong_digit = GST_A[:14] + ("0" if GST_A[14] != "0" else "1")
        self.assertEqual(normalize_gstin(wrong_digit), ("", INVALID_GSTIN_CHECK_DIGIT))

    def test_email_and_contact(self):
        self.assertEqual(normalize_email(" Sales@ABDrives.COM "), ("sales@abdrives.com", None))
        self.assertEqual(normalize_email("not-an-email"), ("", INVALID_EMAIL))
        self.assertEqual(normalize_contact(" +91  99070 81109 "), ("+91 99070 81109", None))
        self.assertEqual(normalize_contact("0091 9907081109"), ("+91 9907081109", None))
        self.assertEqual(normalize_contact("0674-2345678"), ("0674-2345678", None))
        self.assertEqual(normalize_contact("12ab"), ("", INVALID_CONTACT))
        self.assertEqual(normalize_contact("123"), ("", INVALID_CONTACT))

    def test_clean_text_keeps_codes_as_text(self):
        self.assertEqual(clean_vendor_text(10013031.0), "10013031")
        self.assertEqual(clean_vendor_text("  0010013031 "), "0010013031")
        self.assertEqual(clean_vendor_text("AB\u00a0 Drives\u200b"), "AB Drives")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class VendorTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="buyer@example.com", password="pass12345!", first_name="Pur", last_name="Chase"
        )
        grant_access(cls.user, Module.MASTER)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create(self, **overrides):
        data = {
            "sap_vendor_id": " 0010013560 ",
            "vendor_name": "  AB Drives   & Automation Pvt Ltd ",
            "email": " Sales@ABDrives.COM ",
            "contact_no": " 9907081109 ",
            "gstin": f" {GST_A.lower()} ",
            "location": " Raipur ",
        }
        data.update(overrides)
        return self.client.post(URL, data, format="json")

    def run_import(self, content: bytes) -> ImportJob:
        job = ImportJob(
            master_type=ImportJob.MasterType.VENDOR,
            original_filename="vendors.xlsx",
            uploaded_by=self.user,
        )
        job.source_file.save("vendors.xlsx", ContentFile(content), save=True)
        process_import_job(job.pk)
        job.refresh_from_db()
        return job

    def upload(self, path: str, content: bytes):
        file = SimpleUploadedFile(
            "vendors.xlsx",
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        return self.client.post(f"{URL}{path}/", {"file": file}, format="multipart")


class VendorApiTests(VendorTestBase):
    def test_create_generates_erp_id_and_normalizes(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertRegex(data["erp_vendor_id"], VENDOR_ID)
        self.assertEqual(data["sap_vendor_id"], "0010013560")
        self.assertEqual(data["vendor_name"], "AB Drives & Automation Pvt Ltd")
        self.assertEqual(data["email"], "sales@abdrives.com")
        self.assertEqual(data["contact_no"], "9907081109")
        self.assertEqual(data["gstin"], GST_A)
        self.assertEqual(data["location"], "Raipur")
        self.assertTrue(data["is_active"])
        self.assertEqual(data["created_by"]["id"], self.user.pk)

        second = self.create(sap_vendor_id="", gstin="", vendor_name="Second")
        first_no = int(data["erp_vendor_id"][4:])
        self.assertEqual(int(second.data["erp_vendor_id"][4:]), first_no + 1)

    def test_erp_id_is_read_only_and_survives_sap_change(self):
        response = self.create(erp_vendor_id="VEN-999999")
        vendor_id = response.data["erp_vendor_id"]
        self.assertNotEqual(vendor_id, "VEN-999999")
        patch = self.client.patch(
            f"{URL}{response.data['id']}/",
            {"erp_vendor_id": "VEN-000777", "sap_vendor_id": "20000001"},
            format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(patch.data["erp_vendor_id"], vendor_id)
        self.assertEqual(patch.data["sap_vendor_id"], "20000001")

    def test_only_vendor_name_is_required(self):
        response = self.client.post(URL, {"vendor_name": "  "}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(_errors(response)["vendor_name"], ["Vendor Name is required."])
        minimal = self.client.post(URL, {"vendor_name": "Only Name"}, format="json")
        self.assertEqual(minimal.status_code, 201, minimal.data)
        self.assertEqual(minimal.data["sap_vendor_id"], "")
        self.assertEqual(minimal.data["gstin"], "")

    def test_vendor_name_is_not_unique_but_sap_and_gstin_are(self):
        first = self.create()
        same_name = self.create(sap_vendor_id="", gstin="")
        self.assertEqual(same_name.status_code, 201, same_name.data)

        dup_sap = self.create(sap_vendor_id="0010013560", gstin="", vendor_name="Other")
        self.assertEqual(dup_sap.status_code, 400)
        message = _errors(dup_sap)["sap_vendor_id"][0]
        self.assertIn("SAP Vendor ID 0010013560 already exists", message)
        self.assertIn(first.data["erp_vendor_id"], message)

        dup_gstin = self.create(sap_vendor_id="", gstin=GST_A.lower(), vendor_name="Other")
        self.assertEqual(dup_gstin.status_code, 400)
        self.assertIn("GSTIN already assigned to another Vendor", _errors(dup_gstin)["gstin"][0])

        blank_keys = self.create(sap_vendor_id="", gstin="", vendor_name="Third")
        self.assertEqual(blank_keys.status_code, 201)

    def test_editing_keeps_own_sap_and_gstin(self):
        created = self.create()
        response = self.client.patch(
            f"{URL}{created.data['id']}/",
            {"sap_vendor_id": "0010013560", "gstin": GST_A, "location": "Bhilai"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["location"], "Bhilai")
        self.assertEqual(response.data["updated_by"]["id"], self.user.pk)

    def test_invalid_email_gstin_contact(self):
        response = self.create(email="bad@", gstin="22AAAAA0000A1Z5", contact_no="12ab")
        self.assertEqual(response.status_code, 400)
        errors = _errors(response)
        self.assertEqual(errors["email"], [INVALID_EMAIL])
        self.assertEqual(errors["gstin"], [INVALID_GSTIN_CHECK_DIGIT])
        self.assertEqual(errors["contact_no"], [INVALID_CONTACT])

    def test_deactivate_and_activate(self):
        created = self.create()
        vendor_id = created.data["id"]
        blocked = self.client.patch(f"{URL}{vendor_id}/", {"is_active": False}, format="json")
        self.assertTrue(blocked.data["is_active"])
        self.assertEqual(self.client.delete(f"{URL}{vendor_id}/").status_code, 204)
        self.assertFalse(Vendor.objects.get(pk=vendor_id).is_active)
        activated = self.client.post(f"{URL}{vendor_id}/activate/")
        self.assertTrue(activated.data["is_active"])

    def test_search_filters_sort_and_pagination(self):
        first = self.create()
        self.create(
            sap_vendor_id="10013031",
            vendor_name="Mesco Kalinga Steel Ltd",
            email="",
            contact_no="",
            gstin="",
            location="jajpur",
        )
        self.create(
            sap_vendor_id="",
            vendor_name="Sarika Associates",
            email="accounts@sarika.in",
            contact_no="+91 98765 43210",
            gstin=GST_B,
            location="Cuttack",
        )
        Vendor.objects.filter(vendor_name="Sarika Associates").update(is_active=False)

        def names(query: str) -> list[str]:
            return [row["vendor_name"] for row in self.client.get(f"{URL}?{query}").data["results"]]

        self.assertEqual(
            names(f"search={first.data['erp_vendor_id']}"), [first.data["vendor_name"]]
        )
        self.assertEqual(names("search=10013031"), ["Mesco Kalinga Steel Ltd"])
        self.assertEqual(names(f"search={GST_B.lower()}"), ["Sarika Associates"])
        self.assertEqual(names("search=sarika.in"), ["Sarika Associates"])
        self.assertEqual(names("search=9876543210"), ["Sarika Associates"])
        self.assertEqual(names("search=kalinga"), ["Mesco Kalinga Steel Ltd"])
        self.assertEqual(names("location=JAJPUR"), ["Mesco Kalinga Steel Ltd"])
        self.assertEqual(names("is_active=false"), ["Sarika Associates"])
        self.assertEqual(
            names("ordering=-vendor_name"),
            ["Sarika Associates", "Mesco Kalinga Steel Ltd", "AB Drives & Automation Pvt Ltd"],
        )
        self.assertEqual(names("ordering=location")[0], "Sarika Associates")

        page = self.client.get(f"{URL}?page_size=2&page=2").data
        self.assertEqual(page["count"], 3)
        self.assertEqual(len(page["results"]), 1)

        self.create(sap_vendor_id="", gstin="", vendor_name="Fourth", location="Raipur ")
        self.assertEqual(self.client.get(f"{URL}locations/").data, ["Cuttack", "jajpur", "Raipur"])


class VendorExcelTests(VendorTestBase):
    def test_template_has_exact_columns(self):
        response = self.client.get(f"{URL}template/")
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook.worksheets[0]
        self.assertEqual([cell.value for cell in sheet[1]], VENDOR_EXCEL_HEADERS)
        self.assertEqual(
            VENDOR_EXCEL_HEADERS,
            ["SAP Vendor ID", "Vendor Name", "Email ID", "Contact No.", "GSTIN", "Location"],
        )
        self.assertTrue(all(cell.value is None for cell in sheet[2]))
        self.assertEqual(sheet["A2"].number_format, "@")

    def test_wrong_template_is_rejected(self):
        response = self.upload("validate", _workbook([["x"]], headers=["Name", "Code"]))
        self.assertEqual(response.status_code, 400)

    def _mixed_file(self) -> bytes:
        return _workbook(
            [
                ["0010013560", "AB Drives & Automation Pvt Ltd", "", "", GST_A, "Raipur"],
                ["10013031", "Mesco Kalinga Steel Ltd", "", "", "", "Jajpur"],
                [None, None, None, None, None, None],
                ["", "", "x@y.com", "", "", ""],
                ["10013999", "Bad Email", "bad@", "", "", ""],
                ["10014000", "Bad GSTIN", "", "", "22AAAAA0000A1Z", ""],
                ["10013031", "Copy In File", "", "", "", ""],
                ["", "Gst Copy In File", "", "", GST_A, ""],
                ["20000001", "Different Name", "", "", "", ""],
                ["", "Other Gst Owner", "", "", GST_C, ""],
                [
                    10014370,
                    " Sarika  Associates ",
                    "ACCOUNTS@SARIKA.IN",
                    "+91 98765 43210",
                    GST_B.lower(),
                    " Cuttack ",
                ],
            ]
        )

    def _seed(self):
        self.create(
            sap_vendor_id="0010013560", gstin=GST_A, vendor_name="AB Drives & Automation Pvt Ltd"
        )
        self.create(sap_vendor_id="20000001", gstin="", vendor_name="Existing Other")
        self.create(sap_vendor_id="", gstin=GST_C, vendor_name="Gst Holder")

    def test_preview_classifies_rows(self):
        self._seed()
        response = self.upload("validate", self._mixed_file())
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(
            {key: data[key] for key in ("total", "valid", "existing", "duplicate", "failed")},
            {"total": 10, "valid": 2, "existing": 1, "duplicate": 2, "failed": 5},
        )
        reasons = {row["row"]: row["reason"] for row in data["rows"]}
        self.assertIn("Skipped Existing", reasons[2])
        self.assertEqual(reasons[5], "Vendor Name is required.")
        self.assertEqual(reasons[6], INVALID_EMAIL)
        self.assertEqual(reasons[7], INVALID_GSTIN)
        self.assertEqual(
            reasons[8], "Duplicate SAP Vendor ID 10013031 within the Excel file (row 3)."
        )
        self.assertIn("Duplicate GSTIN", reasons[9])
        self.assertIn("SAP Vendor ID 20000001 already exists", reasons[10])
        self.assertIn("GSTIN already assigned to another Vendor", reasons[11])
        sarika = next(row for row in data["rows"] if row["row"] == 12)
        self.assertEqual(sarika["status"], "valid")
        self.assertEqual(sarika["sap_vendor_id"], "10014370")
        self.assertEqual(sarika["gstin"], GST_B)
        self.assertEqual(sarika["email"], "accounts@sarika.in")

    def test_import_creates_active_vendors_with_erp_ids(self):
        self._seed()
        before_ids = set(Vendor.objects.values_list("erp_vendor_id", flat=True))
        job = self.run_import(self._mixed_file())

        self.assertEqual(job.status, ImportJob.Status.COMPLETED_WITH_ERRORS, job.detail)
        self.assertEqual(
            (job.total_rows, job.created_rows, job.skipped_rows, job.failed_rows), (10, 2, 1, 7)
        )
        created = Vendor.objects.exclude(erp_vendor_id__in=before_ids)
        self.assertEqual(created.count(), 2)
        self.assertTrue(all(VENDOR_ID.match(v.erp_vendor_id) for v in created))
        self.assertTrue(all(v.is_active and v.created_by_id == self.user.pk for v in created))
        mesco = created.get(vendor_name="Mesco Kalinga Steel Ltd")
        self.assertEqual(mesco.sap_vendor_id, "10013031")
        sarika = created.get(sap_vendor_id="10014370")
        self.assertEqual(
            (sarika.vendor_name, sarika.gstin, sarika.email, sarika.contact_no, sarika.location),
            ("Sarika Associates", GST_B, "accounts@sarika.in", "+91 98765 43210", "Cuttack"),
        )

        self.assertTrue(job.error_file)
        sheet = load_workbook(job.error_file.path).active
        self.assertEqual(
            [cell.value for cell in sheet[1]], ["Row Number", *VENDOR_EXCEL_HEADERS, "Error Reason"]
        )
        self.assertEqual(sheet.max_row, 8)

        again = self.run_import(self._mixed_file())
        self.assertEqual(again.created_rows, 0)
        self.assertEqual(again.skipped_rows, 3)
