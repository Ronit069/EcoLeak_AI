"""Module I1-I3: circular intervention knowledge base endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import api_rate_limit, require_roles
from app.errors import ConflictError, NotFoundError
from app.models.intervention import CircularIntervention
from app.routers.common import ADMIN_ROLES, audit_ctx
from app.schemas.requests import CircularInterventionCreate
from app.schemas.serialize import intervention_to_dict
from app.security import Principal, get_current_principal
from app.services import audit

router = APIRouter(prefix="/api", tags=["Module I - Interventions"])


@router.get("/interventions")
def list_interventions(
    industry_sector: str | None = None,
    process_category: str | None = None,
    complexity: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    stmt = select(CircularIntervention)
    if industry_sector:
        stmt = stmt.where(CircularIntervention.industry_sector == industry_sector)
    if process_category:
        stmt = stmt.where(CircularIntervention.process_category == process_category)
    if complexity:
        stmt = stmt.where(CircularIntervention.complexity == complexity)
    if active is not None:
        stmt = stmt.where(CircularIntervention.active.is_(active))
    return [intervention_to_dict(i) for i in db.scalars(stmt)]


@router.get("/interventions/{intervention_id}")
def get_intervention(
    intervention_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    intervention = db.get(CircularIntervention, UUID(intervention_id))
    if intervention is None:
        raise NotFoundError("Intervention not found.")
    return intervention_to_dict(intervention)


@router.post(
    "/interventions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_rate_limit)],
)
def create_intervention(
    payload: CircularInterventionCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    existing = db.scalar(
        select(CircularIntervention).where(
            CircularIntervention.intervention_code == payload.intervention_code
        )
    )
    if existing is not None:
        raise ConflictError("Duplicate intervention_code.", details={"code": payload.intervention_code})
    intervention = CircularIntervention(**payload.model_dump())
    db.add(intervention)
    db.flush()
    audit.record(
        db, principal=principal, organization_id=principal.organization_id,
        event_type="INTERVENTION_CREATED", entity_type="circular_intervention",
        entity_id=intervention.id, new_value={"code": intervention.intervention_code},
        **audit_ctx(request),
    )
    db.commit()
    return intervention_to_dict(intervention)
