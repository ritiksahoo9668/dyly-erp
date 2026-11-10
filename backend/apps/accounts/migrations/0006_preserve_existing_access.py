"""Preserve pre-existing effective access when module permissions are introduced.

Before this migration every authenticated ADMIN/USER could open every module screen and
create / edit / upload / deactivate every Master (Master APIs only required authentication).
To avoid anyone losing access on deployment, existing ADMIN/USER accounts (and draft
onboardings, which would have produced such accounts) receive:

- MASTER: every submodule with every Master action (what they could already do), and
- every other module: VIEW on every submodule (those screens were visible to all users).

SUPERADMIN needs no rows (full-access override). Each migrated account gets an
ACCESS_MIGRATED audit event so administrators can review and tighten access afterwards.
Key lists are frozen here on purpose; later registry changes must not alter this migration.
"""

from django.db import migrations

MASTER_SUBMODULES = (
    "EMPLOYEE",
    "DEPARTMENT",
    "MATERIAL_CATEGORY",
    "MATERIAL_SUBCATEGORY",
    "MATERIAL_GROUP",
    "PURCHASING_GROUP",
    "PLANT",
    "MATERIAL_TYPE",
    "MATERIAL",
    "UOM",
    "QC_PARAMETER",
    "VENDOR",
    "DIVISION",
    "VERTICAL",
    "FACILITY",
    "COMPANY",
    "UNIT",
    "DESIGNATION",
    "WEIGHBRIDGE",
    "STOCK_YARD",
)
MASTER_ACTIONS = ("VIEW", "CREATE", "EDIT", "EXPORT", "UPLOAD", "ACTIVATE_DEACTIVATE")
VIEW_MODULES = {
    "DASHBOARD": ("OVERVIEW",),
    "PROCUREMENT": ("PLANNING", "INDENT", "RFQ", "CS", "PO", "GATE_ENTRY", "WEIGHBRIDGE", "QC", "GRN"),
    "PRODUCTION": ("PLANNING", "FEED_CONSUMPTION", "PRODUCTION_ENTRY"),
    "SALES": (
        "PLANNING",
        "INQUIRY_CAPTURE",
        "SALES_OFFER",
        "PO_RECEIVED",
        "DO",
        "GATE_ENTRY",
        "DISPATCH_LOADING",
        "INVOICE",
        "GATE_EXIT",
    ),
    "HR": ("OVERVIEW",),
}
MIGRATED_ROLES = ("ADMIN", "USER")


def preserved_access() -> dict:
    access = {
        module: {"enabled": True, "submodules": {sub: ["VIEW"] for sub in subs}}
        for module, subs in VIEW_MODULES.items()
    }
    access["MASTER"] = {
        "enabled": True,
        "submodules": {sub: list(MASTER_ACTIONS) for sub in MASTER_SUBMODULES},
    }
    return access


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserOnboarding = apps.get_model("accounts", "UserOnboarding")
    UserModuleAccess = apps.get_model("accounts", "UserModuleAccess")
    UserSubmoduleAccess = apps.get_model("accounts", "UserSubmoduleAccess")
    UserAccessEvent = apps.get_model("accounts", "UserAccessEvent")

    users = list(User.objects.filter(role__in=MIGRATED_ROLES))
    module_rows, sub_rows, events = [], [], []
    for user in users:
        if UserModuleAccess.objects.filter(user=user).exists():
            continue
        for module in (*VIEW_MODULES, "MASTER"):
            module_rows.append(UserModuleAccess(user=user, module_key=module, is_enabled=True))
        for module, subs in VIEW_MODULES.items():
            for sub in subs:
                sub_rows.append(
                    UserSubmoduleAccess(
                        user=user, module_key=module, submodule_key=sub, can_view=True
                    )
                )
        for sub in MASTER_SUBMODULES:
            sub_rows.append(
                UserSubmoduleAccess(
                    user=user,
                    module_key="MASTER",
                    submodule_key=sub,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_export=True,
                    can_upload=True,
                    can_activate_deactivate=True,
                )
            )
        onboarding = UserOnboarding.objects.filter(user=user).first()
        events.append(
            UserAccessEvent(
                event="ACCESS_MIGRATED",
                permission="ALL",
                from_value="IMPLICIT",
                to_value="PRESERVED",
                user=user,
                onboarding=onboarding,
            )
        )

    drafts = UserOnboarding.objects.filter(
        is_active=True, status="DRAFT", user__isnull=True, role__in=MIGRATED_ROLES
    )
    for onboarding in drafts:
        if onboarding.pending_access:
            continue
        onboarding.pending_access = preserved_access()
        onboarding.save(update_fields=["pending_access"])
        events.append(
            UserAccessEvent(
                event="ACCESS_MIGRATED",
                permission="ALL",
                from_value="IMPLICIT",
                to_value="PRESERVED",
                onboarding=onboarding,
            )
        )

    UserModuleAccess.objects.bulk_create(module_rows)
    UserSubmoduleAccess.objects.bulk_create(sub_rows)
    UserAccessEvent.objects.bulk_create(events)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_module_access"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
