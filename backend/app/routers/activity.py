"""Modules C/D: activity data, import, and data-quality endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.deps import api_rate_limit, require_roles, upload_rate_limit
from app.errors import DuplicateActivityError, NotFoundError
from app.models.activity import ActivityData
from app.models.core import Facility, ReportingPeriod
from app.models.process import Process
from app.routers.common import WRITE_ROLES, audit_ctx, ensure_period_editable
from app.schemas.requests import ActivityCreate, ActivityUpdate
from app.schemas.serialize import activity_to_dict
from app.security import Principal, get_current_principal
from app.services import access, audit, ingestion, quality, units

router = APIRouter(prefix="/api", tags=["Modules C/D - Activity & Quality"])

ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


def _resolve_process(db: Session, facility: Facility, process_id: UUID | None) -> UUID | None:
    if process_id is None:
        return None
    process = db.get(Process, process_id)
    if process is None or process.facility_id != facility.id:
        raise NotFoundError("Process not found for this facility.")
    return process.id


def _duplicate_exists(
    db: Session,
    facility: Facility,
    period: ReportingPeriod,
    payload: ActivityCreate,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    stmt = select(ActivityData).where(
        ActivityData.facility_id == facility.id,
        ActivityData.reporting_period_id == period.id,
        ActivityData.activity_subcategory == payload.activity_subcategory,
        ActivityData.original_value == payload.original_value,
        ActivityData.original_unit == payload.original_unit,
        ActivityData.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(ActivityData.id != exclude_id)
    return db.scalar(stmt) is not None


@router.post(
    "/facilities/{facility_id}/activity",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_rate_limit)],
)
def create_activity(
    facility_id: str,
    payload: ActivityCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, UUID(facility_id), principal)
    period = access.get_period(db, payload.reporting_period_id, principal, facility=facility)
    ensure_period_editable(period)
    process_id = _resolve_process(db, facility, payload.process_id)

    if _duplicate_exists(db, facility, period, payload):
        raise DuplicateActivityError("An identical activity record already exists for this period.")

    original_value = payload.original_value
    original_unit = payload.original_unit
    if payload.normalized_value is not None and payload.normalized_unit:
        normalized_value = payload.normalized_value
        normalized_unit = payload.normalized_unit
    else:
        result = units.normalize(original_value, original_unit)
        normalized_value = result.normalized_value
        normalized_unit = result.normalized_unit

    activity = ActivityData(
        facility_id=facility.id,
        process_id=process_id,
        asset_id=payload.asset_id,
        reporting_period_id=period.id,
        activity_category=payload.activity_category.value,
        activity_subcategory=payload.activity_subcategory,
        source_name=payload.source_name,
        original_value=original_value,
        original_unit=original_unit,
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        data_source_type=payload.data_source_type.value,
        measured_or_estimated=payload.measured_or_estimated.value,
        confidence_score=payload.confidence_score,
        notes=payload.notes,
        created_at=utcnow(),
    )
    db.add(activity)
    db.flush()
    factor = quality.match_factor(db, activity)
    activity.carbon_data_quality_score = quality.score_activity_record(activity, factor)
    db.flush()
    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="ACTIVITY_CREATED", entity_type="activity_data", entity_id=activity.id,
        new_value={
            "activity_category": activity.activity_category,
            "original_value": str(activity.original_value),
            "original_unit": activity.original_unit,
        },
        **audit_ctx(request),
    )
    db.commit()
    return activity_to_dict(activity)


@router.put("/facilities/{facility_id}/activity/{activity_id}")
def update_activity(
    facility_id: str,
    activity_id: str,
    payload: ActivityUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, UUID(facility_id), principal)
    activity = access.get_activity(db, UUID(activity_id), principal)
    if activity.facility_id != facility.id:
        raise NotFoundError("Activity not found for this facility.")
    period = access.get_period(db, activity.reporting_period_id, principal, facility=facility)
    ensure_period_editable(period)
    process_id = _resolve_process(db, facility, payload.process_id)
    before = activity_to_dict(activity)

    if _duplicate_exists(db, facility, period, payload, exclude_id=activity.id):
        raise DuplicateActivityError("An identical activity record already exists for this period.")

    if payload.normalized_value is not None and payload.normalized_unit:
        normalized_value = payload.normalized_value
        normalized_unit = payload.normalized_unit
    else:
        result = units.normalize(payload.original_value, payload.original_unit)
        normalized_value = result.normalized_value
        normalized_unit = result.normalized_unit

    activity.process_id = process_id
    activity.asset_id = payload.asset_id
    activity.activity_category = payload.activity_category.value
    activity.activity_subcategory = payload.activity_subcategory
    activity.source_name = payload.source_name
    activity.original_value = payload.original_value
    activity.original_unit = payload.original_unit
    activity.normalized_value = normalized_value
    activity.normalized_unit = normalized_unit
    activity.data_source_type = payload.data_source_type.value
    activity.measured_or_estimated = payload.measured_or_estimated.value
    activity.confidence_score = payload.confidence_score
    activity.notes = payload.notes
    db.flush()
    factor = quality.match_factor(db, activity)
    activity.carbon_data_quality_score = quality.score_activity_record(activity, factor)
    db.flush()
    after = activity_to_dict(activity)
    from fastapi.encoders import jsonable_encoder

    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="ACTIVITY_UPDATED", entity_type="activity_data", entity_id=activity.id,
        old_value=jsonable_encoder(before), new_value=jsonable_encoder(after),
        **audit_ctx(request),
    )
    db.commit()
    return after


@router.get("/facilities/{facility_id}/activity")
def list_activity(
    facility_id: str,
    reporting_period_id: UUID | None = None,
    process_id: UUID | None = None,
    activity_category: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    facility = access.get_facility(db, UUID(facility_id), principal)
    stmt = select(ActivityData).where(
        ActivityData.facility_id == facility.id, ActivityData.deleted_at.is_(None)
    )
    if reporting_period_id:
        stmt = stmt.where(ActivityData.reporting_period_id == reporting_period_id)
    if process_id:
        stmt = stmt.where(ActivityData.process_id == process_id)
    if activity_category:
        stmt = stmt.where(ActivityData.activity_category == activity_category)
    activities = db.scalars(stmt.order_by(ActivityData.created_at))
    return [activity_to_dict(a) for a in activities]


@router.post(
    "/facilities/{facility_id}/activity/import",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(upload_rate_limit)],
)
def import_activity_file(
    facility_id: str,
    request: Request,
    file: UploadFile = File(...),
    reporting_period_id: UUID = Form(...),
    sheet: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, UUID(facility_id), principal)
    period = access.get_period(db, reporting_period_id, principal, facility=facility)
    ensure_period_editable(period)

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        from app.errors import FileValidationError

        raise FileValidationError(
            "Unsupported upload MIME type.",
            details={"content_type": file.content_type},
        )
    content = file.file.read()
    batch = ingestion.import_activity(
        db,
        facility=facility,
        period=period,
        content=content,
        filename=file.filename or "upload",
        sheet_name=sheet,
        principal=principal,
        dry_run=dry_run,
        **audit_ctx(request),
    )
    return ingestion.batch_to_job(batch, db)


@router.get("/ingestion/batches/{import_id}")
def get_import_batch(
    import_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    from app.models.ingestion import IngestionBatch

    batch = db.scalar(select(IngestionBatch).where(IngestionBatch.import_id == import_id))
    if batch is None:
        raise NotFoundError("Import job not found.")
    if not principal.is_global and principal.organization_id != batch.organization_id:
        raise NotFoundError("Import job not found.")
    return ingestion.batch_to_job(batch, db)


@router.get("/facilities/{facility_id}/reporting-periods/{period_id}/data-quality")
def get_data_quality(
    facility_id: str,
    period_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    facility = access.get_facility(db, UUID(facility_id), principal)
    period = access.get_period(db, UUID(period_id), principal, facility=facility)
    assessment = quality.assess_period(db, facility, period, persist=True)
    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="DATA_QUALITY_ASSESSED", entity_type="reporting_period",
        entity_id=period.id, new_value={"total_score": str(assessment.total_score)},
        **audit_ctx(request),
    )
    db.commit()
    return quality.assessment_to_dict(assessment)
