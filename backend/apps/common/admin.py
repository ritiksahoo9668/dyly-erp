from django.contrib import admin

from .models import MailLog


@admin.register(MailLog)
class MailLogAdmin(admin.ModelAdmin):
    list_display = ("mail_type", "recipient", "status", "attempts", "queued_at", "sent_at")
    list_filter = ("mail_type", "status")
    search_fields = ("recipient", "related_object_id", "celery_task_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
