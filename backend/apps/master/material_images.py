"""Material image validation, storage, and display resolution.

A Material has at most one active image source:
- UPLOAD: ``image_file`` (+ generated ``image_thumb``)
- URL: ``image_url`` (external http/https)
- NONE: no image (frontend renders the placeholder)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .material_image_rules import (
    ALLOWED_EXTENSIONS,
    MaterialImageError,
    normalize_image_url,
)
from .models import Material, material_thumb_upload_to

logger = logging.getLogger("erp.master.material_images")

__all__ = [
    "MaterialImageError",
    "normalize_image_url",
    "process_uploaded_image",
    "set_uploaded_image",
    "set_image_url",
    "remove_image",
    "resolve_display_image",
    "resolve_display_thumb",
    "generate_thumbnail_for_stored_image",
]

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/webp",
}
FORMAT_EXTENSION = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
INVALID_FILE_TYPE_MESSAGE = "Only JPG, JPEG, PNG or WebP images are allowed."

IMAGE_UPDATE_FIELDS = [
    "image_source",
    "image_url",
    "image_file",
    "image_thumb",
    "updated_by",
    "updated_at",
]

@dataclass
class ProcessedImage:
    original: ContentFile
    original_name: str
    thumb: ContentFile


def _max_bytes() -> int:
    return int(getattr(settings, "MATERIAL_IMAGE_MAX_BYTES", 5 * 1024 * 1024))


def _max_size_label() -> str:
    size_mb = _max_bytes() / (1024 * 1024)
    return f"{size_mb:g} MB"


def _encode(img: Image.Image, fmt: str) -> bytes:
    buffer = BytesIO()
    if fmt == "JPEG":
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(buffer, format="JPEG", quality=90, optimize=True)
    elif fmt == "PNG":
        if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            img = img.convert("RGBA")
        img.save(buffer, format="PNG", optimize=True)
    else:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.save(buffer, format="WEBP", quality=90, method=4)
    return buffer.getvalue()


def _thumbnail(img: Image.Image) -> bytes:
    size = int(getattr(settings, "MATERIAL_IMAGE_THUMB_SIZE", 480))
    thumb = img.copy()
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGBA")
    thumb.thumbnail((size, size), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    thumb.save(buffer, format="WEBP", quality=80, method=4)
    return buffer.getvalue()


def process_uploaded_image(upload) -> ProcessedImage:
    """Validate an uploaded image and return re-encoded original + WebP thumbnail.

    The original filename is only used to check the extension; stored names are
    generated from the detected image format.
    """
    if upload is None:
        raise MaterialImageError("Choose an image file to upload.")

    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0:
        raise MaterialImageError("The uploaded file is empty.")
    if size > _max_bytes():
        raise MaterialImageError(f"Image must be {_max_size_label()} or smaller.")

    ext = Path(getattr(upload, "name", "") or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise MaterialImageError(INVALID_FILE_TYPE_MESSAGE)
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise MaterialImageError(INVALID_FILE_TYPE_MESSAGE)

    upload.seek(0)
    data = upload.read(_max_bytes() + 1)
    if len(data) > _max_bytes():
        raise MaterialImageError(f"Image must be {_max_size_label()} or smaller.")

    max_pixels = int(getattr(settings, "MATERIAL_IMAGE_MAX_PIXELS", 40_000_000))
    try:
        with Image.open(BytesIO(data)) as probe:
            detected = probe.format
            width, height = probe.size
            if width * height > max_pixels:
                raise MaterialImageError("Image dimensions are too large.")
            probe.verify()
    except MaterialImageError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise MaterialImageError("The file is not a valid JPG, PNG or WebP image.") from exc

    if detected not in FORMAT_EXTENSION:
        raise MaterialImageError(INVALID_FILE_TYPE_MESSAGE)

    try:
        with Image.open(BytesIO(data)) as img:
            img.load()
            oriented = ImageOps.exif_transpose(img) or img
            original_bytes = _encode(oriented, detected)
            thumb_bytes = _thumbnail(oriented)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise MaterialImageError("The image could not be processed.") from exc

    stored_ext = FORMAT_EXTENSION[detected]
    return ProcessedImage(
        original=ContentFile(original_bytes),
        original_name=f"image{stored_ext}",
        thumb=ContentFile(thumb_bytes),
    )


def _stored_file_names(material: Material) -> list[str]:
    return [name for name in (material.image_file.name, material.image_thumb.name) if name]


def _delete_files(names: list[str]) -> None:
    storage = Material._meta.get_field("image_file").storage
    for name in names:
        try:
            storage.delete(name)
        except Exception:  # pragma: no cover - storage cleanup is best effort
            logger.warning("Could not delete material image file %s", name, exc_info=True)


def _delete_files_on_commit(names: list[str]) -> None:
    if names:
        transaction.on_commit(lambda: _delete_files(names))


def set_uploaded_image(material: Material, upload, *, user=None) -> Material:
    processed = process_uploaded_image(upload)
    previous = _stored_file_names(material)

    material.image_file.save(processed.original_name, processed.original, save=False)
    material.image_thumb.save("thumb.webp", processed.thumb, save=False)
    new_files = _stored_file_names(material)
    try:
        with transaction.atomic():
            material.image_url = ""
            material.image_source = Material.ImageSource.UPLOAD
            material.updated_by = user
            material.save(update_fields=IMAGE_UPDATE_FIELDS)
            _delete_files_on_commit(previous)
    except Exception:
        _delete_files(new_files)
        raise
    return material


def set_image_url(material: Material, raw_url, *, user=None) -> Material:
    url = normalize_image_url(raw_url)
    previous = _stored_file_names(material)
    with transaction.atomic():
        material.image_file = ""
        material.image_thumb = ""
        material.image_url = url
        material.image_source = Material.ImageSource.URL
        material.updated_by = user
        material.save(update_fields=IMAGE_UPDATE_FIELDS)
        _delete_files_on_commit(previous)
    return material


def remove_image(material: Material, *, user=None) -> Material:
    """Clear the image reference only; the Material record is never deleted/deactivated."""
    previous = _stored_file_names(material)
    with transaction.atomic():
        material.image_file = ""
        material.image_thumb = ""
        material.image_url = ""
        material.image_source = Material.ImageSource.NONE
        material.updated_by = user
        material.save(update_fields=IMAGE_UPDATE_FIELDS)
        _delete_files_on_commit(previous)
    return material


def generate_thumbnail_for_stored_image(image_name: str, storage=None) -> str:
    """Create a WebP thumbnail for an image already in storage; return the new relative path."""
    storage = storage or Material._meta.get_field("image_file").storage
    max_pixels = int(getattr(settings, "MATERIAL_IMAGE_MAX_PIXELS", 40_000_000))
    try:
        with storage.open(image_name, "rb") as handle:
            data = handle.read()
        with Image.open(BytesIO(data)) as img:
            width, height = img.size
            if width * height > max_pixels:
                raise MaterialImageError("Image dimensions are too large.")
            img.load()
            oriented = ImageOps.exif_transpose(img) or img
            thumb_bytes = _thumbnail(oriented)
    except MaterialImageError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise MaterialImageError(f"Could not create thumbnail for {image_name}.") from exc
    return storage.save(material_thumb_upload_to(None, "thumb.webp"), ContentFile(thumb_bytes))


def _absolute_media_url(url: str, request=None) -> str:
    """Build an absolute URL for a storage URL; absolute storage URLs (S3/CDN) pass through."""
    if url.startswith(("http://", "https://", "//")):
        return url
    path = url if url.startswith("/") else f"/{url}"
    if request is not None:
        return request.build_absolute_uri(path)
    return f"{getattr(settings, 'BACKEND_URL', '').rstrip('/')}{path}"


def resolve_display_image(material: Material, request=None) -> str | None:
    """Uploaded file → external URL → None, regardless of ``image_source``."""
    if material.image_file:
        return _absolute_media_url(material.image_file.url, request)
    if material.image_url:
        return material.image_url
    return None


def resolve_display_thumb(material: Material, request=None) -> str | None:
    """Uploaded thumbnail → external URL → None, regardless of ``image_source``."""
    if material.image_thumb:
        return _absolute_media_url(material.image_thumb.url, request)
    if material.image_url:
        return material.image_url
    return None
