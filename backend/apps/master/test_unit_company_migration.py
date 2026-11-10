import io
import os
from contextlib import redirect_stdout
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from .models import Company, Unit

BEFORE_BACKFILL = [("master", "0021_company_and_unit_company")]
ENV = "UNIT_MIGRATION_DEFAULT_COMPANY"


def _migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    with redirect_stdout(io.StringIO()):
        executor.migrate(targets)
    return executor


def _latest():
    return MigrationExecutor(connection).loader.graph.leaf_nodes()


class UnitCompanyMigrationPathTests(TransactionTestCase):
    """Existing Units without a Company must be reported and mapped, never deleted."""

    def setUp(self):
        executor = _migrate(BEFORE_BACKFILL)
        old_apps = executor.loader.project_state(BEFORE_BACKFILL).apps
        self.OldUnit = old_apps.get_model("master", "Unit")
        self.jajpur = self.OldUnit.objects.create(name="Jajpur").pk
        self.bbsr = self.OldUnit.objects.create(name="Bhubaneswar").pk

    def tearDown(self):
        # Historical model: later tables that reference Unit do not exist at this schema state.
        self.OldUnit.objects.filter(company__isnull=True).delete()
        _migrate(_latest())

    def run_command(self, *args) -> str:
        out = io.StringIO()
        call_command("map_units_to_company", *args, stdout=out)
        return out.getvalue()

    def test_migration_stops_and_keeps_unmapped_units(self):
        with mock.patch.dict(os.environ, {ENV: ""}), self.assertRaisesMessage(
            RuntimeError, "2 unit(s) are not mapped to a company"
        ):
            _migrate(_latest())

        self.assertEqual(
            set(Unit.objects.filter(company__isnull=True).values_list("name", flat=True)),
            {"Jajpur", "Bhubaneswar"},
        )
        self.assertFalse(Company.objects.exists())

        report = self.run_command()
        self.assertIn("Without a company: 2", report)
        self.assertIn(f"#{self.jajpur}  Jajpur", report)

    def test_map_with_command_then_migrate(self):
        with self.assertRaises(CommandError):
            self.run_command("--company", "De-Maithan Ispat Limited", "--all")

        preview = self.run_command(
            "--company", "De-Maithan Ispat Limited", "--all", "--create-company", "--dry-run"
        )
        self.assertIn("Dry run", preview)
        self.assertFalse(Company.objects.exists())

        self.run_command("--company", "  de-maithan   ispat limited ", "--unit", str(self.bbsr),
                         "--create-company")
        self.assertEqual(Company.objects.get().name, "de-maithan ispat limited")
        self.run_command("--company", "DE-MAITHAN ISPAT LIMITED", "--all")

        company = Company.objects.get()
        self.assertEqual(
            Unit.objects.filter(company=company).count(), 2
        )
        with mock.patch.dict(os.environ, {ENV: ""}):
            _migrate(_latest())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Unit.objects.create(name="jajpur", company=company)

    def test_env_default_company_assigns_all(self):
        with mock.patch.dict(os.environ, {ENV: " De-Maithan Ispat Limited "}):
            _migrate(_latest())
        company = Company.objects.get(name="De-Maithan Ispat Limited")
        self.assertEqual(
            set(Unit.objects.filter(company=company).values_list("pk", flat=True)),
            {self.jajpur, self.bbsr},
        )


class MapUnitsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Company.objects.create(name="Company A")
        cls.b = Company.objects.create(name="Company B")
        cls.a_jajpur = Unit.objects.create(name="Jajpur", company=cls.a)
        cls.b_jajpur = Unit.objects.create(name=" JAJPUR ", company=cls.b)
        cls.b_angul = Unit.objects.create(name="Angul", company=cls.b)

    def run_command(self, *args) -> str:
        out = io.StringIO()
        call_command("map_units_to_company", *args, stdout=out)
        return out.getvalue()

    def test_report_when_everything_is_mapped(self):
        report = self.run_command()
        self.assertIn("Total units: 3", report)
        self.assertIn("Without a company: 0", report)

    def test_reassign_blocks_duplicate_in_target_company(self):
        with self.assertRaisesMessage(CommandError, "would duplicate a Unit Name"):
            self.run_command("--company", "company a", "--unit", str(self.b_jajpur.pk))
        self.b_jajpur.refresh_from_db()
        self.assertEqual(self.b_jajpur.company_id, self.b.pk)

    def test_reassign_moves_unit(self):
        self.run_command("--company", "company a", "--unit", str(self.b_angul.pk))
        self.b_angul.refresh_from_db()
        self.assertEqual(self.b_angul.company_id, self.a.pk)

    def test_argument_errors(self):
        with self.assertRaises(CommandError):
            self.run_command("--all")
        with self.assertRaises(CommandError):
            self.run_command("--company", "Company A")
        with self.assertRaisesMessage(CommandError, "not found"):
            self.run_command("--company", "Company A", "--unit", "999999")
        with self.assertRaisesMessage(CommandError, "does not exist in Company Master"):
            self.run_command("--company", "Nope Ltd", "--unit", str(self.b_angul.pk))
