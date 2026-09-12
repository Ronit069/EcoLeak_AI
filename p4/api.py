"""Merged-API router for Modules J/M/N (P4 ranker + dashboard aggregation).

Serves the P1 swap targets (J2 recommendations, N1 dashboard, N2 leak-map)
plus the generation/explanation endpoints (J1, M1). All responses follow the
frozen contract shapes; numbers are serialized canonically (Decimal -> JSON
number) via :func:`p4.serialization.to_api_dict` / engine ``to_jsonable``.

Mounted by ``backend/app/main.py`` into the single served API.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query

from contracts.schemas import (
    Facility,
    FeedbackType,
    HotspotDetectionResult,
    Organization,
    Process,
    RecommendationGenerationResult,
    RecommendationStatus,
)
from engine.api import get_engine
from engine.serialization import to_jsonable
from p4.data_source import (
    build_facility_context,
    load_facility_dataset,
    resource_factors_from_factors,
)
from p4.engine import RecommendationConstraints, generate_with_diagnostics
from p4.explainability import TemplateExplainer
from p4.feedback import FeedbackError, InMemoryFeedbackStore
from p4.models import RejectionReasonCode
from p4.serialization import to_api_dict

# Backend auth/guards live in backend/app; make them importable for BOTH the
# merged app (uvicorn --app-dir backend) and standalone engine runs.
_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.errors import ConflictError, NotFoundError, PlatformValidationError  # noqa: E402
from app.guards import (  # noqa: E402  (merged-surface tenant guards, T0-3)
    facility_tenant_guard,
    recommendation_tenant_guard,
)

router = APIRouter(tags=["recommendations"])

# Module Q — Phase-2 remediation decision: wired into the merged surface now.
# Store is in-memory + append-only (Phase-1 store); SQLAlchemy persistence is
# logged as Phase-3 backlog (owner P2) in docs/phase2/contract_changes.md.
_feedback_store = InMemoryFeedbackStore()

REPO_ROOT = Path(__file__).resolve().parent.parent


def _require_decimal(value: Any, field: str) -> Optional[Decimal]:
    """F-13: numeric request fields are 422 in the frozen shape, never 500."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise PlatformValidationError(
            f"{field} must be a valid number.",
            details={"field": field, "value": str(value)},
        )


def _run_ranker(
    facility_id: str,
    reporting_period_id: str,
    constraints: Optional[RecommendationConstraints],
) -> RecommendationGenerationResult:
    """Hotspots (live P3 engine) -> P4 ranker -> frozen J2 envelope.

    GA-01 / P4-C1 fix: facility, organization, processes and resource baselines
    are resolved from the LIVE data source for the requested facility (the mock
    demo facility/context was previously hardcoded here, so every non-demo
    facility raised the engine's facility-match guard and returned 500).
    """
    engine = get_engine()
    hotspots = engine.hotspot_result(facility_id, reporting_period_id)
    organization, facility, processes = load_facility_dataset(engine, facility_id)
    factors = resource_factors_from_factors(
        engine.data_source.get_emission_factors(), facility.country
    )
    context = build_facility_context(engine, facility_id, reporting_period_id)
    run = generate_with_diagnostics(
        hotspots,
        facility,
        organization=organization,
        processes=processes,
        context=context,
        emission_factors=factors,
        constraints=constraints,
        explainer=TemplateExplainer(),
    )
    return run.result


def _dashboard_payload(facility_id: str, reporting_period_id: str) -> dict:
    engine = get_engine()
    inventory = engine.calculate_inventory(facility_id, reporting_period_id)
    analysis = engine.detect_hotspots(facility_id, reporting_period_id)
    hotspots: HotspotDetectionResult = analysis.result
    ranking = _run_ranker(facility_id, reporting_period_id, None)
    potential_reduction = Decimal("0")
    potential_saving = Decimal("0")
    for rec in ranking.recommendations:
        if rec.impact is not None:
            potential_reduction += rec.impact.estimated_co2_saving_kg or Decimal("0")
            potential_saving += rec.impact.estimated_annual_saving or Decimal("0")
    circularity = engine.circularity_score(facility_id, reporting_period_id)
    payload = {
        "total_kgco2e": inventory.total_kgco2e,
        "scope_breakdown": {
            "SCOPE_1": inventory.scope1_kgco2e,
            "SCOPE_2": inventory.scope2_kgco2e,
            "SCOPE_3": inventory.scope3_kgco2e,
        },
        "carbon_intensity": inventory.carbon_intensity,
        "production_unit": inventory.production_unit,
        "largest_hotspot": (
            to_jsonable(hotspots.hotspots[0]) if hotspots.hotspots else None
        ),
        "top_actionable_hotspot_id": analysis.top_actionable_hotspot_id,
        "circularity_score": circularity.total_score,
        "potential_reduction_kgco2e": potential_reduction,
        "potential_annual_saving": potential_saving,
        "last_calculated_at": inventory.generated_at.isoformat(),
        "empty_state": len(hotspots.hotspots) == 0,
        # P1-05: expose unresolved activity count so the UI can show that the
        # totals exclude rows with no matching emission factor.
        "unresolved_count": len(inventory.unresolved),
    }
    return to_jsonable(payload)


# ---------------------------------------------------------------------------
# Module J
# ---------------------------------------------------------------------------


@router.post(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/recommendations/generate",
    status_code=202,
    dependencies=[Depends(facility_tenant_guard)],
)
def generate_recommendations(
    facility_id: str,
    period_id: str,
    body: dict = Body(default={}),
) -> dict:
    constraints = None
    if body.get("budget_limit") is not None or body.get("constraints"):
        raw = dict(body.get("constraints") or {})
        if body.get("budget_limit") is not None:
            raw["budget_limit"] = _require_decimal(body["budget_limit"], "budget_limit")
        constraints = RecommendationConstraints.model_validate(raw)
    result = _run_ranker(facility_id, period_id, constraints)
    return to_api_dict(result)


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/recommendations",
    dependencies=[Depends(facility_tenant_guard)],
)
def get_recommendations(
    facility_id: str,
    period_id: str,
    status: Optional[str] = Query(default=None),
    rank_max: Optional[int] = Query(default=None),
) -> dict:
    # P4-L6: reject invalid filters instead of silently returning an empty 200.
    if status is not None and status not in {s.value for s in RecommendationStatus}:
        raise PlatformValidationError(
            f"Invalid status {status!r}.",
            details={"allowed": [s.value for s in RecommendationStatus]},
        )
    if rank_max is not None and rank_max < 1:
        raise PlatformValidationError(
            "rank_max must be >= 1.", details={"rank_max": rank_max}
        )
    result = _run_ranker(facility_id, period_id, None)
    items = [
        _with_stored_status(rec)
        for rec in result.recommendations
    ]
    if status:
        items = [r for r in items if r.status.value == status]
    if rank_max is not None:
        items = [r for r in items if r.rank <= rank_max]
    out = result.model_copy(update={"recommendations": items})
    return to_api_dict(out)


# Module Q-style decision store for J3 status transitions (in-memory,
# append-only semantics; SQLAlchemy persistence is Phase-3 backlog, same
# deferral decision as Q feedback — see docs/phase3/backlog.md).
_STATUS_STORE: dict[str, str] = {}

_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "SUGGESTED": {"SHORTLISTED", "REJECTED", "PLANNED"},
    "SHORTLISTED": {"PLANNED", "REJECTED"},
    "PLANNED": {"IMPLEMENTED", "REJECTED"},
    "REJECTED": set(),
    "IMPLEMENTED": set(),
}


def _with_stored_status(rec):
    stored = _STATUS_STORE.get(str(rec.id))
    if stored is None or stored == rec.status.value:
        return rec
    return rec.model_copy(update={"status": RecommendationStatus(stored)})


@router.patch(
    "/api/recommendations/{recommendation_id}",
    dependencies=[Depends(recommendation_tenant_guard)],
)
def update_recommendation(recommendation_id: str, body: dict = Body(default={})) -> dict:
    """J3: status transition (SUGGESTED -> SHORTLISTED/PLANNED/REJECTED, ...).
    Unknown status -> 422; invalid transition -> 409; unknown id -> 404 (all
    frozen shape)."""
    raw = body.get("status")
    try:
        new_status = RecommendationStatus(raw)
    except ValueError:
        raise PlatformValidationError(
            f"Invalid recommendation status {raw!r}.",
            details={"status": raw, "allowed": [s.value for s in RecommendationStatus]},
        )
    context = get_engine().default_context()
    result = _run_ranker(context["facility_id"], context["reporting_period_id"], None)
    rec = next((r for r in result.recommendations if str(r.id) == recommendation_id), None)
    if rec is None:
        raise NotFoundError(
            "Recommendation not found.",
            details={"recommendation_id": recommendation_id},
        )
    current = _STATUS_STORE.get(recommendation_id, rec.status.value)
    if new_status.value != current and new_status.value not in _ALLOWED_STATUS_TRANSITIONS.get(current, set()):
        raise ConflictError(
            "Invalid recommendation status transition.",
            details={"from": current, "to": new_status.value},
        )
    _STATUS_STORE[recommendation_id] = new_status.value
    return to_api_dict(rec.model_copy(update={"status": new_status}))


@router.get(
    "/api/recommendations/{recommendation_id}/explanation",
    dependencies=[Depends(recommendation_tenant_guard)],
)
def recommendation_explanation(recommendation_id: str) -> dict:
    result = _run_ranker(
        get_engine().default_context()["facility_id"],
        get_engine().default_context()["reporting_period_id"],
        None,
    )
    rec = next((r for r in result.recommendations if str(r.id) == recommendation_id), None)
    if rec is None:
        # F-6: use the frozen PlatformError shape, not raw HTTPException.
        raise NotFoundError(
            "Recommendation not found.",
            details={"recommendation_id": recommendation_id},
        )
    scores = {
        "carbon_saving": rec.carbon_saving_score,
        "financial_return": rec.financial_return_score,
        "feasibility": rec.feasibility_score,
        "circularity": rec.circularity_score,
        "implementation_speed": rec.implementation_speed_score,
        "confidence": rec.confidence_score,
        "final": rec.final_score,
        "rank": rec.rank,
    }
    payload = {
        "recommendation_id": str(rec.id),
        "summary": rec.explanation or "",
        "evidence": {
            "hotspot_id": str(rec.hotspot_id),
            "intervention_id": str(rec.intervention_id),
            "scores": scores,
            "impact": to_api_dict(rec.impact) if rec.impact else None,
        },
        "assumptions": rec.impact.assumptions if rec.impact else {},
        "confidence_score": rec.confidence_score,
        "generated_by": "TemplateExplainer (deterministic; LLM narrative is labeled separately)",
    }
    return to_jsonable(payload)


# ---------------------------------------------------------------------------
# Module N (P1 dashboard swap targets)
# ---------------------------------------------------------------------------


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/dashboard",
    dependencies=[Depends(facility_tenant_guard)],
)
def dashboard(facility_id: str, period_id: str) -> dict:
    return _dashboard_payload(facility_id, period_id)


@router.get(
    "/api/facilities/{facility_id}/reporting-periods/{period_id}/leak-map",
    dependencies=[Depends(facility_tenant_guard)],
)
def leak_map(facility_id: str, period_id: str) -> dict:
    engine = get_engine()
    hotspots: HotspotDetectionResult = engine.hotspot_result(facility_id, period_id)
    nodes = [
        {
            "process_id": h.process_id,
            "process_name": h.process_name,
            "emissions_kgco2e": h.emissions_kgco2e,
            "contribution_percent": h.contribution_percent,
            "severity": h.severity.value,
        }
        for h in hotspots.hotspots
    ]
    return to_jsonable({"nodes": nodes, "links": []})

# ---------------------------------------------------------------------------
# Module Q — feedback (Q1 submit / Q2 history), Phase-2 remediation wiring
# ---------------------------------------------------------------------------


def _require_recommendation(recommendation_id: str) -> None:
    """P4-M3: reject feedback for ids that are not part of the current ranking
    (previously any UUID was accepted and stored)."""
    engine = get_engine()
    context = engine.default_context()
    result = _run_ranker(context["facility_id"], context["reporting_period_id"], None)
    if not any(str(rec.id) == recommendation_id for rec in result.recommendations):
        raise NotFoundError(
            "Recommendation not found.",
            details={"recommendation_id": recommendation_id},
        )


@router.post(
    "/api/recommendations/{recommendation_id}/feedback",
    status_code=201,
    dependencies=[Depends(recommendation_tenant_guard)],
)
def submit_feedback(recommendation_id: str, body: dict = Body(default={})) -> dict:
    """Q1: capture Useful / Not Applicable / Consider Later / Implemented /
    Rejected feedback with optional actual outcomess. REJECTED requires a
    structured reason_code (spam/rate-limit guarded at the platform layer)."""
    raw_type = body.get("feedback_type")
    if not raw_type:
        from engine.errors import MissingParameterError

        raise MissingParameterError("feedback_type is required", {"recommendation_id": recommendation_id})
    # P4-M1: validate the enum at the boundary (was passed raw into the store
    # and raised an uncaught pydantic ValidationError -> 500).
    try:
        feedback_type = FeedbackType(raw_type)
    except ValueError:
        raise PlatformValidationError(
            f"Invalid feedback_type {raw_type!r}.",
            details={
                "recommendation_id": recommendation_id,
                "allowed": [kind.value for kind in FeedbackType],
            },
        )
    reason_code = None
    if body.get("reason_code"):
        # F-13: invalid enum input is a 422 in the frozen shape, never a 500.
        try:
            reason_code = RejectionReasonCode(body["reason_code"])
        except ValueError:
            raise PlatformValidationError(
                f"Invalid reason_code {body['reason_code']!r}.",
                details={
                    "recommendation_id": recommendation_id,
                    "allowed": [code.value for code in RejectionReasonCode],
                },
            )
    _require_recommendation(recommendation_id)
    event: FeedbackEvent = _feedback_store.submit(
        recommendation_id=recommendation_id,
        feedback_type=feedback_type,
        reason=body.get("reason"),
        reason_code=reason_code,
        actual_capex=_require_decimal(body.get("actual_capex"), "actual_capex"),
        actual_annual_saving=_require_decimal(body.get("actual_annual_saving"), "actual_annual_saving"),
        actual_co2_saving_kg=_require_decimal(body.get("actual_co2_saving_kg"), "actual_co2_saving_kg"),
    )
    return to_api_dict(event)


@router.get(
    "/api/recommendations/{recommendation_id}/feedback",
    dependencies=[Depends(recommendation_tenant_guard)],
)
def feedback_history(recommendation_id: str) -> dict:
    """Q2: latest state + full history for a recommendation."""
    _require_recommendation(recommendation_id)
    events = _feedback_store.history(recommendation_id)
    latest = events[-1] if events else None
    return {
        "recommendation_id": recommendation_id,
        "latest_state": to_api_dict(latest) if latest else None,
        "history": [to_api_dict(e) for e in events],
    }
