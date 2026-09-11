"""Module K - Cost & CO2 Impact Simulator.

Requirements honoured:
- ``adoption_percentage`` parameter (0..100); adoption 0 = no change, > 100 = reject.
- Recomputes projected CO2e, cost, energy and waste against the baseline.
- ``payback = CAPEX / annual_saving`` and, per the Module K edge-case table, when
  ``annual_saving <= 0`` the payback is reported as **UNAVAILABLE**, never a
  normal number.
- Combined interventions apply **sequentially** on the remaining baseline, so the
  same baseline tonne is never reduced twice (no double-counted savings).
- Projected emissions are floored at 0; a saving larger than the baseline is
  capped and flagged as an invalid model.
- CO2 saving may be negative (additional emissions) and is reported as such.

Pure Decimal arithmetic. No ML, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from contracts.schemas import (
    CircularIntervention,
    ImpactAssessment,
    Scope,
)

from .carbon import CarbonInventory
from .config import SimulatorConfig
from .errors import InvalidScenarioError, NegativeActivityError
from .ids import deterministic_id, q2, q6, to_decimal

_ENERGY_CATEGORIES = {"ELECTRICITY", "FUEL", "STEAM"}
_WASTE_CATEGORIES = {"WASTE"}

PAYBACK_AVAILABLE = "AVAILABLE"
PAYBACK_UNAVAILABLE = "UNAVAILABLE"
PAYBACK_INCOMPLETE = "INCOMPLETE"


@dataclass
class InterventionSelection:
    """One selected intervention plus its scenario adoption percentage."""

    intervention: CircularIntervention
    adoption_percentage: Decimal = Decimal("100")
    selected: bool = True
    capex_override: Decimal | None = None


@dataclass
class _State:
    activity: object
    factor: object | None
    quantity: Decimal
    co2e_kg: Decimal
    process_id: str | None
    category: str
    unit: str


@dataclass
class InterventionSim:
    intervention_id: str
    intervention_code: str | None
    title: str
    adoption_percentage: Decimal
    capex: Decimal | None
    baseline_emissions_kg: Decimal
    projected_emissions_kg: Decimal
    co2_saving_kg: Decimal
    baseline_cost: Decimal | None
    projected_cost: Decimal | None
    annual_saving: Decimal | None
    energy_saving: Decimal
    energy_saving_unit: str
    waste_reduction: Decimal
    waste_reduction_unit: str
    payback_years: Decimal | None
    payback_status: str
    payback_reason: str | None
    cost_per_tonne_co2_avoided: Decimal | None
    assumptions: dict


@dataclass
class SimulationResult:
    scenario_id: str | None
    assessment: ImpactAssessment
    interventions: list[InterventionSim] = field(default_factory=list)
    payback_status: str = PAYBACK_AVAILABLE
    payback_reason: str | None = None
    over_budget: bool = False
    issues: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Plain dict with native Decimal/datetime values.

        Encode with :func:`engine.serialization.to_jsonable` for the wire
        representation (numbers, not strings).
        """
        return {
            "scenario_id": self.scenario_id,
            "assessment": self.assessment.model_dump(mode="python"),
            "interventions": [
                {
                    "intervention_id": i.intervention_id,
                    "intervention_code": i.intervention_code,
                    "title": i.title,
                    "adoption_percentage": i.adoption_percentage,
                    "capex": i.capex,
                    "baseline_emissions_kg": i.baseline_emissions_kg,
                    "projected_emissions_kg": i.projected_emissions_kg,
                    "co2_saving_kg": i.co2_saving_kg,
                    "baseline_cost": i.baseline_cost,
                    "projected_cost": i.projected_cost,
                    "annual_saving": i.annual_saving,
                    "payback_years": i.payback_years,
                    "payback_status": i.payback_status,
                    "payback_reason": i.payback_reason,
                    "cost_per_tonne_co2_avoided": i.cost_per_tonne_co2_avoided,
                    "energy_saving": i.energy_saving,
                    "waste_reduction": i.waste_reduction,
                    "assumptions": i.assumptions,
                }
                for i in self.interventions
            ],
            "payback_status": self.payback_status,
            "payback_reason": self.payback_reason,
            "over_budget": self.over_budget,
            "issues": self.issues,
        }


class ImpactSimulator:
    """Module K. Sequential, quantity-based scenario simulation."""

    def __init__(self, config: SimulatorConfig | None = None) -> None:
        self.config = config or SimulatorConfig()

    # -- public API ---------------------------------------------------------
    def simulate(
        self,
        *,
        inventory: CarbonInventory,
        selections: Iterable[InterventionSelection],
        scenario_id: str | None = None,
        facility_id: str | None = None,
        reporting_period_id: str | None = None,
        budget_limit: Decimal | None = None,
        target_reduction_pct: Decimal | None = None,
        scope_boundary: set[Scope] | None = None,
        processes: list | None = None,
        generated_at: datetime | None = None,
    ) -> SimulationResult:
        now = generated_at or datetime.now(timezone.utc)
        selections = list(selections)
        self._validate_selections(selections)
        # The frozen ImpactAssessment.scenario_id is a UUID; allow callers to pass
        # a human label and map it deterministically.
        scenario_uuid = self._scenario_uuid(scenario_id, facility_id, reporting_period_id)

        states = self._build_states(inventory)
        baseline_emissions = self._emissions(states, scope_boundary)
        baseline_cost, cost_complete = self._cost(states)

        issues: list[dict] = []
        if not cost_complete:
            issues.append(
                {
                    "severity": "INFO",
                    "code": "PARTIAL_COST_DATA",
                    "message": "Some activities have no configured price; annual_saving covers priced activities only.",
                }
            )

        sims: list[InterventionSim] = []
        for selection in selections:
            if not selection.selected:
                continue
            before_emissions = self._emissions(states, scope_boundary)
            before_cost, _ = self._cost(states)
            target_states, matched = self._targets(selection.intervention, states, processes or [])
            fractions = self._fractions(selection, target_states)

            for state in target_states:
                frac = fractions.get(state.category, fractions.get("ALL", Decimal("0")))
                if frac <= 0:
                    continue
                old_qty = state.quantity
                new_qty = old_qty * (Decimal("1") - frac)
                if new_qty < 0:
                    new_qty = Decimal("0")
                state.quantity = new_qty
                if state.factor is not None:
                    state.co2e_kg = q6(new_qty * state.factor.total_co2e_factor)

            after_emissions = self._emissions(states, scope_boundary)
            after_cost, _ = self._cost(states)
            sims.append(
                self._build_intervention_sim(
                    selection, before_emissions, after_emissions, before_cost, after_cost,
                    target_states, matched, now
                )
            )

        projected_emissions = self._emissions(states, scope_boundary)
        total_saving = baseline_emissions - projected_emissions
        if self.config.cap_saving_at_baseline and total_saving > baseline_emissions:
            issues.append(
                {
                    "severity": "WARNING",
                    "code": "CO2_SAVING_EXCEEDS_BASELINE",
                    "message": "Modelled CO2 saving exceeded baseline emissions; capped to baseline.",
                }
            )
            total_saving = baseline_emissions
            projected_emissions = Decimal("0")

        final_cost, _ = self._cost(states)
        annual_saving = (baseline_cost - final_cost) if (baseline_cost is not None and final_cost is not None) else None
        total_capex = sum((s.capex for s in sims if s.capex is not None), Decimal("0"))

        payback, payback_status, payback_reason = self._payback(total_capex, annual_saving, bool(sims))
        if total_saving <= 0:
            payback_status = PAYBACK_UNAVAILABLE
            payback_reason = "Annual CO2 saving is zero or negative; no financial payback is estimated."

        reduction_percent = (
            q6(total_saving / baseline_emissions * Decimal("100")) if baseline_emissions > 0 else None
        )

        over_budget = budget_limit is not None and total_capex > budget_limit
        if over_budget:
            issues.append(
                {
                    "severity": "WARNING",
                    "code": "BUDGET_EXCEEDED",
                    "message": f"Total CAPEX {total_capex} exceeds budget limit {budget_limit}.",
                }
            )
        if target_reduction_pct is not None and reduction_percent is not None and reduction_percent < target_reduction_pct:
            issues.append(
                {
                    "severity": "INFO",
                    "code": "TARGET_NOT_MET",
                    "message": (
                        f"Projected reduction {reduction_percent}% is below the target "
                        f"{target_reduction_pct}%. Maximum achievable with current selections is shown."
                    ),
                }
            )

        assessment = ImpactAssessment(
            id=deterministic_id("impact", scenario_uuid, *(s.intervention_id for s in sims)),
            scenario_id=scenario_uuid,
            baseline_emissions_kg=q6(baseline_emissions),
            projected_emissions_kg=q6(max(Decimal("0"), projected_emissions)),
            total_co2_saving_kg=q6(total_saving),
            reduction_percent=reduction_percent,
            total_capex=q6(total_capex),
            annual_saving=q6(annual_saving) if annual_saving is not None else None,
            payback_years=q2(payback) if payback is not None else None,
            generated_at=now,
        )
        return SimulationResult(
            scenario_id=scenario_uuid,
            assessment=assessment,
            interventions=sims,
            payback_status=payback_status,
            payback_reason=payback_reason,
            over_budget=over_budget,
            issues=issues,
        )

    # -- validation ---------------------------------------------------------
    @staticmethod
    def _scenario_uuid(scenario_id, facility_id, reporting_period_id) -> str:
        if scenario_id:
            try:
                return str(UUID(str(scenario_id)))
            except (ValueError, AttributeError, TypeError):
                return deterministic_id("scenario", facility_id, reporting_period_id, scenario_id)
        return deterministic_id("scenario", facility_id, reporting_period_id)

    @staticmethod
    def _validate_selections(selections: list[InterventionSelection]) -> None:
        seen: set[str] = set()
        for s in selections:
            adoption = to_decimal(s.adoption_percentage)
            if adoption is None or adoption < 0 or adoption > 100:
                raise InvalidScenarioError(
                    "adoption_percentage must be between 0 and 100.",
                    {"intervention_id": str(s.intervention.id), "adoption_percentage": str(adoption)},
                )
            key = str(s.intervention.id)
            if key in seen:
                raise InvalidScenarioError(
                    "Duplicate intervention in scenario; each intervention may appear once.",
                    {"intervention_id": key},
                )
            seen.add(key)

    # -- state helpers ------------------------------------------------------
    def _build_states(self, inventory: CarbonInventory) -> list[_State]:
        states: list[_State] = []
        for r in inventory.records:
            if r.ledger != "SCOPE":
                continue
            activity = r.activity
            qty = activity.normalized_value if activity.normalized_value is not None else activity.original_value
            if qty is None:
                continue
            if qty < 0:
                raise NegativeActivityError(
                    "Negative activity value cannot be simulated.",
                    {"activity_id": str(activity.id)},
                )
            states.append(
                _State(
                    activity=activity,
                    factor=r.factor,
                    quantity=to_decimal(qty),  # type: ignore[arg-type]
                    co2e_kg=r.co2e_kg or Decimal("0"),
                    process_id=str(activity.process_id) if activity.process_id else None,
                    category=activity.activity_category.value,
                    unit=activity.normalized_unit,
                )
            )
        return states

    @staticmethod
    def _emissions(states: list[_State], scope_boundary: set[Scope] | None) -> Decimal:
        total = Decimal("0")
        for s in states:
            if scope_boundary is not None and s.factor is not None and s.factor.scope not in scope_boundary:
                continue
            total += s.co2e_kg
        return total

    def _cost(self, states: list[_State]) -> tuple[Decimal | None, bool]:
        total = Decimal("0")
        complete = True
        priced = 0
        for s in states:
            price = self.config.cost_model.price_for(s.category, s.unit)
            if price is None:
                if s.quantity > 0:
                    complete = False
                continue
            total += s.quantity * Decimal(str(price))
            priced += 1
        if priced == 0:
            return None, False
        return total, complete

    # -- targeting + reductions --------------------------------------------
    def _targets(
        self, intervention: CircularIntervention, states: list[_State], processes: list
    ) -> tuple[list[_State], list[str]]:
        pc = (intervention.process_category or "").strip().lower()
        matched_pids: list[str] = []
        if pc:
            for p in processes:
                name = (p.name or "").lower()
                cat = (p.process_category or "").lower()
                if pc in name or name in pc or pc == cat:
                    matched_pids.append(str(p.id))
        candidates = [s for s in states if s.process_id in matched_pids] if matched_pids else list(states)

        has_energy = intervention.energy_reduction_min_pct is not None or intervention.energy_reduction_max_pct is not None
        has_waste = intervention.waste_reduction_min_pct is not None or intervention.waste_reduction_max_pct is not None

        selected: list[_State] = []
        if has_energy:
            selected.extend(s for s in candidates if s.category in _ENERGY_CATEGORIES)
        if has_waste:
            selected.extend(s for s in candidates if s.category in _WASTE_CATEGORIES)
        if not selected:
            selected = [s for s in candidates if s.category in (_ENERGY_CATEGORIES | _WASTE_CATEGORIES)] or list(candidates)
        return selected, matched_pids

    def _fractions(self, selection: InterventionSelection, targets: list[_State]) -> dict[str, Decimal]:
        iv = selection.intervention
        adoption = to_decimal(selection.adoption_percentage) / Decimal("100")
        fractions: dict[str, Decimal] = {}

        if self.config.reduction_basis == "CO2_ONLY":
            pct = self._pct(iv.expected_co2_reduction_min_pct, iv.expected_co2_reduction_max_pct)
            return {"ALL": self._cap(pct * adoption)}
        if not targets:
            return fractions
        # energy states
        e_pct = self._pct(iv.energy_reduction_min_pct, iv.energy_reduction_max_pct)
        if e_pct <= 0:
            e_pct = self._pct(iv.expected_co2_reduction_min_pct, iv.expected_co2_reduction_max_pct)
        for cat in {s.category for s in targets if s.category in _ENERGY_CATEGORIES}:
            fractions[cat] = self._cap(e_pct * adoption)
        w_pct = self._pct(iv.waste_reduction_min_pct, iv.waste_reduction_max_pct)
        if w_pct <= 0:
            w_pct = self._pct(iv.expected_co2_reduction_min_pct, iv.expected_co2_reduction_max_pct)
        for cat in {s.category for s in targets if s.category in _WASTE_CATEGORIES}:
            fractions[cat] = self._cap(w_pct * adoption)
        return fractions

    def _pct(self, low, high) -> Decimal:
        lo = to_decimal(low)
        hi = to_decimal(high)
        if lo is None and hi is None:
            return Decimal("0")
        if lo is None:
            return hi / Decimal("100")  # type: ignore[operator]
        if hi is None:
            return lo / Decimal("100")
        if self.config.reduction_pct_strategy == "MIN":
            chosen = lo
        elif self.config.reduction_pct_strategy == "MID":
            chosen = (lo + hi) / Decimal("2")
        else:
            chosen = hi
        return chosen / Decimal("100")

    def _cap(self, fraction: Decimal) -> Decimal:
        cap = Decimal(str(self.config.max_reduction_fraction))
        if fraction < 0:
            return Decimal("0")
        if fraction > cap:
            return cap
        return fraction

    # -- per-intervention output -------------------------------------------
    def _build_intervention_sim(
        self,
        selection: InterventionSelection,
        before_emissions: Decimal,
        after_emissions: Decimal,
        before_cost: Decimal | None,
        after_cost: Decimal | None,
        targets: list[_State],
        matched_pids: list[str],
        now: datetime,
    ) -> InterventionSim:
        iv = selection.intervention
        capex = selection.capex_override
        if capex is None:
            capex = self._capex_point(iv)
        co2_saving = before_emissions - after_emissions
        annual_saving = (
            before_cost - after_cost if (before_cost is not None and after_cost is not None) else None
        )
        payback, status, reason = self._payback(capex, annual_saving, True)

        # Reconstruct the saved quantity from the fraction actually applied
        # (targets have already been mutated).
        energy_saving = self._quantity_saved(targets, _ENERGY_CATEGORIES, selection)
        waste_reduction = self._quantity_saved(targets, _WASTE_CATEGORIES, selection)
        units = {s.unit for s in targets if s.category in _ENERGY_CATEGORIES}
        energy_unit = units.pop() if len(units) == 1 else ("mixed" if units else "n/a")
        waste_units = {s.unit for s in targets if s.category in _WASTE_CATEGORIES}
        waste_unit = waste_units.pop() if len(waste_units) == 1 else ("mixed" if waste_units else "n/a")

        cost_per_tonne = None
        if capex is not None and co2_saving > 0:
            cost_per_tonne = capex / (co2_saving / Decimal("1000"))

        assumptions = {
            "method": "sequential quantity reduction on remaining baseline (no double counting)",
            "adoption_percentage": str(to_decimal(selection.adoption_percentage)),
            "capex_strategy": self.config.capex_strategy,
            "reduction_pct_strategy": self.config.reduction_pct_strategy,
            "reduction_basis": self.config.reduction_basis,
            "static_prices": self.config.static_prices,
            "cost_model_note": self.config.cost_model.assumption_note,
            "currency": self.config.cost_model.currency,
            "target_processes": matched_pids,
            "target_categories": sorted({s.category for s in targets}),
            "co2_saving_basis": "baseline minus projected emissions after quantity reductions",
            "cost_per_tonne_co2_avoided_basis": "CAPEX / first-year tCO2e avoided",
            "payback_rule": "payback = CAPEX / annual_saving; None (UNAVAILABLE) when annual_saving <= 0",
        }
        return InterventionSim(
            intervention_id=str(iv.id),
            intervention_code=iv.intervention_code,
            title=iv.title,
            adoption_percentage=to_decimal(selection.adoption_percentage),
            capex=capex,
            baseline_emissions_kg=q6(before_emissions),
            projected_emissions_kg=q6(after_emissions),
            co2_saving_kg=q6(co2_saving),
            baseline_cost=q6(before_cost) if before_cost is not None else None,
            projected_cost=q6(after_cost) if after_cost is not None else None,
            annual_saving=q6(annual_saving) if annual_saving is not None else None,
            energy_saving=q6(energy_saving),
            energy_saving_unit=energy_unit or "n/a",
            waste_reduction=q6(waste_reduction),
            waste_reduction_unit=waste_unit or "n/a",
            payback_years=q2(payback) if payback is not None else None,
            payback_status=status,
            payback_reason=reason,
            cost_per_tonne_co2_avoided=q2(cost_per_tonne) if cost_per_tonne is not None else None,
            assumptions=assumptions,
        )

    def _quantity_saved(self, targets: list[_State], categories: set[str], selection: InterventionSelection) -> Decimal:
        # Recompute the saved quantity from the applied fraction (targets already mutated).
        fractions = self._fractions(selection, targets)
        total = Decimal("0")
        for s in targets:
            if s.category not in categories:
                continue
            frac = fractions.get(s.category, Decimal("0"))
            if frac <= 0:
                continue
            # current qty = old*(1-frac)  => saved = current*frac/(1-frac)
            denom = Decimal("1") - frac
            if denom <= 0:
                continue
            total += s.quantity * frac / denom
        return total

    def _capex_point(self, iv: CircularIntervention) -> Decimal | None:
        lo = to_decimal(iv.min_capex)
        hi = to_decimal(iv.max_capex)
        if lo is None and hi is None:
            return None
        if lo is None:
            return hi
        if hi is None:
            return lo
        if self.config.capex_strategy == "MIN":
            return lo
        if self.config.capex_strategy == "MAX":
            return hi
        return (lo + hi) / Decimal("2")

    @staticmethod
    def _payback(capex: Decimal | None, annual_saving: Decimal | None, has_interventions: bool) -> tuple[Decimal | None, str, str | None]:
        if not has_interventions:
            return None, PAYBACK_INCOMPLETE, "No selected interventions."
        if capex is None:
            return None, PAYBACK_INCOMPLETE, "CAPEX is unavailable; financial analysis incomplete."
        if annual_saving is None:
            return None, PAYBACK_INCOMPLETE, "Annual saving could not be computed (missing cost data)."
        if annual_saving <= 0:
            return None, PAYBACK_UNAVAILABLE, "Annual saving is zero or negative; no financial payback estimated."
        if capex == 0:
            return Decimal("0"), PAYBACK_AVAILABLE, "CAPEX is zero; payback is immediate."
        return capex / annual_saving, PAYBACK_AVAILABLE, None
