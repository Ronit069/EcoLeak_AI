"""Optional FastAPI wrapper around :class:`engine.service.EcoLeakEngine`.

P2 owns the platform API; this thin service exists so P1/P4 can hit the real P3
engine during integration. It only exposes the Module F/G/K/L/H calculation
endpoints and reuses the frozen JSON shapes from ``contracts``.

Run:

    uvicorn engine.api:app --reload

If FastAPI is not installed the module raises a clear ImportError on import.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from contracts.schemas import Scope

from .config import HotspotWeights
from .data_source import load_mock_data_source
from .errors import CarbonPlatformError
from .serialization import to_jsonable
from .service import EcoLeakEngine
from .simulator import InterventionSelection

app = FastAPI(title="EcoLeak AI - P3 Engine", version="phase1.0.0")
_engine = EcoLeakEngine(data_source=load_mock_data_source())


def get_engine() -> EcoLeakEngine:
    return _engine


@app.exception_handler(CarbonPlatformError)
async def domain_error_handler(_request, exc: CarbonPlatformError) -> JSONResponse:
    severity = exc.severity
    status = 422 if severity in {"ERROR", "WARNING"} else 400
    return JSONResponse(status_code=status, content=exc.to_error_dict())


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": "phase1.0.0"}


@app.get("/api/facilities/{facility_id}/reporting-periods/{period_id}/inventory-summary")
def inventory_summary(facility_id: str, period_id: str) -> dict:
    summary = get_engine().inventory_summary(facility_id, period_id)
    return _json(summary)


@app.post("/api/facilities/{facility_id}/reporting-periods/{period_id}/calculations")
def calculations(facility_id: str, period_id: str, body: dict = Body(default={})) -> list[dict]:
    inventory = get_engine().calculate_inventory(facility_id, period_id)
    return [_json(r.calculation) for r in inventory.records if r.calculation is not None]


@app.post("/api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots/detect")
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
    payload = _json(analysis.result)
    payload["top_actionable_hotspot_id"] = analysis.top_actionable_hotspot_id
    payload["component_sources"] = analysis.component_sources
    payload["issues"] = analysis.issues
    return payload


@app.get("/api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots")
def get_hotspots(facility_id: str, period_id: str) -> dict:
    analysis = get_engine().detect_hotspots(facility_id, period_id)
    payload = _json(analysis.result)
    payload["top_actionable_hotspot_id"] = analysis.top_actionable_hotspot_id
    payload["issues"] = analysis.issues
    return payload


@app.get("/api/facilities/{facility_id}/reporting-periods/{period_id}/circularity-score")
def circularity_score(facility_id: str, period_id: str) -> dict:
    return _json(get_engine().circularity_score(facility_id, period_id).to_dict())


@app.post("/api/scenarios/{scenario_id}/simulate")
def simulate(scenario_id: str, body: dict = Body(default={})) -> dict:
    engine = get_engine()
    context = engine.default_context()
    facility_id = body.get("facility_id", context["facility_id"])
    period_id = body.get("reporting_period_id", context["reporting_period_id"])
    if not facility_id or not period_id:
        raise HTTPException(status_code=422, detail="facility_id and reporting_period_id are required")

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
            raise HTTPException(status_code=404, detail=f"Unknown intervention: {item}")
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


@app.post("/api/facilities/{facility_id}/anomalies/detect")
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
