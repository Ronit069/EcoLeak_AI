"""Module C/D - CSV/Excel ingestion engine.

Pipeline (Library doc section 35):
    upload -> file allow-list -> parse (pandas/openpyxl) -> header validation
    -> Pandera schema/range validation -> row business rules
    -> Pint normalization -> duplicate/magnitude checks -> transactional insert.

Edge cases handled (DB doc section 21 Module C/D):
    negative values (ERROR), missing units (ERROR), duplicates (ERROR),
    reporting-period mismatch (ERROR), implausible magnitude (WARNING, imported),
    ambiguous units (CONFIRMATION_REQUIRED, not imported), mixed units per row.
"""
from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import pandas as pd
import pandera.pandas as pa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.errors import (
    ConfirmationRequiredError,
    FileValidationError,
    InvalidUnitError,
    PlatformError,
)
from app.models.activity import ActivityData
from app.models.core import Facility, ReportingPeriod
from app.models.ingestion import IngestionBatch, IngestionError
from app.models.process import Process
from app.services import audit, units
from app.security import Principal

REQUIRED_HEADERS = ["activity_category", "activity_subcategory", "original_value", "original_unit"]

HEADER_ALIASES: dict[str, list[str]] = {
    "activity_category": ["activity_category", "category", "activity type"],
    "activity_subcategory": ["activity_subcategory", "subcategory", "item", "description"],
    "original_value": ["original_value", "value", "quantity", "amount", "consumption"],
    "original_unit": ["original_unit", "unit", "uom"],
    "source_name": ["source_name", "source"],
    "process_code": ["process_code", "process"],
    "data_source_type": ["data_source_type", "source_type"],
    "measured_or_estimated": ["measured_or_estimated", "measurement"],
    "confidence_score": ["confidence_score", "confidence"],
    "notes": ["notes", "comment"],
    "reporting_period_id": ["reporting_period_id", "period_id"],
}

# Absolute plausibility ceilings (per reporting period). Exceeding => WARNING only.
MAGNITUDE_LIMITS = {
    "ELECTRICITY": Decimal("50000000"),   # kWh
    "FUEL": Decimal("5000000"),           # L / m3 / kg
    "MATERIAL": Decimal("50000000"),      # kg
    "WATER": Decimal("10000000"),         # m3
    "WASTE": Decimal("50000000"),         # kg / m3
    "TRANSPORT": Decimal("100000000"),    # tonne_km
    "REFRIGERANT": Decimal("100000"),     # kg
    "STEAM": Decimal("50000000"),
    "OTHER": Decimal("50000000"),
}
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


@dataclass
class RowIssue:
    row_number: int
    severity: str
    code: str
    message: str
    field: Optional[str] = None
    raw_row: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "details": {"row_number": self.row_number, "raw_row": self.raw_row},
        }


@dataclass
class ImportReport:
    status: str
    total_rows: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    warning_rows: int = 0
    issues: list[RowIssue] = field(default_factory=list)
    accepted: list[ActivityData] = field(default_factory=list)


def _sanitize_filename(filename: str) -> str:
    name = (filename or "upload").replace("\\", "/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:255]


def _clean_header(value: str) -> str:
    return str(value).lstrip("\ufeff").strip().lower().replace(" ", "_").replace("-", "_")


def _parse_number(value: Any) -> Optional[Decimal]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip()
    if text == "":
        return None
    cleaned = re.sub(r"[^0-9eE+\-.]", "", text)
    if cleaned in {"", "-", "+", ".", "-.", "+."}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_file(content: bytes, filename: str, sheet_name: str | None = None) -> tuple[pd.DataFrame, str]:
    settings = get_settings()
    if not content:
        raise FileValidationError("Empty file uploaded.")
    if len(content) > settings.max_upload_bytes:
        raise FileValidationError(
            "File exceeds the maximum allowed size.",
            details={"max_bytes": settings.max_upload_bytes},
        )
    safe_name = _sanitize_filename(filename)
    suffix = ("." + safe_name.rsplit(".", 1)[-1].lower()) if "." in safe_name else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            "Unsupported file type. Only .csv and .xlsx are allowed.",
            details={"extension": suffix},
        )
    try:
        if suffix == ".csv":
            frame = pd.read_csv(io.BytesIO(content))
            file_type = "CSV"
        else:
            frame = pd.read_excel(
                io.BytesIO(content), engine="openpyxl", sheet_name=sheet_name or 0
            )
            file_type = "EXCEL"
    except Exception as exc:
        raise FileValidationError(
            "Corrupt, password-protected or unreadable file.",
            details={"reason": type(exc).__name__},
        ) from exc

    if frame.empty:
        raise FileValidationError("File contains no data rows.")
    if len(frame) > settings.max_import_rows:
        raise FileValidationError(
            "File exceeds the maximum row limit.",
            details={"max_rows": settings.max_import_rows, "rows": len(frame)},
        )
    frame.columns = [_clean_header(c) for c in frame.columns]
    return frame, file_type


def map_headers(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    rename: dict[str, str] = {}
    for column in frame.columns:
        for canonical, aliases in HEADER_ALIASES.items():
            if column == canonical or column in [a.replace(" ", "_") for a in aliases]:
                rename[column] = canonical
                break
    mapped = frame.rename(columns=rename)
    missing = [h for h in REQUIRED_HEADERS if h not in mapped.columns]
    if missing:
        raise FileValidationError(
            "CSV/Excel is missing mandatory columns.",
            details={"missing_columns": missing, "required": REQUIRED_HEADERS},
        )
    return mapped, rename


def _pandera_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "activity_category": pa.Column(str, nullable=False),
            "activity_subcategory": pa.Column(str, nullable=False),
            "original_value": pa.Column(float, pa.Check.ge(0), nullable=False, coerce=True),
            "original_unit": pa.Column(str, nullable=False),
            "confidence_score": pa.Column(
                float, pa.Check.in_range(0, 100), nullable=True, required=False, coerce=True
            ),
        },
        strict=False,
        coerce=True,
    )


def run_pandera(frame: pd.DataFrame) -> list[RowIssue]:
    issues: list[RowIssue] = []
    try:
        _pandera_schema().validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        cases = exc.failure_cases
        for _, row in cases.iterrows():
            index = row.get("index")
            row_number = int(index) + 2 if pd.notna(index) else 0
            column = row.get("column")
            check = str(row.get("check") or "")
            severity = "ERROR"
            code = "SCHEMA_VALIDATION"
            if "ge(0)" in check or "greater_than_or_equal" in check:
                code = "NEGATIVE_VALUE"
                message = "Negative values are not allowed."
            elif "in_range" in check or "less_than_or_equal" in check:
                code = "CONFIDENCE_RANGE"
                message = "confidence_score must be between 0 and 100."
            elif "not_nullable" in check:
                code = "MISSING_VALUE"
                message = f"Missing required value for '{column}'."
            else:
                message = f"Validation failed for '{column}'."
            issues.append(
                RowIssue(
                    row_number=row_number,
                    severity=severity,
                    code=code,
                    message=message,
                    field=str(column) if column is not None else None,
                )
            )
    return issues


def _row_hash(payload: dict[str, Any]) -> str:
    canonical = "|".join(
        str(payload.get(k, ""))
        for k in ("activity_category", "activity_subcategory", "original_value", "original_unit", "process_code")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_and_build(
    db: Session,
    frame: pd.DataFrame,
    *,
    facility: Facility,
    period: ReportingPeriod,
    process_by_code: dict[str, uuid.UUID],
) -> ImportReport:
    report = ImportReport(status="COMPLETED", total_rows=len(frame))
    report.issues.extend(run_pandera(frame))

    # Index issues by row so business rules can skip invalid rows.
    blocked_rows = {
        issue.row_number
        for issue in report.issues
        if issue.severity == "ERROR" and issue.row_number
    }
    seen_in_file: dict[str, int] = {}

    for position, (_, row) in enumerate(frame.iterrows()):
        row_number = position + 2
        raw = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}

        if row_number in blocked_rows:
            report.rejected_rows += 1
            continue

        process_code = str(row.get("process_code") or "").strip()
        payload = {
            "activity_category": str(row["activity_category"]).strip().upper(),
            "activity_subcategory": str(row["activity_subcategory"]).strip(),
            "original_value": _parse_number(row.get("original_value")),
            "original_unit": str(row.get("original_unit")).strip(),
            "process_code": process_code,
        }

        # Reporting-period mismatch (optional period column in the upload).
        if "reporting_period_id" in row and pd.notna(row.get("reporting_period_id")):
            if str(row.get("reporting_period_id")).strip() != str(period.id):
                report.issues.append(
                    RowIssue(row_number, "ERROR", "PERIOD_MISMATCH",
                             "Row reporting period does not match the target period.",
                             "reporting_period_id", raw)
                )
                report.rejected_rows += 1
                continue

        # Duplicate within the uploaded file.
        row_key = _row_hash(payload)
        if row_key in seen_in_file:
            report.issues.append(
                RowIssue(row_number, "ERROR", "DUPLICATE_IN_FILE",
                         f"Duplicate of row {seen_in_file[row_key]} in the same file.",
                         None, raw)
            )
            report.rejected_rows += 1
            continue
        seen_in_file[row_key] = row_number

        # Duplicate against stored activity.
        existing = db.scalar(
            select(ActivityData).where(
                ActivityData.facility_id == facility.id,
                ActivityData.reporting_period_id == period.id,
                ActivityData.activity_subcategory == payload["activity_subcategory"],
                ActivityData.original_value == payload["original_value"],
                ActivityData.original_unit == payload["original_unit"],
                ActivityData.deleted_at.is_(None),
            )
        )
        if existing is not None:
            report.issues.append(
                RowIssue(row_number, "ERROR", "DUPLICATE_ACTIVITY",
                         "An identical activity record already exists for this period.",
                         None, raw)
            )
            report.rejected_rows += 1
            continue

        # Unit normalization (Module D).
        try:
            normalization = units.normalize(payload["original_value"], payload["original_unit"])
        except ConfirmationRequiredError as exc:
            report.issues.append(
                RowIssue(row_number, "CONFIRMATION_REQUIRED", "AMBIGUOUS_UNIT",
                         exc.message, "original_unit", raw)
            )
            report.rejected_rows += 1
            continue
        except InvalidUnitError as exc:
            report.issues.append(
                RowIssue(row_number, "ERROR", "INVALID_UNIT", exc.message, "original_unit", raw)
            )
            report.rejected_rows += 1
            continue

        process_id = process_by_code.get(process_code) if process_code else None
        if process_code and process_id is None:
            report.issues.append(
                RowIssue(row_number, "WARNING", "UNKNOWN_PROCESS_CODE",
                         f"Process code '{process_code}' not found in this facility; "
                         "record stored without a process link.", "process_code", raw)
            )

        normalized_value = normalization.normalized_value
        measured = str(row.get("measured_or_estimated") or "MEASURED").strip().upper()
        if measured not in {"MEASURED", "ESTIMATED"}:
            measured = "MEASURED"
        source_type = str(row.get("data_source_type") or "").strip().upper() or "CSV"
        if source_type not in {"MANUAL", "CSV", "EXCEL", "API", "SENSOR", "OCR"}:
            source_type = "CSV"
        confidence = _parse_number(row.get("confidence_score"))

        # Implausible magnitude => WARNING only (never silently modified/rejected).
        limit = MAGNITUDE_LIMITS.get(payload["activity_category"])
        if normalized_value is not None and limit is not None and normalized_value > limit:
            report.issues.append(
                RowIssue(row_number, "WARNING", "IMPLAUSIBLE_MAGNITUDE",
                         f"Value {normalized_value} exceeds the plausibility ceiling "
                         f"{limit} for {payload['activity_category']}; imported with warning.",
                         "original_value", raw)
            )
            report.warning_rows += 1
        if payload["original_unit"] in {"kg", "g"} and limit is not None and normalized_value and normalized_value > limit:
            report.issues.append(
                RowIssue(row_number, "WARNING", "UNIT_MAGNITUDE_ANOMALY",
                         "Possible tonne-vs-kg data-entry error; please confirm.", "original_unit", raw)
            )

        activity = ActivityData(
            id=uuid.uuid4(),
            facility_id=facility.id,
            process_id=process_id,
            asset_id=None,
            reporting_period_id=period.id,
            activity_category=payload["activity_category"],
            activity_subcategory=payload["activity_subcategory"],
            source_name=(str(row.get("source_name")).strip() if pd.notna(row.get("source_name")) else None),
            original_value=normalization.original_value,
            original_unit=normalization.original_unit,
            normalized_value=normalization.normalized_value,
            normalized_unit=normalization.normalized_unit,
            data_source_type=source_type,
            measured_or_estimated=measured,
            confidence_score=confidence,
            notes=(str(row.get("notes")).strip() if pd.notna(row.get("notes")) else None),
            source_row_hash=row_key,
            created_at=utcnow(),
        )
        report.accepted.append(activity)
        report.accepted_rows += 1

    if report.accepted_rows == 0 and report.rejected_rows > 0:
        report.status = "FAILED"
    elif report.rejected_rows > 0 or report.warning_rows > 0:
        report.status = "PARTIAL"
    return report


def import_activity(
    db: Session,
    *,
    facility: Facility,
    period: ReportingPeriod,
    content: bytes,
    filename: str,
    sheet_name: str | None,
    principal: Principal,
    ip: str | None = None,
    user_agent: str | None = None,
    dry_run: bool = False,
) -> IngestionBatch:
    safe_name = _sanitize_filename(filename)
    file_hash = hashlib.sha256(content).hexdigest()

    duplicate = db.scalar(
        select(IngestionBatch).where(
            IngestionBatch.facility_id == facility.id,
            IngestionBatch.reporting_period_id == period.id,
            IngestionBatch.file_hash == file_hash,
            IngestionBatch.status.in_(("COMPLETED", "PARTIAL")),
        )
    )
    if duplicate is not None and not dry_run:
        from app.errors import DuplicateImportError

        raise DuplicateImportError(
            "This file was already imported for this facility and period.",
            details={"existing_import_id": duplicate.import_id},
        )

    batch = IngestionBatch(
        id=uuid.uuid4(),
        facility_id=facility.id,
        reporting_period_id=period.id,
        organization_id=facility.organization_id,
        import_id=uuid.uuid4().hex,
        filename=safe_name,
        file_hash=file_hash,
        sheet_name=sheet_name,
        status="PROCESSING",
        created_by=principal.actor_id,
        created_at=utcnow(),
    )
    db.add(batch)
    db.flush()

    try:
        frame, file_type = parse_file(content, safe_name, sheet_name)
        frame, _ = map_headers(frame)
    except PlatformError as exc:
        batch.status = "FAILED"
        db.add(
            IngestionError(
                batch_id=batch.id,
                row_number=None,
                severity=exc.severity,
                code=exc.error_code,
                message=exc.message[:500],
                raw_row=exc.details,
                created_at=utcnow(),
            )
        )
        audit.record(
            db, principal=principal, organization_id=facility.organization_id,
            event_type="FILE_IMPORT_FAILED", entity_type="ingestion_batch",
            entity_id=batch.id, new_value={"filename": safe_name, "error": exc.error_code},
            ip=ip, user_agent=user_agent,
        )
        db.commit()
        return batch

    batch.file_type = file_type
    process_by_code = {
        p.process_code: p.id
        for p in db.scalars(select(Process).where(Process.facility_id == facility.id))
        if p.process_code
    }

    report = validate_and_build(
        db, frame, facility=facility, period=period, process_by_code=process_by_code
    )

    batch.total_rows = report.total_rows
    batch.accepted_rows = report.accepted_rows
    batch.rejected_rows = report.rejected_rows
    batch.warning_rows = report.warning_rows

    for activity in report.accepted:
        if not dry_run:
            db.add(activity)

    if dry_run:
        batch.status = "DRY_RUN"
    else:
        batch.status = report.status

    for issue in report.issues:
        db.add(
            IngestionError(
                batch_id=batch.id,
                row_number=issue.row_number,
                severity=issue.severity,
                code=issue.code,
                message=issue.message[:500],
                field=issue.field,
                raw_row=issue.raw_row,
                created_at=utcnow(),
            )
        )

    if not dry_run:
        db.flush()
        from app.services import quality

        for activity in report.accepted:
            factor = quality.match_factor(db, activity)
            activity.carbon_data_quality_score = quality.score_activity_record(activity, factor)

    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="FILE_IMPORT", entity_type="ingestion_batch", entity_id=batch.id,
        new_value={
            "filename": safe_name,
            "file_type": file_type,
            "status": batch.status,
            "accepted_rows": batch.accepted_rows,
            "rejected_rows": batch.rejected_rows,
            "warning_rows": batch.warning_rows,
        },
        ip=ip, user_agent=user_agent,
    )
    db.commit()
    return batch


def batch_to_job(batch: IngestionBatch, db: Session) -> dict:
    issues = list(
        db.scalars(
            select(IngestionError).where(IngestionError.batch_id == batch.id).order_by(
                IngestionError.row_number
            )
        )
    )
    return {
        "import_id": batch.import_id,
        "status": batch.status,
        "row_issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "field": issue.field,
                "details": {"row_number": issue.row_number, "raw_row": issue.raw_row},
            }
            for issue in issues
        ],
    }
