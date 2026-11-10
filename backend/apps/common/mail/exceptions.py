class MailError(Exception):
    """Base class for mail service errors."""


class MailConfigurationError(MailError):
    """Mail settings are missing or invalid (never retried)."""


class InvalidRecipientError(MailError):
    """The recipient address is empty or malformed (never retried)."""
