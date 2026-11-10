import apps.master.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("master", "0017_material_item_image_textfield"),
    ]

    operations = [
        migrations.RenameField(
            model_name="material",
            old_name="item_image",
            new_name="image_url",
        ),
        migrations.AddField(
            model_name="material",
            name="image_source",
            field=models.CharField(
                choices=[("NONE", "None"), ("UPLOAD", "Upload"), ("URL", "URL")],
                default="NONE",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="image_file",
            field=models.ImageField(
                blank=True,
                default="",
                max_length=255,
                upload_to=apps.master.models.material_image_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="image_thumb",
            field=models.ImageField(
                blank=True,
                default="",
                max_length=255,
                upload_to=apps.master.models.material_thumb_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="importjob",
            name="warning_rows",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjoberror",
            name="is_warning",
            field=models.BooleanField(default=False),
        ),
    ]
