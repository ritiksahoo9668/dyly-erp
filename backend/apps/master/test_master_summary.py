from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.common.access_control.constants import Module
from apps.common.access_control.testing import grant_access

from .models import ImportJob, QcParameter, Uom
from .summary_views import SUMMARY_MODELS

URL = "/api/v1/master/summary/"


class MasterSummaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="summary@example.com", password="pass12345!", first_name="Sum", last_name="Mary"
        )
        grant_access(cls.user, Module.MASTER)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_counts_total_and_active_per_master(self):
        Uom.objects.create(name="Kilogram", symbol="kg")
        Uom.objects.create(name="Metre", symbol="m", is_active=False)
        QcParameter.objects.create(name="Moisture", short_name="MC")

        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        masters = response.data["masters"]
        self.assertEqual(set(masters), set(SUMMARY_MODELS))
        self.assertEqual(masters["uom"], {"total": 2, "active": 1})
        self.assertEqual(masters["qc-parameter"], {"total": 1, "active": 1})
        self.assertEqual(masters["employee"], {"total": 0, "active": 0})

    def test_lists_latest_imports_first(self):
        for master_type in (ImportJob.MasterType.UOM, ImportJob.MasterType.QC_PARAMETER):
            ImportJob.objects.create(
                master_type=master_type,
                status=ImportJob.Status.COMPLETED,
                original_filename=f"{master_type}.xlsx",
                created_rows=3,
                uploaded_by=self.user,
            )

        recent = self.client.get(URL).data["recent_imports"]

        self.assertEqual([item["master_label"] for item in recent], ["QC Parameter", "UOM"])
        self.assertEqual(recent[0]["created_rows"], 3)
        self.assertEqual(recent[0]["uploaded_by"], self.user.display_name)
