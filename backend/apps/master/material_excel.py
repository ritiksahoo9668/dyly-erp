"""Material Master Excel template, dry-run preview, and row resolution helpers."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook, load_workbook

from .excel import INVALID_TEMPLATE_MESSAGE, _empty_preview, _normalize_header, as_sap_text_code
from .material_image_rules import MaterialImageError, normalize_image_url
from .models import (
    Department,
    Division,
    Material,
    MaterialCategory,
    MaterialGroup,
    MaterialSubcategory,
    MaterialType,
    Plant,
    PurchasingGroup,
    StockYard,
    Uom,
)

EXCEL_IMAGE_WARNING = (
    "Warning: Material imported successfully; image skipped because Item image URL is invalid."
)

MATERIAL_EXCEL_HEADERS = [
    "Item name",
    "Item Description",
    "Descriptive Spec",
    "Technical Spec",
    "Document Type",
    "Store Code",
    "Division",
    "Material Category",
    "Material Sub Category",
    "UOM",
    "Stock Yard",
    "Department",
    "HSN/SAC Code",
    "GST %",
    "Price",
    "SAP Code",
    "Plant code",
    "Material group",
    "Material type",
    "Purchasing group",
    "Item image",
]

MATERIAL_HEADER_KEYS = [_normalize_header(h) for h in MATERIAL_EXCEL_HEADERS]

MANDATORY_KEYS = {
    "item name",
    "item description",
    "descriptive spec",
    "document type",
    "store code",
    "material category",
    "material sub category",
    "uom",
    "stock yard",
    "department",
    "hsn/sac code",
    "gst %",
    "price",
    "sap code",
    "plant code",
    "material group",
    "material type",
    "purchasing group",
}

STRING_CODE_KEYS = {
    "store code",
    "hsn/sac code",
    "sap code",
    "plant code",
    "material group",
    "material type",
    "purchasing group",
    "uom",
}


def build_material_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Materials"
    for col, header in enumerate(MATERIAL_EXCEL_HEADERS, start=1):
        sheet.cell(1, col, header)

    sample = [
        "Sample Item",
        "Sample description",
        "Sample descriptive spec",
        "",
        "ZNB",
        "1201",
        "",
        "RAW MATERIAL",
        "STEEL",
        "NOS",
        "CENTRAL STORE",
        "STORES",
        "72042190",
        "18",
        "100.00",
        "000000000000000001",
        "1201",
        "420171",
        "ROH",
        "P01",
        "",
    ]
    for col, value in enumerate(sample, start=1):
        cell = sheet.cell(2, col, value)
        if MATERIAL_HEADER_KEYS[col - 1] in STRING_CODE_KEYS | {"store code", "sap code"}:
            cell.number_format = "@"

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = (
        "Use the same 21 business column headers as the Material Master Excel template. "
        "Do not rename, remove, or reorder headers."
    )
    instructions["A3"] = (
        "Mandatory: Item name, Item Description, Descriptive Spec, Document Type, Store Code, "
        "Material Category, Material Sub Category, UOM, Stock Yard, Department, HSN/SAC Code, "
        "GST %, Price, SAP Code, Plant code, Material group, Material type, Purchasing group."
    )
    instructions["A4"] = "Optional: Technical Spec, Division, Item image."
    instructions["A5"] = (
        "Format SAP Code, Store Code, HSN/SAC Code, Plant code, Material group, "
        "Material type, Purchasing group, and UOM as Text. Never convert 18-digit SAP Codes to Number."
    )
    instructions["A6"] = "Do not add Is Active / Status columns."
    instructions["A7"] = "Imported Materials are created as Active automatically."
    instructions["A8"] = "SAP Code is the unique business key. Item Name may repeat."
    instructions["A9"] = (
        "Material Sub Category is resolved with Material Category (same subcategory name "
        "under different categories are distinct)."
    )
    instructions["A10"] = (
        "Stock Yard is resolved by Store Code (storage location). Stock Yard name is verified when provided."
    )
    instructions["A11"] = "Missing Masters are reported; they are not auto-created."
    instructions["A12"] = (
        "Item image accepts an http:// or https:// image URL only (no files). "
        "Blank is allowed. An invalid URL imports the Material without an image and is "
        "reported as a warning."
    )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_material_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    for key in MATERIAL_HEADER_KEYS:
        if key not in header:
            raise ValueError(INVALID_TEMPLATE_MESSAGE)


def _cell(values: list, idx_map: dict[str, int], key: str):
    idx = idx_map.get(key)
    if idx is None or idx >= len(values):
        return None
    return values[idx]


def _text(raw) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _code_text(raw) -> str:
    return as_sap_text_code(raw).strip()


def row_dict_from_values(values: list, idx_map: dict[str, int]) -> dict[str, str]:
    data: dict[str, str] = {}
    for key in MATERIAL_HEADER_KEYS:
        raw = _cell(values, idx_map, key)
        if key in STRING_CODE_KEYS:
            data[key] = _code_text(raw)
        else:
            data[key] = _text(raw)
    # Item name: trim only (already via _text)
    return data


def row_payload_for_error(data: dict[str, str]) -> str:
    ordered = [data.get(k, "") for k in MATERIAL_HEADER_KEYS]
    return json.dumps(ordered, ensure_ascii=False)


def parse_decimal(raw: str, *, field_label: str) -> tuple[Decimal | None, str | None]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None, f"{field_label} is required."
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None, f"{field_label} must be a valid number."
    if value < 0:
        return None, f"{field_label} cannot be negative."
    return value, None


class MaterialLookupMaps:
    def __init__(self):
        self.divisions = {
            d.name.strip().casefold(): d for d in Division.objects.all()
        }
        self.categories = {
            c.name.strip().casefold(): c for c in MaterialCategory.objects.all()
        }
        self.subcategories = {
            (s.category_id, s.name.strip().casefold()): s
            for s in MaterialSubcategory.objects.select_related("category").all()
        }
        self.uoms = {u.symbol.strip().casefold(): u for u in Uom.objects.all()}
        self.stock_yards = {
            y.sap_storage_code.strip().casefold(): y for y in StockYard.objects.all()
        }
        self.departments = {
            d.name.strip().casefold(): d for d in Department.objects.all()
        }
        self.plants = {
            p.sap_plant_code.strip().casefold(): p for p in Plant.objects.all()
        }
        self.material_groups = {
            g.sap_material_group_code.strip().casefold(): g
            for g in MaterialGroup.objects.all()
        }
        self.material_types = {
            t.material_type_code.strip().casefold(): t for t in MaterialType.objects.all()
        }
        self.purchasing_groups = {
            g.sap_purchase_group_code.strip().casefold(): g
            for g in PurchasingGroup.objects.all()
        }
        self.existing_sap_codes = {
            str(code).strip().casefold()
            for code in Material.objects.values_list("sap_code", flat=True)
        }


def resolve_excel_image(raw: str) -> tuple[str, str, str | None]:
    """Map the Excel ``Item image`` cell to (image_url, image_source, warning).

    Excel images are external URLs only; relative media paths are not treated as uploads.
    """
    cleaned = (raw or "").strip()
    if not cleaned:
        return "", Material.ImageSource.NONE, None
    try:
        url = normalize_image_url(cleaned)
    except MaterialImageError:
        return "", Material.ImageSource.NONE, EXCEL_IMAGE_WARNING
    return url, Material.ImageSource.URL, None


def resolve_material_row(
    data: dict[str, str],
    lookups: MaterialLookupMaps,
    *,
    seen_sap: set[str],
) -> tuple[dict | None, str | None, str | None, str | None]:
    """
    Returns (resolved_kwargs, error_reason, skip_reason, warning).
    skip_reason is set for existing SAP codes (idempotent skip).
    warning is set when the row is importable but a non-critical field (Item image) was dropped.
    """
    for key in MANDATORY_KEYS:
        if not (data.get(key) or "").strip():
            label = next(
                (h for h, k in zip(MATERIAL_EXCEL_HEADERS, MATERIAL_HEADER_KEYS) if k == key),
                key,
            )
            return None, f"{label} is required.", None, None

    sap_code = data["sap code"]
    if len(sap_code) > 50:
        return None, "SAP Code must be 50 characters or fewer.", None, None
    sap_key = sap_code.casefold()
    if sap_key in seen_sap:
        return None, "Duplicate SAP Code within the Excel file.", None, None
    if sap_key in lookups.existing_sap_codes:
        return None, None, "Skipped Existing — SAP Code already exists.", None

    item_name = data["item name"]
    if len(item_name) > 255:
        return None, "Item name must be 255 characters or fewer.", None, None

    gst, gst_err = parse_decimal(data["gst %"], field_label="GST %")
    if gst_err:
        return None, gst_err, None, None
    price, price_err = parse_decimal(data["price"], field_label="Price")
    if price_err:
        return None, price_err, None, None

    division = None
    division_raw = data.get("division") or ""
    if division_raw:
        division = lookups.divisions.get(division_raw.casefold())
        if division is None:
            return None, f"Division {division_raw} not found", None, None

    category = lookups.categories.get(data["material category"].casefold())
    if category is None:
        return None, f"Material Category {data['material category']} not found", None, None

    sub = lookups.subcategories.get(
        (category.pk, data["material sub category"].casefold())
    )
    if sub is None:
        return (
            None,
            (
                f"Category/Subcategory combination not found "
                f"({data['material category']} / {data['material sub category']})"
            ),
            None,
            None,
        )

    uom = lookups.uoms.get(data["uom"].casefold())
    if uom is None:
        return None, f"UOM {data['uom']} not found", None, None

    store_code = data["store code"]
    stock_yard = lookups.stock_yards.get(store_code.casefold())
    if stock_yard is None:
        # Fallback: unique name match when Store Code alone is missing from master.
        yard_name = (data.get("stock yard") or "").strip()
        if yard_name:
            name_matches = [
                y
                for y in lookups.stock_yards.values()
                if y.name.casefold() == yard_name.casefold()
            ]
            if len(name_matches) == 1:
                stock_yard = name_matches[0]
        if stock_yard is None:
            return None, f"Stock Yard / Store Code {store_code} not found", None, None
    # Store Code is the authoritative SAP key. Excel Stock Yard Name may be generic
    # (e.g. CENTRAL STORE) while Master rows use location-specific names.

    department = lookups.departments.get(data["department"].casefold())
    if department is None:
        return None, f"Department {data['department']} not found", None, None

    plant = lookups.plants.get(data["plant code"].casefold())
    if plant is None:
        return None, f"Plant {data['plant code']} not found", None, None

    material_group = lookups.material_groups.get(data["material group"].casefold())
    if material_group is None:
        return None, f"Material Group {data['material group']} not found", None, None

    material_type = lookups.material_types.get(data["material type"].casefold())
    if material_type is None:
        return None, f"Material Type {data['material type']} not found", None, None

    purchasing_group = lookups.purchasing_groups.get(data["purchasing group"].casefold())
    if purchasing_group is None:
        return None, f"Purchasing Group {data['purchasing group']} not found", None, None

    image_url, image_source, image_warning = resolve_excel_image(data.get("item image") or "")

    resolved = {
        "item_name": item_name,
        "item_description": data["item description"],
        "descriptive_spec": data["descriptive spec"],
        "technical_spec": data.get("technical spec") or "",
        "document_type": data["document type"],
        "store_code": store_code,
        "division": division,
        "material_category": category,
        "material_subcategory": sub,
        "uom": uom,
        "stock_yard": stock_yard,
        "department": department,
        "hsn_sac_code": data["hsn/sac code"],
        "gst_percent": gst,
        "price": price,
        "sap_code": sap_code,
        "plant": plant,
        "material_group": material_group,
        "material_type": material_type,
        "purchasing_group": purchasing_group,
        "image_url": image_url,
        "image_source": image_source,
        "is_active": True,
    }
    return resolved, None, None, image_warning


def iter_material_excel_rows(file_obj):
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")
    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    for key in MATERIAL_HEADER_KEYS:
        if key not in header:
            raise ValueError(INVALID_TEMPLATE_MESSAGE)
    idx_map = {key: header.index(key) for key in MATERIAL_HEADER_KEYS}
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) < len(header):
            values.append(None)
        data = row_dict_from_values(values, idx_map)
        if not any((data.get(k) or "").strip() for k in MATERIAL_HEADER_KEYS):
            continue
        yield index, data


def preview_materials_from_excel(file_obj) -> dict:
    try:
        rows = list(iter_material_excel_rows(file_obj))
    except ValueError as exc:
        if str(exc) == INVALID_TEMPLATE_MESSAGE or "empty" in str(exc).lower():
            raise
        return _empty_preview(errors=[{"row": 1, "reason": str(exc)}])

    if not rows:
        return _empty_preview(errors=[{"row": 1, "reason": "Excel file has no data rows."}])

    lookups = MaterialLookupMaps()
    seen_sap: set[str] = set()
    preview_rows: list[dict] = []
    valid_rows: list[dict] = []
    valid = existing = duplicate = failed = warnings = 0
    warning_rows: list[dict] = []

    for row_number, data in rows:
        resolved, error, skip, warning = resolve_material_row(data, lookups, seen_sap=seen_sap)
        entry = {
            "row": row_number,
            "sap_code": data.get("sap code", ""),
            "item_name": data.get("item name", ""),
            "status": "valid",
            "reason": "",
        }
        if error:
            if "Duplicate SAP Code" in error:
                duplicate += 1
                entry["status"] = "duplicate"
            else:
                failed += 1
                entry["status"] = "failed"
            entry["reason"] = error
            preview_rows.append(entry)
            continue
        if skip:
            existing += 1
            entry["status"] = "existing"
            entry["reason"] = skip
            seen_sap.add(data["sap code"].casefold())
            preview_rows.append(entry)
            continue

        seen_sap.add(data["sap code"].casefold())
        valid += 1
        if warning:
            warnings += 1
            entry["reason"] = warning
            if len(warning_rows) < 500:
                warning_rows.append({"row": row_number, "reason": warning})
        preview_rows.append(entry)
        valid_rows.append({"row": row_number, "data": data, "resolved": None})

    return {
        "total": len(rows),
        "valid": valid,
        "existing": existing,
        "duplicate": duplicate,
        "failed": failed,
        "warnings": warnings,
        "warning_rows": warning_rows,
        "rows": preview_rows[:200],
        "valid_rows": valid_rows,
        "errors": [
            {"row": r["row"], "reason": r["reason"]}
            for r in preview_rows
            if r["status"] in {"failed", "duplicate"}
        ][:500],
        "missing_masters_summary": _summarize_missing(preview_rows),
    }


def _summarize_missing(preview_rows: list[dict]) -> list[str]:
    reasons = []
    seen = set()
    for row in preview_rows:
        reason = row.get("reason") or ""
        if "not found" not in reason.casefold():
            continue
        if reason in seen:
            continue
        seen.add(reason)
        reasons.append(f"Row {row['row']} — {reason}")
        if len(reasons) >= 100:
            break
    return reasons
