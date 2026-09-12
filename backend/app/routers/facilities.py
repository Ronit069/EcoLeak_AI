"""Module A4-A9: facility and reporting-period endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import api_rate_limit, require_roles
from app.errors import ConflictError, ForbiddenError
from app.models.core import Facility, ReportingPeriod
from app.routers.common import WRITE_ROLES, audit_ctx
from app.schemas.requests import FacilityCreate, FacilityUpdate, ReportingPeriodCreate
from app.schemas.serialize import facility_to_dict, period_to_dict
from app.security import Principal, get_current_principal
from app.services import access, audit

router = APIRouter(prefix="/api", tags=["Module A - Facility"])


@router.post(
    "/facilities", status_code=status.HTTP_201_CREATED, dependencies=[Depends(api_rate_limit)]
)
def create_facility(
    payload: FacilityCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    organization_id = payload.organization_id or principal.organization_id
    if organization_id is None:
        raise ForbiddenError("No organization resolved for this caller.")
    access.require_org_access(principal, organization_id)

    data = payload.model_dump(exclude={"organization_id"})
    facility = Facility(organization_id=organization_id, **data)
    db.add(facility)
    db.flush()
    audit.record(
        db, principal=principal, organization_id=organization_id,
        event_type="FACILITY_CREATED", entity_type="facility", entity_id=facility.id,
        new_value={"name": facility.name, "facility_code": facility.facility_code},
        **audit_ctx(request),
    )
    db.commit()
    return facility_to_dict(facility)


@router.get("/organizations/{organization_id}/facilities")
def list_facilities(
    organization_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    access.get_organization(db, organization_id, principal)
    facilities = db.scalars(
        select(Facility).where(Facility.organization_id == organization_id)
    )
    return [facility_to_dict(f) for f in facilities]


@router.get("/facilities/{facility_id}")
def get_facility(
    facility_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    return facility_to_dict(access.get_facility(db, facility_id, principal))


@router.patch("/facilities/{facility_id}")
def update_facility(
    facility_id: UUID,
    payload: FacilityUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, facility_id, principal)
    before = facility_to_dict(facility)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(facility, key, value)
    db.flush()
    after = facility_to_dict(facility)
    from fastapi.encoders import jsonable_encoder

    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="FACILITY_UPDATED", entity_type="facility", entity_id=facility.id,
        old_value=jsonable_encoder(before), new_value=jsonable_encoder(after),
        **audit_ctx(request),
    )
    db.commit()
    return after


@router.post(
    "/facilities/{facility_id}/reporting-periods",
    status_code=status.HTTP_201_CREATED,
)
def create_reporting_period(
    facility_id: UUID,
    payload: ReportingPeriodCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, facility_id, principal)
    overlap = db.scalar(
        select(ReportingPeriod).where(
            ReportingPeriod.facility_id == facility.id,
            ReportingPeriod.start_date <= payload.end_date,
            ReportingPeriod.end_date >= payload.start_date,
        )
    )
    if overlap is not None:
        raise ConflictError(
            "Reporting period overlaps an existing period for this facility.",
            details={"existing_period_id": str(overlap.id)},
        )
    data = payload.model_dump(exclude={"facility_id"})
    period = ReportingPeriod(facility_id=facility.id, **data)
    db.add(period)
    db.flush()
    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="REPORTING_PERIOD_CREATED", entity_type="reporting_period",
        entity_id=period.id, new_value={"start_date": str(period.start_date), "end_date": str(period.end_date)},
        **audit_ctx(request),
    )
    db.commit()
    return period_to_dict(period)


@router.get("/facilities/{facility_id}/reporting-periods")
def list_reporting_periods(
    facility_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    facility = access.get_facility(db, facility_id, principal)
    periods = db.scalars(
        select(ReportingPeriod)
        .where(ReportingPeriod.facility_id == facility.id)
        .order_by(ReportingPeriod.start_date.desc())
    )
    return [period_to_dict(p) for p in periods]
