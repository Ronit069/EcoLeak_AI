"""FastAPI surface for the P3 engine (Modules F/G/H/K/L).

Merged deployment: ``backend/app/main.py`` includes ``router`` into the single
served API so P1/P4 hit one base URL. The standalone ``app`` remains available
(``uvicorn engine.api:app``) for engine-only runs.

Every domain error goes through :class:`CarbonPlatformError` (or subclasses);
no raw ``HTTPException`` is raised here, so the merged surface has one
consistent error shape (frozen payload from api_contract.md §28).
"""

from __future__ import annotations

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from contracts.schemas import Scope

from .config import HotspotWeights
from .data_source import default_data_source
from .errors import (
    CarbonPlatformError,
    EntityNotFoundError,
    MissingParameterError,
)
from .serialization import to_jsonable
from .service import EcoLeakEngine
from .simulator import InterventionSelection

# Backend auth/guards live in backend/app; make them importable for BOTH the
# merged app (uvicorn --app-dir backend) and standalone engine runs.
_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.errors import PlatformValidationError  # noqa: E402
from app.guards import (  # noqa: E402  (merged-surface tenant guards, T0-3)
    context_tenant_guard,
    facility_tenant_guard,
    simulate_tenant_guard,
)

router = APIRouter(tags=["engine"])

app = FastAPI(title="EcoLeak AI - P3 Engine", version="phase1.0.0")
# Env-driven: ECOLEAK_SQL_DSN -> P2 SQL tables; unset -> mock fixture.
_engine = EcoLeakEngine(data_source=default_data_source())


def get_engine() -> EcoLeakEngine:
    return _engine


@app.exception_handler(CarbonPlatformError)
async def domain_error_handler(_request: Request, exc: CarbonPlatformError) -> JSONResponse:
    """Frozen error shape + status from the exception (merged-surface contract)."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_error_dict())


@router.get("/health", include_in_schema=True)
def health() -> dict:
    return {"status": "ok", "engine_version": "phase1.0.0"}


@router.get("/api/context", dependencies=[Depends(context_tenant_guard)])
def context() -> dict:
    """Current org/facility/period for the default facility — P1 live-mode
    dataset source (replaces the mock JSON read when USE_MOCKS=false)."""
    engine = get_engine()
    org = engine.data_source.get_organization()
    facilities = engine.data_source.list_facilities()
    periods = (
        engine.data_source.list_reporting_periods(str(facilities[0].id))
        if facilities
        else []
    )
    return _json({"organization": org, "facilities": facilities, "reporting_periods": periods})


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/inventory-summary",
    dependencies=[Depends(facility_tenant_guard)],
)
def inventory_summary(facility_id: str, period_id: str) -> dict:
    summary = get_engine().inventory_summary(facility_id, period_id)
    return _json(summary)


@router.post(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/calculations",
    dependencies=[Depends(facility_tenant_guard)],
)
def calculations(facility_id: str, period_id: str, body: dict = Body(default={})) -> list[dict]:
    return _calculations_payload(facility_id, period_id)


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/calculations",
    dependencies=[Depends(facility_tenant_guard)],
)
def get_calculations(facility_id: str, period_id: str) -> list[dict]:
    """F2: calculations are derived on demand from the versioned inputs
    (same deterministic result as F1's POST), so GET returns the identical
    ``EmissionCalculation[]`` payload rather than a persisted job list."""
    return _calculations_payload(facility_id, period_id)


def _calculations_payload(facility_id: str, period_id: str) -> list[dict]:
    inventory = get_engine().calculate_inventory(facility_id, period_id)
    return [_json(r.calculation) for r in inventory.records if r.calculation is not None]


@router.post(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots/detect",
    dependencies=[Depends(facility_tenant_guard)],
)
def detect_hotspots(facility_id: str, period_id: str, body: dict = Body(default={})) -> dict:
    boundary = None
    if body.get("scope_boundary"):
        boundary = [Scope(s) for s in body["scope_boundary"]]
    weights = None
    if body.get("weights"):
        weights = HotspotWeights(**body["weights"])
    analysis = get_engine().detect_hotspots(
        facility_id, period_id, scope_boundary=boundary, weights=weights
    )
    # G1/G2 return exactly the frozen HotspotDetectionResult envelope (extra
    # keys would break P1's strict Zod mirror of the contract).
    return _json(analysis.result)


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots",
    dependencies=[Depends(facility_tenant_guard)],
)
def get_hotspots(facility_id: str, period_id: str) -> dict:
    analysis = get_engine().detect_hotspots(facility_id, period_id)
    # Frozen envelope only (G2).
    return _json(analysis.result)


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/circularity-score",
    dependencies=[Depends(facility_tenant_guard)],
)
def circularity_score(facility_id: str, period_id: str) -> dict:
    return _json(get_engine().circularity_score(facility_id, period_id).to_dict())


@router.post(
    "/api/scenarios/{scenario_id}/simulate",
    dependencies=[Depends(simulate_tenant_guard)],
)
def simulate(scenario_id: str, body: dict = Body(default={})) -> dict:
    engine = get_engine()
    context = engine.default_context()
    facility_id = body.get("facility_id", context["facility_id"])
    period_id = body.get("reporting_period_id", context["reporting_period_id"])
    if not facility_id or not period_id:
        raise MissingParameterError(
            "facility_id and reporting_period_id are required",
            {"facility_id": facility_id, "reporting_period_id": period_id},
        )

    interventions = {str(iv.id): iv for iv in engine.data_source.get_interventions()}
    interventions_by_code = {iv.intervention_code: iv for iv in engine.data_source.get_interventions()}
    selections: list[InterventionSelection] = []
    for item in body.get("interventions", []):
        iv = None
        if item.get("intervention_id"):
            iv = interventions.get(str(item["intervention_id"]))
        if iv is None and item.get("intervention_code"):
            iv = interventions_by_code.get(item["intervention_code"])
        if iv is None:
            raise EntityNotFoundError(
                f"Unknown intervention: {item}",
                {"intervention": item},
            )
        try:
            adoption = Decimal(str(item.get("adoption_percentage", 100)))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PlatformValidationError(
                "adoption_percentage must be a valid number.",
                details={"intervention": item},
            ) from exc
        selections.append(
            InterventionSelection(
                intervention=iv,
                adoption_percentage=adoption,
                selected=bool(item.get("selected", True)),
                capex_override=_body_decimal(item.get("capex_override"), "capex_override"),
            )
        )

    scope_boundary = None
    if body.get("scope_boundary"):
        scope_boundary = {Scope(s) for s in body["scope_boundary"]}
    result = engine.simulate(
        facility_id,
        period_id,
        selections,
        scenario_id=scenario_id,
        budget_limit=_body_decimal(body.get("budget_limit"), "budget_limit"),
        target_reduction_pct=_body_decimal(body.get("target_reduction_pct"), "target_reduction_pct"),
        scope_boundary=scope_boundary,
    )
    return _json(result.to_dict())


def _body_decimal(value: Any, field: str) -> Decimal | None:
    """F-13: numeric request fields are 422 in the frozen shape, never 500."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PlatformValidationError(
            f"{field} must be a valid number.",
            details={"field": field, "value": str(value)},
        ) from exc


@router.post(
    "/api/facilities/{facility_id}/anomalies/detect",
    dependencies=[Depends(facility_tenant_guard)],
)
def detect_anomalies(facility_id: str, body: dict = Body(default={})) -> dict:
    engine = get_engine()
    period_id = body.get("reporting_period_id")
    if not period_id:
        period_id = engine.default_context()["reporting_period_id"]
    result = engine.anomalies(facility_id, period_id)
    return _json(result.to_dict())


def _json(value: Any) -> Any:
    """Encode engine output using the canonical numeric JSON representation."""
    return to_jsonable(value)


app.include_router(router)