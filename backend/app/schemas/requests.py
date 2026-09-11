"""Phase 1 request DTOs. Field names mirror the frozen contract exactly; only
`id`, timestamps and server-owned fields are omitted as the API contract states.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import (
    ActivityCategory,
    ConfidenceLevel,
    DataSourceType,
    InterventionComplexity,
    MeasuredOrEstimated,
    OrganizationSize,
    PeriodType,
    ReportingPeriodStatus,
    RiskLevel,
    Scope,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationCreate(StrictRequest):
    name: str = Field(min_length=1, max_length=200)
    industry_sector: str = Field(min_length=1, max_length=100)
    industry_subtype: Optional[str] = Field(default=None, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    currency_code: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    organization_size: OrganizationSize


class OrganizationUpdate(StrictRequest):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    industry_sector: Optional[str] = Field(default=None, min_length=1, max_length=100)
    industry_subtype: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, min_length=1, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    organization_size: Optional[OrganizationSize] = None


class FacilityCreate(StrictRequest):
    organization_id: Optional[UUID] = None
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


class FacilityUpdate(StrictRequest):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    facility_code: Optional[str] = Field(default=None, max_length=50)
    country: Optional[str] = Field(default=None, min_length=1, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    latitude: Optional[Decimal] = Field(default=None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(default=None, ge=-180, le=180)
    annual_production: Optional[Decimal] = Field(default=None, ge=0)
    production_unit: Optional[str] = Field(default=None, max_length=30)
    working_days_per_year: Optional[int] = Field(default=None, ge=0, le=366)
    working_hours_per_day: Optional[Decimal] = Field(default=None, ge=0, le=24)
    active: Optional[bool] = None


class ReportingPeriodCreate(StrictRequest):
    facility_id: Optional[UUID] = None
    period_type: PeriodType
    start_date: date
    end_date: date
    status: ReportingPeriodStatus = ReportingPeriodStatus.DRAFT

    @model_validator(mode="after")
    def _dates(self) -> "ReportingPeriodCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ProcessCreate(StrictRequest):
    facility_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=150)
    process_code: Optional[str] = Field(default=None, max_length=50)
    sequence_no: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    process_category: Optional[str] = Field(default=None, max_length=100)
    active: bool = True


class ProcessUpdate(StrictRequest):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    process_code: Optional[str] = Field(default=None, max_length=50)
    sequence_no: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    process_category: Optional[str] = Field(default=None, max_length=100)
    active: Optional[bool] = None


class ActivityCreate(StrictRequest):
    facility_id: Optional[UUID] = None
    process_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    reporting_period_id: UUID
    activity_category: ActivityCategory
    activity_subcategory: str = Field(min_length=1, max_length=100)
    source_name: Optional[str] = Field(default=None, max_length=150)
    original_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    original_unit: str = Field(min_length=1, max_length=30)
    normalized_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    normalized_unit: Optional[str] = Field(default=None, max_length=30)
    data_source_type: DataSourceType = DataSourceType.MANUAL
    measured_or_estimated: MeasuredOrEstimated = MeasuredOrEstimated.MEASURED
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    notes: Optional[str] = None


class ActivityUpdate(ActivityCreate):
    pass


class EmissionFactorCreate(StrictRequest):
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
    supplier_id: Optional[str] = Field(default=None, max_length=80)
    supplier_specific: bool = False


class CircularInterventionCreate(StrictRequest):
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


class NormalizeRequest(StrictRequest):
    value: Decimal = Field(ge=0)
    from_unit: str = Field(min_length=1, max_length=30)
    to_unit: str = Field(min_length=1, max_length=30)


class ReportCreate(StrictRequest):
    template_version: str = Field(min_length=1, max_length=30)
    include_scope3: bool = False
