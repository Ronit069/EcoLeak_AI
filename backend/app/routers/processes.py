"""Module B1-B5: process endpoints (soft delete only)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.deps import api_rate_limit, require_roles
from app.errors import ConflictError
from app.models.process import Process
from app.routers.common import WRITE_ROLES, audit_ctx
from app.schemas.requests import ProcessCreate, ProcessUpdate
from app.schemas.serialize import process_to_dict
from app.security import Principal, get_current_principal
from app.services import access, audit

router = APIRouter(prefix="/api", tags=["Module B - Process"])


@router.post(
    "/facilities/{facility_id}/processes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_rate_limit)],
)
def create_process(
    facility_id: UUID,
    payload: ProcessCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, facility_id, principal)
    if payload.process_code:
        duplicate = db.scalar(
            select(Process).where(
                Process.facility_id == facility.id,
                Process.process_code == payload.process_code,
            )
        )
        if duplicate is not None:
            raise ConflictError("Duplicate process_code within this facility.")
    name_duplicate = db.scalar(
        select(Process).where(
            Process.facility_id == facility.id,
            Process.name == payload.name,
            Process.deleted_at.is_(None),
        )
    )
    if name_duplicate is not None:
        raise ConflictError("Duplicate process name within this facility.")
    data = payload.model_dump(exclude={"facility_id"})
    process = Process(facility_id=facility.id, **data)
    db.add(process)
    db.flush()
    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="PROCESS_CREATED", entity_type="process", entity_id=process.id,
        new_value={"name": process.name}, **audit_ctx(request),
    )
    db.commit()
    return process_to_dict(process)


@router.get("/facilities/{facility_id}/processes")
def list_processes(
    facility_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    facility = access.get_facility(db, facility_id, principal)
    processes = db.scalars(
        select(Process)
        .where(Process.facility_id == facility.id, Process.deleted_at.is_(None))
        .order_by(Process.sequence_no)
    )
    return [process_to_dict(p) for p in processes]


@router.get("/processes/{process_id}")
def get_process(
    process_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    return process_to_dict(access.get_process(db, process_id, principal))


@router.patch("/processes/{process_id}")
def update_process(
    process_id: UUID,
    payload: ProcessUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    process = access.get_process(db, process_id, principal)
    facility = access.get_facility(db, process.facility_id, principal)
    before = process_to_dict(process)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(process, key, value)
    db.flush()
    after = process_to_dict(process)
    from fastapi.encoders import jsonable_encoder

    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="PROCESS_UPDATED", entity_type="process", entity_id=process.id,
        old_value=jsonable_encoder(before), new_value=jsonable_encoder(after),
        **audit_ctx(request),
    )
    db.commit()
    return after


@router.delete("/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(
    process_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> Response:
    process = access.get_process(db, process_id, principal)
    facility = access.get_facility(db, process.facility_id, principal)
    process.deleted_at = utcnow()
    process.active = False
    db.flush()
    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="PROCESS_SOFT_DELETED", entity_type="process", entity_id=process.id,
        **audit_ctx(request),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
