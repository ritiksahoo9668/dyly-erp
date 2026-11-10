"""Vendor normalization, validation and duplicate checks shared by the API and Excel import."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_SPACES = re.compile(r"\s+")
_GSTIN_PATTERN = re.compile(r"^(\d{2})[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_STATE_CODES = {f"{code:02d}" for code in range(1, 39)} | {"97", "99"}
_CONTACT_ALLOWED = re.compile(r"^\+?[\d\s\-().]+$")
_email_validator = EmailValidator()

CONTACT_MIN_DIGITS = 6
CONTACT_MAX_DIGITS = 15

VENDOR_NAME_REQUIRED = "Vendor Name is required."
INVALID_EMAIL = "Invalid Email ID."
INVALID_CONTACT = "Invalid Contact No."
INVALID_GSTIN = "Invalid GSTIN."
INVALID_GSTIN_CHECK_DIGIT = "Invalid GSTIN — check digit does not match."


def clean_vendor_text(raw) -> str:
    """Trim, collapse whitespace and drop invisible characters.

    Whole-number floats from Excel (10013031.0) become "10013031"; leading zeros survive only
    when the cell is text, which is why the template formats every column as Text.
    """
    if raw is None:
        return ""
    if isinstance(raw, bool):
        return str(raw)
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    text = _INVISIBLE.sub("", str(raw)).replace("\u00a0", " ")
    return _SPACES.sub(" ", text).strip()


def length_error(label: str, value: str, limit: int) -> str | None:
    if len(value) > limit:
        return f"{label} must be {limit} characters or fewer."
    return None


def normalize_email(raw) -> tuple[str, str | None]:
    email = clean_vendor_text(raw).replace(" ", "").lower()
    if not email:
        return "", None
    if len(email) > 254:
        return "", INVALID_EMAIL
    try:
        _email_validator(email)
    except ValidationError:
        return "", INVALID_EMAIL
    return email, None


def normalize_contact(raw) -> tuple[str, str | None]:
    """Keep the number as typed (single-spaced); allow +country code, spaces, dashes, brackets."""
    contact = clean_vendor_text(raw)
    if not contact:
        return "", None
    if contact.startswith("00"):
        contact = "+" + contact[2:]
    digits = re.sub(r"\D", "", contact)
    if (
        not _CONTACT_ALLOWED.fullmatch(contact)
        or not CONTACT_MIN_DIGITS <= len(digits) <= CONTACT_MAX_DIGITS
    ):
        return "", INVALID_CONTACT
    from .models import Vendor

    if len(contact) > Vendor.CONTACT_NO_MAX_LENGTH:
        contact = ("+" if contact.startswith("+") else "") + digits
    return contact, None


def contact_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def gstin_check_digit(first_fourteen: str) -> str:
    total = 0
    for index, char in enumerate(first_fourteen):
        product = _GSTIN_CHARS.index(char) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36]


def normalize_gstin(raw) -> tuple[str, str | None]:
    gstin = clean_vendor_text(raw).replace(" ", "").upper()
    if not gstin:
        return "", None
    match = _GSTIN_PATTERN.fullmatch(gstin)
    if not match or match.group(1) not in _GSTIN_STATE_CODES:
        return "", INVALID_GSTIN
    if gstin_check_digit(gstin[:14]) != gstin[14]:
        return "", INVALID_GSTIN_CHECK_DIGIT
    return gstin, None


def normalize_sap_vendor_id(raw) -> str:
    return clean_vendor_text(raw).replace(" ", "")


def describe_vendor(erp_vendor_id: str, vendor_name: str) -> str:
    return f"{erp_vendor_id} — {vendor_name}"


def sap_id_owner(sap_vendor_id: str, *, exclude_pk: int | None = None):
    from .models import Vendor

    qs = Vendor.objects.filter(sap_vendor_id__iexact=sap_vendor_id)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.only("id", "erp_vendor_id", "vendor_name").first()


def gstin_owner(gstin: str, *, exclude_pk: int | None = None):
    from .models import Vendor

    qs = Vendor.objects.filter(gstin=gstin)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.only("id", "erp_vendor_id", "vendor_name").first()


def sap_id_exists_message(sap_vendor_id: str, owner) -> str:
    return (
        f"SAP Vendor ID {sap_vendor_id} already exists "
        f"({describe_vendor(owner.erp_vendor_id, owner.vendor_name)})."
    )


def gstin_taken_message(owner) -> str:
    return (
        "GSTIN already assigned to another Vendor "
        f"({describe_vendor(owner.erp_vendor_id, owner.vendor_name)})."
    )
