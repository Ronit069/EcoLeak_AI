"""Module O — scenario management layer (Phase-3 final-gap closure, Item 5).

Session-scoped scenario store with CRUD + clone + restore + comparison,
built AROUND the existing K1 simulation engine (no re-implementation of
simulation logic). Tenant ownership is enforced by the route layer via the
merged-surface guards; every scenario carries its owning facility_id.

Storage is in-memory (consistent with the feedback/anomaly registries);
SQLAlchemy persistence is Phase-4 backlog (owner P2).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from contracts.schemas import Scenario, ScenarioIntervention


class ScenarioError(Exception):
    """Scenario domain error (mapped to the frozen error shape by the API)."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class StoredScenario:
    scenario: Scenario
    facility_id: str
    interventions: list[ScenarioIntervention] = field(default_factory=list)
    # intervention_id resolved at add-time (ranked J2 output), for K1/K3 reuse
    intervention_ids: list[UUID] = field(default_factory=list)
    # snapshot taken at creation; restore() reverts to it (baseline restore)
    baseline_interventions: list[ScenarioIntervention] = field(default_factory=list)
    baseline_intervention_ids: list[UUID] = field(default_factory=list)
    deleted: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ScenarioStore:
    """Module O CRUD/clone/restore store (session-scoped, tenant-tagged)."""

    def __init__(self) -> None:
        self._items: dict[UUID, StoredScenario] = {}

    # -- helpers ------------------------------------------------------------
    def _get(self, scenario_id: str | UUID, facility_id: str | None = None) -> StoredScenario:
        sid = UUID(str(scenario_id))
        item = self._items.get(sid)
        if item is None or item.deleted:
            raise ScenarioError("NOT_FOUND", "Scenario not found.", {"scenario_id": str(scenario_id)})
        if facility_id and item.facility_id != facility_id:
            # falsy facility_id => route-level tenant guard already enforced;
            # the store never re-checks against a blanket value.
            raise ScenarioError("FORBIDDEN", "Caller does not own this scenario.")
        return item

    # -- O1 create ----------------------------------------------------------
    def create(
        self,
        facility_id: str,
        *,
        name: str,
        budget_limit: Decimal | None = None,
        target_reduction_pct: Decimal | None = None,
    ) -> StoredScenario:
        scenario = Scenario(
            id=uuid4(),
            facility_id=UUID(facility_id),
            reporting_period_id=UUID("0a1b2c3d-0003-4003-8003-000000000003"),
            name=name,
            scenario_type="whatif",
            budget_limit=budget_limit,
            target_reduction_pct=target_reduction_pct,
            created_at=datetime.now(timezone.utc),
        )
        item = StoredScenario(scenario=scenario, facility_id=str(facility_id))
        self._items[scenario.id] = item
        return item

    # -- O2 list ------------------------------------------------------------
    def list_for_facility(self, facility_id: str) -> list[StoredScenario]:
        return [
            item for item in self._items.values()
            if item.facility_id == facility_id and not item.deleted
        ]

    # -- O3 get -------------------------------------------------------------
    def get(self, scenario_id: str, facility_id: str | None = None) -> StoredScenario:
        return self._get(scenario_id, facility_id)

    # -- O4 update ----------------------------------------------------------
    def update(
        self,
        scenario_id: str,
        facility_id: str,
        *,
        name: str | None = None,
        budget_limit: Decimal | None = None,
        target_reduction_pct: Decimal | None = None,
    ) -> StoredScenario:
        item = self._get(scenario_id, facility_id)
        if name is not None:
            item.scenario = item.scenario.model_copy(update={"name": name})
        if budget_limit is not None:
            item.scenario = item.scenario.model_copy(update={"budget_limit": budget_limit})
        if target_reduction_pct is not None:
            item.scenario = item.scenario.model_copy(
                update={"target_reduction_pct": target_reduction_pct})
        item.updated_at = datetime.now(timezone.utc)
        return item

    # -- O5 delete (soft) ----------------------------------------------------
    def delete(self, scenario_id: str, facility_id: str) -> None:
        item = self._get(scenario_id, facility_id)
        item.deleted = True

    # -- O6 add intervention -------------------------------------------------
    def add_intervention(
        self,
        scenario_id: str,
        facility_id: str,
        *,
        recommendation_id: str,
        intervention_id: str,
        adoption_percentage: Decimal,
        selected: bool = True,
    ) -> ScenarioIntervention:
        item = self._get(scenario_id, facility_id)
        if adoption_percentage < 0 or adoption_percentage > 100:
            raise ScenarioError(
                "INVALID_ADOPTION", "adoption_percentage must be within 0..100")
        for iv in item.interventions:
            if str(iv.recommendation_id) == recommendation_id:
                raise ScenarioError(
                    "DUPLICATE_INTERVENTION",
                    "This recommendation is already in the scenario.",
                    {"recommendation_id": recommendation_id},
                )
        entry = ScenarioIntervention(
            id=uuid4(),
            scenario_id=item.scenario.id,
            recommendation_id=UUID(recommendation_id),
            adoption_percentage=adoption_percentage,
            selected=selected,
        )
        item.interventions.append(entry)
        item.intervention_ids.append(UUID(intervention_id))
        item.updated_at = datetime.now(timezone.utc)
        return entry

    # -- O7 remove intervention ----------------------------------------------
    def remove_intervention(
        self, scenario_id: str, facility_id: str, scenario_intervention_id: str
    ) -> None:
        item = self._get(scenario_id, facility_id)
        for idx, iv in enumerate(item.interventions):
            if str(iv.id) == scenario_intervention_id:
                del item.interventions[idx]
                del item.intervention_ids[idx]
                item.updated_at = datetime.now(timezone.utc)
                return
        raise ScenarioError("NOT_FOUND", "Scenario intervention not found.")

    # -- clone ----------------------------------------------------------------
    def clone(self, scenario_id: str, facility_id: str, *, new_name: str | None = None) -> StoredScenario:
        src = self._get(scenario_id, facility_id)
        # The clone inherits the SOURCE facility (never the route placeholder),
        # so tenant resolution on the clone resolves to a real organization.
        owner_facility = src.facility_id
        scenario = src.scenario.model_copy(update={
            "id": uuid4(),
            "name": new_name or f"{src.scenario.name} (clone)",
            "created_at": datetime.now(timezone.utc),
        })
        item = StoredScenario(
            scenario=scenario,
            facility_id=owner_facility,
            interventions=[iv.model_copy(update={"id": uuid4(), "scenario_id": scenario.id})
                           for iv in src.interventions],
            intervention_ids=list(src.intervention_ids),
            baseline_interventions=[iv.model_copy(update={"id": uuid4(), "scenario_id": scenario.id})
                                    for iv in src.baseline_interventions],
            baseline_intervention_ids=list(src.baseline_intervention_ids),
        )
        self._items[scenario.id] = item
        return item

    # -- restore (revert to creation snapshot) -------------------------------
    def restore(self, scenario_id: str, facility_id: str) -> StoredScenario:
        item = self._get(scenario_id, facility_id)
        item.interventions = [
            iv.model_copy(update={"id": uuid4(), "scenario_id": item.scenario.id})
            for iv in item.baseline_interventions
        ]
        item.intervention_ids = list(item.baseline_intervention_ids)
        item.updated_at = datetime.now(timezone.utc)
        return item

    # -- snapshot management ------------------------------------------------
    def take_baseline(self, scenario_id: str, facility_id: str) -> None:
        item = self._get(scenario_id, facility_id)
        item.baseline_interventions = copy.deepcopy(item.interventions)
        item.baseline_intervention_ids = list(item.intervention_ids)


STORE = ScenarioStore()