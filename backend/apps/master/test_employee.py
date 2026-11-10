import re
import shutil
import tempfile
from datetime import date, datetime
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from apps.common.access_control.constants import Module
from apps.common.access_control.testing import grant_access

from .employee_excel import EMPLOYEE_EXCEL_HEADERS
from .employee_rules import normalize_gender, normalize_mobile, parse_joining_date
from .import_engine import process_import_job
from .models import (
    Company,
    Department,
    Designation,
    Division,
    Employee,
    Facility,
    ImportJob,
    Unit,
    Vertical,
)

MEDIA_ROOT = tempfile.mkdtemp(prefix="employee-test-")
EMPLOYEES = "/api/v1/master/employees/"
CODE_PATTERN = re.compile(r"^EMP-\d{6}$")


def _errors(response) -> dict:
    return response.data["error"]["detail"]


def _workbook(rows: list[list], headers: list[str] | None = None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers or EMPLOYEE_EXCEL_HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _row(**overrides) -> list:
    values = {
        "Full Name": "Ravi Kumar",
        "Department": "purchase",
        "Vertical": "",
        "Personal Email": "",
        "Company Email": "",
        "Designation": "Manager",
        "Company": "de-maithan ispat limited",
        "Division": "",
        "Facility": "",
        "Date Of Joining": "01-04-2026",
        "Location": "Jajpur",
        "Gender": "M",
        "Mobile Number": "9876543210",
    }
    values.update(overrides)
    return [values[header] for header in EMPLOYEE_EXCEL_HEADERS]


class EmployeeRulesTests(SimpleTestCase):
    def test_gender_normalization(self):
        self.assertEqual(normalize_gender("M"), "Male")
        self.assertEqual(normalize_gender(" female "), "Female")
        self.assertEqual(normalize_gender("prefer not to say"), "Prefer Not to Say")
        self.assertIsNone(normalize_gender("X"))

    def test_mobile_normalization(self):
        self.assertEqual(normalize_mobile("+91 98765-43210"), ("+919876543210", None))
        self.assertEqual(normalize_mobile(9876543210), ("9876543210", None))
        self.assertEqual(normalize_mobile(9876543210.0), ("9876543210", None))
        self.assertEqual(normalize_mobile("0091 9876543210"), ("+919876543210", None))
        self.assertEqual(normalize_mobile("12345")[1], "Invalid Mobile Number")
        self.assertEqual(normalize_mobile("98765abc10")[1], "Invalid Mobile Number")

    def test_joining_date_parsing(self):
        self.assertEqual(parse_joining_date("01-04-2026"), (date(2026, 4, 1), None))
        self.assertEqual(parse_joining_date("2026-04-01"), (date(2026, 4, 1), None))
        self.assertEqual(parse_joining_date(datetime(2026, 4, 1, 0, 0)), (date(2026, 4, 1), None))
        self.assertEqual(parse_joining_date(46113), (date(2026, 4, 1), None))
        self.assertEqual(parse_joining_date("31-02-2026")[1], "Invalid Date Of Joining")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class EmployeeTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="hr@example.com", password="pass12345!", first_name="Asha", last_name="Rao"
        )
        grant_access(cls.user, Module.MASTER)
        cls.purchase = Department.objects.create(name="Purchase")
        cls.production = Department.objects.create(name="Production")
        cls.steel = Vertical.objects.create(name="Steel", department=cls.purchase)
        cls.melting = Vertical.objects.create(name="Melting", department=cls.production)
        cls.manager = Designation.objects.create(name="Manager")
        cls.dmil = Company.objects.create(name="De-Maithan Ispat Limited")
        cls.abc = Company.objects.create(name="ABC Pvt Ltd")
        cls.jajpur = Unit.objects.create(name="Jajpur", company=cls.dmil)
        cls.bbsr = Unit.objects.create(name="Bhubaneswar", company=cls.abc)
        cls.division = Division.objects.create(name="Operations")
        cls.facility = Facility.objects.create(name="Plant 1")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def payload(self, **overrides) -> dict:
        data = {
            "full_name": "  Ravi Kumar ",
            "gender": "M",
            "mobile_number": "+91 98765 43210",
            "personal_email": " Ravi@Gmail.com ",
            "date_of_joining": "2026-04-01",
            "location": " Jajpur ",
            "department_id": self.purchase.pk,
            "vertical_id": self.steel.pk,
            "designation_id": self.manager.pk,
            "company_id": self.dmil.pk,
            "division_id": self.division.pk,
            "facility_id": None,
            "company_email": "Ravi.Kumar@DMIL.com",
        }
        data.update(overrides)
        return data

    def create(self, **overrides):
        return self.client.post(EMPLOYEES, self.payload(**overrides), format="json")

    def run_import(self, content: bytes) -> ImportJob:
        job = ImportJob(
            master_type=ImportJob.MasterType.EMPLOYEE,
            original_filename="employees.xlsx",
            uploaded_by=self.user,
        )
        job.source_file.save("employees.xlsx", ContentFile(content), save=False)
        job.save()
        process_import_job(job.pk)
        job.refresh_from_db()
        return job


class EmployeeApiTests(EmployeeTestBase):
    def test_create_normalizes_and_generates_code(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertRegex(data["employee_code"], CODE_PATTERN)
        self.assertEqual(data["full_name"], "Ravi Kumar")
        self.assertEqual(data["location"], "Jajpur")
        self.assertEqual(data["gender"], "Male")
        self.assertEqual(data["mobile_number"], "+919876543210")
        self.assertEqual(data["personal_email"], "ravi@gmail.com")
        self.assertEqual(data["company_email"], "ravi.kumar@dmil.com")
        self.assertTrue(data["is_active"])
        self.assertEqual(data["created_by"]["name"], "Asha Rao")
        self.assertNotIn("unit", data)
        self.assertIsNone(Employee.objects.get(pk=data["id"]).unit)

        second = self.create(mobile_number="9123456789", personal_email="")
        self.assertEqual(second.status_code, 201, second.data)
        first_no = int(data["employee_code"][4:])
        self.assertEqual(int(second.data["employee_code"][4:]), first_no + 1)

    def test_employee_code_is_read_only(self):
        response = self.create(employee_code="EMP-999999")
        self.assertNotEqual(response.data["employee_code"], "EMP-999999")
        employee = Employee.objects.get(pk=response.data["id"])
        patch = self.client.patch(
            f"{EMPLOYEES}{employee.pk}/", {"employee_code": "X-1"}, format="json"
        )
        self.assertEqual(patch.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(patch.data["employee_code"], employee.employee_code)
        self.assertRegex(employee.employee_code, CODE_PATTERN)

    def test_required_fields(self):
        response = self.client.post(EMPLOYEES, {}, format="json")
        self.assertEqual(response.status_code, 400)
        errors = _errors(response)
        for field in (
            "full_name",
            "gender",
            "mobile_number",
            "date_of_joining",
            "location",
            "department_id",
            "designation_id",
            "company_id",
        ):
            self.assertIn(field, errors)
        for optional in (
            "vertical_id", "personal_email", "company_email", "division_id", "unit_id"
        ):
            self.assertNotIn(optional, errors)

    def test_optional_fields_can_be_blank(self):
        response = self.create(
            vertical_id=None, personal_email="", company_email="", division_id=None
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["vertical"])

    def test_hidden_unit_is_kept_until_company_changes(self):
        employee_id = self.create().data["id"]
        Employee.objects.filter(pk=employee_id).update(unit=self.jajpur)

        self.client.patch(f"{EMPLOYEES}{employee_id}/", {"unit_id": self.bbsr.pk}, format="json")
        self.client.patch(f"{EMPLOYEES}{employee_id}/", {"location": "Kolkata"}, format="json")
        self.assertEqual(Employee.objects.get(pk=employee_id).unit, self.jajpur)

        response = self.client.patch(
            f"{EMPLOYEES}{employee_id}/", {"company_id": self.abc.pk}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(Employee.objects.get(pk=employee_id).unit)

    def test_vertical_must_belong_to_department(self):
        response = self.create(vertical_id=self.melting.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not belong to Department", str(_errors(response)["vertical_id"]))

    def test_invalid_values(self):
        response = self.create(
            gender="unknown", mobile_number="123", personal_email="bad", date_of_joining="x"
        )
        self.assertEqual(response.status_code, 400)
        errors = _errors(response)
        self.assertIn("Gender must be one of", str(errors["gender"]))
        self.assertIn("Invalid Mobile Number", str(errors["mobile_number"]))
        self.assertIn("Invalid Personal Email", str(errors["personal_email"]))
        self.assertIn("date_of_joining", errors)

    def test_inactive_master_rejected_for_new_selection(self):
        inactive = Designation.objects.create(name="Retired Role", is_active=False)
        response = self.create(designation_id=inactive.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("inactive", str(_errors(response)["designation_id"]))

    def test_mobile_number_blocks_duplicates(self):
        first = self.create()
        response = self.create(mobile_number="+919876543210", personal_email="other@x.com")
        self.assertEqual(response.status_code, 400)
        message = str(_errors(response)["mobile_number"])
        self.assertNotIn(first.data["employee_code"], message)
        self.assertIn("Ravi Kumar (Manager, Purchase)", message)

    def test_personal_email_warns_until_confirmed(self):
        first = self.create()
        response = self.create(full_name="Ravi K", mobile_number="9000000001")
        self.assertEqual(response.status_code, 400)
        errors = _errors(response)
        self.assertIn("possible_duplicate", errors)
        self.assertIn("Ravi Kumar (Manager, Purchase)", str(errors["personal_email"]))
        self.assertNotIn(first.data["employee_code"], str(errors["personal_email"]))

        confirmed = self.create(
            full_name="Ravi K", mobile_number="9000000001", confirm_possible_duplicate=True
        )
        self.assertEqual(confirmed.status_code, 201, confirmed.data)

    def test_company_email_is_not_unique(self):
        self.create(company_email="stores@dmil.com")
        response = self.create(
            full_name="Anil", mobile_number="9000000002", personal_email="",
            company_email="stores@dmil.com",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_edit_updates_audit_and_keeps_unchanged_email(self):
        employee_id = self.create().data["id"]
        response = self.client.patch(
            f"{EMPLOYEES}{employee_id}/",
            {"location": "Kolkata", "company_id": self.abc.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["company"]["name"], "ABC Pvt Ltd")
        self.assertEqual(response.data["updated_by"]["email"], "hr@example.com")

    def test_deactivate_and_activate(self):
        employee_id = self.create().data["id"]
        self.assertEqual(self.client.delete(f"{EMPLOYEES}{employee_id}/").status_code, 204)
        self.assertFalse(Employee.objects.get(pk=employee_id).is_active)
        response = self.client.post(f"{EMPLOYEES}{employee_id}/activate/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_active"])

    def test_search_filter_sort_paginate(self):
        self.create()
        self.create(
            full_name="Anita Das", gender="F", mobile_number="9111111111",
            personal_email="anita@x.com", company_id=self.abc.pk,
            department_id=self.production.pk, vertical_id=None,
        )
        list_response = self.client.get(EMPLOYEES)
        self.assertEqual(list_response.data["count"], 2)
        row = list_response.data["results"][0]
        self.assertNotIn("created_by", row)
        self.assertIn("employee_code", row)

        def names(query: str) -> list[str]:
            return [r["full_name"] for r in self.client.get(f"{EMPLOYEES}?{query}").data["results"]]

        self.assertEqual(names("search=anita@x"), ["Anita Das"])
        self.assertEqual(names("search=98765%2043210"), ["Ravi Kumar"])
        self.assertEqual(names(f"company={self.abc.pk}"), ["Anita Das"])
        self.assertEqual(names(f"department={self.production.pk}"), ["Anita Das"])
        self.assertEqual(names(f"vertical={self.steel.pk}"), ["Ravi Kumar"])
        self.assertEqual(names("gender=Female"), ["Anita Das"])
        self.assertEqual(names("ordering=full_name"), ["Anita Das", "Ravi Kumar"])
        self.assertEqual(names("ordering=-full_name"), ["Ravi Kumar", "Anita Das"])

        page = self.client.get(f"{EMPLOYEES}?page_size=1&page=2").data
        self.assertEqual(page["count"], 2)
        self.assertEqual(len(page["results"]), 1)

        Employee.objects.filter(full_name="Anita Das").update(is_active=False)
        self.assertEqual(names("is_active=false"), ["Anita Das"])

    def test_stats_bulk_status_and_list_contact_fields(self):
        first = self.create().data["id"]
        second = self.create(
            full_name="Anita Das", mobile_number="9111111111", personal_email="",
            company_id=self.abc.pk, department_id=self.production.pk, vertical_id=None,
        ).data["id"]

        row = self.client.get(f"{EMPLOYEES}?ordering=full_name").data["results"][1]
        self.assertEqual(row["company_email"], "ravi.kumar@dmil.com")
        self.assertEqual(row["date_of_joining"], "2026-04-01")

        response = self.client.post(
            f"{EMPLOYEES}bulk-status/", {"ids": [first, second], "is_active": False}, format="json"
        )
        self.assertEqual(response.data, {"updated": 2})
        self.assertFalse(Employee.objects.filter(is_active=True).exists())
        self.assertEqual(Employee.objects.get(pk=first).updated_by, self.user)
        self.client.post(
            f"{EMPLOYEES}bulk-status/", {"ids": [first], "is_active": True}, format="json"
        )
        bad = self.client.post(f"{EMPLOYEES}bulk-status/", {"ids": []}, format="json")
        self.assertEqual(bad.status_code, 400)

        stats = self.client.get(f"{EMPLOYEES}stats/").data
        self.assertEqual(stats, {"total": 2, "active": 1, "departments": 2})

        ordered = self.client.get(f"{EMPLOYEES}?ordering=-status").data["results"]
        self.assertEqual(ordered[0]["id"], first)

    def test_template_has_exact_columns(self):
        response = self.client.get(f"{EMPLOYEES}template/")
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.content)).active
        headers = [cell.value for cell in sheet[1] if cell.value]
        self.assertEqual(headers, EMPLOYEE_EXCEL_HEADERS)
        self.assertNotIn("Employee Code", headers)
        self.assertNotIn("Is Active", headers)
        self.assertNotIn("Unit", headers)


class EmployeeImportTests(EmployeeTestBase):
    def test_wrong_template_rejected(self):
        upload = SimpleUploadedFile("x.xlsx", _workbook([["a"]], headers=["Name", "Mobile"]))
        response = self.client.post(f"{EMPLOYEES}validate/", {"file": upload})
        self.assertEqual(response.status_code, 400)

    def test_old_template_with_unit_column_is_accepted(self):
        headers = [*EMPLOYEE_EXCEL_HEADERS[:7], "Unit", *EMPLOYEE_EXCEL_HEADERS[7:]]
        row = _row()
        content = _workbook([[*row[:7], "Anything", *row[7:]]], headers=headers)
        upload = SimpleUploadedFile("employees.xlsx", content)
        response = self.client.post(f"{EMPLOYEES}validate/", {"file": upload})
        self.assertEqual(response.data["valid"], 1, response.data)
        job = self.run_import(content)
        self.assertEqual(job.created_rows, 1, job.detail)
        self.assertIsNone(Employee.objects.get(mobile_number="9876543210").unit)

    def test_hidden_characters_still_match_masters(self):
        Department.objects.create(name="Director's Office")
        Designation.objects.create(name="Deputy General Manager")
        content = _workbook(
            [
                _row(
                    **{
                        "Full Name": "Arun\u00a0Kumar  Dey",
                        "Department": "Director\u2019s\u00a0Office",
                        "Designation": "\ufeffDeputy  General\u00a0Manager\u200b",
                        "Mobile Number": "9692883028",
                    }
                ),
            ]
        )
        upload = SimpleUploadedFile("employees.xlsx", content)
        response = self.client.post(f"{EMPLOYEES}validate/", {"file": upload})
        self.assertEqual(response.data["valid"], 1, response.data)
        job = self.run_import(content)
        self.assertEqual(job.created_rows, 1, job.detail)
        employee = Employee.objects.get(mobile_number="9692883028")
        self.assertEqual(employee.full_name, "Arun Kumar Dey")
        self.assertEqual(employee.designation.name, "Deputy General Manager")

    def test_preview_classifies_rows(self):
        Employee.objects.create(
            full_name="Existing Person", department=self.purchase, designation=self.manager,
            company=self.dmil, unit=self.jajpur, date_of_joining=date(2025, 1, 1),
            location="Jajpur", gender="Male", mobile_number="9999999999",
            personal_email="dup@x.com",
        )
        content = _workbook(
            [
                _row(),
                _row(**{"Mobile Number": "9999999999"}),
                _row(**{"Mobile Number": "9000000003", "Personal Email": "DUP@x.com"}),
                _row(**{"Department": "Sales", "Mobile Number": "9000000004"}),
                [""] * len(EMPLOYEE_EXCEL_HEADERS),
            ]
        )
        upload = SimpleUploadedFile("employees.xlsx", content)
        response = self.client.post(f"{EMPLOYEES}validate/", {"file": upload})
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["valid"], 1)
        self.assertEqual(data["existing"], 1)
        self.assertEqual(data["possible_duplicates"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertIn('Department "Sales" not found', data["errors"][0]["reason"])
        self.assertEqual(Employee.objects.count(), 1)

    def test_import_creates_active_employees_and_reports_rows(self):
        Employee.objects.create(
            full_name="Existing Person", department=self.purchase, designation=self.manager,
            company=self.dmil, unit=self.jajpur, date_of_joining=date(2025, 1, 1),
            location="Jajpur", gender="Male", mobile_number="9999999999",
            personal_email="dup@x.com", company_email="shared@dmil.com",
        )
        content = _workbook(
            [
                _row(**{"Vertical": "steel", "Personal Email": "Ravi@Gmail.com",
                        "Division": "operations", "Facility": "plant 1",
                        "Mobile Number": "+91 98765-43210"}),
                _row(**{"Full Name": "Sita", "Gender": "female", "Mobile Number": 9123456780,
                        "Date Of Joining": datetime(2026, 5, 2)}),
                _row(**{"Mobile Number": "9999999999"}),
                _row(**{"Full Name": "Dup", "Mobile Number": "9000000005",
                        "Personal Email": "dup@x.com"}),
                _row(**{"Full Name": "Existing Person", "Mobile Number": "9000000006",
                        "Company Email": "Shared@DMIL.com"}),
                _row(**{"Full Name": "Anil", "Mobile Number": "9000000007",
                        "Company": "Unknown Co"}),
                _row(**{"Full Name": "Bad Designation", "Mobile Number": "9000000008",
                        "Designation": "Sr Mngr"}),
                _row(**{"Full Name": "Bad Date", "Mobile Number": "9000000009",
                        "Date Of Joining": "31/13/2026"}),
                _row(**{"Full Name": "Bad Mobile", "Mobile Number": "12345"}),
                _row(**{"Full Name": "Bad Vertical", "Mobile Number": "9000000010",
                        "Vertical": "Melting"}),
                _row(**{"Full Name": "Repeat", "Mobile Number": "9123456780"}),
            ]
        )
        job = self.run_import(content)
        self.assertEqual(job.status, ImportJob.Status.COMPLETED_WITH_ERRORS, job.detail)
        self.assertEqual(job.total_rows, 11)
        self.assertEqual(job.created_rows, 2)
        self.assertEqual(job.skipped_rows, 1)
        self.assertEqual(job.warning_rows, 2)
        self.assertEqual(job.failed_rows, 6)
        self.assertTrue(job.error_file)

        ravi = Employee.objects.get(mobile_number="+919876543210")
        self.assertRegex(ravi.employee_code, CODE_PATTERN)
        self.assertTrue(ravi.is_active)
        self.assertEqual(ravi.vertical, self.steel)
        self.assertEqual(ravi.division, self.division)
        self.assertEqual(ravi.facility, self.facility)
        self.assertEqual(ravi.personal_email, "ravi@gmail.com")
        self.assertEqual(ravi.gender, "Male")
        self.assertEqual(ravi.created_by, self.user)
        sita = Employee.objects.get(full_name="Sita")
        self.assertEqual(sita.mobile_number, "9123456780")
        self.assertEqual(sita.date_of_joining, date(2026, 5, 2))
        self.assertNotEqual(sita.employee_code, ravi.employee_code)

        reasons = {e.row_number: (e.reason, e.is_warning) for e in job.errors.all()}
        self.assertTrue(reasons[5][0].startswith("Possible Duplicate"))
        self.assertTrue(reasons[5][1])
        self.assertTrue(reasons[6][0].startswith("Possible Duplicate"))
        self.assertIn('Company "Unknown Co" not found', reasons[7][0])
        self.assertIn('Designation "Sr Mngr" not found', reasons[8][0])
        self.assertEqual(reasons[9][0], "Invalid Date Of Joining")
        self.assertEqual(reasons[10][0], "Invalid Mobile Number")
        self.assertIn("does not belong to Department", reasons[11][0])
        self.assertIn("Duplicate Mobile Number within the Excel file", reasons[12][0])

        error_sheet = load_workbook(job.error_file.path).active
        header = [cell.value for cell in error_sheet[1]]
        self.assertEqual(header, ["Row Number", *EMPLOYEE_EXCEL_HEADERS, "Error Reason"])
