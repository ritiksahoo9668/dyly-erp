from django.core.files.storage import default_storage
from django.db import migrations

from apps.master.material_image_rules import (
    LEGACY_BLANK,
    LEGACY_UPLOAD,
    LEGACY_URL,
    classify_legacy_image_value,
    matching_thumb_path,
)


def backfill_image_source(apps, schema_editor):
    """Classify legacy single-column image values (renamed item_image -> image_url).

    - valid http/https URL           -> URL
    - existing relative storage path -> UPLOAD (image_file; matching thumb if present)
    - blank                          -> NONE
    - anything else                  -> cleared to NONE and reported
    Material records are never deleted or deactivated.
    """
    Material = apps.get_model("master", "Material")
    counts = {"total": 0, LEGACY_URL: 0, LEGACY_UPLOAD: 0, "invalid": 0, LEGACY_BLANK: 0}
    invalid_samples: list[str] = []

    rows = Material.objects.values_list("pk", "sap_code", "image_url").iterator(chunk_size=2000)
    for pk, sap_code, raw in rows:
        counts["total"] += 1
        kind, value = classify_legacy_image_value(raw, default_storage)
        qs = Material.objects.filter(pk=pk)
        if kind == LEGACY_URL:
            counts[LEGACY_URL] += 1
            qs.update(image_url=value, image_source="URL")
        elif kind == LEGACY_UPLOAD:
            counts[LEGACY_UPLOAD] += 1
            qs.update(
                image_file=value,
                image_thumb=matching_thumb_path(value, default_storage) or "",
                image_url="",
                image_source="UPLOAD",
            )
        elif kind == LEGACY_BLANK:
            counts[LEGACY_BLANK] += 1
            qs.update(image_url="", image_source="NONE")
        else:
            counts["invalid"] += 1
            if len(invalid_samples) < 20:
                invalid_samples.append(f"{sap_code}: {value[:120]}")
            qs.update(image_url="", image_source="NONE")

    print(
        "\n  Material image backfill: "
        f"checked={counts['total']}, url={counts[LEGACY_URL]}, "
        f"upload_path={counts[LEGACY_UPLOAD]}, cleared_invalid={counts['invalid']}, "
        f"blank={counts[LEGACY_BLANK]}"
    )
    for line in invalid_samples:
        print(f"    cleared: {line}")
    if counts[LEGACY_UPLOAD]:
        print(
            "  Run `python manage.py audit_material_images --apply` to generate missing thumbnails."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("master", "0018_material_image_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_image_source, migrations.RunPython.noop),
    ]
