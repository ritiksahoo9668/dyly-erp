"""Normalization and duplicate rules shared by the Employee API and Excel import."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from .models import Employee

MOBILE_MIN_DIGITS = 10
MOBILE_MAX_DIGITS = 15
INVALID_MOBILE_MESSAGE = "Invalid Mobile Number"
INVALID_DATE_MESSAGE = "Invalid Date Of Joining"
GENDER_CHOICES_TEXT = ", ".join(label for _, label in Employee.Gender.choices)

_GENDER_ALIASES = {
    "m": Employee.Gender.MALE,
    "male": Employee.Gender.MALE,
    "f": Employee.Gender.FEMALE,
    "female": Employee.Gender.FEMALE,
    "o": Employee.Gender.OTHER,
    "other": Employee.Gender.OTHER,
    "others": Employee.Gender.OTHER,
    "prefer not to say": Employee.Gender.PREFER_NOT_TO_SAY,
    "prefer not to disclose": Employee.Gender.PREFER_NOT_TO_SAY,
    "not disclosed": Employee.Gender.PREFER_NOT_TO_SAY,
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%d-%b-%y",
    "%d/%m/%y",
)

_EXCEL_EPOCH = date(1899, 12, 30)
_email_validator = EmailValidator()


_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
_LOOKALIKES = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def clean_text(raw) -> str:
    """Trim Excel text and neutralize invisible differences (NBSP, zero-width, curly quotes,
    en dashes, repeated spaces) so values match their Masters."""
    if raw is None:
        return ""
    text = unicodedata.normalize("NFKC", str(raw)).translate(_INVISIBLE).translate(_LOOKALIKES)
    return re.sub(r"\s+", " ", text).strip()


def normalize_gender(raw) -> str | None:
    """Return a controlled Gender value, or None when the input is not recognized."""
    key = re.sub(r"[\s_\-]+", " ", str(raw or "")).strip().casefold()
    if not key:
        return None
    return _GENDER_ALIASES.get(key)


def normalize_mobile(raw) -> tuple[str, str | None]:
    """Return (normalized, error). Keeps a leading "+" country code and strips separators."""
    if raw is None:
        return "", "Mobile Number is required."
    if isinstance(raw, bool):
        return "", INVALID_MOBILE_MESSAGE
    if isinstance(raw, int):
        text = str(raw)
    elif isinstance(raw, float):
        if not raw.is_integer():
            return "", INVALID_MOBILE_MESSAGE
        text = str(int(raw))
    else:
        text = str(raw).strip()
    if not text:
        return "", "Mobile Number is required."
    compact = re.sub(r"[\s\-().]", "", text)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if not re.fullmatch(r"\+?\d+", compact):
        return "", INVALID_MOBILE_MESSAGE
    digits = compact.lstrip("+")
    if not (MOBILE_MIN_DIGITS <= len(digits) <= MOBILE_MAX_DIGITS):
        return "", INVALID_MOBILE_MESSAGE
    return compact, None


def normalize_email(raw, *, label: str) -> tuple[str, str | None]:
    """Return (lowercased email or "", error). Blank is allowed."""
    cleaned = str(raw or "").strip().lower()
    if not cleaned:
        return "", None
    if len(cleaned) > 254:
        return "", f"{label} must be 254 characters or fewer."
    try:
        _email_validator(cleaned)
    except ValidationError:
        return "", f"Invalid {label}"
    return cleaned, None


def parse_joining_date(raw) -> tuple[date | None, str | None]:
    """Parse Excel dates, Excel serial numbers and common text formats (day-first)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, "Date Of Joining is required."
    if isinstance(raw, datetime):
        value = raw.date()
    elif isinstance(raw, date):
        value = raw
    elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if not 1 <= raw <= 2958465:
            return None, INVALID_DATE_MESSAGE
        value = _EXCEL_EPOCH + timedelta(days=int(raw))
    else:
        text = str(raw).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?", text):
            text = text[:10]
        value = None
        for fmt in _DATE_FORMATS:
            try:
                value = datetime.strptime(text, fmt).date()
                break
            except ValueError:
                continue
        if value is None:
            return None, INVALID_DATE_MESSAGE
    if value.year < 1900 or value.year > 2100:
        return None, INVALID_DATE_MESSAGE
    return value, None


def employee_label(full_name: str, designation: str | None, department: str | None) -> str:
    """User-facing identity of an Employee. Employee Code is internal and never shown."""
    role = ", ".join(part for part in (designation, department) if part)
    return f"{full_name} ({role})" if role else full_name


def describe_employee(employee: Employee) -> str:
    return employee_label(
        employee.full_name,
        getattr(employee.designation, "name", None),
        getattr(employee.department, "name", None),
    )


def _identity_qs():
    return Employee.objects.select_related("designation", "department").only(
        "id", "employee_code", "full_name", "designation__name", "department__name"
    )


def find_mobile_owner(mobile: str, *, exclude_pk: int | None = None) -> Employee | None:
    qs = _identity_qs().filter(mobile_number=mobile)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


def find_personal_email_matches(email: str, *, exclude_pk: int | None = None) -> list[Employee]:
    if not email:
        return []
    qs = _identity_qs().filter(personal_email=email)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return list(qs.order_by("employee_code")[:5])
