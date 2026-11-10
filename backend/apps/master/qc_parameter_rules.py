"""QC Parameter normalization and duplicate checks shared by the API and Excel import."""

from __future__ import annotations

import re

_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_SPACES = re.compile(r"\s+")

NAME_REQUIRED = "QC Parameter Name is required."
SHORT_NAME_REQUIRED = "Short Name is required."
NAME_EXISTS = "QC Parameter Name already exists."
SHORT_NAME_EXISTS = "Short Name already exists."


def clean_qc_text(raw) -> str:
    """Trim and collapse whitespace, drop invisible characters.

    Unicode is deliberately not NFKC-normalized so units such as kg/cm², °C and µm keep
    their exact characters.
    """
    if raw is None:
        return ""
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    text = _INVISIBLE.sub("", str(raw)).replace("\u00a0", " ")
    return _SPACES.sub(" ", text).strip()


def normalize_short_name(raw) -> str:
    return clean_qc_text(raw).upper()


def length_error(label: str, value: str, limit: int) -> str | None:
    if len(value) > limit:
        return f"{label} must be {limit} characters or fewer."
    return None


def name_taken(name: str, *, exclude_pk: int | None = None) -> bool:
    from .models import QcParameter

    qs = QcParameter.objects.filter(name__iexact=name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def short_name_taken(short_name: str, *, exclude_pk: int | None = None) -> bool:
    from .models import QcParameter

    qs = QcParameter.objects.filter(short_name__iexact=short_name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()
