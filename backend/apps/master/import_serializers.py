from rest_framework import serializers

from .models import ImportJob


class ImportJobSerializer(serializers.ModelSerializer):
    has_error_file = serializers.SerializerMethodField()
    progress_label = serializers.SerializerMethodField()

    class Meta:
        model = ImportJob
        fields = (
            "id",
            "master_type",
            "status",
            "original_filename",
            "total_rows",
            "processed_rows",
            "created_rows",
            "skipped_rows",
            "failed_rows",
            "warning_rows",
            "progress_percentage",
            "progress_label",
            "detail",
            "has_error_file",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_has_error_file(self, obj: ImportJob) -> bool:
        return bool(obj.error_file)

    def get_progress_label(self, obj: ImportJob) -> str:
        total = obj.total_rows
        processed = obj.processed_rows
        pct = obj.progress_percentage
        if total:
            return f"{processed:,} / {total:,} processed — {pct}%"
        return f"{pct}%"
