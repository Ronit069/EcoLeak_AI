"""Shared fixtures and builders for the P4 test suite."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from p4.contracts import (  # noqa: E402
    Facility,
    HotspotDetectionResult,
    HotspotOutputItem,
    Organization,
    Process,
)
from p4.engine import EngineRun, generate_with_diagnostics  # noqa: E402
from p4.explainability import TemplateExplainer  # noqa: E402
from p4.library import InterventionLibrary  # noqa: E402
from p4.models import (  # noqa: E402
    ExplanationEvidence,
    FacilityContext,
    InterventionEntry,
    RecommendationConstraints,
    ResourceEmissionFactors,
    ScoreBreakdown,
)

MOCKS_DIR = PROJECT_ROOT / "mocks"
DEMO_DIR = PROJECT_ROOT / "p4" / "demo"

FACILITY_ID = UUID("0a1b2c3d-0002-4002-8002-000000000002")
PERIOD_ID = UUID("0a1b2c3d-0003-4003-8003-000000000003")
FIXED_NOW = datetime(2026, 4, 5, 10, 45, tzinfo=timezone.utc)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def organization() -> Organization:
    return Organization.model_validate(_load(MOCKS_DIR / "mock_dataset.json")["organization"])


@lru_cache(maxsize=1)
def facility() -> Facility:
    return Facility.model_validate(_load(MOCKS_DIR / "mock_dataset.json")["facilities"][0])


@lru_cache(maxsize=1)
def processes() -> list[Process]:
    return [Process.model_validate(item) for item in _load(MOCKS_DIR / "mock_dataset.json")["processes"]]


@lru_cache(maxsize=1)
def hotspot_envelope() -> HotspotDetectionResult:
    return HotspotDetectionResult.model_validate(_load(MOCKS_DIR / "mock_hotspot_output.json"))


@lru_cache(maxsize=1)
def demo_context() -> FacilityContext:
    return FacilityContext.model_validate(_load(DEMO_DIR / "demo_context.json"))


@lru_cache(maxsize=1)
def demo_emission_factors() -> ResourceEmissionFactors:
    mapping = {
        "EF-ELEC-GRID-IN-2023": "electricity_per_kwh",
        "EF-FUEL-NG-M3-2006": "natural_gas_per_m3",
        "EF-FUEL-DIESEL-L-2006": "diesel_per_litre",
        "EF-WATER-SUPPLY-M3-2020": "water_per_m3",
        "EF-WASTE-TEXTILE-LF-KG-2023": "waste_per_kg",
        "EF-MAT-LDPE-KG-2021": "packaging_per_kg",
    }
    values = {
        target: factor["total_co2e_factor"]
        for factor in _load(MOCKS_DIR / "mock_dataset.json")["emission_factors"]
        if (target := mapping.get(factor["factor_code"]))
    }
    return ResourceEmissionFactors.model_validate(values)


DEFAULT_ENTRY = {
    "id": "0a1b2c3d-0e01-4e01-8e01-000000000e01",
    "intervention_code": "INT-TEST-001",
    "title": "Synthetic test intervention",
    "industry_sector": "Textile",
    "min_capex": 100000.0,
    "max_capex": 200000.0,
    "currency": "INR",
    "expected_co2_reduction_min_pct": 5.0,
    "expected_co2_reduction_max_pct": 10.0,
    "energy_reduction_min_pct": 5.0,
    "energy_reduction_max_pct": 10.0,
    "implementation_months_min": 2,
    "implementation_months_max": 4,
    "complexity": "LOW",
    "risk_level": "LOW",
    "evidence_source": "test fixture (mock)",
    "applicable_process_categories": ["Boiler"],
    "applicable_activity_categories": ["FUEL"],
    "technical_requirements": ["test fixture"],
    "active": True,
}


def make_entry(**overrides) -> InterventionEntry:
    return InterventionEntry.model_validate({**DEFAULT_ENTRY, **overrides})


DEFAULT_HOTSPOT = {
    "id": "0a1b2c3d-0f01-4f01-8f01-000000000f01",
    "facility_id": FACILITY_ID,
    "reporting_period_id": PERIOD_ID,
    "process_id": "0a1b2c3d-0006-4006-8006-000000000006",
    "asset_id": None,
    "hotspot_type": "PROCESS",
    "emissions_kgco2e": 200000.0,
    "contribution_percent": 50.0,
    "carbon_intensity": 200.0,
    "inefficiency_score": 70.0,
    "waste_ratio_score": None,
    "improvement_potential_score": 80.0,
    "hotspot_score": 80.0,
    "severity": "CRITICAL",
    "explanation": "synthetic hotspot",
    "created_at": "2026-04-05T10:30:00+05:30",
    "rank": 1,
    "process_name": "Boiler",
    "activity_category": "FUEL",
}


def make_hotspot(**overrides) -> HotspotOutputItem:
    return HotspotOutputItem.model_validate({**DEFAULT_HOTSPOT, **overrides})


def make_envelope(hotspots: Optional[list[HotspotOutputItem]] = None, **overrides) -> HotspotDetectionResult:
    items = hotspots if hotspots is not None else [make_hotspot()]
    data = {
        "facility_id": FACILITY_ID,
        "reporting_period_id": PERIOD_ID,
        "generated_at": FIXED_NOW,
        "scope_boundary": ["SCOPE_1", "SCOPE_2"],
        "total_emissions_kgco2e": sum(float(item.emissions_kgco2e) for item in items),
        "data_quality_score": 78.4,
        "hotspots": items,
    }
    data.update(overrides)
    return HotspotDetectionResult.model_validate(data)


def make_library(entries: list[InterventionEntry]) -> InterventionLibrary:
    return InterventionLibrary(entries)


def run_engine(
    *,
    library: Optional[InterventionLibrary] = None,
    hotspots: Optional[HotspotDetectionResult] = None,
    context: Optional[FacilityContext] = None,
    use_context: bool = True,
    use_factors: bool = True,
    constraints: Optional[RecommendationConstraints] = None,
    explainer=None,
) -> EngineRun:
    return generate_with_diagnostics(
        hotspots or hotspot_envelope(),
        facility(),
        organization=organization(),
        processes=processes(),
        context=(demo_context() if use_context else None) if context is None else context,
        emission_factors=demo_emission_factors() if use_factors else None,
        constraints=constraints,
        library=library,
        explainer=explainer or TemplateExplainer(),
        clock=lambda: FIXED_NOW,
    )


def make_evidence(**overrides) -> ExplanationEvidence:
    data = {
        "recommendation_id": UUID("0a1b2c3d-0d01-4d01-8d01-000000000d01"),
        "intervention_code": "INT-TEST-001",
        "intervention_title": "Synthetic test intervention",
        "rank": 1,
        "final_score": 80.0,
        "scores": ScoreBreakdown(
            carbon_saving=70.0,
            financial_return=90.0,
            feasibility=80.0,
            circularity=60.0,
            implementation_speed=88.0,
            confidence=84.0,
        ),
        "hotspot_rank": 1,
        "hotspot_process_name": "Boiler",
        "hotspot_severity": "CRITICAL",
        "hotspot_contribution_percent": 39.69,
        "hotspot_emissions_kgco2e": 224250.0,
        "hotspot_carbon_intensity": 224.25,
        "hotspot_inefficiency_score": 82.0,
        "hotspot_waste_ratio_score": None,
        "hotspot_improvement_potential_score": 90.0,
        "hotspot_explanation": "Boiler combustion dominates; no flue-gas heat recovery.",
        "co2_reduction_min_pct": 12.0,
        "co2_reduction_max_pct": 18.0,
        "energy_reduction_min_pct": 10.0,
        "energy_reduction_max_pct": 15.0,
        "waste_reduction_min_pct": None,
        "waste_reduction_max_pct": None,
        "water_reduction_min_pct": None,
        "water_reduction_max_pct": None,
        "capex_min": 1200000.0,
        "capex_max": 2000000.0,
        "estimated_capex": 1600000.0,
        "estimated_annual_saving": 830025.0,
        "estimated_annual_opex_change": -45000.0,
        "estimated_co2_saving_kg": 33637.5,
        "co2_saving_basis": "resource-based: quantity saved x versioned emission factor",
        "estimated_energy_saving_kwh": 180000.0,
        "estimated_waste_reduction_kg": None,
        "estimated_water_reduction_m3": None,
        "payback_years": 1.93,
        "cost_per_tonne_co2_avoided": 47567.5,
        "currency": "INR",
        "implementation_months_min": 4,
        "implementation_months_max": 8,
        "evidence_source": "IEA heat recovery (mock)",
        "confidence_score": 84.0,
        "data_quality_score": 78.4,
        "context_available": True,
        "assumptions": {"static_energy_prices": True},
        "prerequisites": [],
        "prerequisites_unmet": [],
        "conflicts_with": [],
        "feasibility_notes": [],
    }
    data.update(overrides)
    return ExplanationEvidence.model_validate(data)
