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
from .models import ImportJob, QcParameter, Uom
from .qc_parameter_excel import QC_PARAMETER_EXCEL_HEADERS
from .qc_parameter_rules import clean_qc_text

MEDIA_ROOT = tempfile.mkdtemp(prefix="qc-parameter-test-")
URL = "/api/v1/master/qc-parameters/"


def _errors(response) -> dict:
    return response.data["error"]["detail"]


def _workbook(rows: list[list], headers: list[str] | None = None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers or QC_PARAMETER_EXCEL_HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class QcParameterRulesTests(SimpleTestCase):
    def test_clean_keeps_unit_symbols(self):
        self.assertEqual(clean_qc_text("  kg/cm²  "), "kg/cm²")
        self.assertEqual(clean_qc_text("\u00a0°C\u200b"), "°C")
        self.assertEqual(clean_qc_text("Gross   Calorific\u00a0Value"), "Gross Calorific Value")
        self.assertEqual(clean_qc_text(None), "")
        self.assertEqual(clean_qc_text(5.0), "5")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class QcParameterTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="qc@example.com", password="pass12345!", first_name="Qa", last_name="Lead"
        )
        grant_access(cls.user, Module.MASTER)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create(self, **overrides):
        data = {"name": "  Moisture ", "short_name": " mc ", "unit": " % "}
        data.update(overrides)
        return self.client.post(URL, data, format="json")

    def run_import(self, content: bytes) -> ImportJob:
        job = ImportJob(
            master_type=ImportJob.MasterType.QC_PARAMETER,
            original_filename="qc.xlsx",
            uploaded_by=self.user,
        )
        job.source_file.save("qc.xlsx", ContentFile(content), save=False)
        job.save()
        process_import_job(job.pk)
        job.refresh_from_db()
        return job


class QcParameterApiTests(QcParameterTestBase):
    def test_create_normalizes_and_audits(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertEqual(data["name"], "Moisture")
        self.assertEqual(data["short_name"], "MC")
        self.assertEqual(data["unit"], "%")
        self.assertTrue(data["is_active"])
        self.assertEqual(data["created_by"]["email"], "qc@example.com")
        self.assertEqual(data["updated_by"]["email"], "qc@example.com")

    def test_unit_is_optional_free_text_without_uom_link(self):
        blank = self.create(name="Appearance", short_name="APP", unit="")
        self.assertEqual(blank.status_code, 201, blank.data)
        self.assertEqual(blank.data["unit"], "")
        missing = self.client.post(URL, {"name": "Colour", "short_name": "CLR"}, format="json")
        self.assertEqual(missing.status_code, 201, missing.data)
        self.assertEqual(missing.data["unit"], "")

        for index, unit in enumerate(["kg/cm²", "kcal/kg", "ppm", "MPa", "°C", "mm"]):
            response = self.create(name=f"Param {index}", short_name=f"P{index}", unit=unit)
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["unit"], unit)
        self.assertFalse(Uom.objects.exists())
        field_names = {field.name for field in QcParameter._meta.get_fields()}
        self.assertNotIn("uom", field_names)

    def test_required_fields(self):
        response = self.client.post(URL, {"name": "  ", "short_name": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        errors = _errors(response)
        self.assertIn("QC Parameter Name is required.", str(errors["name"]))
        self.assertIn("Short Name is required.", str(errors["short_name"]))

    def test_case_insensitive_duplicates(self):
        self.create()
        by_name = self.create(name="MOISTURE", short_name="MOI")
        self.assertEqual(by_name.status_code, 400)
        self.assertIn("QC Parameter Name already exists.", str(_errors(by_name)["name"]))
        by_short = self.create(name="Moisture Content", short_name="Mc")
        self.assertEqual(by_short.status_code, 400)
        self.assertIn("Short Name already exists.", str(_errors(by_short)["short_name"]))

    def test_edit_view_and_keep_own_values(self):
        record_id = self.create().data["id"]
        response = self.client.patch(
            f"{URL}{record_id}/",
            {"name": "Moisture", "short_name": "mc", "unit": " % w/w "},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["unit"], "% w/w")
        detail = self.client.get(f"{URL}{record_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["short_name"], "MC")

    def test_is_active_not_writable_and_deactivate_activate(self):
        record_id = self.create().data["id"]
        self.client.patch(f"{URL}{record_id}/", {"is_active": False}, format="json")
        self.assertTrue(QcParameter.objects.get(pk=record_id).is_active)

        self.assertEqual(self.client.delete(f"{URL}{record_id}/").status_code, 204)
        record = QcParameter.objects.get(pk=record_id)
        self.assertFalse(record.is_active)
        response = self.client.post(f"{URL}{record_id}/activate/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_active"])

    def test_search_status_and_pagination(self):
        self.create()
        self.create(name="Ash Content", short_name="ASH", unit="%")
        self.create(name="Volatile Matter", short_name="VM", unit="%")
        QcParameter.objects.filter(short_name="VM").update(is_active=False)

        def names(query: str) -> list[str]:
            return [row["name"] for row in self.client.get(f"{URL}?{query}").data["results"]]

        self.assertEqual(names("search=ash"), ["Ash Content"])
        self.assertEqual(names("search=mc"), ["Moisture"])
        self.assertEqual(names("is_active=false"), ["Volatile Matter"])
        self.assertEqual(names("is_active=true"), ["Ash Content", "Moisture"])
        page = self.client.get(f"{URL}?page_size=2&page=2").data
        self.assertEqual(page["count"], 3)
        self.assertEqual([row["name"] for row in page["results"]], ["Volatile Matter"])

    def test_template_has_exact_columns(self):
        response = self.client.get(f"{URL}template/")
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.content)).active
        headers = [cell.value for cell in sheet[1] if cell.value]
        self.assertEqual(headers, ["Name", "Short Name", "Unit"])
        self.assertTrue(all(cell.value is None for cell in sheet[2]))


class QcParameterImportTests(QcParameterTestBase):
    def test_wrong_template_rejected(self):
        upload = SimpleUploadedFile("x.xlsx", _workbook([["a"]], headers=["Name", "Code"]))
        response = self.client.post(f"{URL}validate/", {"file": upload})
        self.assertEqual(response.status_code, 400)

    def test_preview_classifies_rows(self):
        QcParameter.objects.create(name="Moisture", short_name="MC", unit="%")
        QcParameter.objects.create(name="Volatile Matter", short_name="VM", unit="%")
        content = _workbook(
            [
                [" moisture ", "mc", "%"],
                ["Ash Content", " ash ", ""],
                ["ASH CONTENT", "ASH2", "%"],
                ["", "", ""],
                ["Volatile Content", "vm", "%"],
                ["", "NM", "%"],
            ]
        )
        response = self.client.post(
            f"{URL}validate/", {"file": SimpleUploadedFile("qc.xlsx", content)}
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(
            (data["total"], data["valid"], data["existing"], data["duplicate"], data["failed"]),
            (5, 1, 1, 1, 2),
        )
        reasons = {row["row"]: row["reason"] for row in data["rows"]}
        self.assertIn("Skipped Existing", reasons[2])
        self.assertIn("Duplicate Name within the Excel file (row 3)", reasons[4])
        self.assertIn('Short Name "VM" already belongs to "Volatile Matter"', reasons[6])
        self.assertEqual(reasons[7], "QC Parameter Name is required.")
        self.assertEqual(QcParameter.objects.count(), 2)

    def test_import_creates_active_records_and_reports_rows(self):
        QcParameter.objects.create(name="Moisture", short_name="MC", unit="%")
        content = _workbook(
            [
                ["Moisture", "MC", "%"],
                [" Gross Calorific Value ", "gcv", " kcal/kg "],
                ["Tensile Strength", "ts", "kg/cm²"],
                ["Appearance", "app", None],
                [None, None, None],
                ["Tensile strength", "TS2", "MPa"],
                ["Hardness", "", "HRC"],
            ]
        )
        job = self.run_import(content)
        self.assertEqual(job.status, ImportJob.Status.COMPLETED_WITH_ERRORS, job.detail)
        self.assertEqual(job.total_rows, 6)
        self.assertEqual(job.created_rows, 3)
        self.assertEqual(job.skipped_rows, 1)
        self.assertEqual(job.failed_rows, 2)
        self.assertTrue(job.error_file)

        gcv = QcParameter.objects.get(short_name="GCV")
        self.assertEqual(gcv.name, "Gross Calorific Value")
        self.assertEqual(gcv.unit, "kcal/kg")
        self.assertTrue(gcv.is_active)
        self.assertEqual(gcv.created_by, self.user)
        self.assertEqual(QcParameter.objects.get(short_name="TS").unit, "kg/cm²")
        self.assertEqual(QcParameter.objects.get(short_name="APP").unit, "")

        reasons = {e.row_number: e.reason for e in job.errors.all()}
        self.assertIn("Duplicate Name within the Excel file (row 4)", reasons[7])
        self.assertEqual(reasons[8], "Short Name is required.")
        error_sheet = load_workbook(job.error_file.path).active
        header = [cell.value for cell in error_sheet[1]]
        self.assertEqual(header, ["Row Number", "Name", "Short Name", "Unit", "Error Reason"])
