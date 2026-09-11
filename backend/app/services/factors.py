"""Module E - Emission Factor Knowledge Base.

- Geography / year / source aware lookup with deterministic priority.
- Supplier-specific factors override generic ones when active.
- Missing factor returns None -> callers raise an explicit unresolved state.
- Versioning: superseding deactivates the old row, never updates/deletes it.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError, PlatformValidationError
from app.models.factor import EmissionFactor


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _token_overlap(haystack: str, needle: str) -> int:
    hay = set(_norm(haystack).replace("-", " ").split())
    nee = set(_norm(needle).replace("-", " ").split())
    return len(hay & nee)


def list_factors(
    db: Session,
    *,
    category: str | None = None,
    subcategory: str | None = None,
    region_country: str | None = None,
    region_state: str | None = None,
    scope: str | None = None,
    active: bool | None = None,
    source_year: int | None = None,
) -> list[EmissionFactor]:
    stmt: Select = select(EmissionFactor)
    if category:
        stmt = stmt.where(EmissionFactor.category == category)
    if subcategory:
        stmt = stmt.where(EmissionFactor.subcategory == subcategory)
    if region_country:
        stmt = stmt.where(EmissionFactor.region_country == region_country)
    if region_state:
        stmt = stmt.where(EmissionFactor.region_state == region_state)
    if scope:
        stmt = stmt.where(EmissionFactor.scope == scope)
    if active is not None:
        stmt = stmt.where(EmissionFactor.active.is_(active))
    if source_year is not None:
        stmt = stmt.where(EmissionFactor.source_year == source_year)
    stmt = stmt.order_by(
        EmissionFactor.category,
        EmissionFactor.subcategory,
        EmissionFactor.source_year.desc(),
    )
    return list(db.scalars(stmt))


def get_factor(db: Session, factor_id: UUID) -> EmissionFactor:
    factor = db.get(EmissionFactor, factor_id)
    if factor is None:
        raise NotFoundError("Emission factor not found.")
    return factor


def lookup_factor(
    db: Session,
    *,
    category: str,
    activity_subcategory: str,
    normalized_unit: str,
    scope: str | None = None,
    region_country: str | None = None,
    region_state: str | None = None,
    on_date: date | None = None,
    supplier_id: str | None = None,
) -> EmissionFactor | None:
    """Return the best active factor or None (explicit unresolved state)."""
    on_date = on_date or date.today()
    stmt = select(EmissionFactor).where(
        EmissionFactor.active.is_(True),
        EmissionFactor.category == category,
        EmissionFactor.input_unit == normalized_unit,
    )
    if scope:
        stmt = stmt.where(EmissionFactor.scope == scope)

    candidates = list(db.scalars(stmt))
    best: EmissionFactor | None = None
    best_key: tuple | None = None

    for factor in candidates:
        if factor.valid_from and factor.valid_from > on_date:
            continue
        if factor.valid_to and factor.valid_to < on_date:
            continue

        region_score = 0
        if region_state and factor.region_state and _norm(region_state) == _norm(factor.region_state):
            region_score = 3
        elif region_country and factor.region_country and _norm(region_country) == _norm(factor.region_country):
            region_score = 2
        elif factor.region_country is None and factor.region_state is None:
            region_score = 1

        supplier_score = 1 if (supplier_id and factor.supplier_id == supplier_id) else 0
        supplier_score += 1 if factor.supplier_specific else 0
        overlap = _token_overlap(activity_subcategory, f"{factor.subcategory} {factor.item_name}")
        confidence_score = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
            factor.confidence_level or "", 0
        )
        year = factor.source_year or 0
        key = (supplier_score, region_score, overlap, confidence_score, year)
        if best_key is None or key > best_key:
            best, best_key = factor, key

    return best


def create_factor(db: Session, data: dict, *, actor_id: UUID | None) -> EmissionFactor:
    factor_code = data["factor_code"]
    existing = db.scalar(
        select(EmissionFactor).where(EmissionFactor.factor_code == factor_code)
    )
    if existing is not None:
        raise ConflictError(
            "A factor with this factor_code already exists; use new-version instead.",
            details={"factor_code": factor_code},
        )
    _validate_factor_values(data)
    factor = EmissionFactor(**data)
    db.add(factor)
    db.flush()
    return factor


def create_new_version(
    db: Session,
    old_factor: EmissionFactor,
    data: dict,
    *,
    actor_id: UUID | None,
) -> EmissionFactor:
    old_factor.active = False
    payload = {k: v for k, v in data.items() if k != "id"}
    new_code = payload.get("factor_code")
    if not new_code or new_code == old_factor.factor_code:
        version_label = payload.get("version") or "new"
        payload["factor_code"] = f"{old_factor.factor_code}::{version_label}"
    _validate_factor_values(payload)
    new_factor = EmissionFactor(**payload)
    db.add(new_factor)
    db.flush()
    return new_factor


def _validate_factor_values(data: dict) -> None:
    total = data.get("total_co2e_factor")
    if total is None or Decimal(str(total)) < 0:
        raise PlatformValidationError("total_co2e_factor must be >= 0.")
    for key in ("co2_factor", "ch4_factor", "n2o_factor"):
        value = data.get(key)
        if value is not None and Decimal(str(value)) < 0:
            raise PlatformValidationError(f"{key} must be >= 0 or null.")
    valid_from = data.get("valid_from")
    valid_to = data.get("valid_to")
    if valid_from and valid_to and valid_to < valid_from:
        raise PlatformValidationError("valid_to cannot be before valid_from.")


def factor_to_dict(factor: EmissionFactor) -> dict:
    return {
        "id": factor.id,
        "factor_code": factor.factor_code,
        "category": factor.category,
        "subcategory": factor.subcategory,
        "item_name": factor.item_name,
        "region_country": factor.region_country,
        "region_state": factor.region_state,
        "scope": factor.scope,
        "input_unit": factor.input_unit,
        "output_unit": factor.output_unit,
        "co2_factor": factor.co2_factor,
        "ch4_factor": factor.ch4_factor,
        "n2o_factor": factor.n2o_factor,
        "total_co2e_factor": factor.total_co2e_factor,
        "source_name": factor.source_name,
        "source_url": factor.source_url,
        "source_year": factor.source_year,
        "valid_from": factor.valid_from,
        "valid_to": factor.valid_to,
        "methodology": factor.methodology,
        "confidence_level": factor.confidence_level,
        "version": factor.version,
        "active": factor.active,
        "created_at": factor.created_at,
    }
