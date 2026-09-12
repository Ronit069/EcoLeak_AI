"""Configurable engine policy.

The requirements doc (Module G) specifies the hotspot composite as

    w1(Carbon Contribution) + w2(Carbon Intensity) + w3(Inefficiency)
    + w4(Waste Ratio) + w5(Improvement Potential)

but does not publish numeric weights or thresholds. Every weight, threshold and
estimator strategy therefore lives here as an explicit, overridable setting -
nothing is hardcoded in the calculation logic. Defaults are documented and are
the values used by the Phase 0 fixture.

Defaults chosen against the Phase 0 fixture:
- Severity thresholds 80/60/40 are configurable defaults. NOTE (B3 decision):
  they do NOT reproduce the mock labels exactly — the live engine scores Boiler
  76.4 (HIGH) where the mock shows CRITICAL 88.5. The mock is an illustrative
  reference (shape/rank/contribution), not an exact reproduction target; see
  CONTRACTS_README "Phase 1 change requests" and tests/test_real_factors.py.
- Improvement reference of 20 percentage points approximates the fixture's
  improvement-potential scores.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ConfigBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class HotspotWeights(_ConfigBase):
    """Composite hotspot weights (need not sum to 1; present weights are renormalized)."""

    carbon_contribution: float = Field(default=0.30, ge=0)
    carbon_intensity: float = Field(default=0.15, ge=0)
    inefficiency: float = Field(default=0.20, ge=0)
    waste_ratio: float = Field(default=0.15, ge=0)
    improvement_potential: float = Field(default=0.20, ge=0)

    @model_validator(mode="after")
    def _validate(self) -> "HotspotWeights":
        if sum(self.as_dict().values()) <= 0:
            raise ValueError("At least one hotspot weight must be > 0")
        return self

    def as_dict(self) -> dict[str, float]:
        return {
            "carbon_contribution": self.carbon_contribution,
            "carbon_intensity": self.carbon_intensity,
            "inefficiency": self.inefficiency,
            "waste_ratio": self.waste_ratio,
            "improvement_potential": self.improvement_potential,
        }


class SeverityThresholds(_ConfigBase):
    """Lower bounds for each severity band (score 0-100)."""

    critical: float = Field(default=80.0, ge=0, le=100)
    high: float = Field(default=60.0, ge=0, le=100)
    moderate: float = Field(default=40.0, ge=0, le=100)

    @model_validator(mode="after")
    def _validate(self) -> "SeverityThresholds":
        if not (self.critical >= self.high >= self.moderate >= 0):
            raise ValueError("Severity thresholds must satisfy critical >= high >= moderate >= 0")
        return self

    def classify(self, score: float) -> str:
        if score >= self.critical:
            return "CRITICAL"
        if score >= self.high:
            return "HIGH"
        if score >= self.moderate:
            return "MODERATE"
        return "LOW"


class HotspotConfig(_ConfigBase):
    weights: HotspotWeights = Field(default_factory=HotspotWeights)
    severity: SeverityThresholds = Field(default_factory=SeverityThresholds)
    group_by: Literal["PROCESS", "SOURCE", "CATEGORY"] = "PROCESS"

    # Normalization of the raw carbon intensity (kgCO2e / production unit).
    intensity_reference: Literal["MAX_WITHIN_SET", "BENCHMARK"] = "MAX_WITHIN_SET"

    # How the inefficiency component is estimated when no benchmark is supplied.
    #   BENCHMARK        -> only from an explicit benchmark row (else unavailable)
    #   INTENSITY_PROXY  -> deterministic within-set carbon-intensity ranking proxy
    #   UNAVAILABLE      -> never estimate (component is skipped)
    inefficiency_strategy: Literal["BENCHMARK", "INTENSITY_PROXY", "UNAVAILABLE"] = "INTENSITY_PROXY"

    waste_ratio_strategy: Literal["EMISSIONS_RATIO", "UNAVAILABLE"] = "EMISSIONS_RATIO"

    # Intervention reduction ceiling (percent) that maps to a 100/100 improvement score.
    improvement_reference_pct: float = Field(default=20.0, gt=0)

    # Missing-component policy. When True the composite renormalizes over the
    # components that are available (edge case: "adapt to missing benchmark").
    reweight_missing: bool = True
    # Minimum number of available components required before a score is emitted.
    min_components: int = Field(default=1, ge=1, le=5)

    # On-site generation accounting. On-site self-consumption is kept in its own
    # ledger and excluded from purchased totals to avoid double counting.
    onsite_ledger_only: bool = True


class CostModel(_ConfigBase):
    """Resource unit costs used by the Module K simulator.

    These are *assumptions*, surfaced in every simulation response. They are not
    part of the frozen contract and can be replaced by P2 cost data.
    """

    currency: str = "INR"
    # price per activity normalized unit, keyed "CATEGORY:unit" (lowercase unit)
    unit_prices: dict[str, float] = Field(
        default_factory=lambda: {
            "electricity:kwh": 8.0,
            "fuel:m3": 45.0,
            "fuel:l": 90.0,
            "water:m3": 40.0,
            "waste:kg": 3.0,
            "transport:tonne_km": 4.0,
        }
    )
    # fallback per category (per normalized unit) when no unit-specific price exists
    category_prices: dict[str, float] = Field(default_factory=dict)
    # P3-08: provenance for the price assumptions (this is a fixture source, not
    # a live P2 cost feed — recorded so every "costed" number is traceable).
    price_source: str = "EcoLeak P4/Module-K demo tariff fixture (static)"
    price_version: str = "p4-tariff-1.0"
    price_valid_year: int = 2026
    assumption_note: str = (
        "Static mock resource prices (Phase 1 fixture). Replace with P2 cost data; "
        "annual_saving is unavailable if a targeted activity has no price."
    )

    def price_for(self, category: str, unit: str) -> float | None:
        key = f"{category.strip().lower()}:{(unit or '').strip().lower()}"
        if key in self.unit_prices:
            return self.unit_prices[key]
        return self.category_prices.get(category.strip().upper())


class SimulatorConfig(_ConfigBase):
    # How a point CAPEX estimate is derived from the intervention's min/max range.
    capex_strategy: Literal["MIN", "MID", "MAX"] = "MID"
    # Which end of an expected-impact range to apply (MAX = high case, matching the mock).
    reduction_pct_strategy: Literal["MIN", "MID", "MAX"] = "MAX"
    # How quantity reductions are selected: energy/waste percentages when present,
    # otherwise fall back to the intervention CO2 percentage.
    reduction_basis: Literal["ENERGY_WASTE_THEN_CO2", "CO2_ONLY"] = "ENERGY_WASTE_THEN_CO2"
    max_reduction_fraction: float = Field(default=0.95, gt=0, le=1)
    floor_projected_at_zero: bool = True
    cap_saving_at_baseline: bool = True
    static_prices: bool = True
    cost_model: CostModel = Field(default_factory=CostModel)


class CircularityWeights(_ConfigBase):
    recycled_input: float = Field(default=0.25, ge=0)
    waste_recovery: float = Field(default=0.25, ge=0)
    energy_recovery: float = Field(default=0.20, ge=0)
    water_reuse: float = Field(default=0.15, ge=0)
    reuse: float = Field(default=0.15, ge=0)

    @model_validator(mode="after")
    def _validate(self) -> "CircularityWeights":
        if sum(self.as_dict().values()) <= 0:
            raise ValueError("At least one circularity weight must be > 0")
        return self

    def as_dict(self) -> dict[str, float]:
        return {
            "recycled_input": self.recycled_input,
            "waste_recovery": self.waste_recovery,
            "energy_recovery": self.energy_recovery,
            "water_reuse": self.water_reuse,
            "reuse": self.reuse,
        }


class CircularityConfig(_ConfigBase):
    weights: CircularityWeights = Field(default_factory=CircularityWeights)
    methodology_version: str = "ecoleak-circularity-1.0"
    reweight_missing: bool = True
    disclaimer: str = (
        "EcoLeak internal circularity indicator - NOT a statutory, certified or "
        "standard-mapped rating. Use for internal decision support only."
    )


class AnomalyConfig(_ConfigBase):
    min_samples_for_ml: int = Field(default=10, ge=2)
    contamination: float = Field(default=0.1, gt=0, lt=0.5)
    random_state: int = 42
    model_name: str = "IsolationForest"
    model_version: str = "sklearn-1.0"


class EngineConfig(_ConfigBase):
    calculation_version: str = "phase1.0.0"
    factor_match_threshold: float = Field(default=0.15, ge=0, le=1)
    # When a category/unit pair has exactly one active factor, allow it as an
    # approved fallback even if the free-text description does not overlap
    # (requirements Module E: "No exact factor available -> approved fallback").
    allow_single_candidate_fallback: bool = True
    # P3-02/03/06: preference + confidence penalties for weak matches.
    # In-window / region-matching factors are preferred; fallback, region
    # mismatch and out-of-window factors lower the calculation confidence and
    # are recorded in assumptions (never applied silently at full confidence).
    prefer_region_match: bool = True
    prefer_validity_window: bool = True
    factor_fallback_penalty: float = Field(default=15.0, ge=0, le=100)
    factor_region_mismatch_penalty: float = Field(default=10.0, ge=0, le=100)
    factor_region_national_fallback_penalty: float = Field(default=5.0, ge=0, le=100)
    factor_validity_penalty: float = Field(default=10.0, ge=0, le=100)
    hotspot: HotspotConfig = Field(default_factory=HotspotConfig)
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    circularity: CircularityConfig = Field(default_factory=CircularityConfig)
    anomaly: AnomalyConfig = Field(default_factory=AnomalyConfig)
