"""Module A1-A3: organization endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import api_rate_limit, require_roles
from app.models.core import Organization
from app.routers.common import ADMIN_ROLES, audit_ctx
from app.schemas.requests import OrganizationCreate, OrganizationUpdate
from app.schemas.serialize import organization_to_dict
from app.security import Principal, get_current_principal
from app.services import access, audit

router = APIRouter(prefix="/api", tags=["Module A - Organization"])


@router.post(
    "/organizations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_rate_limit)],
)
def create_organization(
    payload: OrganizationCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    organization = Organization(**payload.model_dump())
    db.add(organization)
    db.commit()
    audit.record(
        db, principal=principal, organization_id=organization.id,
        event_type="ORGANIZATION_CREATED", entity_type="organization",
        entity_id=organization.id, new_value={"name": organization.name},
        **audit_ctx(request),
    )
    db.commit()
    return organization_to_dict(organization)


@router.get("/organizations/{organization_id}")
def get_organization(
    organization_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    from uuid import UUID

    organization = access.get_organization(db, UUID(organization_id), principal)
    return organization_to_dict(organization)


@router.patch("/organizations/{organization_id}")
def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    from uuid import UUID

    organization = access.get_organization(db, UUID(organization_id), principal)
    before = organization_to_dict(organization)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(organization, key, value)
    db.flush()
    after = organization_to_dict(organization)
    audit.record(
        db, principal=principal, organization_id=organization.id,
        event_type="ORGANIZATION_UPDATED", entity_type="organization",
        entity_id=organization.id, old_value=_jsonable(before), new_value=_jsonable(after),
        **audit_ctx(request),
    )
    db.commit()
    return after


def _jsonable(value: dict) -> dict:
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(value)
