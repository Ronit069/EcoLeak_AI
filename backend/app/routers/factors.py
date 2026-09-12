"""Module E1-E4: emission factor knowledge base endpoints."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import api_rate_limit, require_roles
from app.errors import EmissionFactorNotFoundError
from app.routers.common import ADMIN_ROLES, audit_ctx
from app.schemas.requests import EmissionFactorCreate
from app.security import Principal, get_current_principal
from app.services import audit, factors as factor_service

router = APIRouter(prefix="/api", tags=["Module E - Emission Factors"])


@router.get("/emission-factors")
def list_factors(
    category: str | None = None,
    subcategory: str | None = None,
    region_country: str | None = None,
    region_state: str | None = None,
    scope: str | None = None,
    active: bool | None = None,
    source_year: int | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    factors = factor_service.list_factors(
        db,
        category=category,
        subcategory=subcategory,
        region_country=region_country,
        region_state=region_state,
        scope=scope,
        active=active,
        source_year=source_year,
    )
    return [factor_service.factor_to_dict(f) for f in factors]


@router.get("/emission-factors/lookup")
def lookup_factor(
    category: str,
    activity_subcategory: str,
    normalized_unit: str,
    scope: str | None = None,
    region_country: str | None = None,
    region_state: str | None = None,
    on_date: date | None = None,
    supplier_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    factor = factor_service.lookup_factor(
        db,
        category=category,
        activity_subcategory=activity_subcategory,
        normalized_unit=normalized_unit,
        scope=scope,
        region_country=region_country,
        region_state=region_state,
        on_date=on_date,
        supplier_id=supplier_id,
    )
    if factor is None:
        raise EmissionFactorNotFoundError(
            "No compatible emission factor is available.",
            details={"category": category, "normalized_unit": normalized_unit},
        )
    return factor_service.factor_to_dict(factor)


@router.get("/emission-factors/{factor_id}")
def get_factor(
    factor_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    return factor_service.factor_to_dict(factor_service.get_factor(db, factor_id))


@router.post(
    "/emission-factors",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_rate_limit)],
)
def create_factor(
    payload: EmissionFactorCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    factor = factor_service.create_factor(db, payload.model_dump(), actor_id=principal.actor_id)
    audit.record(
        db, principal=principal, organization_id=principal.organization_id,
        event_type="EMISSION_FACTOR_CREATED", entity_type="emission_factor",
        entity_id=factor.id, new_value={"factor_code": factor.factor_code, "version": factor.version},
        **audit_ctx(request),
    )
    db.commit()
    return factor_service.factor_to_dict(factor)


@router.post(
    "/emission-factors/{factor_id}/new-version",
    status_code=status.HTTP_201_CREATED,
)
def create_new_version(
    factor_id: UUID,
    payload: EmissionFactorCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    old_factor = factor_service.get_factor(db, factor_id)
    new_factor = factor_service.create_new_version(
        db, old_factor, payload.model_dump(), actor_id=principal.actor_id
    )
    audit.record(
        db, principal=principal, organization_id=principal.organization_id,
        event_type="EMISSION_FACTOR_VERSIONED", entity_type="emission_factor",
        entity_id=new_factor.id,
        old_value={"factor_code": old_factor.factor_code, "active": False},
        new_value={"factor_code": new_factor.factor_code, "version": new_factor.version},
        **audit_ctx(request),
    )
    db.commit()
    return factor_service.factor_to_dict(new_factor)
