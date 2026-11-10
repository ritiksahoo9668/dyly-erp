class MailType:
    USER_ONBOARDING_INVITE = "USER_ONBOARDING_INVITE"
    PASSWORD_RESET = "PASSWORD_RESET"
    GENERIC_NOTIFICATION = "GENERIC_NOTIFICATION"


# Template base names; ``.html`` and ``.txt`` variants are rendered from each.
TEMPLATES = {
    MailType.USER_ONBOARDING_INVITE: "mail/user_onboarding_invite",
    MailType.PASSWORD_RESET: "mail/password_reset",
    MailType.GENERIC_NOTIFICATION: "mail/generic_notification",
}

SUBJECTS = {
    MailType.USER_ONBOARDING_INVITE: "Welcome to DYLY ERP – Activate Your Account",
    MailType.PASSWORD_RESET: "DYLY ERP – Reset Your Password",
}

BRAND_NAME = "DYLY ERP"

MAIL_MAX_RETRIES = 3
MAIL_RETRY_BASE_SECONDS = 15
MAIL_RETRY_MAX_SECONDS = 300
MAIL_RETRY_JITTER = 0.2
FAILURE_REASON_MAX_LENGTH = 500

# Worker-side ceilings for one delivery attempt (seconds); EMAIL_TIMEOUT bounds each socket op.
MAIL_TASK_SOFT_TIME_LIMIT = 60
MAIL_TASK_TIME_LIMIT = 90

# Request-side publish to the broker: a couple of quick retries, then give up (MailLog FAILED).
ENQUEUE_RETRY_POLICY = {
    "max_retries": 2,
    "interval_start": 0,
    "interval_step": 0.2,
    "interval_max": 0.5,
}

MAIL_QUEUE = "mail"
