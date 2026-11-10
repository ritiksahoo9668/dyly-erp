"""Consolidate global roles into SUPERADMIN / ADMIN / USER.

No code path ever granted DIRECTOR any privilege (roles were display-only), so DIRECTOR
maps to USER. ADMINISTRATOR maps to ADMIN. is_staff / is_superuser are left untouched.
Reversing restores SUPER_ADMIN and ADMINISTRATOR; former DIRECTOR accounts stay USER.
"""

from django.db import migrations, models

FORWARD = {
    "SUPER_ADMIN": "SUPERADMIN",
    "ADMINISTRATOR": "ADMIN",
    "DIRECTOR": "USER",
}
BACKWARD = {
    "SUPERADMIN": "SUPER_ADMIN",
    "ADMIN": "ADMINISTRATOR",
}


def _remap(mapping):
    def run(apps, schema_editor):
        User = apps.get_model("accounts", "User")
        for old, new in mapping.items():
            User.objects.filter(role=old).update(role=new)

    return run


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_role_passwordresettoken"),
    ]

    operations = [
        migrations.RunPython(_remap(FORWARD), _remap(BACKWARD)),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("SUPERADMIN", "Superadmin"), ("ADMIN", "Admin"), ("USER", "User")],
                default="USER",
                max_length=32,
            ),
        ),
    ]
