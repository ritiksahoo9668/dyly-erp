import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from .models import PasswordResetToken

RESET_TOKEN_TTL = timedelta(hours=1)


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def hash_reset_token(raw_token: str) -> str:
    return hash_token(raw_token)


def create_password_reset_token(user) -> str:
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    raw_token = generate_raw_token()
    PasswordResetToken.objects.create(
        user=user,
        token_hash=hash_reset_token(raw_token),
        expires_at=timezone.now() + RESET_TOKEN_TTL,
    )
    return raw_token


def get_valid_reset_token(raw_token: str) -> PasswordResetToken | None:
    token_hash = hash_reset_token(raw_token)
    try:
        record = PasswordResetToken.objects.select_related("user").get(token_hash=token_hash)
    except PasswordResetToken.DoesNotExist:
        return None
    if not record.is_valid:
        return None
    return record
