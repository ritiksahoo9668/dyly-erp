from io import BytesIO

from openpyxl import Workbook, load_workbook

INVALID_TEMPLATE_MESSAGE = (
    "Invalid Excel template.\nPlease download and use the latest template."
)


def _normalize_header(value) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def as_sap_text_code(raw) -> str:
    """Preserve SAP codes as text; never coerce via int when already a string."""
    if raw is None:
        return ""
    if isinstance(raw, bool):
        return str(raw).strip()
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, float):
        if raw.is_integer():
            return str(int(raw))
        return str(raw).strip()
    return str(raw).strip()


def _empty_preview(*, errors: list[dict] | None = None) -> dict:
    return {
        "total": 0,
        "valid": 0,
        "existing": 0,
        "duplicate": 0,
        "failed": 0,
        "rows": [],
        "valid_rows": [],
        "errors": errors or [],
    }


def build_name_master_template(
    *,
    sheet_title: str,
    header: str,
    sample_rows: list[str],
) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title[:31]
    sheet["A1"] = header
    for index, value in enumerate(sample_rows, start=2):
        sheet[f"A{index}"] = value

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = f'Use column header "{header}" exactly. Do not rename headers.'
    instructions["A3"] = f"{header} is mandatory."
    instructions["A4"] = "Do not add Is Active / Status columns."
    instructions["A5"] = "Imported records are created as Active automatically."
    instructions["A6"] = "Duplicate names (case-insensitive) are not imported."
    instructions["A7"] = "Existing names in the system are skipped."

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_name_master_template(file_obj, *, header: str) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    actual = _normalize_header(header_row[0] if header_row else "")
    expected = {_normalize_header(header), "name"}
    if actual not in expected:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def validate_vertical_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "vertical name" not in header or "department" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def preview_name_master_from_excel(
    file_obj,
    *,
    model,
    header: str,
    label: str,
) -> dict:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        return _empty_preview(errors=[{"row": 1, "reason": "Excel file is empty."}])

    expected = {_normalize_header(header), "name"}
    actual = _normalize_header(rows[0][0] if rows[0] else "")
    if actual not in expected:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    total = 0
    valid = 0
    existing = 0
    duplicate = 0
    failed = 0
    preview_rows: list[dict] = []
    valid_rows: list[dict] = []
    errors: list[dict] = []
    seen_in_file: set[str] = set()

    for index, row in enumerate(rows[1:], start=2):
        raw = row[0] if row else None
        if raw is None or str(raw).strip() == "":
            continue

        total += 1
        name = str(raw).strip()
        entry = {
            "row": index,
            "name": name,
            "status": "failed",
            "reason": "",
        }

        if not name:
            failed += 1
            entry["reason"] = f"{label} is required."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue

        if len(name) > 150:
            failed += 1
            entry["reason"] = f"{label} must be 150 characters or fewer."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue

        key = name.casefold()
        if key in seen_in_file:
            duplicate += 1
            entry["status"] = "duplicate"
            entry["reason"] = f"Duplicate {label} within the Excel file."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue
        seen_in_file.add(key)

        if model.name_exists(name):
            existing += 1
            entry["status"] = "existing"
            entry["reason"] = "Already exists in the system."
            preview_rows.append(entry)
            continue

        valid += 1
        entry["status"] = "valid"
        entry["reason"] = ""
        preview_rows.append(entry)
        valid_rows.append({"name": name})

    return {
        "total": total,
        "valid": valid,
        "existing": existing,
        "duplicate": duplicate,
        "failed": failed,
        "rows": preview_rows,
        "valid_rows": valid_rows,
        "errors": errors,
    }


def commit_name_master_rows(
    *,
    model,
    label: str,
    rows: list[dict],
) -> dict:
    total = 0
    created = 0
    skipped = 0
    failed = 0
    errors: list[dict] = []
    seen: set[str] = set()

    for index, item in enumerate(rows or [], start=1):
        total += 1
        name = str((item or {}).get("name") or "").strip()
        if not name:
            failed += 1
            errors.append({"row": index, "reason": f"{label} is required."})
            continue
        if len(name) > 150:
            failed += 1
            errors.append({"row": index, "reason": f"{label} must be 150 characters or fewer."})
            continue

        key = name.casefold()
        if key in seen:
            failed += 1
            errors.append({"row": index, "reason": f"Duplicate {label} within the import payload."})
            continue
        seen.add(key)

        if model.name_exists(name):
            skipped += 1
            continue

        model.objects.create(name=name, is_active=True)
        created += 1

    return {
        "total": total,
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


def import_name_master_from_excel(
    file_obj,
    *,
    model,
    header: str,
    label: str,
) -> dict:
    """One-shot import (used by Unit Master). Always creates Active records."""
    preview = preview_name_master_from_excel(
        file_obj,
        model=model,
        header=header,
        label=label,
    )
    commit = commit_name_master_rows(
        model=model,
        label=label,
        rows=preview.get("valid_rows") or [],
    )
    return {
        "total": preview["total"],
        "created": commit["created"],
        "skipped": preview["existing"] + commit["skipped"],
        "failed": preview["failed"] + preview["duplicate"] + commit["failed"],
        "errors": (preview.get("errors") or []) + (commit.get("errors") or []),
    }


def build_vertical_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Verticals"
    sheet["A1"] = "Vertical Name"
    sheet["B1"] = "Department"
    samples = [
        ("HR", "HR & Admin"),
        ("Security", "HR & Admin"),
        ("IT", "HR & Admin"),
        ("Safety", "HR & Admin"),
        ("Environment", "HR & Admin"),
        ("Corporate Affairs", "HR & Admin"),
        ("Store", "Procurement"),
        ("Commercial", "Procurement"),
    ]
    for index, (name, department) in enumerate(samples, start=2):
        sheet[f"A{index}"] = name
        sheet[f"B{index}"] = department

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "Vertical Name" and "Department" exactly.'
    instructions["A3"] = "Vertical Name is mandatory."
    instructions["A4"] = "Department is mandatory and must already exist in Department Master."
    instructions["A5"] = "Do not add Is Active / Status columns."
    instructions["A6"] = "Imported Verticals are created as Active automatically."
    instructions["A7"] = "Duplicate Vertical Names (case-insensitive) are not imported."

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


_VERTICAL_NAME_CORRECTIONS = {
    "enviroment": "Environment",
    "corporate affarirs": "Corporate Affairs",
}


def _correct_vertical_name(name: str) -> str:
    return _VERTICAL_NAME_CORRECTIONS.get(name.casefold(), name)


def preview_verticals_from_excel(file_obj) -> dict:
    from .models import Department, Vertical

    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        return _empty_preview(errors=[{"row": 1, "reason": "Excel file is empty."}])

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "vertical name" not in header or "department" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    # Reject templates that require a status column as the third business field.
    # Extra ignored columns are fine only when required headers exist; Is Active is never used.
    name_idx = header.index("vertical name")
    dept_idx = header.index("department")

    total = 0
    valid = 0
    existing = 0
    duplicate = 0
    failed = 0
    preview_rows: list[dict] = []
    valid_rows: list[dict] = []
    errors: list[dict] = []
    seen_in_file: set[str] = set()

    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(name_idx, dept_idx):
            values.append(None)

        raw_name = values[name_idx]
        raw_dept = values[dept_idx]

        if (raw_name is None or str(raw_name).strip() == "") and (
            raw_dept is None or str(raw_dept).strip() == ""
        ):
            continue

        total += 1
        name = _correct_vertical_name(str(raw_name or "").strip())
        department_name = str(raw_dept or "").strip()
        entry = {
            "row": index,
            "name": name,
            "department": department_name,
            "status": "failed",
            "reason": "",
        }

        if not name:
            failed += 1
            entry["reason"] = "Vertical Name is required."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue
        if len(name) > 150:
            failed += 1
            entry["reason"] = "Vertical Name must be 150 characters or fewer."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue
        if not department_name:
            failed += 1
            entry["reason"] = "Department is required."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue

        key = name.casefold()
        if key in seen_in_file:
            duplicate += 1
            entry["status"] = "duplicate"
            entry["reason"] = "Duplicate Vertical Name within the Excel file."
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue
        seen_in_file.add(key)

        department = Department.objects.filter(name__iexact=department_name).first()
        if department is None:
            failed += 1
            entry["reason"] = (
                f'Department "{department_name}" does not exist in Department Master.'
            )
            errors.append({"row": index, "reason": entry["reason"]})
            preview_rows.append(entry)
            continue

        entry["department"] = department.name

        if Vertical.name_exists(name):
            existing += 1
            entry["status"] = "existing"
            entry["reason"] = "Already exists in the system."
            preview_rows.append(entry)
            continue

        valid += 1
        entry["status"] = "valid"
        entry["reason"] = ""
        preview_rows.append(entry)
        valid_rows.append({"name": name, "department_id": department.id})

    return {
        "total": total,
        "valid": valid,
        "existing": existing,
        "duplicate": duplicate,
        "failed": failed,
        "rows": preview_rows,
        "valid_rows": valid_rows,
        "errors": errors,
    }


def commit_vertical_rows(rows: list[dict]) -> dict:
    from .models import Department, Vertical

    total = 0
    created = 0
    skipped = 0
    failed = 0
    errors: list[dict] = []
    seen: set[str] = set()

    for index, item in enumerate(rows or [], start=1):
        total += 1
        name = _correct_vertical_name(str((item or {}).get("name") or "").strip())
        department_id = (item or {}).get("department_id")

        if not name:
            failed += 1
            errors.append({"row": index, "reason": "Vertical Name is required."})
            continue
        if department_id is None:
            failed += 1
            errors.append({"row": index, "reason": "Department is required."})
            continue

        key = name.casefold()
        if key in seen:
            failed += 1
            errors.append({"row": index, "reason": "Duplicate Vertical Name within the import payload."})
            continue
        seen.add(key)

        department = Department.objects.filter(pk=department_id).first()
        if department is None:
            failed += 1
            errors.append({"row": index, "reason": "Department was not found in Department Master."})
            continue

        if Vertical.name_exists(name):
            skipped += 1
            continue

        Vertical.objects.create(name=name, department=department, is_active=True)
        created += 1

    return {
        "total": total,
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


def build_uom_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "UOMs"
    sheet["A1"] = "UOM Name"
    sheet["B1"] = "UOM Symbol"
    samples = [
        ("Metric Ton", "MT"),
        ("Kilogram", "KG"),
        ("Number", "NOS"),
        ("Meter", "MTR"),
        ("Liter", "LTR"),
        ("Set", "SET"),
    ]
    for index, (name, symbol) in enumerate(samples, start=2):
        sheet[f"A{index}"] = name
        sheet[f"B{index}"] = symbol

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "UOM Name" and "UOM Symbol" exactly.'
    instructions["A3"] = "UOM Name and UOM Symbol are both mandatory."
    instructions["A4"] = "Do not add Is Active / Status columns."
    instructions["A5"] = "Imported UOMs are created as Active automatically."
    instructions["A6"] = "Duplicate names or symbols (case-insensitive) are not imported."

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_uom_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "uom name" not in header or "uom symbol" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_material_subcategory_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Subcategories"
    sheet["A1"] = "Subcategory Name"
    sheet["B1"] = "Category Name"
    samples = [
        ("Cable", "Electrical"),
        ("Motor", "Electrical"),
        ("Bearing", "Mechanical"),
        ("Pump", "Mechanical"),
    ]
    for index, (name, category) in enumerate(samples, start=2):
        sheet[f"A{index}"] = name
        sheet[f"B{index}"] = category

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "Subcategory Name" and "Category Name" exactly.'
    instructions["A3"] = "Subcategory Name and Category Name are mandatory."
    instructions["A4"] = "Category Name must already exist in Material Category Master."
    instructions["A5"] = "Do not add Is Active / Status columns."
    instructions["A6"] = "Imported Subcategories are created as Active automatically."
    instructions["A7"] = "Duplicate Subcategory Name within the same Category is not allowed."

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_material_subcategory_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "subcategory name" not in header or "category name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_unit_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Units"
    sheet["A1"] = "Unit Name"
    sheet["B1"] = "Company Name"
    samples = [
        ("Jajpur", "De-Maithan Ispat Limited"),
        ("Bhubaneswar", "De-Maithan Ispat Limited"),
    ]
    for index, (name, company) in enumerate(samples, start=2):
        sheet[f"A{index}"] = name
        sheet[f"B{index}"] = company

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "Unit Name" and "Company Name" exactly.'
    instructions["A3"] = "Unit Name and Company Name are mandatory."
    instructions["A4"] = "Company Name must already exist in Company Master."
    instructions["A5"] = "Do not add Is Active / Status columns."
    instructions["A6"] = "Imported Units are created as Active automatically."
    instructions["A7"] = "Duplicate Unit Name within the same Company is not allowed."

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_unit_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "unit name" not in header or "company name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_stock_yard_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Stock Yards"
    sheet["A1"] = "Stock Yard Name"
    sheet["B1"] = "Storage Code"
    samples = [
        ("Raw Material Yard", "RM01"),
        ("Coal Yard", "CY01"),
        ("Finished Goods Yard", "FG01"),
        ("Central Store", "CS01"),
    ]
    for index, (name, code) in enumerate(samples, start=2):
        sheet[f"A{index}"] = name
        sheet[f"B{index}"] = code

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "Stock Yard Name" and "Storage Code" exactly.'
    instructions["A3"] = "Stock Yard Name and Storage Code are both mandatory."
    instructions["A4"] = "Storage Code is saved in uppercase (e.g. rm01 becomes RM01)."
    instructions["A5"] = "Do not add Is Active / Status columns."
    instructions["A6"] = "Imported Stock Yards are created as Active automatically."
    instructions["A7"] = (
        "Duplicate Storage Codes (case-insensitive) are not imported. "
        "Stock Yard Name may repeat across different Storage Codes."
    )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_stock_yard_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "stock yard name" not in header or "storage code" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_material_group_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Material Groups"
    sheet["A1"] = "SAP Material Group Code"
    sheet["B1"] = "Group Name"
    samples = [
        ("1001", "Electrical Materials"),
        ("1002", "Mechanical Spares"),
        ("1003", "Consumables"),
        ("1004", "Raw Materials"),
        ("0010", "Leading Zero Sample"),
    ]
    for index, (code, name) in enumerate(samples, start=2):
        code_cell = sheet[f"A{index}"]
        code_cell.value = code
        code_cell.number_format = "@"
        sheet[f"B{index}"] = name

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = (
        'Use headers "SAP Material Group Code" and "Group Name" exactly.'
    )
    instructions["A3"] = "Both columns are mandatory."
    instructions["A4"] = (
        "Format the SAP Material Group Code column as Text so leading zeros are preserved "
        "(e.g. 0010 stays 0010)."
    )
    instructions["A5"] = "Do not auto-change or regenerate SAP codes."
    instructions["A6"] = "Do not add Is Active / Status columns."
    instructions["A7"] = "Imported Material Groups are created as Active automatically."
    instructions["A8"] = (
        "Duplicate SAP codes or Group Names (case-insensitive) are not imported."
    )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_material_group_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "sap material group code" not in header or "group name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_purchasing_group_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Purchasing Groups"
    sheet["A1"] = "SAP Purchase Group Code"
    sheet["B1"] = "Purchase Group Name"
    sheet["C1"] = "Remarks"
    samples = [
        ("001", "MISL", "Primary purchasing group"),
        ("002", "BARBIL", ""),
        ("003", "CWIP-MISL", "CWIP related"),
        ("004", "MIL", ""),
        ("005", "CWIP-MIL", ""),
    ]
    for index, (code, name, remarks) in enumerate(samples, start=2):
        code_cell = sheet[f"A{index}"]
        code_cell.value = code
        code_cell.number_format = "@"
        sheet[f"B{index}"] = name
        sheet[f"C{index}"] = remarks

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = (
        'Use headers "SAP Purchase Group Code", "Purchase Group Name", and "Remarks" exactly.'
    )
    instructions["A3"] = "SAP Purchase Group Code and Purchase Group Name are mandatory."
    instructions["A4"] = "Remarks is optional."
    instructions["A5"] = (
        "Format the SAP Purchase Group Code column as Text so leading zeros are preserved "
        "(e.g. 001 stays 001)."
    )
    instructions["A6"] = "Do not expand or rename Purchase Group Names."
    instructions["A7"] = "Do not add Is Active / Status columns."
    instructions["A8"] = "Imported Purchasing Groups are created as Active automatically."
    instructions["A9"] = (
        "Existing or duplicate SAP codes / names (case-insensitive) are skipped or rejected."
    )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_purchasing_group_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "sap purchase group code" not in header or "purchase group name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_plant_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Plants"
    sheet["A1"] = "SAP Plant Code"
    sheet["B1"] = "Plant Name"
    samples = [
        ("1000", "Kalinga Nagar Plant"),
        ("2000", "Barbil Plant"),
        ("0001", "Leading Zero Sample"),
    ]
    for index, (code, name) in enumerate(samples, start=2):
        code_cell = sheet[f"A{index}"]
        code_cell.value = code
        code_cell.number_format = "@"
        sheet[f"B{index}"] = name

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "SAP Plant Code" and "Plant Name" exactly.'
    instructions["A3"] = "Both columns are mandatory."
    instructions["A4"] = (
        "Format the SAP Plant Code column as Text so leading zeros are preserved "
        "(e.g. 0001 stays 0001)."
    )
    instructions["A5"] = "Do not auto-change or regenerate SAP Plant Codes."
    instructions["A6"] = "Do not add Is Active / Status columns."
    instructions["A7"] = "Imported Plants are created as Active automatically."
    instructions["A8"] = (
        "Duplicate SAP Plant Codes or Plant Names (case-insensitive) are not imported."
    )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_plant_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "sap plant code" not in header or "plant name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)


def build_material_type_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Material Types"
    sheet["A1"] = "Material Type Code"
    sheet["B1"] = "ERP Category Desc"
    samples = [
        ("ROH", "Raw Material"),
        ("HALB", "Semi Finished Material"),
        ("FERT", "Finished Material"),
        ("ERSA", "Spare Parts"),
    ]
    for index, (code, desc) in enumerate(samples, start=2):
        code_cell = sheet[f"A{index}"]
        code_cell.value = code
        code_cell.number_format = "@"
        sheet[f"B{index}"] = desc

    instructions = workbook.create_sheet("Instructions")
    instructions["A1"] = "Instructions"
    instructions["A2"] = 'Use headers "Material Type Code" and "ERP Category Desc" exactly.'
    instructions["A3"] = "Both columns are mandatory."
    instructions["A4"] = (
        "Format Material Type Code as Text so leading zeros / alphanumeric codes are preserved."
    )
    instructions["A5"] = "Do not auto-change or regenerate Material Type Codes."
    instructions["A6"] = "Do not add Is Active / Status columns."
    instructions["A7"] = "Imported Material Types are created as Active automatically."
    instructions["A8"] = (
        "Duplicate Material Type Codes (case-insensitive) are not imported. "
        "ERP Category Desc may repeat across different codes."
    )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def validate_material_type_template(file_obj) -> None:
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    header = [_normalize_header(cell) for cell in (header_row or ())]
    if "material type code" not in header or "erp category desc" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)
