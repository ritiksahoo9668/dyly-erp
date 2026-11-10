import os

from django.db import migrations

DEFAULT_COMPANY_ENV = "UNIT_MIGRATION_DEFAULT_COMPANY"


def _report(rows) -> str:
    return "\n".join(f"    #{pk}  {name}" for pk, name in rows)


def check_unmapped_units(apps, schema_editor):
    """Stop before Unit.company becomes required while any Unit has no Company."""
    Company = apps.get_model("master", "Company")
    Unit = apps.get_model("master", "Unit")

    unmapped = list(
        Unit.objects.filter(company__isnull=True).order_by("name", "id").values_list("id", "name")
    )
    if not unmapped:
        return

    print(f"\n  Found {len(unmapped)} unit(s) without a company:\n{_report(unmapped)}")

    default_name = " ".join((os.environ.get(DEFAULT_COMPANY_ENV) or "").split())
    if not default_name:
        raise RuntimeError(
            f"{len(unmapped)} unit(s) are not mapped to a company. No data was changed.\n"
            "Map them, then run `python manage.py migrate` again:\n"
            '  python manage.py map_units_to_company --company "<Company Name>" --all '
            "[--create-company]\n"
            '  python manage.py map_units_to_company --company "<Company Name>" --unit <id> ...\n'
            f'Or set {DEFAULT_COMPANY_ENV}="<Company Name>" to assign all of them to one company.'
        )

    company = Company.objects.filter(name__iexact=default_name).first()
    if company is None:
        company = Company.objects.create(name=default_name, is_active=True)
        print(f"  Created company '{company.name}'.")

    taken = {
        name.strip().casefold()
        for name in Unit.objects.filter(company=company).values_list("name", flat=True)
    }
    conflicts = [(pk, name) for pk, name in unmapped if name.strip().casefold() in taken]
    if conflicts:
        raise RuntimeError(
            f"These units already exist under '{company.name}' and cannot be assigned to it:\n"
            f"{_report(conflicts)}\n"
            "Map them to another company with `python manage.py map_units_to_company`."
        )

    updated = Unit.objects.filter(company__isnull=True).update(company=company)
    print(f"  Assigned {updated} unit(s) to company '{company.name}'.")


class Migration(migrations.Migration):
    dependencies = [
        ("master", "0021_company_and_unit_company"),
    ]

    operations = [
        migrations.RunPython(check_unmapped_units, migrations.RunPython.noop),
    ]
