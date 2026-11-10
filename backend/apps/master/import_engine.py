"""Background Master Excel import engine (one Celery job per file, batched writes)."""

from __future__ import annotations

import json
import logging
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from .employee_excel import (
    EMPLOYEE_EXCEL_HEADERS,
    EmployeeLookupMaps,
    iter_employee_excel_rows,
    resolve_employee_row,
)
from .employee_excel import (
    row_payload_for_error as employee_row_payload,
)
from .excel import (
    INVALID_TEMPLATE_MESSAGE,
    _correct_vertical_name,
    _normalize_header,
    as_sap_text_code,
)
from .material_excel import (
    MATERIAL_EXCEL_HEADERS,
    MaterialLookupMaps,
    iter_material_excel_rows,
    resolve_material_row,
    row_payload_for_error,
)
from .models import (
    Company,
    Department,
    Designation,
    Division,
    Employee,
    Facility,
    ImportJob,
    ImportJobError,
    Material,
    MaterialCategory,
    MaterialGroup,
    MaterialSubcategory,
    MaterialType,
    Plant,
    PurchasingGroup,
    QcParameter,
    StockYard,
    Unit,
    Uom,
    Vendor,
    Vertical,
    WeighBridge,
    next_employee_codes,
    next_vendor_ids,
)
from .qc_parameter_excel import (
    QC_PARAMETER_EXCEL_HEADERS,
    QcParameterRowResolver,
    iter_qc_parameter_rows,
)
from .vendor_excel import VENDOR_EXCEL_HEADERS, VendorRowResolver, iter_vendor_rows

logger = logging.getLogger("erp.master.import")

BATCH_SIZE = getattr(settings, "MASTER_IMPORT_BATCH_SIZE", 500)

NAME_MASTER_CONFIG = {
    ImportJob.MasterType.DIVISION: {
        "model": Division,
        "header": "Division Name",
        "label": "Division Name",
    },
    ImportJob.MasterType.DEPARTMENT: {
        "model": Department,
        "header": "Department Name",
        "label": "Department Name",
    },
    ImportJob.MasterType.DESIGNATION: {
        "model": Designation,
        "header": "Designation Name",
        "label": "Designation Name",
    },
    ImportJob.MasterType.FACILITY: {
        "model": Facility,
        "header": "Facility Name",
        "label": "Facility Name",
    },
    ImportJob.MasterType.COMPANY: {
        "model": Company,
        "header": "Company Name",
        "label": "Company Name",
    },
    ImportJob.MasterType.MATERIAL_CATEGORY: {
        "model": MaterialCategory,
        "header": "Category Name",
        "label": "Category Name",
    },
    ImportJob.MasterType.WEIGHBRIDGE: {
        "model": WeighBridge,
        "header": "WeighBridge Name",
        "label": "WeighBridge Name",
    },
}


def _save_job(job: ImportJob, **fields) -> None:
    for key, value in fields.items():
        setattr(job, key, value)
    job.refresh_progress()
    update_fields = list(fields.keys()) + ["progress_percentage", "updated_at"]
    job.save(update_fields=update_fields)


def _flush_errors(job: ImportJob, buffer: list[ImportJobError]) -> None:
    if buffer:
        ImportJobError.objects.bulk_create(buffer, batch_size=BATCH_SIZE)
        buffer.clear()


def _build_error_workbook(job: ImportJob) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Errors"
    if job.master_type == ImportJob.MasterType.MATERIAL:
        sheet.append([*MATERIAL_EXCEL_HEADERS, "Error Reason"])
        for err in job.errors.order_by("row_number", "id").iterator(chunk_size=1000):
            try:
                cols = json.loads(err.input_data) if err.input_data else []
            except (json.JSONDecodeError, TypeError):
                cols = [err.input_data]
            while len(cols) < len(MATERIAL_EXCEL_HEADERS):
                cols.append("")
            sheet.append([*(cols[: len(MATERIAL_EXCEL_HEADERS)]), err.reason])
    elif job.master_type == ImportJob.MasterType.EMPLOYEE:
        sheet.append(["Row Number", *EMPLOYEE_EXCEL_HEADERS, "Error Reason"])
        for err in job.errors.order_by("row_number", "id").iterator(chunk_size=1000):
            try:
                cols = json.loads(err.input_data) if err.input_data else []
            except (json.JSONDecodeError, TypeError):
                cols = [err.input_data]
            cols = (cols + [""] * len(EMPLOYEE_EXCEL_HEADERS))[: len(EMPLOYEE_EXCEL_HEADERS)]
            sheet.append([err.row_number, *cols, err.reason])
    elif job.master_type in (ImportJob.MasterType.QC_PARAMETER, ImportJob.MasterType.VENDOR):
        headers = (
            QC_PARAMETER_EXCEL_HEADERS
            if job.master_type == ImportJob.MasterType.QC_PARAMETER
            else VENDOR_EXCEL_HEADERS
        )
        width = len(headers)
        sheet.append(["Row Number", *headers, "Error Reason"])
        for err in job.errors.order_by("row_number", "id").iterator(chunk_size=1000):
            try:
                cols = json.loads(err.input_data) if err.input_data else []
            except (json.JSONDecodeError, TypeError):
                cols = [err.input_data]
            cols = (cols + [""] * width)[:width]
            sheet.append([err.row_number, *cols, err.reason])
    else:
        sheet.append(["Row Number", "Input Data", "Error Reason"])
        for err in job.errors.order_by("row_number", "id").iterator(chunk_size=1000):
            sheet.append([err.row_number, err.input_data, err.reason])
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def _finalize_job(job: ImportJob) -> None:
    job.refresh_from_db()
    if job.failed_rows > 0 or job.warning_rows > 0:
        error_buffer = _build_error_workbook(job)
        filename = f"import_job_{job.pk}_errors.xlsx"
        job.error_file.save(filename, ContentFile(error_buffer.getvalue()), save=False)

    if job.status == ImportJob.Status.FAILED:
        status = ImportJob.Status.FAILED
    elif job.failed_rows > 0:
        status = ImportJob.Status.COMPLETED_WITH_ERRORS
    else:
        status = ImportJob.Status.COMPLETED

    job.status = status
    job.completed_at = timezone.now()
    job.processed_rows = job.total_rows
    job.refresh_progress()
    job.save(
        update_fields=[
            "status",
            "completed_at",
            "processed_rows",
            "progress_percentage",
            "error_file",
            "updated_at",
        ]
    )


def process_import_job(job_id: int) -> None:
    job = ImportJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.error("ImportJob %s not found", job_id)
        return

    _save_job(
        job,
        status=ImportJob.Status.VALIDATING,
        started_at=timezone.now(),
        detail="Validating Excel template?",
    )

    try:
        if job.master_type == ImportJob.MasterType.VERTICAL:
            _process_vertical_job(job)
        elif job.master_type == ImportJob.MasterType.UOM:
            _process_uom_job(job)
        elif job.master_type == ImportJob.MasterType.STOCK_YARD:
            _process_stock_yard_job(job)
        elif job.master_type == ImportJob.MasterType.MATERIAL_GROUP:
            _process_material_group_job(job)
        elif job.master_type == ImportJob.MasterType.PURCHASING_GROUP:
            _process_purchasing_group_job(job)
        elif job.master_type == ImportJob.MasterType.PLANT:
            _process_plant_job(job)
        elif job.master_type == ImportJob.MasterType.MATERIAL_TYPE:
            _process_material_type_job(job)
        elif job.master_type == ImportJob.MasterType.MATERIAL_SUBCATEGORY:
            _process_material_subcategory_job(job)
        elif job.master_type == ImportJob.MasterType.UNIT:
            _process_unit_job(job)
        elif job.master_type == ImportJob.MasterType.MATERIAL:
            _process_material_job(job)
        elif job.master_type == ImportJob.MasterType.EMPLOYEE:
            _process_employee_job(job)
        elif job.master_type == ImportJob.MasterType.QC_PARAMETER:
            _process_qc_parameter_job(job)
        elif job.master_type == ImportJob.MasterType.VENDOR:
            _process_vendor_job(job)
        elif job.master_type in NAME_MASTER_CONFIG:
            _process_name_master_job(job)
        else:
            raise ValueError(f"Unsupported master type: {job.master_type}")
    except ValueError as exc:
        _save_job(
            job,
            status=ImportJob.Status.FAILED,
            detail=str(exc),
            completed_at=timezone.now(),
            progress_percentage=100,
        )
        logger.warning("ImportJob %s failed validation: %s", job_id, exc)
        return
    except Exception as exc:
        logger.exception("ImportJob %s crashed", job_id)
        _save_job(
            job,
            status=ImportJob.Status.FAILED,
            detail=f"Import failed: {exc}",
            completed_at=timezone.now(),
            progress_percentage=100,
        )
        return

    _finalize_job(job)


def _process_name_master_job(job: ImportJob) -> None:
    config = NAME_MASTER_CONFIG[job.master_type]
    model = config["model"]
    header = config["header"]
    label = config["label"]

    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
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

    # Count non-blank rows first for progress total (single pass collect).
    data_rows: list[tuple[int, object]] = []
    for index, row in enumerate(rows, start=2):
        raw = row[0] if row else None
        if raw is None or str(raw).strip() == "":
            continue
        data_rows.append((index, raw))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing rows?",
    )

    existing = {str(name).strip().casefold() for name in model.objects.values_list("name", flat=True)}
    seen_in_file: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            model.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw in data_rows:
        processed += 1
        name = str(raw).strip()
        input_data = name

        if not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason=f"{label} is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason=f"{label} must be 150 characters or fewer.",
                )
            )
        else:
            key = name.casefold()
            if key in seen_in_file:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason=f"Duplicate {label} within the Excel file.",
                    )
                )
            elif key in existing:
                skipped += 1
                seen_in_file.add(key)
            else:
                seen_in_file.add(key)
                existing.add(key)
                pending_create.append(model(name=name, is_active=True))

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()

        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)

        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_vertical_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "vertical name" not in header or "department" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    name_idx = header.index("vertical name")
    dept_idx = header.index("department")

    data_rows: list[tuple[int, object, object]] = []
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
        data_rows.append((index, raw_name, raw_dept))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing verticals?",
    )

    existing = {str(name).strip().casefold() for name in Vertical.objects.values_list("name", flat=True)}
    departments = {
        str(name).strip().casefold(): pk
        for pk, name in Department.objects.values_list("id", "name")
    }
    seen_in_file: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            Vertical.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_name, raw_dept in data_rows:
        processed += 1
        name = _correct_vertical_name(str(raw_name or "").strip())
        department_name = str(raw_dept or "").strip()
        input_data = f"{name} | {department_name}".strip(" |")

        if not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Vertical Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Vertical Name must be 150 characters or fewer.",
                )
            )
        elif not department_name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Department is required.",
                )
            )
        else:
            key = name.casefold()
            if key in seen_in_file:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate Vertical Name within the Excel file.",
                    )
                )
            else:
                department_id = departments.get(department_name.casefold())
                if department_id is None:
                    failed += 1
                    error_buffer.append(
                        ImportJobError(
                            job=job,
                            row_number=row_number,
                            input_data=input_data,
                            reason=(
                                f'Department "{department_name}" does not exist in Department Master.'
                            ),
                        )
                    )
                elif key in existing:
                    skipped += 1
                    seen_in_file.add(key)
                else:
                    seen_in_file.add(key)
                    existing.add(key)
                    pending_create.append(
                        Vertical(name=name, department_id=department_id, is_active=True)
                    )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )



def _process_uom_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "uom name" not in header or "uom symbol" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    name_idx = header.index("uom name")
    symbol_idx = header.index("uom symbol")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(name_idx, symbol_idx):
            values.append(None)
        raw_name = values[name_idx]
        raw_symbol = values[symbol_idx]
        if (raw_name is None or str(raw_name).strip() == "") and (
            raw_symbol is None or str(raw_symbol).strip() == ""
        ):
            continue
        data_rows.append((index, raw_name, raw_symbol))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing UOMs?",
    )

    existing_names = {
        str(name).strip().casefold() for name in Uom.objects.values_list("name", flat=True)
    }
    existing_symbols = {
        str(symbol).strip().casefold()
        for symbol in Uom.objects.values_list("symbol", flat=True)
    }
    seen_names: set[str] = set()
    seen_symbols: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            Uom.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_name, raw_symbol in data_rows:
        processed += 1
        name = str(raw_name or "").strip()
        symbol = str(raw_symbol or "").strip()
        input_data = f"{name} | {symbol}".strip(" |")

        if not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="UOM Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="UOM Name must be 150 characters or fewer.",
                )
            )
        elif not symbol:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="UOM Symbol is required.",
                )
            )
        elif len(symbol) > 50:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="UOM Symbol must be 50 characters or fewer.",
                )
            )
        else:
            name_key = name.casefold()
            symbol_key = symbol.casefold()
            if name_key in seen_names:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate UOM Name within the Excel file.",
                    )
                )
            elif symbol_key in seen_symbols:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate UOM Symbol within the Excel file.",
                    )
                )
            elif name_key in existing_names or symbol_key in existing_symbols:
                skipped += 1
                seen_names.add(name_key)
                seen_symbols.add(symbol_key)
            else:
                seen_names.add(name_key)
                seen_symbols.add(symbol_key)
                existing_names.add(name_key)
                existing_symbols.add(symbol_key)
                pending_create.append(Uom(name=name, symbol=symbol, is_active=True))

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_vendor_job(job: ImportJob) -> None:
    with job.source_file.open("rb") as handle:
        rows = list(iter_vendor_rows(handle))
    if not rows:
        raise ValueError("Excel file has no data rows.")

    total = len(rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Vendors...",
    )

    resolver = VendorRowResolver()
    user = job.uploaded_by
    pending: list[tuple[int, str, Vendor]] = []
    error_buffer: list[ImportJobError] = []
    counts = {"created": 0, "skipped": 0, "failed": 0}

    def record_error(row_number: int, payload: str, reason: str) -> None:
        counts["failed"] += 1
        error_buffer.append(
            ImportJobError(job=job, row_number=row_number, input_data=payload, reason=reason)
        )

    def flush_creates() -> None:
        if not pending:
            return
        # ERP Vendor IDs are reserved only for rows that are about to be created.
        for (_, _, vendor), vendor_id in zip(
            pending, next_vendor_ids(len(pending)), strict=True
        ):
            vendor.erp_vendor_id = vendor_id
        try:
            with transaction.atomic():
                Vendor.objects.bulk_create([vendor for _, _, vendor in pending])
            counts["created"] += len(pending)
        except IntegrityError:
            for row_number, payload, vendor in pending:
                try:
                    with transaction.atomic():
                        vendor.save()
                    counts["created"] += 1
                except IntegrityError:
                    record_error(
                        row_number,
                        payload,
                        "SAP Vendor ID or GSTIN already exists (saved meanwhile).",
                    )
        pending.clear()

    for processed, row in enumerate(rows, start=1):
        result = resolver.resolve(row)
        if result.status == "valid":
            pending.append(
                (
                    row.row_number,
                    row.payload(),
                    Vendor(**result.values, is_active=True, created_by=user, updated_by=user),
                )
            )
        elif result.status == "existing":
            counts["skipped"] += 1
        else:
            record_error(row.row_number, row.payload(), result.reason)

        if len(pending) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=counts["created"] + len(pending),
                skipped_rows=counts["skipped"],
                failed_rows=counts["failed"],
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=total,
        created_rows=counts["created"],
        skipped_rows=counts["skipped"],
        failed_rows=counts["failed"],
        detail="Import finished.",
    )


def _process_qc_parameter_job(job: ImportJob) -> None:
    with job.source_file.open("rb") as handle:
        rows = list(iter_qc_parameter_rows(handle))
    if not rows:
        raise ValueError("Excel file has no data rows.")

    total = len(rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing QC Parameters...",
    )

    resolver = QcParameterRowResolver()
    user = job.uploaded_by
    pending: list[tuple[int, str, QcParameter]] = []
    error_buffer: list[ImportJobError] = []
    counts = {"created": 0, "skipped": 0, "failed": 0}

    def record_error(row_number: int, payload: str, reason: str) -> None:
        counts["failed"] += 1
        error_buffer.append(
            ImportJobError(job=job, row_number=row_number, input_data=payload, reason=reason)
        )

    def flush_creates() -> None:
        if not pending:
            return
        try:
            with transaction.atomic():
                QcParameter.objects.bulk_create([obj for _, _, obj in pending])
            counts["created"] += len(pending)
        except IntegrityError:
            for row_number, payload, obj in pending:
                try:
                    with transaction.atomic():
                        obj.save()
                    counts["created"] += 1
                except IntegrityError:
                    record_error(
                        row_number, payload, "Name or Short Name already exists (saved meanwhile)."
                    )
        pending.clear()

    for processed, row in enumerate(rows, start=1):
        result = resolver.resolve(row)
        if result.status == "valid":
            pending.append(
                (
                    row.row_number,
                    row.payload(),
                    QcParameter(
                        name=row.name,
                        short_name=row.short_name,
                        unit=row.unit,
                        is_active=True,
                        created_by=user,
                        updated_by=user,
                    ),
                )
            )
        elif result.status == "existing":
            counts["skipped"] += 1
        else:
            record_error(row.row_number, row.payload(), result.reason)

        if len(pending) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=counts["created"] + len(pending),
                skipped_rows=counts["skipped"],
                failed_rows=counts["failed"],
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=total,
        created_rows=counts["created"],
        skipped_rows=counts["skipped"],
        failed_rows=counts["failed"],
        detail="Import finished.",
    )


def _process_stock_yard_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "stock yard name" not in header or "storage code" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    name_idx = header.index("stock yard name")
    code_idx = header.index("storage code")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(name_idx, code_idx):
            values.append(None)
        raw_name = values[name_idx]
        raw_code = values[code_idx]
        if (raw_name is None or str(raw_name).strip() == "") and (
            raw_code is None or str(raw_code).strip() == ""
        ):
            continue
        data_rows.append((index, raw_name, raw_code))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Stock Yards?",
    )

    existing_codes = {
        str(code).strip().casefold()
        for code in StockYard.objects.values_list("sap_storage_code", flat=True)
    }
    seen_codes: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            StockYard.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_name, raw_code in data_rows:
        processed += 1
        name = str(raw_name or "").strip()
        sap_storage_code = str(raw_code or "").strip().upper()
        input_data = f"{name} | {sap_storage_code}".strip(" |")

        if not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Stock Yard Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Stock Yard Name must be 150 characters or fewer.",
                )
            )
        elif not sap_storage_code:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Storage Code is required.",
                )
            )
        elif len(sap_storage_code) > 50:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Storage Code must be 50 characters or fewer.",
                )
            )
        else:
            code_key = sap_storage_code.casefold()
            if code_key in seen_codes:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate Storage Code within the Excel file.",
                    )
                )
            elif code_key in existing_codes:
                skipped += 1
                seen_codes.add(code_key)
            else:
                seen_codes.add(code_key)
                existing_codes.add(code_key)
                pending_create.append(
                    StockYard(
                        name=name,
                        sap_storage_code=sap_storage_code,
                        is_active=True,
                    )
                )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_material_group_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "sap material group code" not in header or "group name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    code_idx = header.index("sap material group code")
    name_idx = header.index("group name")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(code_idx, name_idx):
            values.append(None)
        raw_code = values[code_idx]
        raw_name = values[name_idx]
        if (raw_code is None or str(raw_code).strip() == "") and (
            raw_name is None or str(raw_name).strip() == ""
        ):
            continue
        data_rows.append((index, raw_code, raw_name))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Material Groups?",
    )

    existing_codes = {
        str(code).strip().casefold()
        for code in MaterialGroup.objects.values_list("sap_material_group_code", flat=True)
    }
    existing_names = {
        str(name).strip().casefold()
        for name in MaterialGroup.objects.values_list("name", flat=True)
    }
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            MaterialGroup.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_code, raw_name in data_rows:
        processed += 1
        sap_code = as_sap_text_code(raw_code)
        name = str(raw_name or "").strip()
        input_data = f"{sap_code} | {name}".strip(" |")

        if not sap_code:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="SAP Material Group Code is required.",
                )
            )
        elif len(sap_code) > 50:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="SAP Material Group Code must be 50 characters or fewer.",
                )
            )
        elif not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Group Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Group Name must be 150 characters or fewer.",
                )
            )
        else:
            code_key = sap_code.casefold()
            name_key = name.casefold()
            if code_key in seen_codes:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate SAP Material Group Code within the Excel file.",
                    )
                )
            elif name_key in seen_names:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate Group Name within the Excel file.",
                    )
                )
            elif code_key in existing_codes or name_key in existing_names:
                skipped += 1
                seen_codes.add(code_key)
                seen_names.add(name_key)
            else:
                seen_codes.add(code_key)
                seen_names.add(name_key)
                existing_codes.add(code_key)
                existing_names.add(name_key)
                pending_create.append(
                    MaterialGroup(
                        sap_material_group_code=sap_code,
                        name=name,
                        is_active=True,
                    )
                )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_purchasing_group_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "sap purchase group code" not in header or "purchase group name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    code_idx = header.index("sap purchase group code")
    name_idx = header.index("purchase group name")
    remarks_idx = header.index("remarks") if "remarks" in header else None

    data_rows: list[tuple[int, object, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        max_idx = max(code_idx, name_idx, remarks_idx if remarks_idx is not None else 0)
        while len(values) <= max_idx:
            values.append(None)
        raw_code = values[code_idx]
        raw_name = values[name_idx]
        raw_remarks = values[remarks_idx] if remarks_idx is not None else None
        if (raw_code is None or str(raw_code).strip() == "") and (
            raw_name is None or str(raw_name).strip() == ""
        ):
            continue
        data_rows.append((index, raw_code, raw_name, raw_remarks))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Purchasing Groups?",
    )

    existing_codes = {
        str(code).strip().casefold()
        for code in PurchasingGroup.objects.values_list("sap_purchase_group_code", flat=True)
    }
    existing_names = {
        str(name).strip().casefold()
        for name in PurchasingGroup.objects.values_list("name", flat=True)
    }
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            PurchasingGroup.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_code, raw_name, raw_remarks in data_rows:
        processed += 1
        sap_code = as_sap_text_code(raw_code)
        name = str(raw_name or "").strip()
        remarks = str(raw_remarks or "").strip()
        input_data = f"{sap_code} | {name} | {remarks}".strip(" |")

        if not sap_code:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="SAP Purchase Group Code is required.",
                )
            )
        elif len(sap_code) > 50:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="SAP Purchase Group Code must be 50 characters or fewer.",
                )
            )
        elif not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Purchase Group Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Purchase Group Name must be 150 characters or fewer.",
                )
            )
        elif len(remarks) > 255:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Remarks must be 255 characters or fewer.",
                )
            )
        else:
            code_key = sap_code.casefold()
            name_key = name.casefold()
            if code_key in seen_codes:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate SAP Purchase Group Code within the Excel file.",
                    )
                )
            elif name_key in seen_names:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate Purchase Group Name within the Excel file.",
                    )
                )
            elif code_key in existing_codes or name_key in existing_names:
                skipped += 1
                seen_codes.add(code_key)
                seen_names.add(name_key)
            else:
                seen_codes.add(code_key)
                seen_names.add(name_key)
                existing_codes.add(code_key)
                existing_names.add(name_key)
                pending_create.append(
                    PurchasingGroup(
                        sap_purchase_group_code=sap_code,
                        name=name,
                        remarks=remarks,
                        is_active=True,
                    )
                )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_plant_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "sap plant code" not in header or "plant name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    code_idx = header.index("sap plant code")
    name_idx = header.index("plant name")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(code_idx, name_idx):
            values.append(None)
        raw_code = values[code_idx]
        raw_name = values[name_idx]
        if (raw_code is None or str(raw_code).strip() == "") and (
            raw_name is None or str(raw_name).strip() == ""
        ):
            continue
        data_rows.append((index, raw_code, raw_name))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Plants?",
    )

    existing_codes = {
        str(code).strip().casefold()
        for code in Plant.objects.values_list("sap_plant_code", flat=True)
    }
    existing_names = {
        str(name).strip().casefold()
        for name in Plant.objects.values_list("name", flat=True)
    }
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            Plant.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_code, raw_name in data_rows:
        processed += 1
        sap_code = as_sap_text_code(raw_code)
        name = str(raw_name or "").strip()
        input_data = f"{sap_code} | {name}".strip(" |")

        if not sap_code:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="SAP Plant Code is required.",
                )
            )
        elif len(sap_code) > 50:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="SAP Plant Code must be 50 characters or fewer.",
                )
            )
        elif not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Plant Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Plant Name must be 150 characters or fewer.",
                )
            )
        else:
            code_key = sap_code.casefold()
            name_key = name.casefold()
            if code_key in seen_codes:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate SAP Plant Code within the Excel file.",
                    )
                )
            elif name_key in seen_names:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate Plant Name within the Excel file.",
                    )
                )
            elif code_key in existing_codes or name_key in existing_names:
                skipped += 1
                seen_codes.add(code_key)
                seen_names.add(name_key)
            else:
                seen_codes.add(code_key)
                seen_names.add(name_key)
                existing_codes.add(code_key)
                existing_names.add(name_key)
                pending_create.append(
                    Plant(sap_plant_code=sap_code, name=name, is_active=True)
                )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_material_type_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "material type code" not in header or "erp category desc" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    code_idx = header.index("material type code")
    desc_idx = header.index("erp category desc")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(code_idx, desc_idx):
            values.append(None)
        raw_code = values[code_idx]
        raw_desc = values[desc_idx]
        if (raw_code is None or str(raw_code).strip() == "") and (
            raw_desc is None or str(raw_desc).strip() == ""
        ):
            continue
        data_rows.append((index, raw_code, raw_desc))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Material Types?",
    )

    existing_codes = {
        str(code).strip().casefold()
        for code in MaterialType.objects.values_list("material_type_code", flat=True)
    }
    seen_codes: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            MaterialType.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_code, raw_desc in data_rows:
        processed += 1
        code = as_sap_text_code(raw_code)
        desc = str(raw_desc or "").strip()
        input_data = f"{code} | {desc}".strip(" |")

        if not code:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Material Type Code is required.",
                )
            )
        elif len(code) > 50:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Material Type Code must be 50 characters or fewer.",
                )
            )
        elif not desc:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="ERP Category Desc is required.",
                )
            )
        elif len(desc) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="ERP Category Desc must be 150 characters or fewer.",
                )
            )
        else:
            code_key = code.casefold()
            if code_key in seen_codes:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Duplicate Material Type Code within the Excel file.",
                    )
                )
            elif code_key in existing_codes:
                skipped += 1
                seen_codes.add(code_key)
            else:
                seen_codes.add(code_key)
                existing_codes.add(code_key)
                pending_create.append(
                    MaterialType(
                        material_type_code=code,
                        erp_category_desc=desc,
                        is_active=True,
                    )
                )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_material_subcategory_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "subcategory name" not in header or "category name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    name_idx = header.index("subcategory name")
    cat_idx = header.index("category name")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(name_idx, cat_idx):
            values.append(None)
        raw_name = values[name_idx]
        raw_cat = values[cat_idx]
        if (raw_name is None or str(raw_name).strip() == "") and (
            raw_cat is None or str(raw_cat).strip() == ""
        ):
            continue
        data_rows.append((index, raw_name, raw_cat))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing material subcategories?",
    )

    categories = {
        str(name).strip().casefold(): pk
        for pk, name in MaterialCategory.objects.values_list("id", "name")
    }
    existing = {
        (str(name).strip().casefold(), category_id)
        for name, category_id in MaterialSubcategory.objects.values_list("name", "category_id")
    }
    seen_in_file: set[tuple[str, int]] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            MaterialSubcategory.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    for row_number, raw_name, raw_cat in data_rows:
        processed += 1
        name = str(raw_name or "").strip()
        category_name = str(raw_cat or "").strip()
        input_data = f"{name} | {category_name}".strip(" |")

        if not name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Subcategory Name is required.",
                )
            )
        elif len(name) > 150:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Subcategory Name must be 150 characters or fewer.",
                )
            )
        elif not category_name:
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason="Category Name is required.",
                )
            )
        else:
            category_id = categories.get(category_name.casefold())
            if category_id is None:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason=(
                            f'Category "{category_name}" does not exist in Material Category Master.'
                        ),
                    )
                )
            else:
                key = (name.casefold(), category_id)
                if key in seen_in_file:
                    failed += 1
                    error_buffer.append(
                        ImportJobError(
                            job=job,
                            row_number=row_number,
                            input_data=input_data,
                            reason="Duplicate Subcategory Name within the Excel file for this Category.",
                        )
                    )
                elif key in existing:
                    skipped += 1
                    seen_in_file.add(key)
                else:
                    seen_in_file.add(key)
                    existing.add(key)
                    pending_create.append(
                        MaterialSubcategory(
                            name=name,
                            category_id=category_id,
                            is_active=True,
                        )
                    )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_unit_job(job: ImportJob) -> None:
    workbook = load_workbook(job.source_file.path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty.")

    header = [_normalize_header(cell) for cell in (rows[0] or ())]
    if "unit name" not in header or "company name" not in header:
        raise ValueError(INVALID_TEMPLATE_MESSAGE)

    name_idx = header.index("unit name")
    company_idx = header.index("company name")

    data_rows: list[tuple[int, object, object]] = []
    for index, row in enumerate(rows[1:], start=2):
        values = list(row or ())
        while len(values) <= max(name_idx, company_idx):
            values.append(None)
        raw_name = values[name_idx]
        raw_company = values[company_idx]
        if (raw_name is None or str(raw_name).strip() == "") and (
            raw_company is None or str(raw_company).strip() == ""
        ):
            continue
        data_rows.append((index, raw_name, raw_company))

    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing units...",
    )

    companies = {
        str(name).strip().casefold(): pk
        for pk, name in Company.objects.values_list("id", "name")
    }
    existing = {
        (str(name).strip().casefold(), company_id)
        for name, company_id in Unit.objects.values_list("name", "company_id")
    }
    seen_in_file: set[tuple[str, int]] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            Unit.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []

    def reject(row_number: int, input_data: str, reason: str) -> None:
        nonlocal failed
        failed += 1
        error_buffer.append(
            ImportJobError(
                job=job,
                row_number=row_number,
                input_data=input_data,
                reason=reason,
            )
        )

    for row_number, raw_name, raw_company in data_rows:
        processed += 1
        name = str(raw_name or "").strip()
        company_name = str(raw_company or "").strip()
        input_data = f"{name} | {company_name}".strip(" |")

        if not name:
            reject(row_number, input_data, "Unit Name is required.")
        elif len(name) > 150:
            reject(row_number, input_data, "Unit Name must be 150 characters or fewer.")
        elif not company_name:
            reject(row_number, input_data, "Company Name is required.")
        else:
            company_id = companies.get(company_name.casefold())
            if company_id is None:
                reject(
                    row_number,
                    input_data,
                    f'Company "{company_name}" does not exist in Company Master.',
                )
            else:
                key = (name.casefold(), company_id)
                if key in seen_in_file:
                    reject(
                        row_number,
                        input_data,
                        "Duplicate Unit Name within the Excel file for this Company.",
                    )
                elif key in existing:
                    skipped += 1
                    seen_in_file.add(key)
                else:
                    seen_in_file.add(key)
                    existing.add(key)
                    pending_create.append(
                        Unit(name=name, company_id=company_id, is_active=True)
                    )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        detail="Import finished.",
    )


def _process_material_job(job: ImportJob) -> None:
    data_rows = list(iter_material_excel_rows(job.source_file.path))
    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        detail="Processing Materials...",
    )

    lookups = MaterialLookupMaps()
    seen_sap: set[str] = set()
    pending_create: list = []
    error_buffer: list[ImportJobError] = []

    created = 0
    skipped = 0
    failed = 0
    warnings = 0
    processed = 0
    pending_warnings: list[ImportJobError] = []

    def flush_creates() -> None:
        nonlocal created, pending_create
        if not pending_create:
            return
        with transaction.atomic():
            Material.objects.bulk_create(pending_create, batch_size=BATCH_SIZE)
        created += len(pending_create)
        pending_create = []
        error_buffer.extend(pending_warnings)
        pending_warnings.clear()

    for row_number, data in data_rows:
        processed += 1
        input_data = row_payload_for_error(data)
        try:
            resolved, error, skip, warning = resolve_material_row(
                data, lookups, seen_sap=seen_sap
            )
            if error:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason=error,
                    )
                )
            elif skip:
                skipped += 1
                seen_sap.add(data["sap code"].casefold())
            elif resolved is not None:
                seen_sap.add(data["sap code"].casefold())
                lookups.existing_sap_codes.add(data["sap code"].casefold())
                pending_create.append(Material(**resolved))
                if warning:
                    warnings += 1
                    pending_warnings.append(
                        ImportJobError(
                            job=job,
                            row_number=row_number,
                            input_data=input_data,
                            reason=warning,
                            is_warning=True,
                        )
                    )
            else:
                failed += 1
                error_buffer.append(
                    ImportJobError(
                        job=job,
                        row_number=row_number,
                        input_data=input_data,
                        reason="Unable to resolve Material row.",
                    )
                )
        except Exception as exc:
            logger.exception(
                "Material import job %s row %s failed unexpectedly", job.pk, row_number
            )
            failed += 1
            error_buffer.append(
                ImportJobError(
                    job=job,
                    row_number=row_number,
                    input_data=input_data,
                    reason=f"Unexpected error: {exc}",
                )
            )

        if len(pending_create) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending_create),
                skipped_rows=skipped,
                failed_rows=failed,
                warning_rows=warnings,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    detail = "Import finished."
    if warnings:
        detail = f"Import finished with {warnings:,} image URL warning(s)."
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        warning_rows=warnings,
        detail=detail,
    )


def _process_employee_job(job: ImportJob) -> None:
    """Create valid Employees; Possible Duplicates are held back as warning rows, not created."""
    data_rows = list(iter_employee_excel_rows(job.source_file.path))
    total = len(data_rows)
    _save_job(
        job,
        status=ImportJob.Status.PROCESSING,
        total_rows=total,
        processed_rows=0,
        created_rows=0,
        skipped_rows=0,
        failed_rows=0,
        warning_rows=0,
        detail="Processing Employees...",
    )

    lookups = EmployeeLookupMaps()
    user = job.uploaded_by
    pending: list[tuple[int, str, Employee]] = []
    error_buffer: list[ImportJobError] = []
    created = skipped = failed = possible = processed = 0

    def row_error(row_number: int, input_data: str, reason: str, *, warning=False):
        return ImportJobError(
            job=job,
            row_number=row_number,
            input_data=input_data,
            reason=reason,
            is_warning=warning,
        )

    def flush_creates() -> None:
        nonlocal created, failed, pending
        if not pending:
            return
        employees = [employee for _, _, employee in pending]
        for employee, code in zip(employees, next_employee_codes(len(employees)), strict=True):
            employee.employee_code = code
        try:
            with transaction.atomic():
                Employee.objects.bulk_create(employees, batch_size=BATCH_SIZE)
            created += len(employees)
        except IntegrityError:
            # Another user saved a conflicting Mobile Number meanwhile; retry row by row.
            for row_number, input_data, employee in pending:
                employee.pk = None
                try:
                    with transaction.atomic():
                        employee.save()
                    created += 1
                except IntegrityError:
                    failed += 1
                    error_buffer.append(
                        row_error(row_number, input_data, "Mobile Number already exists.")
                    )
        pending = []

    for row_number, data in data_rows:
        processed += 1
        input_data = employee_row_payload(data)
        try:
            resolved, error, skip, possible_reason = resolve_employee_row(
                data, lookups, row_number=row_number
            )
            if error:
                failed += 1
                error_buffer.append(row_error(row_number, input_data, error))
            elif skip:
                skipped += 1
            elif possible_reason:
                possible += 1
                error_buffer.append(
                    row_error(row_number, input_data, possible_reason, warning=True)
                )
            elif resolved is not None:
                pending.append(
                    (
                        row_number,
                        input_data,
                        Employee(**resolved, created_by=user, updated_by=user),
                    )
                )
            else:
                failed += 1
                error_buffer.append(
                    row_error(row_number, input_data, "Unable to resolve Employee row.")
                )
        except Exception as exc:
            logger.exception(
                "Employee import job %s row %s failed unexpectedly", job.pk, row_number
            )
            failed += 1
            error_buffer.append(row_error(row_number, input_data, f"Unexpected error: {exc}"))

        if len(pending) >= BATCH_SIZE:
            flush_creates()
        if len(error_buffer) >= BATCH_SIZE:
            _flush_errors(job, error_buffer)
        if processed % BATCH_SIZE == 0 or processed == total:
            _save_job(
                job,
                processed_rows=processed,
                created_rows=created + len(pending),
                skipped_rows=skipped,
                failed_rows=failed,
                warning_rows=possible,
            )

    flush_creates()
    _flush_errors(job, error_buffer)
    detail = "Import finished."
    if possible:
        detail = f"Import finished. {possible:,} possible duplicate(s) held for review."
    _save_job(
        job,
        processed_rows=processed,
        created_rows=created,
        skipped_rows=skipped,
        failed_rows=failed,
        warning_rows=possible,
        detail=detail,
    )
