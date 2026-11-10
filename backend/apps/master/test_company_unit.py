import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from apps.common.access_control.constants import Module
from apps.common.access_control.testing import grant_access

from .import_engine import process_import_job
from .models import Company, ImportJob, Unit

MEDIA_ROOT = tempfile.mkdtemp(prefix="company-unit-test-")
COMPANIES = "/api/v1/master/companies/"
UNITS = "/api/v1/master/units/"


def _field_errors(response) -> dict:
    return response.data["error"]["detail"]


def _workbook(headers: list[str], rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CompanyUnitTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="company@example.com", password="pass12345!"
        )
        grant_access(cls.user, Module.MASTER)
        cls.dmil = Company.objects.create(name="De-Maithan Ispat Limited")
        cls.other = Company.objects.create(name="Devika Ventures")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def run_import(self, master_type: str, content: bytes) -> ImportJob:
        job = ImportJob(master_type=master_type, original_filename="upload.xlsx")
        job.source_file.save("upload.xlsx", ContentFile(content), save=False)
        job.save()
        process_import_job(job.pk)
        job.refresh_from_db()
        return job


class CompanyApiTests(CompanyUnitTestBase):
    def test_create_trims_and_defaults_active(self):
        response = self.client.post(COMPANIES, {"name": "  Acme Steel  "}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["name"], "Acme Steel")
        self.assertTrue(response.data["is_active"])

    def test_required_and_case_insensitive_duplicate(self):
        response = self.client.post(COMPANIES, {"name": "   "}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", _field_errors(response))

        for variant in ["devika ventures", " DEVIKA VENTURES "]:
            response = self.client.post(COMPANIES, {"name": variant}, format="json")
            self.assertEqual(response.status_code, 400, variant)
            self.assertIn("already exists", str(_field_errors(response)["name"][0]))

    def test_edit_view_search_and_status_filter(self):
        response = self.client.patch(
            f"{COMPANIES}{self.other.pk}/", {"name": "Devika Ventures Pvt", "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self.client.get(f"{COMPANIES}{self.other.pk}/")
        self.assertEqual(response.data["name"], "Devika Ventures Pvt")
        self.assertFalse(response.data["is_active"])

        response = self.client.get(COMPANIES, {"search": "maithan"})
        self.assertEqual(
            [r["name"] for r in response.data["results"]], ["De-Maithan Ispat Limited"]
        )
        response = self.client.get(COMPANIES, {"is_active": "false"})
        self.assertEqual([r["id"] for r in response.data["results"]], [self.other.pk])

    def test_rename_to_existing_company_rejected(self):
        response = self.client.patch(
            f"{COMPANIES}{self.other.pk}/", {"name": "de-maithan ispat limited"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_company_with_units_is_blocked(self):
        Unit.objects.create(name="Jajpur", company=self.dmil)
        response = self.client.delete(f"{COMPANIES}{self.dmil.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Deactivate", response.data["detail"])
        self.assertTrue(Company.objects.filter(pk=self.dmil.pk).exists())

    def test_template_has_only_company_name(self):
        response = self.client.get(f"{COMPANIES}template/")
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.content)).active
        self.assertEqual([c.value for c in sheet[1] if c.value], ["Company Name"])

    def test_excel_preview_reports_new_existing_duplicate(self):
        upload = SimpleUploadedFile(
            "companies.xlsx",
            _workbook(
                ["Company Name"],
                [["Acme Steel"], [" ACME STEEL "], [" de-maithan ispat limited "], ["Nova"]],
            ),
        )
        response = self.client.post(f"{COMPANIES}validate/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            {k: response.data[k] for k in ("total", "valid", "existing", "duplicate", "failed")},
            {"total": 4, "valid": 2, "existing": 1, "duplicate": 1, "failed": 0},
        )
        self.assertEqual(Company.objects.count(), 2)

    def test_units_of_company_are_derived_from_unit_records(self):
        for name in ["Jajpur", "Bhubaneswar", "Rourkela"]:
            Unit.objects.create(name=name, company=self.dmil)
        Unit.objects.create(name="Jajpur", company=self.other)
        response = self.client.get(UNITS, {"company": self.dmil.pk, "page_size": 500})
        self.assertEqual(
            [r["name"] for r in response.data["results"]], ["Bhubaneswar", "Jajpur", "Rourkela"]
        )
        self.assertEqual(
            sorted(self.dmil.units.values_list("name", flat=True)),
            ["Bhubaneswar", "Jajpur", "Rourkela"],
        )

    def test_company_list_shows_associated_units(self):
        for name in ["Rourkela", "Jajpur", "Bhubaneswar"]:
            Unit.objects.create(name=name, company=self.dmil)
        angul = Unit.objects.create(name="Angul", company=self.other, is_active=False)
        for index in range(5):
            Unit.objects.create(
                name="Plant", company=Company.objects.create(name=f"Extra Co {index}")
            )

        with self.assertNumQueries(4):
            response = self.client.get(COMPANIES, {"page_size": 50})
        by_name = {row["name"]: row for row in response.data["results"]}
        self.assertEqual(
            [u["name"] for u in by_name["De-Maithan Ispat Limited"]["units"]],
            ["Bhubaneswar", "Jajpur", "Rourkela"],
        )
        self.assertEqual(
            by_name["Devika Ventures"]["units"],
            [{"id": angul.pk, "name": "Angul", "is_active": False}],
        )

        response = self.client.patch(
            f"{COMPANIES}{self.dmil.pk}/", {"units": []}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.dmil.units.count(), 3)

    def test_excel_import_creates_active_and_dedupes(self):
        content = _workbook(
            ["Company Name"],
            [["  Acme Steel "], ["acme steel"], ["DEVIKA VENTURES"], [""], ["Nova Metals"]],
        )
        job = self.run_import(ImportJob.MasterType.COMPANY, content)
        self.assertEqual(job.status, ImportJob.Status.COMPLETED_WITH_ERRORS, job.detail)
        self.assertEqual(job.created_rows, 2)
        acme = Company.objects.get(name="Acme Steel")
        self.assertTrue(acme.is_active)
        self.assertTrue(Company.objects.get(name="Nova Metals").is_active)
        self.assertEqual(Company.objects.filter(name__iexact="devika ventures").count(), 1)


class UnitApiTests(CompanyUnitTestBase):
    def test_create_with_company_and_view(self):
        response = self.client.post(
            UNITS, {"name": "  Jajpur ", "company_id": self.dmil.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["name"], "Jajpur")
        self.assertTrue(response.data["is_active"])
        self.assertEqual(
            response.data["company"],
            {"id": self.dmil.pk, "name": "De-Maithan Ispat Limited", "is_active": True},
        )
        detail = self.client.get(f"{UNITS}{response.data['id']}/")
        self.assertEqual(detail.data["company"]["id"], self.dmil.pk)

    def test_name_and_company_required(self):
        response = self.client.post(UNITS, {"name": "Jajpur"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(_field_errors(response)["company_id"][0]), "Company is required.")
        response = self.client.post(
            UNITS, {"name": "  ", "company_id": self.dmil.pk}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", _field_errors(response))
        response = self.client.post(UNITS, {"name": "X", "company_id": 999999}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("company_id", _field_errors(response))

    def test_duplicate_scoped_to_company(self):
        Unit.objects.create(name="Jajpur", company=self.dmil)
        for variant in ["jajpur", " Jajpur ", "JAJPUR"]:
            response = self.client.post(
                UNITS, {"name": variant, "company_id": self.dmil.pk}, format="json"
            )
            self.assertEqual(response.status_code, 400, variant)
            self.assertEqual(
                str(_field_errors(response)["name"][0]),
                "A unit with this name already exists in this company.",
            )

        response = self.client.post(
            UNITS, {"name": "Bhubaneswar", "company_id": self.dmil.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        response = self.client.post(
            UNITS, {"name": "Jajpur", "company_id": self.other.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_db_constraint_is_scoped_and_case_insensitive(self):
        Unit.objects.create(name="Jajpur", company=self.dmil)
        Unit.objects.create(name="JAJPUR", company=self.other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Unit.objects.create(name="jajpur", company=self.dmil)

    def test_edit_moving_into_conflict_rejected(self):
        Unit.objects.create(name="Jajpur", company=self.dmil)
        other_unit = Unit.objects.create(name="Jajpur", company=self.other)
        response = self.client.patch(
            f"{UNITS}{other_unit.pk}/", {"company_id": self.dmil.pk}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"{UNITS}{other_unit.pk}/", {"name": "Jajpur Plant 2", "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        other_unit.refresh_from_db()
        self.assertEqual(other_unit.company_id, self.other.pk)
        self.assertFalse(other_unit.is_active)

    def test_list_filters(self):
        Unit.objects.create(name="Jajpur", company=self.dmil)
        Unit.objects.create(name="Bhubaneswar", company=self.dmil, is_active=False)
        Unit.objects.create(name="Jajpur", company=self.other)
        response = self.client.get(UNITS, {"company": self.dmil.pk})
        self.assertEqual(response.data["count"], 2)
        response = self.client.get(UNITS, {"search": "jaj"})
        self.assertEqual(response.data["count"], 2)
        response = self.client.get(UNITS, {"is_active": "false"})
        self.assertEqual([r["name"] for r in response.data["results"]], ["Bhubaneswar"])

    def test_template_headers(self):
        response = self.client.get(f"{UNITS}template/")
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.content)).active
        self.assertEqual([c.value for c in sheet[1] if c.value], ["Unit Name", "Company Name"])

    def test_import_rejects_wrong_template(self):
        upload = SimpleUploadedFile("u.xlsx", _workbook(["Unit Name"], [["Jajpur"]]))
        response = self.client.post(f"{UNITS}import/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_excel_import_matches_company_and_reports_rows(self):
        Unit.objects.create(name="Jajpur", company=self.dmil)
        content = _workbook(
            ["Unit Name", "Company Name"],
            [
                ["Bhubaneswar", "  de-maithan ispat LIMITED "],
                [" jajpur ", "De-Maithan Ispat Limited"],
                ["Jajpur", "Devika Ventures"],
                ["jajpur", "devika ventures"],
                ["Angul", "Unknown Company"],
                ["", "Devika Ventures"],
                ["Kalinganagar", ""],
            ],
        )
        job = self.run_import(ImportJob.MasterType.UNIT, content)

        self.assertEqual(job.status, ImportJob.Status.COMPLETED_WITH_ERRORS, job.detail)
        self.assertEqual(job.total_rows, 7)
        self.assertEqual(job.created_rows, 2)
        self.assertEqual(job.skipped_rows, 1)
        self.assertEqual(job.failed_rows, 4)
        self.assertTrue(job.error_file)

        self.assertTrue(
            Unit.objects.filter(name="Bhubaneswar", company=self.dmil, is_active=True).exists()
        )
        self.assertTrue(
            Unit.objects.filter(name="Jajpur", company=self.other, is_active=True).exists()
        )
        self.assertFalse(Company.objects.filter(name__iexact="Unknown Company").exists())

        reasons = dict(job.errors.values_list("row_number", "reason"))
        self.assertIn("Duplicate Unit Name", reasons[5])
        self.assertEqual(reasons[6], 'Company "Unknown Company" does not exist in Company Master.')
        self.assertEqual(reasons[7], "Unit Name is required.")
        self.assertEqual(reasons[8], "Company Name is required.")
