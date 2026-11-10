import logging
import random

from celery import shared_task

from .constants import (
    MAIL_MAX_RETRIES,
    MAIL_RETRY_BASE_SECONDS,
    MAIL_RETRY_JITTER,
    MAIL_RETRY_MAX_SECONDS,
    MAIL_TASK_SOFT_TIME_LIMIT,
    MAIL_TASK_TIME_LIMIT,
)
from .services import (
    is_transient_mail_error,
    mark_mail_attempt,
    mark_mail_failed,
    mark_mail_sent,
    send_notification_email,
)

logger = logging.getLogger("erp.mail")

MAIL_TASK_OPTIONS = {
    "bind": True,
    "max_retries": MAIL_MAX_RETRIES,
    "soft_time_limit": MAIL_TASK_SOFT_TIME_LIMIT,
    "time_limit": MAIL_TASK_TIME_LIMIT,
}


def retry_delay(retries: int) -> int:
    """Exponential backoff (15s, 30s, 60s …) capped, with ±20% jitter."""
    base = min(MAIL_RETRY_BASE_SECONDS * (2**retries), MAIL_RETRY_MAX_SECONDS)
    spread = base * MAIL_RETRY_JITTER
    return max(1, round(base + random.uniform(-spread, spread)))


def handle_delivery_error(task, mail_log_id: int, exc: BaseException) -> None:
    """Retry transient errors a bounded number of times; otherwise mark the MailLog FAILED.

    Raises ``celery.exceptions.Retry`` when a retry is scheduled.
    """
    retries = task.request.retries
    if is_transient_mail_error(exc) and retries < task.max_retries:
        logger.warning(
            "Mail log %s transient failure (%s); retry %s of %s",
            mail_log_id,
            exc.__class__.__name__,
            retries + 1,
            task.max_retries,
        )
        raise task.retry(exc=exc, countdown=retry_delay(retries))
    logger.error("Mail log %s failed: %s", mail_log_id, exc.__class__.__name__)
    mark_mail_failed(mail_log_id, exc)


@shared_task(name="common.mail.send_generic_notification_email", **MAIL_TASK_OPTIONS)
def send_generic_notification_email_task(
    self,
    mail_log_id: int,
    recipient: str,
    subject: str,
    heading: str,
    message: str,
    action_url: str = "",
    action_label: str = "",
) -> str:
    mark_mail_attempt(mail_log_id)
    try:
        send_notification_email(
            recipient=recipient,
            subject=subject,
            heading=heading,
            message=message,
            action_url=action_url,
            action_label=action_label,
        )
    except Exception as exc:
        handle_delivery_error(self, mail_log_id, exc)
        return "failed"
    mark_mail_sent(mail_log_id)
    return "sent"
