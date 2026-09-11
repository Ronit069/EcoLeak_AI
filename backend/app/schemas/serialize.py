"""ORM -> contract-shaped dict serializers.

The keys returned here are asserted against `contracts/schemas.py` by
`tests/test_contract_parity.py`, so the frozen response shapes cannot drift.
"""
from __future__ import annotations

from app.models.activity import ActivityData
from app.models.core import Facility, Organization, ReportingPeriod
from app.models.intervention import CircularIntervention
from app.models.process import Process


def organization_to_dict(org: Organization) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "industry_sector": org.industry_sector,
        "industry_subtype": org.industry_subtype,
        "country": org.country,
        "state": org.state,
        "city": org.city,
        "currency_code": org.currency_code,
        "organization_size": org.organization_size,
        "created_at": org.created_at,
        "updated_at": org.updated_at,
    }


def facility_to_dict(facility: Facility) -> dict:
    return {
        "id": facility.id,
        "organization_id": facility.organization_id,
        "name": facility.name,
        "facility_code": facility.facility_code,
        "country": facility.country,
        "state": facility.state,
        "city": facility.city,
        "latitude": facility.latitude,
        "longitude": facility.longitude,
        "annual_production": facility.annual_production,
        "production_unit": facility.production_unit,
        "working_days_per_year": facility.working_days_per_year,
        "working_hours_per_day": facility.working_hours_per_day,
        "active": facility.active,
        "created_at": facility.created_at,
        "updated_at": facility.updated_at,
    }


def period_to_dict(period: ReportingPeriod) -> dict:
    return {
        "id": period.id,
        "facility_id": period.facility_id,
        "period_type": period.period_type,
        "start_date": period.start_date,
        "end_date": period.end_date,
        "status": period.status,
        "created_at": period.created_at,
    }


def process_to_dict(process: Process) -> dict:
    return {
        "id": process.id,
        "facility_id": process.facility_id,
        "name": process.name,
        "process_code": process.process_code,
        "sequence_no": process.sequence_no,
        "description": process.description,
        "process_category": process.process_category,
        "active": process.active,
        "created_at": process.created_at,
    }


def activity_to_dict(activity: ActivityData) -> dict:
    return {
        "id": activity.id,
        "facility_id": activity.facility_id,
        "process_id": activity.process_id,
        "asset_id": activity.asset_id,
        "reporting_period_id": activity.reporting_period_id,
        "activity_category": activity.activity_category,
        "activity_subcategory": activity.activity_subcategory,
        "source_name": activity.source_name,
        "original_value": activity.original_value,
        "original_unit": activity.original_unit,
        "normalized_value": activity.normalized_value,
        "normalized_unit": activity.normalized_unit,
        "data_source_type": activity.data_source_type,
        "measured_or_estimated": activity.measured_or_estimated,
        "confidence_score": activity.confidence_score,
        "notes": activity.notes,
        "created_at": activity.created_at,
    }


def intervention_to_dict(intervention: CircularIntervention) -> dict:
    return {
        "id": intervention.id,
        "intervention_code": intervention.intervention_code,
        "title": intervention.title,
        "industry_sector": intervention.industry_sector,
        "process_category": intervention.process_category,
        "current_practice": intervention.current_practice,
        "alternative_practice": intervention.alternative_practice,
        "description": intervention.description,
        "min_capex": intervention.min_capex,
        "max_capex": intervention.max_capex,
        "currency": intervention.currency,
        "expected_co2_reduction_min_pct": intervention.expected_co2_reduction_min_pct,
        "expected_co2_reduction_max_pct": intervention.expected_co2_reduction_max_pct,
        "energy_reduction_min_pct": intervention.energy_reduction_min_pct,
        "energy_reduction_max_pct": intervention.energy_reduction_max_pct,
        "waste_reduction_min_pct": intervention.waste_reduction_min_pct,
        "waste_reduction_max_pct": intervention.waste_reduction_max_pct,
        "implementation_months_min": intervention.implementation_months_min,
        "implementation_months_max": intervention.implementation_months_max,
        "complexity": intervention.complexity,
        "risk_level": intervention.risk_level,
        "evidence_source": intervention.evidence_source,
        "active": intervention.active,
    }
