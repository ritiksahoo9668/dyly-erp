from django.db import models
from django.utils import timezone


class MailLog(models.Model):
    """Delivery record for one outgoing email. Never stores bodies, links or secrets."""

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    mail_type = models.CharField(max_length=50)
    recipient = models.EmailField(max_length=254)
    subject = models.CharField(max_length=255)
    related_object_type = models.CharField(max_length=100, blank=True, default="")
    related_object_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    queued_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["mail_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["related_object_type", "related_object_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.mail_type} → {self.recipient} ({self.status})"
