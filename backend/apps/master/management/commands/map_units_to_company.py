"""Report Units without a Company and map Units to a Company.

Without ``--company`` the command only reports. Typical migration flow when
existing Units have no Company yet:

    python manage.py migrate master 0021
    python manage.py map_units_to_company
    python manage.py map_units_to_company --company "De-Maithan Ispat Limited" --all
    python manage.py migrate

``--unit`` also reassigns Units that already belong to another Company.
Unit names must stay unique (case-insensitive, trimmed) within the target Company.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.master.models import Company, Unit


def _clean(value: str) -> str:
    return " ".join((value or "").split())


class Command(BaseCommand):
    help = "Report Units without a Company, or map Units to a Company (use --dry-run to preview)."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Target Company Name (matched case-insensitively).")
        target = parser.add_mutually_exclusive_group()
        target.add_argument(
            "--all",
            action="store_true",
            help="Map every Unit that has no Company.",
        )
        target.add_argument(
            "--unit",
            type=int,
            nargs="+",
            metavar="ID",
            help="Unit IDs to map or reassign.",
        )
        parser.add_argument(
            "--create-company",
            action="store_true",
            help="Create the Company (Active) if it does not exist.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving.")

    def handle(self, *args, **options):
        company_name = _clean(options.get("company") or "")
        if not company_name:
            if options["all"] or options["unit"]:
                raise CommandError("--company is required with --all or --unit.")
            self._report()
            return
        if not (options["all"] or options["unit"]):
            raise CommandError("Choose the Units to map with --all or --unit <id> ...")

        company = Company.objects.filter(name__iexact=company_name).first()
        create_company = company is None
        if create_company and not options["create_company"]:
            raise CommandError(
                f'Company "{company_name}" does not exist in Company Master. '
                "Create it first or pass --create-company."
            )

        if options["all"]:
            rows = list(
                Unit.objects.filter(company__isnull=True)
                .order_by("name", "id")
                .values_list("id", "name", "company_id")
            )
        else:
            ids = list(dict.fromkeys(options["unit"]))
            rows = list(
                Unit.objects.filter(pk__in=ids).order_by("name", "id").values_list(
                    "id", "name", "company_id"
                )
            )
            missing = sorted(set(ids) - {pk for pk, _, _ in rows})
            if missing:
                raise CommandError(f"Unit ID(s) not found: {', '.join(map(str, missing))}.")

        if company is not None:
            rows = [row for row in rows if row[2] != company.pk]
        if not rows:
            self.stdout.write("Nothing to map.")
            return

        moving_ids = {pk for pk, _, _ in rows}
        taken: dict[str, str] = {}
        if company is not None:
            for name in (
                Unit.objects.filter(company=company)
                .exclude(pk__in=moving_ids)
                .values_list("name", flat=True)
            ):
                taken[name.strip().casefold()] = name
        conflicts: list[str] = []
        for pk, name, _ in rows:
            key = name.strip().casefold()
            if key in taken:
                conflicts.append(f"  #{pk}  {name} (clashes with '{taken[key]}')")
            else:
                taken[key] = name
        if conflicts:
            raise CommandError(
                f'These Units would duplicate a Unit Name under "{company_name}":\n'
                + "\n".join(conflicts)
            )

        target_label = company.name if company else company_name
        self.stdout.write(f'Mapping {len(rows)} unit(s) to "{target_label}":')
        for pk, name, _ in rows:
            self.stdout.write(f"  #{pk}  {name}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no changes saved."))
            return

        with transaction.atomic():
            if company is None:
                company = Company.objects.create(name=company_name, is_active=True)
                self.stdout.write(f'Created company "{company.name}".')
            updated = Unit.objects.filter(pk__in=moving_ids).update(company=company)
        self.stdout.write(self.style.SUCCESS(f'Mapped {updated} unit(s) to "{company.name}".'))

    def _report(self) -> None:
        unmapped = list(
            Unit.objects.filter(company__isnull=True).order_by("name", "id").values_list(
                "id", "name"
            )
        )
        total = Unit.objects.count()
        self.stdout.write(f"Total units: {total}")
        self.stdout.write(f"Mapped to a company: {total - len(unmapped)}")
        self.stdout.write(f"Without a company: {len(unmapped)}")
        for pk, name in unmapped:
            self.stdout.write(f"  #{pk}  {name}")

        companies = list(Company.objects.order_by("name").values_list("name", "is_active"))
        self.stdout.write(f"Companies in Company Master: {len(companies)}")
        for name, is_active in companies:
            self.stdout.write(f"  {name}{'' if is_active else ' (inactive)'}")
        if unmapped:
            self.stdout.write(
                self.style.WARNING(
                    'Map them with: map_units_to_company --company "<Company Name>" '
                    "--all | --unit <id> ..."
                )
            )
