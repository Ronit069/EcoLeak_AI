"""Module F - Carbon Accounting Engine (deterministic).

    CO2e = normalized_activity_value x total_co2e_factor

Requirements honoured here:
- Scope 1 (direct fuels/owned sources), Scope 2 (purchased electricity),
  selected Scope 3 (materials, transport, waste, packaging, water).
- Aggregation by facility / process / source / scope / reporting period.
- Missing factor => explicit ``unresolved`` result, never a fabricated value.
- On-site generation and exported electricity kept in separate ledgers to avoid
  double counting against purchased grid electricity.
- Every calculation retains factor id, version, source and year for
  reproducibility after factors update.

No ML, no LLM. Pure Decimal arithmetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from contracts.schemas import (
    ActivityData,
    ConfidenceLevel,
    EmissionCalculation,
    EmissionFactor,
    Facility,
    Process,
    Scope,
)

from .config import EngineConfig
from .ids import deterministic_id, q2, q6, to_decimal
from .units import compatible_factor_unit

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "and", "or", "the", "for", "with", "of", "to", "in", "on", "a", "an",
    "per", "from", "at", "by", "process", "average", "mix",
}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOPWORDS}


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


@dataclass
class CalculationRecord:
    """A single activity -> factor resolution attempt."""

    activity: ActivityData
    factor: EmissionFactor | None
    resolved: bool
    co2e_kg: Decimal | None
    scope: Scope | None
    calculation: EmissionCalculation | None = None
    reason: str | None = None
    ledger: str = "SCOPE"  # SCOPE | ONSITE | EXPORT
    match_score: float = 0.0


@dataclass
class UnresolvedActivity:
    activity_id: str
    activity_category: str
    activity_subcategory: str
    code: str
    reason: str

    def to_issue(self) -> dict:
        return {
            "severity": "WARNING",
            "code": self.code,
            "message": self.reason,
            "field": f"activity_data[{self.activity_id}]",
            "details": {
                "activity_category": self.activity_category,
                "activity_subcategory": self.activity_subcategory,
            },
        }


@dataclass
class CarbonInventory:
    """Aggregated, reproducible carbon inventory for one facility/period."""

    facility_id: str
    reporting_period_id: str
    calculation_version: str
    generated_at: datetime
    records: list[CalculationRecord] = field(default_factory=list)
    unresolved: list[UnresolvedActivity] = field(default_factory=list)
    production: Decimal | None = None
    production_unit: str | None = None
    onsite_generation_kgco2e: Decimal = Decimal("0")
    exported_electricity_kgco2e: Decimal = Decimal("0")
    exported_electricity_count: int = 0
    onsite_generation_count: int = 0
    data_quality_score: Decimal | None = None

    # -- derived aggregates -------------------------------------------------
    def _resolved_in_scope(self) -> Iterable[CalculationRecord]:
        return (r for r in self.records if r.resolved and r.ledger == "SCOPE" and r.co2e_kg is not None)

    def scope_total(self, scope: Scope) -> Decimal:
        return sum((r.co2e_kg for r in self._resolved_in_scope() if r.scope == scope), Decimal("0"))

    @property
    def scope1_kgco2e(self) -> Decimal:
        return self.scope_total(Scope.SCOPE_1)

    @property
    def scope2_kgco2e(self) -> Decimal:
        return self.scope_total(Scope.SCOPE_2)

    @property
    def scope3_kgco2e(self) -> Decimal:
        return self.scope_total(Scope.SCOPE_3)

    @property
    def total_kgco2e(self) -> Decimal:
        return self.scope1_kgco2e + self.scope2_kgco2e + self.scope3_kgco2e

    @property
    def operational_kgco2e(self) -> Decimal:
        """Scope 1 + Scope 2 (the Phase 0 hotspot boundary)."""
        return self.scope1_kgco2e + self.scope2_kgco2e

    @property
    def carbon_intensity(self) -> Decimal | None:
        if self.production is None or self.production <= 0:
            return None
        return self.total_kgco2e / self.production

    def by_process(self, scopes: set[Scope] | None = None) -> dict[str | None, Decimal]:
        out: dict[str | None, Decimal] = {}
        for r in self._resolved_in_scope():
            if scopes is not None and r.scope not in scopes:
                continue
            key = str(r.activity.process_id) if r.activity.process_id else None
            out[key] = out.get(key, Decimal("0")) + r.co2e_kg
        return out

    def by_category(self, scopes: set[Scope] | None = None) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for r in self._resolved_in_scope():
            if scopes is not None and r.scope not in scopes:
                continue
            key = r.activity.activity_category.value
            out[key] = out.get(key, Decimal("0")) + r.co2e_kg
        return out

    def by_source(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for r in self._resolved_in_scope():
            key = r.activity.source_name or r.activity.activity_subcategory
            out[key] = out.get(key, Decimal("0")) + r.co2e_kg
        return out

    def waste_emissions_by_process(self) -> dict[str | None, Decimal]:
        out: dict[str | None, Decimal] = {}
        for r in self.records:
            if not r.resolved or r.co2e_kg is None:
                continue
            if r.activity.activity_category.value != "WASTE":
                continue
            key = str(r.activity.process_id) if r.activity.process_id else None
            out[key] = out.get(key, Decimal("0")) + r.co2e_kg
        return out

    def process_emissions_all_scopes(self) -> dict[str | None, Decimal]:
        out: dict[str | None, Decimal] = {}
        for r in self.records:
            if not r.resolved or r.co2e_kg is None or r.ledger != "SCOPE":
                continue
            key = str(r.activity.process_id) if r.activity.process_id else None
            out[key] = out.get(key, Decimal("0")) + r.co2e_kg
        return out

    def factor_provenance(self) -> dict[str, dict]:
        prov: dict[str, dict] = {}
        for r in self.records:
            if r.factor is None:
                continue
            prov[str(r.factor.id)] = {
                "factor_id": str(r.factor.id),
                "factor_code": r.factor.factor_code,
                "version": r.factor.version,
                "source_name": r.factor.source_name,
                "source_year": r.factor.source_year,
                "scope": r.factor.scope.value,
                "total_co2e_factor": str(r.factor.total_co2e_factor),
                "input_unit": r.factor.input_unit,
            }
        return prov

    def inventory_summary(self) -> dict:
        return {
            "scope1_kgco2e": q6(self.scope1_kgco2e),
            "scope2_kgco2e": q6(self.scope2_kgco2e),
            "scope3_kgco2e": q6(self.scope3_kgco2e),
            "total_kgco2e": q6(self.total_kgco2e),
            "carbon_intensity": q6(self.carbon_intensity) if self.carbon_intensity is not None else None,
            "production_unit": self.production_unit,
            "generated_at": self.generated_at,
        }


_LEVEL_SCORE = {
    ConfidenceLevel.HIGH: Decimal("100"),
    ConfidenceLevel.MEDIUM: Decimal("75"),
    ConfidenceLevel.LOW: Decimal("50"),
}


class CarbonAccountingEngine:
    """Module F calculator. Deterministic and side-effect free."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()

    # -- factor selection ---------------------------------------------------
    @staticmethod
    def _region_match(
        factor: EmissionFactor, country: str | None, state: str | None
    ) -> str:
        """P3-03: classify factor region specificity against the facility."""
        fcountry = (factor.region_country or "").strip().lower()
        fstate = (factor.region_state or "").strip().lower()
        if not fcountry and not fstate:
            return "GENERIC"
        if not country:
            return "GENERIC"
        if fcountry == country.strip().lower():
            if fstate and (not state or fstate != state.strip().lower()):
                return "NATIONAL_FALLBACK"
            return "MATCH"
        return "MISMATCH"

    @staticmethod
    def _validity(factor: EmissionFactor, period_start: date | None, period_end: date | None) -> str:
        """P3-02: is the factor valid within the reporting period?"""
        if factor.valid_from is None and factor.valid_to is None:
            return "UNKNOWN"
        if factor.valid_to is not None and period_start is not None and factor.valid_to < period_start:
            return "OUT_OF_WINDOW"
        if factor.valid_from is not None and period_end is not None and factor.valid_from > period_end:
            return "OUT_OF_WINDOW"
        return "IN_WINDOW"

    def select_factor(
        self,
        activity: ActivityData,
        factors: list[EmissionFactor],
        *,
        facility_country: str | None = None,
        facility_state: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> tuple[EmissionFactor | None, float, str | None, dict]:
        value = activity.normalized_value if activity.normalized_value is not None else activity.original_value
        if value is None:
            return None, 0.0, "MISSING_ACTIVITY_VALUE", {}
        if value < 0:
            return None, 0.0, "NEGATIVE_ACTIVITY", {}

        category = activity.activity_category.value.upper()
        candidates = [
            f
            for f in factors
            if f.category.upper() == category
            and f.active
            and compatible_factor_unit(activity.normalized_unit, f.input_unit)
        ]
        if not candidates:
            return None, 0.0, "EMISSION_FACTOR_NOT_FOUND", {}

        region_rank = {"MATCH": 3, "GENERIC": 2, "NATIONAL_FALLBACK": 1, "MISMATCH": 0}
        window_rank = {"IN_WINDOW": 2, "UNKNOWN": 1, "OUT_OF_WINDOW": 0}
        scored: list[tuple] = []
        for f in candidates:
            sim = max(
                _overlap(activity.activity_subcategory, f.item_name),
                _overlap(activity.activity_subcategory, f.subcategory),
                _overlap(activity.activity_subcategory or "", f.item_name + " " + f.subcategory),
            )
            region = self._region_match(f, facility_country, facility_state)
            window = self._validity(f, period_start, period_end)
            year = f.source_year or 0
            version_rank = 1 if f.version else 0
            scored.append(
                (
                    sim,
                    region_rank.get(region, 0) if self.config.prefer_region_match else 1,
                    window_rank.get(window, 1) if self.config.prefer_validity_window else 1,
                    year,
                    version_rank,
                    f.version,
                    f,
                    region,
                    window,
                )
            )
        scored.sort(key=lambda x: x[:6], reverse=True)
        (best_sim, _, _, _, _, _, best, region, window) = scored[0]
        if best_sim < self.config.factor_match_threshold:
            if len(candidates) == 1 and self.config.allow_single_candidate_fallback:
                # Only one active factor for this category + unit; accept it as
                # the approved fallback but flag it (P3-06 lowers confidence).
                return best, best_sim, None, {
                    "match_basis": "SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK",
                    "region": region,
                    "validity": window,
                }
            return None, best_sim, "NO_MATCHING_FACTOR", {}
        return best, best_sim, None, {
            "match_basis": "DESCRIPTION_MATCH",
            "region": region,
            "validity": window,
        }

    # -- calculation --------------------------------------------------------
    def calculate(
        self,
        *,
        facility: Facility,
        reporting_period_id: str,
        activity_data: list[ActivityData],
        emission_factors: list[EmissionFactor],
        generated_at: datetime | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> CarbonInventory:
        now = generated_at or datetime.now(timezone.utc)
        inventory = CarbonInventory(
            facility_id=str(facility.id),
            reporting_period_id=str(reporting_period_id),
            calculation_version=self.config.calculation_version,
            generated_at=now,
            production=to_decimal(facility.annual_production),
            production_unit=facility.production_unit,
        )
        confidence_weighted = Decimal("0")
        factor_quality_weighted = Decimal("0")
        weighted_emissions = Decimal("0")

        for activity in activity_data:
            if activity.normalized_value is not None and activity.normalized_value < 0:
                inventory.unresolved.append(
                    UnresolvedActivity(
                        activity_id=str(activity.id),
                        activity_category=activity.activity_category.value,
                        activity_subcategory=activity.activity_subcategory,
                        code="NEGATIVE_ACTIVITY",
                        reason="Negative activity value rejected; no emission calculated.",
                    )
                )
                inventory.records.append(
                    CalculationRecord(activity=activity, factor=None, resolved=False, co2e_kg=None, scope=None,
                                      reason="NEGATIVE_ACTIVITY")
                )
                continue

            factor, score, reason, flags = self.select_factor(
                activity,
                emission_factors,
                facility_country=facility.country,
                facility_state=facility.state,
                period_start=period_start,
                period_end=period_end,
            )
            if factor is None:
                inventory.unresolved.append(
                    UnresolvedActivity(
                        activity_id=str(activity.id),
                        activity_category=activity.activity_category.value,
                        activity_subcategory=activity.activity_subcategory,
                        code=reason or "UNRESOLVED",
                        reason=self._unresolved_message(reason),
                    )
                )
                inventory.records.append(
                    CalculationRecord(activity=activity, factor=None, resolved=False, co2e_kg=None,
                                      scope=None, reason=reason, match_score=score)
                )
                continue

            value = activity.normalized_value if activity.normalized_value is not None else activity.original_value
            assert value is not None
            co2e = q6(to_decimal(value) * factor.total_co2e_factor)  # type: ignore[operator]
            ledger, ledger_methodology = self._ledger_for(activity)
            # P3-02/03/06: record the match quality and lower confidence for
            # weak matches instead of presenting them as exact.
            penalty = 0.0
            if flags.get("match_basis") == "SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK":
                penalty += self.config.factor_fallback_penalty
            region = flags.get("region")
            if region == "MISMATCH":
                penalty += self.config.factor_region_mismatch_penalty
            elif region == "NATIONAL_FALLBACK":
                penalty += self.config.factor_region_national_fallback_penalty
            if flags.get("validity") == "OUT_OF_WINDOW":
                penalty += self.config.factor_validity_penalty
            effective_confidence = (
                max(0.0, float(activity.confidence_score) - penalty)
                if activity.confidence_score is not None
                else None
            )
            scope = factor.scope
            assumptions = {
                "formula": "CO2e = normalized_activity_value * total_co2e_factor",
                "activity_value": str(value),
                "activity_unit": activity.normalized_unit,
                "factor_input_unit": factor.input_unit,
                "factor_code": factor.factor_code,
                "factor_version": factor.version,
                "factor_source": factor.source_name,
                "factor_source_year": factor.source_year,
                "factor_methodology": factor.methodology,
                "calculation_version": self.config.calculation_version,
                "ledger": ledger,
                "ledger_methodology": ledger_methodology,
                "match_score": round(score, 4),
                "factor_region_match": flags.get("region"),
                "factor_validity": flags.get("validity"),
                "confidence_penalty": penalty,
                "original_confidence": (
                    str(activity.confidence_score) if activity.confidence_score is not None else None
                ),
                "effective_confidence": (
                    str(Decimal(str(effective_confidence))) if effective_confidence is not None else None
                ),
                "factor_match_basis": flags.get(
                    "match_basis",
                    "DESCRIPTION_MATCH"
                    if score >= self.config.factor_match_threshold
                    else "SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK",
                ),
            }
            calc = EmissionCalculation(
                id=deterministic_id("calc", activity.id, factor.id, self.config.calculation_version),
                activity_data_id=activity.id,
                emission_factor_id=factor.id,
                calculation_version=self.config.calculation_version,
                scope=scope,
                co2e_kg=co2e,
                calculation_formula="CO2e = normalized_activity_value * total_co2e_factor",
                assumptions=assumptions,
                confidence_score=(
                    Decimal(str(effective_confidence)) if effective_confidence is not None else None
                ),
                calculated_at=now,
            )
            inventory.records.append(
                CalculationRecord(
                    activity=activity, factor=factor, resolved=True, co2e_kg=co2e, scope=scope,
                    calculation=calc, ledger=ledger, match_score=score,
                )
            )

            if ledger == "ONSITE":
                inventory.onsite_generation_kgco2e += co2e
                inventory.onsite_generation_count += 1
            elif ledger == "EXPORT":
                inventory.exported_electricity_kgco2e += co2e
                inventory.exported_electricity_count += 1
            else:
                weighted_emissions += co2e
                if effective_confidence is not None:
                    confidence_weighted += co2e * Decimal(str(effective_confidence))
                if factor.confidence_level is not None:
                    factor_quality_weighted += co2e * _LEVEL_SCORE[factor.confidence_level]

        inventory.data_quality_score = self._data_quality(
            inventory, weighted_emissions, confidence_weighted, factor_quality_weighted
        )
        return inventory

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _unresolved_message(reason: str | None) -> str:
        return {
            "EMISSION_FACTOR_NOT_FOUND": "No active emission factor matches this activity category and unit.",
            "NO_MATCHING_FACTOR": "No emission factor matched the activity description above the confidence threshold.",
            "MISSING_ACTIVITY_VALUE": "Activity has no normalized or original value; emission cannot be calculated.",
            "NEGATIVE_ACTIVITY": "Negative activity value is not permitted.",
        }.get(reason or "", "Activity could not be resolved to an emission factor.")

    @staticmethod
    def _ledger_for(activity: ActivityData) -> tuple[str, str]:
        """P3-04: classify the electricity ledger and record the methodology.

        Only genuine on-site self-consumption goes to the ONSITE ledger (a
        separate ledger to avoid double counting against purchased grid). The
        previous substring list routed ANY text containing "solar"/"renewable"
        AND any "captive" text to ONSITE — silently excluding purchased
        renewable electricity (market-based) and **captive fossil generation**
        (which is really Scope 1) from the totals. Captive/bare-renewable rows
        are now counted in scope (no silent zero).
        """
        if activity.activity_category.value != "ELECTRICITY":
            return "SCOPE", ""
        text = f"{activity.activity_subcategory} {activity.source_name or ''}".lower()
        if any(k in text for k in ("export", "exported", "feed-in", "feed in", "surplus", "net metering")):
            return "EXPORT", "exported generation ledger (outside purchased totals)"
        onsite_markers = ("on-site", "onsite", "self-consum", "rooftop", "behind the meter",
                          "behind-the-meter")
        if any(k in text for k in onsite_markers):
            return (
                "ONSITE",
                "on-site self-consumption kept in a separate ledger (not counted as "
                "purchased grid electricity); accounting methodology recorded",
            )
        return "SCOPE", ""

    @staticmethod
    def _data_quality(
        inventory: CarbonInventory,
        weighted_emissions: Decimal,
        confidence_weighted: Decimal,
        factor_quality_weighted: Decimal,
    ) -> Decimal | None:
        total_activities = len(inventory.records)
        unresolved_ratio = (
            Decimal(len(inventory.unresolved)) / Decimal(total_activities) if total_activities else Decimal("0")
        )
        if weighted_emissions > 0:
            activity_q = confidence_weighted / weighted_emissions
            factor_q = factor_quality_weighted / weighted_emissions
        else:
            scores = [r.activity.confidence_score for r in inventory.records if r.activity.confidence_score is not None]
            activity_q = sum(scores, Decimal("0")) / Decimal(len(scores)) if scores else None
            levels = [_LEVEL_SCORE[r.factor.confidence_level] for r in inventory.records
                      if r.factor is not None and r.factor.confidence_level is not None]
            factor_q = sum(levels, Decimal("0")) / Decimal(len(levels)) if levels else None
        if activity_q is None and factor_q is None:
            return None
        activity_q = activity_q if activity_q is not None else Decimal("60")
        factor_q = factor_q if factor_q is not None else Decimal("60")
        completeness = Decimal("100") * (Decimal("1") - unresolved_ratio)
        score = Decimal("0.55") * activity_q + Decimal("0.35") * factor_q + Decimal("0.10") * completeness
        return q2(max(Decimal("0"), min(Decimal("100"), score)))
