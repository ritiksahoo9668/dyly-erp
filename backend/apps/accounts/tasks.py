import logging

from celery import shared_task
from django.conf import settings

from apps.common.mail.context import frontend_url
from apps.common.mail.services import (
    log_queue_wait,
    mark_mail_attempt,
    mark_mail_failed,
    mark_mail_sent,
    send_password_reset_email,
    send_user_onboarding_invitation,
)
from apps.common.mail.tasks import MAIL_TASK_OPTIONS, handle_delivery_error
from apps.common.timing import timed

logger = logging.getLogger("erp.accounts.tasks")


@shared_task(name="accounts.send_user_onboarding_email", **MAIL_TASK_OPTIONS)
def send_user_onboarding_email_task(
    self, mail_log_id: int, onboarding_id: int, invite_version: int
) -> str:
    """Issue a fresh activation token and deliver the onboarding invitation."""
    from .onboarding import (
        build_activation_url,
        issue_invite_token,
        mark_invite_failed,
        mark_invite_sent,
    )

    ids = {"onboarding": onboarding_id, "mail_log": mail_log_id, "attempt": self.request.retries}
    log_queue_wait(mail_log_id, onboarding=onboarding_id, attempt=self.request.retries)
    with timed("invite_deliver_total", **ids):
        with timed("invite_token", **ids):
            issued = issue_invite_token(onboarding_id, invite_version)
        if issued is None:
            mark_mail_failed(mail_log_id, reason="Superseded by a newer invitation or revocation.")
            logger.info("Onboarding %s invite v%s superseded", onboarding_id, invite_version)
            return "superseded"

        onboarding, raw_token = issued
        mark_mail_attempt(mail_log_id)
        try:
            send_user_onboarding_invitation(
                recipient=onboarding.login_email,
                employee_name=onboarding.employee.full_name,
                login_email=onboarding.login_email,
                activation_url=build_activation_url(raw_token),
                expiry_hours=settings.USER_INVITE_EXPIRY_HOURS,
            )
        except Exception as exc:
            handle_delivery_error(self, mail_log_id, exc)
            mark_invite_failed(onboarding_id, invite_version)
            return "failed"

        with timed("invite_mark_sent", **ids):
            mark_mail_sent(mail_log_id)
            mark_invite_sent(onboarding_id, invite_version)
    logger.info("Onboarding %s invite v%s sent", onboarding_id, invite_version)
    return "sent"


@shared_task(name="accounts.send_password_reset_email", **MAIL_TASK_OPTIONS)
def send_password_reset_email_task(self, mail_log_id: int, user_id: int) -> str:
    """Issue a password-reset token and email it; the raw token never leaves the worker."""
    from .models import User
    from .tokens import RESET_TOKEN_TTL, create_password_reset_token

    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        mark_mail_failed(mail_log_id, reason="The account is no longer active.")
        return "skipped"

    raw_token = create_password_reset_token(user)
    mark_mail_attempt(mail_log_id)
    try:
        send_password_reset_email(
            recipient=user.email,
            user_name=user.display_name,
            reset_url=frontend_url(f"reset-password?token={raw_token}"),
            expiry_minutes=int(RESET_TOKEN_TTL.total_seconds() // 60),
        )
    except Exception as exc:
        handle_delivery_error(self, mail_log_id, exc)
        return "failed"

    mark_mail_sent(mail_log_id)
    return "sent"


@shared_task(name="accounts.expire_user_invitations")
def expire_user_invitations_task() -> int:
    from .onboarding import expire_stale_invitations

    expired = expire_stale_invitations()
    if expired:
        logger.info("Marked %s user invitation(s) as expired", expired)
    return expired
