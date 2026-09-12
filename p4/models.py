"""P4-local models.

These extend the frozen Phase 0 contract models (contracts/schemas.py) with
fields the Module I knowledge base, constraint handling, and diagnostics need.
Nothing here redefines a frozen DB entity; `InterventionEntry` inherits from
`CircularIntervention` and only adds optional P4 metadata (OPEX impact,
water reduction, technical requirements, applicability, prerequisites).
This keeps the Phase 0 contract untouched while satisfying the Module I
requirement list (DB doc section 11.1 + requirements doc section 11).
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field, model_validator

from p4.contracts import (
    ActivityCategory,
    CircularIntervention,
    InterventionComplexity,
    RecommendationAssessment,
    RecommendationOutputItem,
    StrictBaseModel,
)


class LoopType(str, Enum):
    ENERGY = "ENERGY"
    HEAT_RECOVERY = "HEAT_RECOVERY"
    MATERIAL = "MATERIAL"
    WATER = "WATER"
    WASTE = "WASTE"
    PACKAGING = "PACKAGING"
    CHEMICAL = "CHEMICAL"


class OpexImpact(str, Enum):
    REDUCES = "REDUCES"
    NEUTRAL = "NEUTRAL"
    INCREASES = "INCREASES"


class RejectionReasonCode(str, Enum):
    """Module Q structured rejection reasons (DB doc section 21, Module Q)."""

    TOO_COSTLY = "TOO_COSTLY"
    NOT_APPLICABLE_LOCALLY = "NOT_APPLICABLE_LOCALLY"
    SPACE_CONSTRAINTS = "SPACE_CONSTRAINTS"
    PROCESS_INCOMPATIBLE = "PROCESS_INCOMPATIBLE"
    REGULATORY = "REGULATORY"
    DATA_QUALITY = "DATA_QUALITY"
    OTHER = "OTHER"


class InterventionEntry(CircularIntervention):
    """Module I knowledge-base entry: frozen DB fields + P4 metadata."""

    water_reduction_min_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    water_reduction_max_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)

    opex_impact: OpexImpact = OpexImpact.NEUTRAL
    # Percentage change of the affected operating cost baseline.
    # Negative = cost reduction, positive = extra annual cost.
    opex_change_pct_min: Optional[Decimal] = Field(default=None, ge=-100, le=100)
    opex_change_pct_max: Optional[Decimal] = Field(default=None, ge=-100, le=100)

    technical_requirements: list[str] = Field(default_factory=list)
    # "*" means applicable to any process.
    applicable_process_categories: list[str] = Field(default_factory=list)
    applicable_activity_categories: list[ActivityCategory] = Field(default_factory=list)
    # None = available everywhere; otherwise list of country/state names.
    applicable_regions: Optional[list[str]] = None
    min_annual_production_tonnes: Optional[Decimal] = Field(default=None, ge=0)
    prerequisite_codes: list[str] = Field(default_factory=list)
    conflicts_with_codes: list[str] = Field(default_factory=list)
    loop_types: list[LoopType] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_p4_ranges(self) -> "InterventionEntry":
        pairs = (
            ("water_reduction_min_pct", "water_reduction_max_pct"),
            ("opex_change_pct_min", "opex_change_pct_max"),
        )
        for low_name, high_name in pairs:
            low = getattr(self, low_name)
            high = getattr(self, high_name)
            if low is not None and high is not None and high < low:
                raise ValueError(f"{high_name} cannot be less than {low_name}")
        return self


class RecommendationConstraints(StrictBaseModel):
    """Module J inputs: budget, location, and technical limits."""

    budget_limit: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    region_country: Optional[str] = Field(default=None, max_length=100)
    region_state: Optional[str] = Field(default=None, max_length=100)
    max_complexity: Optional[InterventionComplexity] = None
    max_payback_years: Optional[Decimal] = Field(default=None, gt=0)
    excluded_intervention_codes: list[str] = Field(default_factory=list)
    locally_unavailable_codes: list[str] = Field(default_factory=list)
    require_prerequisites_met: bool = False
    strict_budget_filter: bool = True
    max_recommendations: Optional[int] = Field(default=None, ge=1)


class ProcessResourceBaseline(StrictBaseModel):
    """Annual resource use for one process (P4 demo fixture until P3 is live)."""

    process_name: str = Field(min_length=1, max_length=150)
    electricity_kwh_per_year: Optional[Decimal] = Field(default=None, ge=0)
    natural_gas_m3_per_year: Optional[Decimal] = Field(default=None, ge=0)
    diesel_litres_per_year: Optional[Decimal] = Field(default=None, ge=0)
    water_m3_per_year: Optional[Decimal] = Field(default=None, ge=0)
    wastewater_m3_per_year: Optional[Decimal] = Field(default=None, ge=0)
    waste_kg_per_year: Optional[Decimal] = Field(default=None, ge=0)
    packaging_kg_per_year: Optional[Decimal] = Field(default=None, ge=0)


class TariffSet(StrictBaseModel):
    """Static price assumptions used by the deterministic financial estimator."""

    currency: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    electricity_per_kwh: Decimal = Field(ge=0)
    natural_gas_per_m3: Decimal = Field(ge=0)
    diesel_per_litre: Decimal = Field(ge=0)
    water_per_m3: Decimal = Field(ge=0)
    wastewater_per_m3: Decimal = Field(ge=0)
    waste_disposal_per_kg: Decimal = Field(ge=0)
    packaging_per_kg: Decimal = Field(ge=0)


class EnergyConversions(StrictBaseModel):
    natural_gas_kwh_per_m3: Decimal = Field(default=Decimal("10.55"), gt=0)
    diesel_kwh_per_litre: Decimal = Field(default=Decimal("9.96"), gt=0)


class FacilityContext(StrictBaseModel):
    facility_id: UUID
    reporting_period_id: UUID
    process_resources: list[ProcessResourceBaseline]
    tariffs: TariffSet
    conversions: EnergyConversions = Field(default_factory=EnergyConversions)
    # F-8: True while the demo fixture supplies resource baselines/tariffs;
    # surfaced per-recommendation as assumptions.data_is_stub so degraded
    # financials are machine-readable instead of silently presented as real.
    is_fixture: bool = True


class ResourceEmissionFactors(StrictBaseModel):
    """kgCO2e per resource unit, taken from the versioned emission-factor KB.

    When supplied, the engine computes resource-based CO2 savings (physical
    basis) instead of the percentage-of-hotspot fallback. Both paths are
    deterministic; only the basis differs (recorded in assumptions).

    ``waste_per_kg`` is the landfill-avoidance factor. Recycling pathways are
    NOT assumed zero-emission (C2): when
    ``recycling_processing_emission_factor`` is set, the net saving is
    ``waste_kg x waste_per_kg - waste_kg x recycling_processing_emission_factor``.
    """

    electricity_per_kwh: Optional[Decimal] = Field(default=None, ge=0)
    natural_gas_per_m3: Optional[Decimal] = Field(default=None, ge=0)
    diesel_per_litre: Optional[Decimal] = Field(default=None, ge=0)
    water_per_m3: Optional[Decimal] = Field(default=None, ge=0)
    wastewater_per_m3: Optional[Decimal] = Field(default=None, ge=0)
    waste_per_kg: Optional[Decimal] = Field(default=None, ge=0)
    packaging_per_kg: Optional[Decimal] = Field(default=None, ge=0)
    recycling_processing_emission_factor: Optional[Decimal] = Field(
        default=None, ge=0,
        description="kgCO2e per kg of waste processed by the recycling pathway; "
                    "netted against landfill avoidance.",
    )


class ScoreBreakdown(StrictBaseModel):
    carbon_saving: float = Field(ge=0, le=100)
    financial_return: float = Field(ge=0, le=100)
    feasibility: float = Field(ge=0, le=100)
    circularity: float = Field(ge=0, le=100)
    implementation_speed: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)


class FilterRecord(StrictBaseModel):
    intervention_code: str
    reason: str
    detail: Optional[str] = None


class ScoredCandidateDiagnostics(StrictBaseModel):
    intervention_code: str
    hotspot_id: UUID
    process_name: Optional[str] = None
    scores: ScoreBreakdown
    final_score: float = Field(ge=0, le=100)
    estimated_co2_saving_kg: Optional[Decimal] = None
    estimated_capex: Optional[Decimal] = None
    estimated_annual_saving: Optional[Decimal] = None
    payback_years: Optional[Decimal] = None
    prerequisites_unmet: list[str] = Field(default_factory=list)
    feasibility_notes: list[str] = Field(default_factory=list)


class EngineDiagnostics(StrictBaseModel):
    considered: int = 0
    applicable: int = 0
    filtered: list[FilterRecord] = Field(default_factory=list)
    scored: list[ScoredCandidateDiagnostics] = Field(default_factory=list)
    duplicates_removed: list[str] = Field(default_factory=list)
    conflicts: list[list[str]] = Field(default_factory=list)
    explanation_sources: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ExplanationEvidence(StrictBaseModel):
    """Everything Module M is allowed to talk about (untrusted text included)."""

    recommendation_id: UUID
    intervention_code: str
    intervention_title: str
    rank: int = Field(ge=1)
    final_score: float = Field(ge=0, le=100)
    scores: ScoreBreakdown

    hotspot_rank: int = Field(ge=1)
    hotspot_process_name: Optional[str] = None
    hotspot_severity: str
    hotspot_contribution_percent: Optional[Decimal] = None
    hotspot_emissions_kgco2e: Decimal = Field(ge=0)
    hotspot_carbon_intensity: Optional[Decimal] = None
    hotspot_inefficiency_score: Optional[Decimal] = None
    hotspot_waste_ratio_score: Optional[Decimal] = None
    hotspot_improvement_potential_score: Optional[Decimal] = None
    hotspot_explanation: Optional[str] = None

    co2_reduction_min_pct: Optional[Decimal] = None
    co2_reduction_max_pct: Optional[Decimal] = None
    energy_reduction_min_pct: Optional[Decimal] = None
    energy_reduction_max_pct: Optional[Decimal] = None
    waste_reduction_min_pct: Optional[Decimal] = None
    waste_reduction_max_pct: Optional[Decimal] = None
    water_reduction_min_pct: Optional[Decimal] = None
    water_reduction_max_pct: Optional[Decimal] = None

    capex_min: Optional[Decimal] = None
    capex_max: Optional[Decimal] = None
    estimated_capex: Optional[Decimal] = None
    estimated_annual_saving: Optional[Decimal] = None
    estimated_annual_opex_change: Optional[Decimal] = None
    estimated_co2_saving_kg: Optional[Decimal] = None
    co2_saving_basis: Optional[str] = None
    estimated_energy_saving_kwh: Optional[Decimal] = None
    estimated_waste_reduction_kg: Optional[Decimal] = None
    estimated_water_reduction_m3: Optional[Decimal] = None
    payback_years: Optional[Decimal] = None
    cost_per_tonne_co2_avoided: Optional[Decimal] = None
    currency: str = "INR"
    implementation_months_min: Optional[int] = None
    implementation_months_max: Optional[int] = None
    evidence_source: Optional[str] = None

    confidence_score: float = Field(ge=0, le=100)
    data_quality_score: Optional[Decimal] = None
    context_available: bool = False
    assumptions: dict[str, Any] = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    prerequisites_unmet: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    feasibility_notes: list[str] = Field(default_factory=list)


class ExplanationOutcome(StrictBaseModel):
    """Result of one explanation attempt (LLM or deterministic template)."""

    text: str = Field(min_length=1)
    source: str = "template"  # template | llm | template_fallback
    attempts: int = Field(default=1, ge=1)
    validation_errors: list[str] = Field(default_factory=list)


class RecommendationWithEvidence(StrictBaseModel):
    """Internal pairing used before the response envelope is assembled."""

    recommendation: RecommendationOutputItem
    assessment: RecommendationAssessment
    evidence: ExplanationEvidence
    explanation_source: str = "template"
