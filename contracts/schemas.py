"""
EcoLeak AI - Phase 0 Contract Schemas
=====================================

Pydantic v2 models that mirror the authoritative database design in
"Industrial_Emission_Database_Security_Edge_Cases.md" (column names, types,
CHECK constraints, enums).

Rules of this file (Phase 0 - Contract Lock):
- Field names match the DB design document column names exactly.
- Every numeric range stated in the DB doc (CHECK / edge cases) has a matching
  Pydantic Field(ge=..., le=...) constraint.
- No business logic, no calculation, no ML, no auth. Models only.

Supporting tables needed by the required entities (ReportingPeriod,
ScenarioIntervention, RecommendationAssessment) are included so every mock
record has a target model. The *_result / *OutputItem models at the bottom are
API response DTOs (Module G / Module J output envelopes), not DB entities.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class StrictBaseModel(BaseModel):
    """Reject unexpected fields (security checklist: 'Reject unexpected fields')."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Enums (source: DB design doc sections 2-15, 23)
# ---------------------------------------------------------------------------


class OrganizationSize(str, Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"


class PeriodType(str, Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"
    CUSTOM = "CUSTOM"


class ReportingPeriodStatus(str, Enum):
    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    CLOSED = "CLOSED"


class ActivityCategory(str, Enum):
    ELECTRICITY = "ELECTRICITY"
    FUEL = "FUEL"
    MATERIAL = "MATERIAL"
    WATER = "WATER"
    TRANSPORT = "TRANSPORT"
    WASTE = "WASTE"
    REFRIGERANT = "REFRIGERANT"
    STEAM = "STEAM"
    OTHER = "OTHER"


class DataSourceType(str, Enum):
    MANUAL = "MANUAL"
    CSV = "CSV"
    EXCEL = "EXCEL"
    API = "API"
    SENSOR = "SENSOR"
    OCR = "OCR"


class MeasuredOrEstimated(str, Enum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"


class Scope(str, Enum):
    SCOPE_1 = "SCOPE_1"
    SCOPE_2 = "SCOPE_2"
    SCOPE_3 = "SCOPE_3"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class HotspotSeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationStatus(str, Enum):
    SUGGESTED = "SUGGESTED"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    PLANNED = "PLANNED"
    IMPLEMENTED = "IMPLEMENTED"


class FeedbackType(str, Enum):
    USEFUL = "USEFUL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONSIDER_LATER = "CONSIDER_LATER"
    IMPLEMENTED = "IMPLEMENTED"
    REJECTED = "REJECTED"


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"


# NOTE (Phase 0 assumption): the DB doc declares `complexity` and `risk_level`
# as VARCHAR(20) without enumerating values. LOW/MEDIUM/HIGH is assumed.
class InterventionComplexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ---------------------------------------------------------------------------
# Module A - Organization / Facility (DB doc 2.1, 2.2)
# ---------------------------------------------------------------------------


class Organization(StrictBaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    industry_sector: str = Field(min_length=1, max_length=100)
    industry_subtype: Optional[str] = Field(default=None, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    currency_code: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    organization_size: OrganizationSize
    created_at: datetime
    updated_at: datetime


class Facility(StrictBaseModel):
    id: UUID
    organization_id: UUID
    name: str = Field(min_length=1, max_length=200)
    facility_code: Optional[str] = Field(default=None, max_length=50)
    country: str = Field(min_length=1, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    latitude: Optional[Decimal] = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Optional[Decimal] = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    annual_production: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    production_unit: Optional[str] = Field(default=None, max_length=30)
    working_days_per_year: Optional[int] = Field(default=None, ge=0, le=366)
    working_hours_per_day: Optional[Decimal] = Field(default=None, ge=0, le=24, max_digits=5, decimal_places=2)
    active: bool = True
    created_at: datetime
    updated_at: datetime


class ReportingPeriod(StrictBaseModel):
    id: UUID
    facility_id: UUID
    period_type: PeriodType
    start_date: date
    end_date: date
    status: ReportingPeriodStatus = ReportingPeriodStatus.DRAFT
    created_at: datetime

    @model_validator(mode="after")
    def validate_period_dates(self) -> "ReportingPeriod":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


# ---------------------------------------------------------------------------
# Module B - Process (DB doc 3.1)
# ---------------------------------------------------------------------------


class Process(StrictBaseModel):
    id: UUID
    facility_id: UUID
    name: str = Field(min_length=1, max_length=150)
    process_code: Optional[str] = Field(default=None, max_length=50)
    sequence_no: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    process_category: Optional[str] = Field(default=None, max_length=100)
    active: bool = True
    created_at: datetime


# ---------------------------------------------------------------------------
# Modules C/D - Activity data (DB doc 4.1)
# ---------------------------------------------------------------------------


class ActivityData(StrictBaseModel):
    id: UUID
    facility_id: UUID
    process_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    reporting_period_id: UUID
    activity_category: ActivityCategory
    activity_subcategory: str = Field(min_length=1, max_length=100)
    source_name: Optional[str] = Field(default=None, max_length=150)
    original_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    original_unit: str = Field(min_length=1, max_length=30)
    normalized_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    normalized_unit: str = Field(min_length=1, max_length=30)
    data_source_type: DataSourceType = DataSourceType.MANUAL
    measured_or_estimated: MeasuredOrEstimated = MeasuredOrEstimated.MEASURED
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    notes: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Module E - Emission factor (DB doc 6.1)
# ---------------------------------------------------------------------------


class EmissionFactor(StrictBaseModel):
    id: UUID
    factor_code: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=50)
    subcategory: str = Field(min_length=1, max_length=100)
    item_name: str = Field(min_length=1, max_length=150)
    region_country: Optional[str] = Field(default=None, max_length=100)
    region_state: Optional[str] = Field(default=None, max_length=100)
    scope: Scope
    input_unit: str = Field(min_length=1, max_length=30)
    output_unit: str = Field(default="kgCO2e", max_length=30)
    co2_factor: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    ch4_factor: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    n2o_factor: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    total_co2e_factor: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    source_name: str = Field(min_length=1, max_length=255)
    source_url: Optional[str] = None
    source_year: int = Field(ge=1900, le=2100)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    methodology: Optional[str] = None
    confidence_level: Optional[ConfidenceLevel] = None
    version: str = Field(min_length=1, max_length=30)
    active: bool = True
    created_at: datetime

    @model_validator(mode="after")
    def validate_factor_dates(self) -> "EmissionFactor":
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to cannot be before valid_from")
        return self


# ---------------------------------------------------------------------------
# Module F - Carbon accounting (DB doc 7.1)
# ---------------------------------------------------------------------------


class EmissionCalculation(StrictBaseModel):
    id: UUID
    activity_data_id: UUID
    emission_factor_id: UUID
    calculation_version: str = Field(min_length=1, max_length=30)
    scope: Scope
    co2e_kg: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    calculation_formula: Optional[str] = None
    assumptions: Optional[dict[str, Any]] = None
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    calculated_at: datetime


# ---------------------------------------------------------------------------
# Module G - Hotspot (DB doc 9.1)
# ---------------------------------------------------------------------------


class EmissionHotspot(StrictBaseModel):
    id: UUID
    facility_id: UUID
    reporting_period_id: UUID
    process_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    hotspot_type: Optional[str] = Field(default=None, max_length=30)
    emissions_kgco2e: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    contribution_percent: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=8, decimal_places=4)
    carbon_intensity: Optional[Decimal] = Field(default=None, ge=0)
    inefficiency_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    waste_ratio_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    improvement_potential_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    hotspot_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    severity: HotspotSeverity
    explanation: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Module I - Circular intervention (DB doc 11.1)
# ---------------------------------------------------------------------------


class CircularIntervention(StrictBaseModel):
    id: UUID
    intervention_code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    industry_sector: Optional[str] = Field(default=None, max_length=100)
    process_category: Optional[str] = Field(default=None, max_length=100)
    current_practice: Optional[str] = None
    alternative_practice: Optional[str] = None
    description: Optional[str] = None
    min_capex: Optional[Decimal] = Field(default=None, ge=0)
    max_capex: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    expected_co2_reduction_min_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    expected_co2_reduction_max_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    energy_reduction_min_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    energy_reduction_max_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    waste_reduction_min_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    waste_reduction_max_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    implementation_months_min: Optional[int] = Field(default=None, ge=0)
    implementation_months_max: Optional[int] = Field(default=None, ge=0)
    complexity: Optional[InterventionComplexity] = None
    risk_level: Optional[RiskLevel] = None
    evidence_source: Optional[str] = None
    active: bool = True

    @model_validator(mode="after")
    def validate_ranges(self) -> "CircularIntervention":
        pairs = (
            ("min_capex", "max_capex"),
            ("expected_co2_reduction_min_pct", "expected_co2_reduction_max_pct"),
            ("energy_reduction_min_pct", "energy_reduction_max_pct"),
            ("waste_reduction_min_pct", "waste_reduction_max_pct"),
            ("implementation_months_min", "implementation_months_max"),
        )
        for low_name, high_name in pairs:
            low = getattr(self, low_name)
            high = getattr(self, high_name)
            if low is not None and high is not None and high < low:
                raise ValueError(f"{high_name} cannot be less than {low_name}")
        return self


# ---------------------------------------------------------------------------
# Module J - Recommendation (DB doc 12.1) + assessment (DB doc 12.2)
# ---------------------------------------------------------------------------


class Recommendation(StrictBaseModel):
    id: UUID
    facility_id: UUID
    reporting_period_id: UUID
    hotspot_id: UUID
    intervention_id: UUID
    rank: int = Field(ge=1)
    carbon_saving_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    financial_return_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    feasibility_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    circularity_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    implementation_speed_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    final_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    status: RecommendationStatus = RecommendationStatus.SUGGESTED
    generated_at: datetime


class RecommendationAssessment(StrictBaseModel):
    id: UUID
    recommendation_id: UUID
    estimated_capex: Optional[Decimal] = Field(default=None, ge=0)
    estimated_annual_opex_change: Optional[Decimal] = None
    estimated_annual_saving: Optional[Decimal] = None
    estimated_co2_saving_kg: Optional[Decimal] = Field(default=None, ge=0)
    estimated_energy_saving: Optional[Decimal] = Field(default=None, ge=0)
    estimated_waste_reduction: Optional[Decimal] = Field(default=None, ge=0)
    payback_years: Optional[Decimal] = Field(default=None, ge=0)
    cost_per_tonne_co2_avoided: Optional[Decimal] = None
    assumptions: Optional[dict[str, Any]] = None
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=100)


# ---------------------------------------------------------------------------
# Modules K/O - Scenario (DB doc 13.1, 13.2, 13.3)
# ---------------------------------------------------------------------------


class Scenario(StrictBaseModel):
    id: UUID
    facility_id: UUID
    reporting_period_id: UUID
    name: str = Field(min_length=1, max_length=150)
    scenario_type: Optional[str] = Field(default=None, max_length=30)
    budget_limit: Optional[Decimal] = Field(default=None, ge=0)
    target_reduction_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    created_at: datetime


class ScenarioIntervention(StrictBaseModel):
    id: UUID
    scenario_id: UUID
    recommendation_id: UUID
    adoption_percentage: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    selected: bool = True


class ImpactAssessment(StrictBaseModel):
    id: UUID
    scenario_id: UUID
    baseline_emissions_kg: Decimal = Field(ge=0)
    projected_emissions_kg: Decimal = Field(ge=0)
    total_co2_saving_kg: Optional[Decimal] = None
    reduction_percent: Optional[Decimal] = None
    total_capex: Optional[Decimal] = Field(default=None, ge=0)
    annual_saving: Optional[Decimal] = None
    payback_years: Optional[Decimal] = Field(default=None, ge=0)
    generated_at: datetime


# ---------------------------------------------------------------------------
# Module Q - Feedback (DB doc 15.1)
# ---------------------------------------------------------------------------


class RecommendationFeedback(StrictBaseModel):
    id: UUID
    recommendation_id: UUID
    feedback_type: FeedbackType
    reason: Optional[str] = None
    actual_capex: Optional[Decimal] = Field(default=None, ge=0)
    actual_annual_saving: Optional[Decimal] = None
    actual_co2_saving_kg: Optional[Decimal] = Field(default=None, ge=0)
    submitted_at: datetime


# ---------------------------------------------------------------------------
# Validation severity payload (DB doc 23) - used by API error/validation shape
# ---------------------------------------------------------------------------


class ValidationIssue(StrictBaseModel):
    severity: ValidationSeverity
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1)
    field: Optional[str] = Field(default=None, max_length=200)
    details: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# API response DTOs (Module G / Module J engine output envelopes, Phase 0 mock
# contracts). These are NOT database tables; they wrap DB entities plus fields
# the UI needs (rank, process name, intervention title, explanation, impact).
# ---------------------------------------------------------------------------


class HotspotOutputItem(EmissionHotspot):
    rank: int = Field(ge=1)
    process_name: Optional[str] = Field(default=None, max_length=150)
    activity_category: Optional[ActivityCategory] = None


class HotspotDetectionResult(StrictBaseModel):
    facility_id: UUID
    reporting_period_id: UUID
    generated_at: datetime
    scope_boundary: list[Scope] = Field(default_factory=lambda: [Scope.SCOPE_1, Scope.SCOPE_2])
    total_emissions_kgco2e: Decimal = Field(ge=0)
    data_quality_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    hotspots: list[HotspotOutputItem] = Field(default_factory=list)


class RecommendationOutputItem(Recommendation):
    intervention_code: Optional[str] = Field(default=None, max_length=80)
    intervention_title: Optional[str] = Field(default=None, max_length=200)
    explanation: Optional[str] = None
    impact: Optional[RecommendationAssessment] = None


class RecommendationGenerationResult(StrictBaseModel):
    facility_id: UUID
    reporting_period_id: UUID
    generated_at: datetime
    budget_limit: Optional[Decimal] = Field(default=None, ge=0)
    recommendations: list[RecommendationOutputItem] = Field(default_factory=list)
