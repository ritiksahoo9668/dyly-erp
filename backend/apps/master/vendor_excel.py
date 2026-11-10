"""Vendor Excel template, row resolution and dry-run preview."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import Workbook, load_workbook

from .excel import INVALID_TEMPLATE_MESSAGE
from .models import Vendor
from .vendor_rules import (
    VENDOR_NAME_REQUIRED,
    clean_vendor_text,
    describe_vendor,
    gstin_check_digit,
    length_error,
    normalize_contact,
    normalize_email,
    normalize_gstin,
    normalize_sap_vendor_id,
)

VENDOR_EXCEL_HEADERS = [
    "SAP Vendor ID",
    "Vendor Name",
    "Email ID",
    "Contact No.",
    "GSTIN",
    "Location",
]
FIELD_KEYS = ["sap_vendor_id", "vendor_name", "email", "contact_no", "gstin", "location"]
REQUIRED_HEADER_KEYS = {"sap_vendor_id", "vendor_name"}
TEMPLATE_FORMATTED_ROWS = 1000
PREVIEW_ROW_LIMIT = 500


def _header_key(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


HEADER_ALIASES = {
    "sapvendorid": "sap_vendor_id",
    "sapvendorcode": "sap_vendor_id",
    "vendorname": "vendor_name",
    "emailid": "email",
    "email": "email",
    "contactno": "contact_no",
    "contactnumber": "contact_no",
    "gstin": "gstin",
    "location": "location",
}


def build_vendor_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Vendors"
    widths = (18, 40, 30, 20, 20, 22)
    for col, (header, width) in enumerate(zip(VENDOR_EXCEL_HEADERS, widths), start=1):
        cell = sheet.cell(1, col, header)
        sheet.column_dimensions[cell.column_letter].width = width
        for row in range(2, TEMPLATE_FORMATTED_ROWS + 2):
            sheet.cell(row, col).number_format = "@"
    sheet.freeze_panes = "A2"

    instructions = workbook.create_sheet("Instructions")
    lines = [
        "Instructions",
        "Keep the 6 column headers exactly as they are.",
        "Do not add ERP Vendor ID, Is Active, Created At or Updated At columns.",
        "ERP Vendor ID (VEN-000001) is generated automatically for every new Vendor.",
        "Vendor Name is mandatory. All other columns are optional.",
        "SAP Vendor ID is kept as text, so leading zeros are preserved. It must be unique.",
        "Email ID is validated and saved in lowercase.",
        "Contact No. is kept as text; a +country code is allowed (e.g. +91 9907081109).",
        "GSTIN must be a valid 15-character GSTIN. It is saved in UPPERCASE and must be unique.",
        "Location is free text.",
        "A row whose SAP Vendor ID or GSTIN matches an existing Vendor is never overwritten:",
        "  the same Vendor is skipped; a different Vendor is reported as an error.",
        "Blank rows are ignored. Imported Vendors are created as Active.",
        "",
        "Examples:",
    ]
    for index, text in enumerate(lines, start=1):
        instructions.cell(index, 1, text)
    examples = [
        (
            "10013560",
            "AB Drives & Automation Pvt Ltd",
            "sales@abdrives.example",
            "9907081109",
            f"22AAAAA0000A1Z{gstin_check_digit('22AAAAA0000A1Z')}",
            "Raipur",
        ),
        ("0010013031", "Mesco Kalinga Steel Ltd", "", "", "", "Jajpur"),
        (
            "",
            "Sarika Associates",
            "",
            "+91 98765 43210",
            f"21ABCDE1234F1Z{gstin_check_digit('21ABCDE1234F1Z')}",
            "Cuttack",
        ),
    ]
    start = len(lines) + 1
    for col, header in enumerate(VENDOR_EXCEL_HEADERS, start=1):
        instructions.cell(start, col, header)
    for offset, example in enumerate(examples, start=1):
        for col, value in enumerate(example, start=1):
            cell = instructions.cell(start + offset, col, value)
            cell.number_format = "@"
    instructions.column_dimensions["A"].width = 95

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def _header_index(header_row) -> dict[str, int]:
    index: dict[str, int] = {}
    for position, cell in enumerate(header_row or ()):
        key = HEADER_ALIASES.get(_header_key(cell))
        if key and key not in index:
            index[key] = position
    if not REQUIRED_HEADER_KEYS.issubset(index) or len(index) < len(FIELD_KEYS):
        raise ValueError(INVALID_TEMPLATE_MESSAGE)
    return index


def validate_vendor_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    _header_index(header_row)


@dataclass
class VendorRow:
    row_number: int
    sap_vendor_id: str
    vendor_name: str
    email: str
    contact_no: str
    gstin: str
    location: str

    def payload(self) -> str:
        return json.dumps([getattr(self, key) for key in FIELD_KEYS], ensure_ascii=False)


def iter_vendor_rows(file_obj):
    """Yield VendorRow for every non-blank data row, with text trimmed."""
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    idx = _header_index(header_row)
    for row_number, row in enumerate(rows, start=2):
        values = list(row or ())
        cleaned = {
            key: clean_vendor_text(values[idx[key]] if idx[key] < len(values) else None)
            for key in FIELD_KEYS
        }
        if not any(cleaned.values()):
            continue
        yield VendorRow(row_number, **cleaned)


@dataclass
class VendorRowResult:
    status: str  # "valid" | "existing" | "duplicate" | "failed"
    reason: str = ""
    values: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _Known:
    pk: int
    erp_vendor_id: str
    vendor_name: str
    sap_vendor_id: str
    gstin: str

    @property
    def label(self) -> str:
        return describe_vendor(self.erp_vendor_id, self.vendor_name)


class VendorRowResolver:
    """Classifies rows against existing Vendors and earlier rows of the same file.

    SAP Vendor ID and GSTIN are the strong duplicate keys; Vendor Name alone never is.
    """

    def __init__(self):
        self.by_sap: dict[str, _Known] = {}
        self.by_gstin: dict[str, _Known] = {}
        for values in Vendor.objects.values_list(
            "id", "erp_vendor_id", "vendor_name", "sap_vendor_id", "gstin"
        ):
            known = _Known(*values)
            if known.sap_vendor_id:
                self.by_sap[known.sap_vendor_id.casefold()] = known
            if known.gstin:
                self.by_gstin[known.gstin] = known
        self.file_sap: dict[str, int] = {}
        self.file_gstin: dict[str, int] = {}

    def resolve(self, row: VendorRow) -> VendorRowResult:
        if not row.vendor_name:
            return VendorRowResult("failed", VENDOR_NAME_REQUIRED)
        sap_id = normalize_sap_vendor_id(row.sap_vendor_id)
        for label, value, limit in (
            ("SAP Vendor ID", sap_id, Vendor.SAP_VENDOR_ID_MAX_LENGTH),
            ("Vendor Name", row.vendor_name, Vendor.VENDOR_NAME_MAX_LENGTH),
            ("Location", row.location, Vendor.LOCATION_MAX_LENGTH),
        ):
            error = length_error(label, value, limit)
            if error:
                return VendorRowResult("failed", error)
        email, error = normalize_email(row.email)
        if error:
            return VendorRowResult("failed", error)
        contact, error = normalize_contact(row.contact_no)
        if error:
            return VendorRowResult("failed", error)
        gstin, error = normalize_gstin(row.gstin)
        if error:
            return VendorRowResult("failed", error)

        sap_key = sap_id.casefold()
        if sap_id and sap_key in self.file_sap:
            return VendorRowResult(
                "duplicate",
                f"Duplicate SAP Vendor ID {sap_id} within the Excel file "
                f"(row {self.file_sap[sap_key]}).",
            )
        if gstin and gstin in self.file_gstin:
            return VendorRowResult(
                "duplicate",
                f"Duplicate GSTIN {gstin} within the Excel file (row {self.file_gstin[gstin]}).",
            )
        if sap_id:
            self.file_sap[sap_key] = row.row_number
        if gstin:
            self.file_gstin[gstin] = row.row_number

        sap_match = self.by_sap.get(sap_key) if sap_id else None
        gstin_match = self.by_gstin.get(gstin) if gstin else None
        if sap_match and gstin_match and sap_match.pk != gstin_match.pk:
            return VendorRowResult(
                "failed",
                f"SAP Vendor ID {sap_id} belongs to {sap_match.label}, "
                f"but GSTIN belongs to {gstin_match.label}.",
            )
        match = sap_match or gstin_match
        if match is not None:
            same_vendor = (
                match.vendor_name.casefold() == row.vendor_name.casefold()
                and (not sap_id or sap_key == match.sap_vendor_id.casefold())
                and (not gstin or gstin == match.gstin)
            )
            if same_vendor:
                return VendorRowResult("existing", f"Skipped Existing — {match.label}.")
            if sap_match:
                return VendorRowResult(
                    "failed", f"SAP Vendor ID {sap_id} already exists ({match.label})."
                )
            return VendorRowResult(
                "failed", f"GSTIN already assigned to another Vendor ({match.label})."
            )

        return VendorRowResult(
            "valid",
            values={
                "sap_vendor_id": sap_id,
                "vendor_name": row.vendor_name,
                "email": email,
                "contact_no": contact,
                "gstin": gstin,
                "location": row.location,
            },
        )


def preview_vendors_from_excel(file_obj) -> dict:
    rows = list(iter_vendor_rows(file_obj))
    summary = {"total": len(rows), "valid": 0, "existing": 0, "duplicate": 0, "failed": 0}
    if not rows:
        return {
            **summary,
            "rows": [],
            "errors": [{"row": 1, "reason": "Excel file has no data rows."}],
        }

    resolver = VendorRowResolver()
    issues: list[dict] = []
    valid_rows: list[dict] = []
    for row in rows:
        result = resolver.resolve(row)
        summary[result.status] += 1
        entry = {
            "row": row.row_number,
            **{key: result.values.get(key, getattr(row, key)) for key in FIELD_KEYS},
            "status": result.status,
            "reason": result.reason,
        }
        if result.status == "valid":
            if len(valid_rows) < PREVIEW_ROW_LIMIT:
                valid_rows.append(entry)
        elif len(issues) < PREVIEW_ROW_LIMIT:
            issues.append(entry)

    return {
        **summary,
        "rows": issues + valid_rows[: max(0, PREVIEW_ROW_LIMIT - len(issues))],
        "errors": [
            {"row": entry["row"], "reason": entry["reason"]}
            for entry in issues
            if entry["status"] in {"failed", "duplicate"}
        ],
    }
