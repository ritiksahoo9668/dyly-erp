"""QC Parameter Excel template, row resolution and dry-run preview."""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook, load_workbook

from .excel import INVALID_TEMPLATE_MESSAGE, _normalize_header
from .models import QcParameter
from .qc_parameter_rules import (
    NAME_REQUIRED,
    SHORT_NAME_REQUIRED,
    clean_qc_text,
    length_error,
    normalize_short_name,
)

QC_PARAMETER_EXCEL_HEADERS = ["Name", "Short Name", "Unit"]
QC_PARAMETER_HEADER_KEYS = [_normalize_header(h) for h in QC_PARAMETER_EXCEL_HEADERS]
TEMPLATE_FORMATTED_ROWS = 1000
PREVIEW_ROW_LIMIT = 500


def build_qc_parameter_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "QC Parameters"
    widths = (32, 16, 16)
    for col, (header, width) in enumerate(zip(QC_PARAMETER_EXCEL_HEADERS, widths), start=1):
        cell = sheet.cell(1, col, header)
        sheet.column_dimensions[cell.column_letter].width = width
        for row in range(2, TEMPLATE_FORMATTED_ROWS + 2):
            sheet.cell(row, col).number_format = "@"
    sheet.freeze_panes = "A2"

    instructions = workbook.create_sheet("Instructions")
    lines = [
        "Instructions",
        'Use the headers "Name", "Short Name" and "Unit" exactly. Do not add other columns.',
        "Name and Short Name are mandatory and must be unique (case-insensitive).",
        "Short Name is saved in UPPERCASE automatically.",
        "Unit is optional free text (for example %, mm, kg/cm², kcal/kg, ppm, MPa, °C).",
        "Unit is not checked against the UOM Master.",
        "Do not add Is Active / Status columns. Imported QC Parameters are created as Active.",
        "Blank rows are ignored. Existing QC Parameters are skipped.",
        "",
        "Examples:",
    ]
    for index, text in enumerate(lines, start=1):
        instructions.cell(index, 1, text)
    examples = [
        ("Moisture", "MC", "%"),
        ("Ash Content", "ASH", "%"),
        ("Gross Calorific Value", "GCV", "kcal/kg"),
        ("Size", "SIZE", "mm"),
        ("Tensile Strength", "TS", "MPa"),
    ]
    start = len(lines) + 1
    for col, header in enumerate(QC_PARAMETER_EXCEL_HEADERS, start=1):
        instructions.cell(start, col, header)
    for offset, example in enumerate(examples, start=1):
        for col, value in enumerate(example, start=1):
            instructions.cell(start + offset, col, value)
    instructions.column_dimensions["A"].width = 90

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def _header_index(header_row) -> dict[str, int]:
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if any(key not in header for key in QC_PARAMETER_HEADER_KEYS):
        raise ValueError(INVALID_TEMPLATE_MESSAGE)
    return {key: header.index(key) for key in QC_PARAMETER_HEADER_KEYS}


def validate_qc_parameter_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    _header_index(header_row)


@dataclass
class QcRow:
    row_number: int
    name: str
    short_name: str
    unit: str

    def payload(self) -> str:
        return json.dumps([self.name, self.short_name, self.unit], ensure_ascii=False)


def iter_qc_parameter_rows(file_obj):
    """Yield QcRow for every non-blank data row, with values already cleaned."""
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    rows = workbook.active.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    idx = _header_index(header_row)
    for row_number, row in enumerate(rows, start=2):
        values = list(row or ())

        def cell(key: str):
            position = idx[key]
            return values[position] if position < len(values) else None

        name = clean_qc_text(cell("name"))
        short_name = normalize_short_name(cell("short name"))
        unit = clean_qc_text(cell("unit"))
        if not (name or short_name or unit):
            continue
        yield QcRow(row_number, name, short_name, unit)


@dataclass
class QcRowResult:
    status: str  # "valid" | "existing" | "duplicate" | "failed"
    reason: str = ""


class QcParameterRowResolver:
    """Classifies rows against the database and earlier rows of the same file."""

    def __init__(self):
        self.by_name: dict[str, tuple[int, str, str]] = {}
        self.by_short: dict[str, tuple[int, str, str]] = {}
        for pk, name, short_name in QcParameter.objects.values_list("id", "name", "short_name"):
            record = (pk, name, short_name)
            self.by_name[name.casefold()] = record
            self.by_short[short_name.casefold()] = record
        self.file_names: dict[str, int] = {}
        self.file_shorts: dict[str, int] = {}

    def resolve(self, row: QcRow) -> QcRowResult:
        if not row.name:
            return QcRowResult("failed", NAME_REQUIRED)
        if not row.short_name:
            return QcRowResult("failed", SHORT_NAME_REQUIRED)
        for label, value, limit in (
            ("Name", row.name, QcParameter.NAME_MAX_LENGTH),
            ("Short Name", row.short_name, QcParameter.SHORT_NAME_MAX_LENGTH),
            ("Unit", row.unit, QcParameter.UNIT_MAX_LENGTH),
        ):
            error = length_error(label, value, limit)
            if error:
                return QcRowResult("failed", error)

        name_key = row.name.casefold()
        short_key = row.short_name.casefold()
        if name_key in self.file_names:
            return QcRowResult(
                "duplicate",
                f"Duplicate Name within the Excel file (row {self.file_names[name_key]}).",
            )
        if short_key in self.file_shorts:
            return QcRowResult(
                "duplicate",
                f"Duplicate Short Name within the Excel file "
                f"(row {self.file_shorts[short_key]}).",
            )
        self.file_names[name_key] = row.row_number
        self.file_shorts[short_key] = row.row_number

        same_name = self.by_name.get(name_key)
        same_short = self.by_short.get(short_key)
        if same_name and same_short and same_name[0] == same_short[0]:
            return QcRowResult(
                "existing", f'Skipped Existing — "{same_name[1]}" ({same_name[2]}) already exists.'
            )
        if same_name:
            return QcRowResult(
                "failed",
                f'Name "{row.name}" already exists with Short Name "{same_name[2]}".',
            )
        if same_short:
            return QcRowResult(
                "failed",
                f'Short Name "{row.short_name}" already belongs to "{same_short[1]}".',
            )
        return QcRowResult("valid")


def preview_qc_parameters_from_excel(file_obj) -> dict:
    rows = list(iter_qc_parameter_rows(file_obj))
    summary = {"total": len(rows), "valid": 0, "existing": 0, "duplicate": 0, "failed": 0}
    if not rows:
        return {
            **summary,
            "rows": [],
            "errors": [{"row": 1, "reason": "Excel file has no data rows."}],
        }

    resolver = QcParameterRowResolver()
    issues: list[dict] = []
    valid_rows: list[dict] = []
    for row in rows:
        result = resolver.resolve(row)
        summary[result.status] += 1
        entry = {
            "row": row.row_number,
            "name": row.name,
            "short_name": row.short_name,
            "unit": row.unit,
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
