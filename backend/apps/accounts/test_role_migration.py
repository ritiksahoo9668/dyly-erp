import io
from contextlib import redirect_stdout

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("accounts", "0002_user_role_passwordresettoken")]


def _migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    with redirect_stdout(io.StringIO()):
        executor.migrate(targets)
    return executor


def _latest():
    return MigrationExecutor(connection).loader.graph.leaf_nodes()


class RoleMigrationTests(TransactionTestCase):
    """Old roles map onto SUPERADMIN / ADMIN / USER without granting extra privileges."""

    def tearDown(self):
        _migrate(_latest())

    def test_roles_are_remapped_and_flags_preserved(self):
        executor = _migrate(BEFORE)
        OldUser = executor.loader.project_state(BEFORE).apps.get_model("accounts", "User")
        rows = {
            "super@example.com": ("SUPER_ADMIN", True),
            "director@example.com": ("DIRECTOR", False),
            "administrator@example.com": ("ADMINISTRATOR", False),
            "user@example.com": ("USER", False),
        }
        for email, (role, staff) in rows.items():
            OldUser.objects.create(email=email, role=role, is_staff=staff, password="!")

        executor = _migrate(_latest())
        User = executor.loader.project_state(_latest()).apps.get_model("accounts", "User")
        result = dict(User.objects.values_list("email", "role"))
        self.assertEqual(
            result,
            {
                "super@example.com": "SUPERADMIN",
                "director@example.com": "USER",
                "administrator@example.com": "ADMIN",
                "user@example.com": "USER",
            },
        )
        self.assertEqual(
            set(User.objects.filter(is_staff=True).values_list("email", flat=True)),
            {"super@example.com"},
        )
        self.assertEqual(User.objects.count(), 4)
