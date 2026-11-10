"""Reusable mail rendering, sending and delivery logging.

This layer knows about recipients, subjects, templates and delivery status only. Business
state (onboarding status, tokens, etc.) belongs to the calling module.
"""

import logging
import smtplib
import uuid
from collections.abc import Callable

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.validators import validate_email
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.common.models import MailLog
from apps.common.timing import log_step, timed

from .constants import (
    ENQUEUE_RETRY_POLICY,
    FAILURE_REASON_MAX_LENGTH,
    SUBJECTS,
    TEMPLATES,
    MailType,
)
from .context import base_context
from .exceptions import InvalidRecipientError, MailConfigurationError, MailError

logger = logging.getLogger("erp.mail")


# --- Rendering and sending -------------------------------------------------------------


def render_mail(template: str, context: dict) -> tuple[str, str]:
    """Return ``(text, html)`` for a template base name such as ``mail/password_reset``."""
    full_context = base_context(**context)
    text = render_to_string(f"{template}.txt", full_context)
    html = render_to_string(f"{template}.html", full_context)
    return text, html


def _validated_recipient(recipient: str) -> str:
    value = (recipient or "").strip()
    try:
        validate_email(value)
    except ValidationError as exc:
        raise InvalidRecipientError("Recipient email address is invalid.") from exc
    return value


def send_templated_mail(*, recipient: str, subject: str, template: str, context: dict) -> None:
    """Render and send one HTML email with a plain-text fallback. Raises on failure.

    Must only run in a Celery worker: it opens a network connection to the SMTP server.
    """
    to = _validated_recipient(recipient)
    from_email = settings.DEFAULT_FROM_EMAIL
    if not from_email:
        raise MailConfigurationError("DEFAULT_FROM_EMAIL is not configured.")
    with timed("mail_render", template=template):
        text, html = render_mail(template, context)
    message = EmailMultiAlternatives(subject=subject, body=text, from_email=from_email, to=[to])
    message.attach_alternative(html, "text/html")

    connection = get_connection(fail_silently=False)
    try:
        # For the SMTP backend, open() covers TCP connect, STARTTLS and login.
        with timed("smtp_connect"):
            connection.open()
        message.connection = connection
        with timed("smtp_send", to_domain=to.rsplit("@", 1)[-1]):
            message.send(fail_silently=False)
    finally:
        with timed("smtp_close"):
            try:
                connection.close()
            except Exception:  # the message outcome is already decided
                logger.warning("SMTP connection close failed", exc_info=False)


def send_user_onboarding_invitation(
    *,
    recipient: str,
    employee_name: str,
    login_email: str,
    activation_url: str,
    expiry_hours: int,
) -> None:
    send_templated_mail(
        recipient=recipient,
        subject=SUBJECTS[MailType.USER_ONBOARDING_INVITE],
        template=TEMPLATES[MailType.USER_ONBOARDING_INVITE],
        context={
            "employee_name": employee_name,
            "login_email": login_email,
            "activation_url": activation_url,
            "expiry_hours": expiry_hours,
        },
    )


def send_password_reset_email(
    *, recipient: str, user_name: str, reset_url: str, expiry_minutes: int
) -> None:
    send_templated_mail(
        recipient=recipient,
        subject=SUBJECTS[MailType.PASSWORD_RESET],
        template=TEMPLATES[MailType.PASSWORD_RESET],
        context={"user_name": user_name, "reset_url": reset_url, "expiry_minutes": expiry_minutes},
    )


def send_notification_email(
    *,
    recipient: str,
    subject: str,
    heading: str,
    message: str,
    action_url: str = "",
    action_label: str = "",
) -> None:
    send_templated_mail(
        recipient=recipient,
        subject=subject,
        template=TEMPLATES[MailType.GENERIC_NOTIFICATION],
        context={
            "heading": heading,
            "message": message,
            "action_url": action_url,
            "action_label": action_label,
        },
    )


def is_transient_mail_error(exc: BaseException) -> bool:
    """True for temporary delivery problems worth retrying (network, 4xx SMTP replies)."""
    if isinstance(exc, MailError):
        return False
    if isinstance(exc, SoftTimeLimitExceeded):
        return True
    if isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError)):
        return True
    if isinstance(
        exc,
        (
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPNotSupportedError,
        ),
    ):
        return False
    if isinstance(exc, smtplib.SMTPResponseException):
        return 400 <= exc.smtp_code < 500
    if isinstance(exc, smtplib.SMTPException):
        return False
    return isinstance(exc, OSError)


# --- Delivery log ----------------------------------------------------------------------


def _related_ref(obj) -> tuple[str, str]:
    if obj is None:
        return "", ""
    return f"{obj._meta.app_label}.{obj._meta.model_name}", str(obj.pk)


def describe_failure(exc: BaseException) -> str:
    return f"{exc.__class__.__name__}: {exc}"[:FAILURE_REASON_MAX_LENGTH]


def create_mail_log(
    *, mail_type: str, recipient: str, subject: str, related_object=None
) -> MailLog:
    related_type, related_id = _related_ref(related_object)
    return MailLog.objects.create(
        mail_type=mail_type,
        recipient=recipient,
        subject=subject,
        related_object_type=related_type,
        related_object_id=related_id,
        celery_task_id=str(uuid.uuid4()),
    )


def mark_mail_attempt(mail_log_id: int) -> None:
    MailLog.objects.filter(pk=mail_log_id).update(attempts=models.F("attempts") + 1)


def log_queue_wait(mail_log_id: int, **fields) -> None:
    """Log how long the MailLog waited between queueing and this worker attempt."""
    queued_at = MailLog.objects.filter(pk=mail_log_id).values_list("queued_at", flat=True).first()
    if queued_at is not None:
        waited = (timezone.now() - queued_at).total_seconds() * 1000
        log_step("mail_queue_wait", waited, mail_log=mail_log_id, **fields)


def mark_mail_sent(mail_log_id: int) -> None:
    MailLog.objects.filter(pk=mail_log_id).update(
        status=MailLog.Status.SENT, sent_at=timezone.now(), failure_reason=""
    )


def mark_mail_failed(
    mail_log_id: int, exc: BaseException | None = None, *, reason: str = ""
) -> None:
    MailLog.objects.filter(pk=mail_log_id).update(
        status=MailLog.Status.FAILED,
        failed_at=timezone.now(),
        failure_reason=(describe_failure(exc) if exc else reason)[:FAILURE_REASON_MAX_LENGTH],
    )


def enqueue_on_commit(
    task,
    mail_log: MailLog,
    *args,
    on_enqueue_error: Callable[[BaseException], None] | None = None,
) -> None:
    """Queue ``task(mail_log.pk, *args)`` only after the current transaction commits.

    If the broker is unreachable the MailLog is marked FAILED and ``on_enqueue_error`` runs,
    so callers can surface a retryable state instead of failing the committed request.
    Publishing is bounded (``ENQUEUE_RETRY_POLICY`` plus the broker connect timeout) so a
    Redis outage cannot hold the HTTP request for long.
    """
    mail_log_id = mail_log.pk
    task_id = mail_log.celery_task_id

    def _enqueue():
        try:
            with timed("mail_enqueue", task=task.name, mail_log=mail_log_id):
                task.apply_async(
                    args=[mail_log_id, *args],
                    task_id=task_id,
                    retry=True,
                    retry_policy=ENQUEUE_RETRY_POLICY,
                )
        except Exception as exc:  # broker/connection errors
            logger.error("Unable to queue mail log %s: %s", mail_log_id, exc.__class__.__name__)
            mark_mail_failed(mail_log_id, exc)
            if on_enqueue_error is not None:
                on_enqueue_error(exc)

    transaction.on_commit(_enqueue)


def queue_notification_email(
    *,
    recipient: str,
    subject: str,
    heading: str,
    message: str,
    action_url: str = "",
    action_label: str = "",
    related_object=None,
) -> MailLog:
    """Queue a generic branded notification email through Celery."""
    from .tasks import send_generic_notification_email_task

    mail_log = create_mail_log(
        mail_type=MailType.GENERIC_NOTIFICATION,
        recipient=recipient,
        subject=subject,
        related_object=related_object,
    )
    enqueue_on_commit(
        send_generic_notification_email_task,
        mail_log,
        recipient,
        subject,
        heading,
        message,
        action_url,
        action_label,
    )
    return mail_log
