"""Module O — scenario CRUD + clone/restore/compare routes (Phase-3 final gaps).

Mounted by backend/app/main.py alongside the other merged routers. Scenario
management builds AROUND the existing K1 simulation engine (no reimplementation
of simulation logic). Tenant ownership is enforced on every route BEFORE any
state is written (scenario -> facility -> organization, merged guards).

Store is session-scoped (p4.scenarios.ScenarioStore); persistence is
Phase-4 backlog (owner P2) — recorded in docs/phase2/contract_changes.md.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query, Response

from app.security import Principal, get_current_principal  # merged-surface only
from engine.api import get_engine
from engine.simulator import InterventionSelection
from p4.api import _run_ranker  # noqa: E402
from p4.serialization import to_api_dict  # noqa: E402
from engine.serialization import to_jsonable  # noqa: E402
from p4.scenarios import STORE as SCENARIO_STORE
from p4.scenarios import ScenarioError

router = APIRouter(tags=["scenarios"])


def _principal(principal: Principal = Depends(get_current_principal)) -> Principal:
    # Real sub-dependency: FastAPI resolves the Depends INSIDE this function's
    # parameters. Returning a raw Depends(...) object would inject the object
    # itself (classic 'Depends has no attribute organization_id' failure).
    return principal


def _facility_guard(facility_id: str, principal: Principal = Depends(_principal)) -> None:
    from app.guards import facility_tenant_guard

    facility_tenant_guard(facility_id, principal)


def _assert_scenario_tenant(scenario_id: str, principal: Principal) -> None:
    """Scenario ownership resolved BEFORE any write (H3 pattern)."""
    item = SCENARIO_STORE.get(scenario_id)
    facility = get_engine().data_source.get_facility(item.facility_id)
    if facility is None:
        from engine.errors import EntityNotFoundError

        raise EntityNotFoundError("Unknown facility", {"facility_id": item.facility_id})
    principal.assert_org(facility.organization_id)


def _raise(exc: ScenarioError) -> None:
    from engine.errors import CarbonPlatformError

    raise CarbonPlatformError(exc.message, exc.details)


@router.post(
    "/api/facilities/{facility_id}/scenarios",
    status_code=201,
    dependencies=[Depends(_facility_guard)],
)
def create_scenario(facility_id: str, body: dict = Body(default={})) -> dict:
    """O1: create a named scenario (budget >= 0, target 0..100 optional)."""
    name = body.get("name")
    if not name or not str(name).strip():
        from engine.errors import MissingParameterError

        raise MissingParameterError("name is required")
    budget = Decimal(str(body["budget_limit"])) if body.get("budget_limit") is not None else None
    target = Decimal(str(body["target_reduction_pct"])) if body.get("target_reduction_pct") is not None else None
    item = SCENARIO_STORE.create(facility_id, name=str(name).strip(), budget_limit=budget, target_reduction_pct=target)
    SCENARIO_STORE.take_baseline(str(item.scenario.id), facility_id)
    return to_api_dict(item.scenario)


@router.get(
    "/api/facilities/{facility_id}/scenarios",
    dependencies=[Depends(_facility_guard)],
)
def list_scenarios(facility_id: str) -> dict:
    """O2: list scenarios for a facility."""
    items = SCENARIO_STORE.list_for_facility(facility_id)
    return {"scenarios": [to_api_dict(i.scenario) for i in items]}


@router.get("/api/scenarios/compare")
def compare_scenarios(
    scenario_ids: str = Query(default=""),
    principal: Principal = Depends(_principal),
) -> dict:
    """K3: simulate each scenario with the existing K1 engine -> comparisons +
    deltas vs the first scenario."""
    ids = [x.strip() for x in scenario_ids.split(",") if x.strip()]
    if len(ids) < 2:
        from engine.errors import MissingParameterError

        raise MissingParameterError("scenario_ids must list at least 2 scenario ids")
    ctx = get_engine().default_context()
    fid, pid = ctx["facility_id"], ctx["reporting_period_id"]
    interventions_by_id = {str(iv.id): iv for iv in get_engine().data_source.get_interventions()}
    comparisons: list[dict] = []
    seen: set[str] = set()
    for sid in ids:
        if sid in seen:
            from engine.errors import MissingParameterError

            raise MissingParameterError("duplicate scenario_ids in compare request")
        seen.add(sid)
        _assert_scenario_tenant(sid, principal)
        item = SCENARIO_STORE.get(sid)
        selections = [
            InterventionSelection(
                intervention=interventions_by_id[str(iv_id)],
                adoption_percentage=iv.adoption_percentage,
                selected=iv.selected,
            )
            for iv, iv_id in zip(item.interventions, item.intervention_ids)
            if str(iv_id) in interventions_by_id
        ]
        sim = get_engine().simulate(fid, pid, selections, scenario_id=str(item.scenario.id))
        entry = to_jsonable(sim.to_dict())
        entry["scenario_id"] = str(item.scenario.id)
        entry["name"] = item.scenario.name
        comparisons.append(entry)
    base = comparisons[0].get("assessment") or {}
    deltas = {}
    for c in comparisons[1:]:
        a = c.get("assessment") or {}
        deltas[c["scenario_id"]] = {
            "projected_emissions_delta_kg": (a.get("projected_emissions_kg", 0) - base.get("projected_emissions_kg", 0)),
            "annual_saving_delta": ((a.get("annual_saving") or 0) - (base.get("annual_saving") or 0)),
            "capex_delta": ((a.get("total_capex") or 0) - (base.get("total_capex") or 0)),
        }
    return to_jsonable({"comparisons": comparisons, "deltas": deltas})

@router.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, principal: Principal = Depends(_principal)) -> dict:
    """O3: scenario + its interventions (tenant-scoped)."""
    _assert_scenario_tenant(scenario_id, principal)
    item = SCENARIO_STORE.get(scenario_id)
    return {
        "scenario": to_api_dict(item.scenario),
        "scenario_interventions": [to_api_dict(iv) for iv in item.interventions],
    }


@router.patch("/api/scenarios/{scenario_id}")
def update_scenario(
    scenario_id: str,
    body: dict = Body(default={}),
    principal: Principal = Depends(_principal),
) -> dict:
    """O4: update name/budget/target."""
    _assert_scenario_tenant(scenario_id, principal)
    item = SCENARIO_STORE.update(
        scenario_id,
        facility_id="",
        name=body.get("name"),
        budget_limit=Decimal(str(body["budget_limit"])) if body.get("budget_limit") is not None else None,
        target_reduction_pct=Decimal(str(body["target_reduction_pct"])) if body.get("target_reduction_pct") is not None else None,
    )
    return to_api_dict(item.scenario)


@router.delete("/api/scenarios/{scenario_id}")
def delete_scenario(
    scenario_id: str, principal: Principal = Depends(_principal),
) -> Response:
    """O5: soft delete."""
    _assert_scenario_tenant(scenario_id, principal)
    SCENARIO_STORE.delete(scenario_id, facility_id="")
    return Response(status_code=204)


@router.post("/api/scenarios/{scenario_id}/interventions", status_code=201)
def add_scenario_intervention(
    scenario_id: str,
    body: dict = Body(default={}),
    principal: Principal = Depends(_principal),
) -> dict:
    """O6: add a recommendation at an adoption %; resolves to intervention_id
    via live J2 output; duplicates rejected."""
    _assert_scenario_tenant(scenario_id, principal)
    recommendation_id = body.get("recommendation_id")
    if not recommendation_id:
        from engine.errors import MissingParameterError

        raise MissingParameterError("recommendation_id is required")
    adoption = Decimal(str(body.get("adoption_percentage", 100)))
    ctx = get_engine().default_context()
    ranking = _run_ranker(ctx["facility_id"], ctx["reporting_period_id"], None)
    target = next((r for r in ranking.recommendations if str(r.id) == recommendation_id), None)
    if target is None:
        from engine.errors import EntityNotFoundError

        raise EntityNotFoundError("Unknown recommendation_id", {"recommendation_id": recommendation_id})
    try:
        entry = SCENARIO_STORE.add_intervention(
            scenario_id,
            facility_id="",
            recommendation_id=recommendation_id,
            intervention_id=str(target.intervention_id),
            adoption_percentage=adoption,
            selected=bool(body.get("selected", True)),
        )
    except ScenarioError as exc:
        _raise(exc)
    return to_api_dict(entry)


@router.delete("/api/scenarios/{scenario_id}/interventions/{scenario_intervention_id}")
def remove_scenario_intervention(
    scenario_id: str,
    scenario_intervention_id: str,
    principal: Principal = Depends(_principal),
) -> Response:
    """O7: remove one intervention."""
    _assert_scenario_tenant(scenario_id, principal)
    SCENARIO_STORE.remove_intervention(scenario_id, facility_id="", scenario_intervention_id=scenario_intervention_id)
    return Response(status_code=204)


@router.post("/api/scenarios/{scenario_id}/clone", status_code=201)
def clone_scenario(
    scenario_id: str,
    body: dict = Body(default={}),
    principal: Principal = Depends(_principal),
) -> dict:
    """Clone as an INDEPENDENT scenario (mutating the clone must not affect
    the original — guaranteed by id/snapshot isolation in the store)."""
    _assert_scenario_tenant(scenario_id, principal)
    new = SCENARIO_STORE.clone(scenario_id, facility_id="", new_name=body.get("new_name"))
    return to_api_dict(new.scenario)


@router.post("/api/scenarios/{scenario_id}/restore")
def restore_scenario(scenario_id: str, principal: Principal = Depends(_principal)) -> dict:
    """Restore: revert to the creation-time (baseline) intervention state."""
    _assert_scenario_tenant(scenario_id, principal)
    item = SCENARIO_STORE.restore(scenario_id, facility_id="")
    return to_api_dict(item.scenario)


