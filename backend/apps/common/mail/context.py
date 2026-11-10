from django.conf import settings
from django.utils import timezone

from .constants import BRAND_NAME


def frontend_url(path: str = "") -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}" if path else base


def base_context(**extra) -> dict:
    """Branding shared by every mail template."""
    return {
        "brand_name": BRAND_NAME,
        "frontend_url": frontend_url(),
        "current_year": timezone.now().year,
        **extra,
    }
