"""Merged-surface tenant guards for engine/P4 routers (T0-3).

api_contract.md documents "AuthN, tenant ownership" on every engine and
recommendation endpoint. AuthN is enforced router-wide in
``backend/app/main.py`` via ``get_current_principal``; the guards here add the
ownership half against the engine's live data source.

Stub mode: an ABSENT organization header means "the seeded default tenant" so
dev/demo tooling keeps working (README-documented stub semantics); a PRESENT
but wrong org header is rejected. JWT mode (production) enforces the
organization claim strictly via ``Principal.assert_org``.
"""
from __future__ import annotations

from fastapi import Body, Depends

from app.config import get_settings
from app.errors import NotFoundError
from app.security import Principal, get_current_principal


def _assert_org(principal: Principal, organization_id) -> None:
    """Tenant-ownership check with documented stub-mode semantics.

    Stub mode + ABSENT organization header = the seeded default tenant
    (dev/demo tooling keeps working). JWT mode (production) and any PRESENT
    org header are enforced strictly: wrong tenant -> 403.
    """
    if get_settings().auth_mode == "stub" and principal.organization_id is None:
        return
    principal.assert_org(organization_id)


def _facility_org(facility_id: str):
    from engine.api import get_engine

    facility = get_engine().data_source.get_facility(str(facility_id))
    if facility is None:
        raise NotFoundError("Facility not found.")
    return facility.organization_id


def facility_tenant_guard(
    facility_id: str,
    principal: Principal = Depends(get_current_principal),
) -> None:
    _assert_org(principal, _facility_org(facility_id))


def context_tenant_guard(
    principal: Principal = Depends(get_current_principal),
) -> None:
    from engine.api import get_engine

    org = get_engine().data_source.get_organization()
    if org is not None:
        _assert_org(principal, org.id)


def simulate_tenant_guard(
    body: dict = Body(default={}),
    principal: Principal = Depends(get_current_principal),
) -> None:
    from engine.api import get_engine

    engine = get_engine()
    context = engine.default_context()
    facility_id = str(body.get("facility_id") or context.get("facility_id") or "")
    facility = engine.data_source.get_facility(facility_id)
    if facility is None:
        raise NotFoundError("Facility not found.")
    _assert_org(principal, facility.organization_id)


def recommendation_tenant_guard(
    recommendation_id: str,
    principal: Principal = Depends(get_current_principal),
) -> None:
    """Recommendations are served from the default context's facility; a
    valid-but-wrong-tenant caller is rejected against that org."""
    from engine.api import get_engine

    engine = get_engine()
    context = engine.default_context()
    facility = engine.data_source.get_facility(str(context["facility_id"]))
    if facility is None:
        raise NotFoundError("Facility not found.")
    _assert_org(principal, facility.organization_id)
