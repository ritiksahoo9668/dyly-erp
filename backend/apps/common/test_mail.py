import smtplib

from celery.exceptions import SoftTimeLimitExceeded
from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.tasks import send_user_onboarding_email_task
from config.celery import app as celery_app

from .mail.constants import (
    MAIL_MAX_RETRIES,
    MAIL_RETRY_MAX_SECONDS,
    MAIL_TASK_SOFT_TIME_LIMIT,
    MAIL_TASK_TIME_LIMIT,
)
from .mail.exceptions import InvalidRecipientError, MailConfigurationError
from .mail.services import (
    is_transient_mail_error,
    queue_notification_email,
    render_mail,
    send_templated_mail,
    send_user_onboarding_invitation,
)
from .mail.tasks import retry_delay, send_generic_notification_email_task
from .models import MailLog

MAIL_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "DYLY ERP <erp@example.com>",
    "FRONTEND_URL": "https://erp.example.com",
}


class TransientErrorTests(SimpleTestCase):
    def test_classification(self):
        transient = [
            smtplib.SMTPServerDisconnected("gone"),
            smtplib.SMTPConnectError(421, b"busy"),
            smtplib.SMTPDataError(451, b"try later"),
            ConnectionResetError(),
            TimeoutError(),
        ]
        permanent = [
            smtplib.SMTPAuthenticationError(535, b"bad credentials"),
            smtplib.SMTPRecipientsRefused({}),
            smtplib.SMTPDataError(550, b"rejected"),
            InvalidRecipientError("bad"),
            MailConfigurationError("missing"),
            ValueError("bug"),
        ]
        for exc in transient:
            self.assertTrue(is_transient_mail_error(exc), exc)
        for exc in permanent:
            self.assertFalse(is_transient_mail_error(exc), exc)


class RetryPolicyTests(SimpleTestCase):
    def test_backoff_is_exponential_bounded_and_jittered(self):
        for retries, base in ((0, 15), (1, 30), (2, 60), (3, 120), (10, MAIL_RETRY_MAX_SECONDS)):
            delays = {retry_delay(retries) for _ in range(50)}
            self.assertTrue(all(base * 0.8 - 1 <= d <= base * 1.2 + 1 for d in delays), delays)
        self.assertGreater(len({retry_delay(2) for _ in range(50)}), 1)

    def test_mail_tasks_have_time_limits_and_bounded_retries(self):
        for task in (send_generic_notification_email_task, send_user_onboarding_email_task):
            self.assertEqual(task.max_retries, MAIL_MAX_RETRIES)
            self.assertEqual(task.soft_time_limit, MAIL_TASK_SOFT_TIME_LIMIT)
            self.assertEqual(task.time_limit, MAIL_TASK_TIME_LIMIT)
        self.assertTrue(is_transient_mail_error(SoftTimeLimitExceeded()))


@override_settings(**MAIL_SETTINGS)
class MailServiceTests(TestCase):
    def test_onboarding_template_uses_base_layout_and_text_fallback(self):
        text, html = render_mail(
            "mail/user_onboarding_invite",
            {
                "employee_name": "Rajesh Kumar",
                "login_email": "rajesh@dmil.com",
                "activation_url": "https://erp.example.com/activate-account/abc",
                "expiry_hours": 48,
            },
        )
        self.assertIn("DYLY ERP", html)
        self.assertIn("Activate Account", html)
        self.assertIn("https://erp.example.com/activate-account/abc", html)
        self.assertIn("This link will expire in 48 hours", text)
        self.assertNotIn("<", text)

    def test_html_is_escaped(self):
        _, html = render_mail(
            "mail/generic_notification",
            {
                "heading": "<script>x</script>",
                "message": "Hi",
                "action_url": "",
                "action_label": "",
            },
        )
        self.assertNotIn("<script>", html)

    def test_sends_multipart_message_from_default_sender(self):
        send_user_onboarding_invitation(
            recipient="rajesh@dmil.com",
            employee_name="Rajesh Kumar",
            login_email="rajesh@dmil.com",
            activation_url="https://erp.example.com/activate-account/abc",
            expiry_hours=48,
        )
        message = mail.outbox[0]
        self.assertEqual(message.from_email, "DYLY ERP <erp@example.com>")
        self.assertEqual(message.subject, "Welcome to DYLY ERP – Activate Your Account")
        self.assertEqual(message.alternatives[0][1], "text/html")

    def test_invalid_recipient_is_rejected(self):
        with self.assertRaises(InvalidRecipientError):
            send_templated_mail(
                recipient="not-an-email",
                subject="x",
                template="mail/generic_notification",
                context={"heading": "x", "message": "y"},
            )
        self.assertEqual(mail.outbox, [])

    def test_generic_notification_is_logged_and_sent_via_celery(self):
        previous = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        try:
            with self.captureOnCommitCallbacks(execute=True):
                log = queue_notification_email(
                    recipient="ops@example.com",
                    subject="Indent approved",
                    heading="Indent approved",
                    message="Indent IND-1 was approved.",
                    action_url="https://erp.example.com/procurement",
                )
                self.assertEqual(MailLog.objects.get(pk=log.pk).status, "QUEUED")
        finally:
            celery_app.conf.task_always_eager = previous
        log.refresh_from_db()
        self.assertEqual((log.status, log.attempts), ("SENT", 1))
        self.assertIsNotNone(log.sent_at)
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])
