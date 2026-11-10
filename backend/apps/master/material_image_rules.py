"""Pure Material image rules shared by the API, Excel import, migrations and audit command.

This module must not import models so data migrations can use it safely.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

logger = logging.getLogger("erp.master.material_images")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
BLOCKED_URL_PREFIXES = ("javascript:", "data:", "vbscript:", "file:", "blob:")
INVALID_URL_MESSAGE = "Enter a valid http:// or https:// image URL."
MEDIA_PATH_MAX_LENGTH = 255
UPLOAD_IMAGE_PREFIX = "materials/images/"
UPLOAD_THUMB_PREFIX = "materials/thumbs/"

LEGACY_URL = "url"
LEGACY_UPLOAD = "upload"
LEGACY_BLANK = "blank"
LEGACY_INVALID = "invalid"

_url_validator = URLValidator(schemes=["http", "https"])


class MaterialImageError(ValueError):
    """User-facing image validation error."""


def normalize_image_url(raw) -> str:
    """Return a trimmed, safe http(s) URL or raise ``MaterialImageError``."""
    cleaned = str(raw or "").strip()
    if not cleaned:
        raise MaterialImageError("Image URL is required.")
    max_length = int(getattr(settings, "MATERIAL_IMAGE_URL_MAX_LENGTH", 500))
    if len(cleaned) > max_length:
        raise MaterialImageError(f"Image URL must be {max_length} characters or fewer.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cleaned):
        raise MaterialImageError("Image URL must not contain control characters.")
    if cleaned.lower().startswith(BLOCKED_URL_PREFIXES):
        raise MaterialImageError("Only http:// or https:// image URLs are allowed.")
    cleaned = cleaned.replace(" ", "%20")
    try:
        _url_validator(cleaned)
    except ValidationError as exc:
        raise MaterialImageError(INVALID_URL_MESSAGE) from exc
    return cleaned


def normalize_relative_media_path(raw) -> str | None:
    """Return a safe relative storage path for an image file, or ``None``.

    Rejects schemes, absolute paths, traversal segments and non-image extensions.
    """
    value = str(raw or "").strip().replace("\\", "/")
    if not value or len(value) > MEDIA_PATH_MAX_LENGTH:
        return None
    if ":" in value or value.startswith("/"):
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return None
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    if PurePosixPath(value).suffix.lower() not in ALLOWED_EXTENSIONS:
        return None
    return value


def _storage_exists(storage, name: str) -> bool:
    try:
        return bool(storage.exists(name))
    except Exception:
        logger.warning("Could not check storage for %s", name, exc_info=True)
        return False


def find_existing_media_path(raw, storage) -> str | None:
    """Return the relative path if it points to an existing image file in ``storage``.

    A leading MEDIA_URL segment (e.g. ``media/``) is tolerated and stripped.
    """
    path = normalize_relative_media_path(raw)
    if path is None:
        return None
    candidates = [path]
    media_prefix = str(getattr(settings, "MEDIA_URL", "") or "").strip("/")
    if media_prefix and path.startswith(f"{media_prefix}/"):
        candidates.append(path[len(media_prefix) + 1 :])
    for candidate in candidates:
        if _storage_exists(storage, candidate):
            return candidate
    return None


def matching_thumb_path(image_path: str, storage) -> str | None:
    """Return an existing thumbnail following the ``materials/thumbs/<same>.webp`` convention."""
    if not image_path.startswith(UPLOAD_IMAGE_PREFIX):
        return None
    relative = PurePosixPath(image_path[len(UPLOAD_IMAGE_PREFIX) :]).with_suffix(".webp")
    candidate = f"{UPLOAD_THUMB_PREFIX}{relative.as_posix()}"
    return candidate if _storage_exists(storage, candidate) else None


def classify_legacy_image_value(raw, storage) -> tuple[str, str]:
    """Classify a legacy single-column image value.

    Returns ``(kind, value)`` where kind is one of LEGACY_URL, LEGACY_UPLOAD,
    LEGACY_BLANK or LEGACY_INVALID and value is the cleaned URL / relative path.
    """
    cleaned = str(raw or "").strip()
    if not cleaned:
        return LEGACY_BLANK, ""
    try:
        return LEGACY_URL, normalize_image_url(cleaned)
    except MaterialImageError:
        pass
    path = find_existing_media_path(cleaned, storage)
    if path:
        return LEGACY_UPLOAD, path
    return LEGACY_INVALID, cleaned
