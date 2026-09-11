"""FastAPI surface for the P3 engine (Modules F/G/H/K/L).

Merged deployment: ``backend/app/main.py`` includes ``router`` into the single
served API so P1/P4 hit one base URL. The standalone ``app`` remains available
(``uvicorn engine.api:app``) for engine-only runs.

Every domain error goes through :class:`CarbonPlatformError` (or subclasses);
no raw ``HTTPException`` is raised here, so the merged surface has one
consistent error shape (frozen payload from api_contract.md §28).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body, FastAPI, Request
from fastapi.responses import JSONResponse

from contracts.schemas import Scope

from .config import HotspotWeights
from .data_source import default_data_source
from .errors import CarbonPlatformError, EntityNotFoundError, MissingParameterError
from .serialization import to_jsonable
from .service import EcoLeakEngine
from .simulator import InterventionSelection

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


@router.get("/api/context")
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


@router.get("/api/facilities/{facility_id}/reporting-periods/{period_id}/inventory-summary")
def inventory_summary(facility_id: str, period_id: str) -> dict:
    summary = get_engine().inventory_summary(facility_id, period_id)
    return _json(summary)


@router.post("/api/facilities/{facility_id}/reporting-periods/{period_id}/calculations")
def calculations(facility_id: str, period_id: str, body: dict = Body(default={})) -> list[dict]:
    inventory = get_engine().calculate_inventory(facility_id, period_id)
    return [_json(r.calculation) for r in inventory.records if r.calculation is not None]


@router.post("/api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots/detect")
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


@router.get("/api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots")
def get_hotspots(facility_id: str, period_id: str) -> dict:
    analysis = get_engine().detect_hotspots(facility_id, period_id)
    # Frozen envelope only (G2).
    return _json(analysis.result)


@router.get("/api/facilities/{facility_id}/reporting-periods/{period_id}/circularity-score")
def circularity_score(facility_id: str, period_id: str) -> dict:
    return _json(get_engine().circularity_score(facility_id, period_id).to_dict())


@router.post("/api/scenarios/{scenario_id}/simulate")
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
        selections.append(
            InterventionSelection(
                intervention=iv,
                adoption_percentage=Decimal(str(item.get("adoption_percentage", 100))),
                selected=bool(item.get("selected", True)),
                capex_override=Decimal(str(item["capex_override"])) if item.get("capex_override") is not None else None,
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
        budget_limit=Decimal(str(body["budget_limit"])) if body.get("budget_limit") is not None else None,
        target_reduction_pct=(
            Decimal(str(body["target_reduction_pct"])) if body.get("target_reduction_pct") is not None else None
        ),
        scope_boundary=scope_boundary,
    )
    return _json(result.to_dict())


@router.post("/api/facilities/{facility_id}/anomalies/detect")
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