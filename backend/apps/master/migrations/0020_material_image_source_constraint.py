from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("master", "0019_material_image_source_backfill"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="material",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        image_source="NONE",
                        image_url="",
                        image_file="",
                        image_thumb="",
                    )
                    | (models.Q(image_source="UPLOAD", image_url="") & ~models.Q(image_file=""))
                    | (
                        models.Q(image_source="URL", image_file="", image_thumb="")
                        & ~models.Q(image_url="")
                    )
                ),
                name="master_material_image_source_ck",
            ),
        ),
    ]
