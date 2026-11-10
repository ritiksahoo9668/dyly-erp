"""Audit / repair Material image references.

Dry run by default. Use ``--apply`` to write changes.

Per Material (defensive, independent of the stored ``image_source``):
- image_file set and present in storage   -> UPLOAD (missing thumbnail generated on --apply)
- image_file set but missing from storage -> cleared to NONE (reported)
- image_url is a valid http/https URL      -> URL
- image_url is an existing relative path   -> moved to image_file, UPLOAD
- image_url anything else                  -> cleared to NONE (reported)
- nothing                                  -> NONE

Material records are never deleted or deactivated; only image fields change.
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.master.material_image_rules import (
    LEGACY_UPLOAD,
    LEGACY_URL,
    MaterialImageError,
    classify_legacy_image_value,
    matching_thumb_path,
)
from apps.master.material_images import generate_thumbnail_for_stored_image
from apps.master.models import Material

NONE = Material.ImageSource.NONE
UPLOAD = Material.ImageSource.UPLOAD
URL = Material.ImageSource.URL


def _exists(storage, name: str) -> bool:
    try:
        return bool(name) and bool(storage.exists(name))
    except Exception:
        return False


class Command(BaseCommand):
    help = "Audit Material image references and optionally repair them (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes to the database.")
        parser.add_argument(
            "--skip-thumbnails",
            action="store_true",
            help="Do not generate missing thumbnails for uploaded images.",
        )
        parser.add_argument(
            "--show",
            type=int,
            default=50,
            help="Maximum number of invalid values to list (default 50).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        make_thumbs = not options["skip_thumbnails"]
        show = max(0, options["show"])
        storage = Material._meta.get_field("image_file").storage

        stats: Counter[str] = Counter()
        invalid: list[str] = []

        materials = (
            Material.objects.only(
                "pk", "sap_code", "image_source", "image_url", "image_file", "image_thumb"
            )
            .order_by("pk")
            .iterator(chunk_size=1000)
        )

        for material in materials:
            stats["total"] += 1
            file_name = material.image_file.name or ""
            thumb_name = material.image_thumb.name or ""
            updates: dict[str, str] = {}
            upload_path = ""

            if file_name:
                if _exists(storage, file_name):
                    stats["upload"] += 1
                    upload_path = file_name
                    if material.image_source != UPLOAD or material.image_url:
                        updates.update(image_source=UPLOAD, image_url="")
                else:
                    stats["cleared_invalid"] += 1
                    invalid.append(f"{material.sap_code}: uploaded file missing ({file_name})")
                    updates.update(image_source=NONE, image_file="", image_thumb="", image_url="")
            elif material.image_url:
                kind, value = classify_legacy_image_value(material.image_url, storage)
                if kind == LEGACY_URL:
                    stats["url"] += 1
                    if material.image_source != URL or value != material.image_url or thumb_name:
                        updates.update(image_source=URL, image_url=value, image_thumb="")
                elif kind == LEGACY_UPLOAD:
                    stats["upload"] += 1
                    stats["moved_to_upload"] += 1
                    upload_path = value
                    updates.update(image_source=UPLOAD, image_file=value, image_url="")
                    thumb_name = ""
                else:
                    stats["cleared_invalid"] += 1
                    invalid.append(f"{material.sap_code}: {value[:160]}")
                    updates.update(image_source=NONE, image_url="", image_thumb="")
            else:
                stats["blank"] += 1
                if material.image_source != NONE or thumb_name:
                    updates.update(image_source=NONE, image_thumb="")

            new_thumb = ""
            if upload_path:
                if thumb_name and not _exists(storage, thumb_name):
                    updates["image_thumb"] = ""
                    thumb_name = ""
                if not thumb_name:
                    matched = matching_thumb_path(upload_path, storage)
                    if matched:
                        updates["image_thumb"] = matched
                    elif make_thumbs:
                        stats["thumb_missing"] += 1
                        if apply:
                            try:
                                new_thumb = generate_thumbnail_for_stored_image(
                                    upload_path, storage
                                )
                                updates["image_thumb"] = new_thumb
                                stats["thumb_generated"] += 1
                            except MaterialImageError as exc:
                                stats["thumb_failed"] += 1
                                self.stderr.write(f"  {material.sap_code}: {exc}")

            if not updates:
                continue
            stats["rows_to_update"] += 1
            if not apply:
                continue
            try:
                with transaction.atomic():
                    Material.objects.filter(pk=material.pk).update(**updates)
                stats["rows_updated"] += 1
            except Exception as exc:
                if new_thumb:
                    storage.delete(new_thumb)
                stats["rows_failed"] += 1
                self.stderr.write(f"  {material.sap_code}: update failed ({exc})")

        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"Material image audit ({mode})"))
        self.stdout.write(f"  Total checked:         {stats['total']}")
        self.stdout.write(f"  URL images:            {stats['url']}")
        self.stdout.write(
            f"  Uploaded images:       {stats['upload']}"
            f" (moved from legacy path: {stats['moved_to_upload']})"
        )
        self.stdout.write(f"  Cleared invalid:       {stats['cleared_invalid']}")
        self.stdout.write(f"  Blank / no image:      {stats['blank']}")
        self.stdout.write(f"  Thumbnails missing:    {stats['thumb_missing']}")
        if apply:
            self.stdout.write(f"  Thumbnails generated:  {stats['thumb_generated']}")
            self.stdout.write(f"  Thumbnail failures:    {stats['thumb_failed']}")
            self.stdout.write(f"  Rows updated:          {stats['rows_updated']}")
            self.stdout.write(f"  Rows failed:           {stats['rows_failed']}")
        else:
            self.stdout.write(f"  Rows needing changes:  {stats['rows_to_update']}")
        if invalid:
            self.stdout.write(self.style.WARNING("  Invalid / missing image values:"))
            for line in invalid[:show]:
                self.stdout.write(f"    {line}")
            if len(invalid) > show:
                self.stdout.write(f"    … and {len(invalid) - show} more")
        if not apply and stats["rows_to_update"]:
            self.stdout.write("  Re-run with --apply to write these changes.")
