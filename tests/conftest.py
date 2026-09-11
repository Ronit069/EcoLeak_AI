"""Shared pytest fixtures for the P3 engine.

Adds the repository root to ``sys.path`` before importing ``engine`` so tests
work regardless of the launch directory.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.schemas import (  # noqa: E402
    ActivityCategory,
    ActivityData,
    CircularIntervention,
    ConfidenceLevel,
    DataSourceType,
    EmissionFactor,
    Facility,
    MeasuredOrEstimated,
    OrganizationSize,
    PeriodType,
    Process,
    ReportingPeriod,
    ReportingPeriodStatus,
    Scope,
)
from engine.data_source import InMemoryDataSource  # noqa: E402

NOW = datetime(2026, 4, 5, 10, 30, tzinfo=timezone.utc)


def new_id() -> str:
    return str(uuid4())


@pytest.fixture
def make_facility():
    def _make(production: Decimal | None = Decimal("1000"), unit: str | None = "tonne", facility_id: str | None = None):
        return Facility(
            id=facility_id or new_id(),
            organization_id=new_id(),
            name="Test Facility",
            country="India",
            state="Gujarat",
            city="Surat",
            annual_production=production,
            production_unit=unit,
            working_days_per_year=300,
            working_hours_per_day=Decimal("16"),
            created_at=NOW,
            updated_at=NOW,
        )

    return _make


@pytest.fixture
def make_period():
    def _make(facility_id: str, period_id: str | None = None):
        return ReportingPeriod(
            id=period_id or new_id(),
            facility_id=facility_id,
            period_type=PeriodType.ANNUAL,
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status=ReportingPeriodStatus.DRAFT,
            created_at=NOW,
        )

    return _make


@pytest.fixture
def make_process():
    def _make(facility_id: str, name: str = "Boiler", category: str = "Utilities", process_id: str | None = None):
        return Process(
            id=process_id or new_id(),
            facility_id=facility_id,
            name=name,
            process_code=name.upper()[:6],
            sequence_no=1,
            process_category=category,
            created_at=NOW,
        )

    return _make


@pytest.fixture
def make_activity():
    def _make(
        facility_id: str,
        period_id: str,
        *,
        process_id: str | None = None,
        category: ActivityCategory = ActivityCategory.FUEL,
        subcategory: str = "Natural gas - stationary combustion",
        value: Decimal | None = Decimal("1000"),
        unit: str = "m3",
        confidence: Decimal | None = Decimal("90"),
        source: str = "Test source",
        notes: str | None = None,
        activity_id: str | None = None,
    ):
        return ActivityData(
            id=activity_id or new_id(),
            facility_id=facility_id,
            process_id=process_id,
            reporting_period_id=period_id,
            activity_category=category,
            activity_subcategory=subcategory,
            source_name=source,
            original_value=value,
            original_unit=unit,
            normalized_value=value,
            normalized_unit=unit,
            data_source_type=DataSourceType.MANUAL,
            measured_or_estimated=MeasuredOrEstimated.MEASURED,
            confidence_score=confidence,
            notes=notes,
            created_at=NOW,
        )

    return _make


@pytest.fixture
def make_factor():
    def _make(
        *,
        category: str = "FUEL",
        subcategory: str = "Natural gas",
        item_name: str = "Natural gas - stationary combustion",
        scope: Scope = Scope.SCOPE_1,
        input_unit: str = "m3",
        factor: Decimal = Decimal("2.022"),
        active: bool = True,
        source_year: int = 2006,
        version: str = "2006.2",
        confidence: ConfidenceLevel | None = ConfidenceLevel.HIGH,
        factor_id: str | None = None,
    ):
        return EmissionFactor(
            id=factor_id or new_id(),
            factor_code=f"EF-{category}-{input_unit}".upper(),
            category=category,
            subcategory=subcategory,
            item_name=item_name,
            region_country="India",
            scope=scope,
            input_unit=input_unit,
            output_unit="kgCO2e",
            total_co2e_factor=factor,
            source_name="Test source",
            source_year=source_year,
            version=version,
            confidence_level=confidence,
            active=active,
            created_at=NOW,
        )

    return _make


@pytest.fixture
def make_intervention():
    def _make(
        *,
        process_category: str = "Boiler",
        title: str = "Waste heat recovery",
        min_capex: Decimal | None = Decimal("1000000"),
        max_capex: Decimal | None = Decimal("2000000"),
        co2_min: Decimal | None = Decimal("10"),
        co2_max: Decimal | None = Decimal("20"),
        energy_min: Decimal | None = Decimal("10"),
        energy_max: Decimal | None = Decimal("15"),
        waste_min: Decimal | None = None,
        waste_max: Decimal | None = None,
        code: str = "INT-TEST-1",
    ):
        return CircularIntervention(
            id=new_id(),
            intervention_code=f"{code}-{new_id()[:6]}",
            title=title,
            industry_sector="Textile",
            process_category=process_category,
            min_capex=min_capex,
            max_capex=max_capex,
            currency="INR",
            expected_co2_reduction_min_pct=co2_min,
            expected_co2_reduction_max_pct=co2_max,
            energy_reduction_min_pct=energy_min,
            energy_reduction_max_pct=energy_max,
            waste_reduction_min_pct=waste_min,
            waste_reduction_max_pct=waste_max,
            implementation_months_min=2,
            implementation_months_max=6,
            complexity="LOW",
            risk_level="LOW",
            active=True,
        )

    return _make


@pytest.fixture
def mock_engine():
    from engine.data_source import load_mock_data_source
    from engine.service import EcoLeakEngine

    engine = EcoLeakEngine(data_source=load_mock_data_source())
    ctx = engine.default_context()
    return engine, ctx["facility_id"], ctx["reporting_period_id"]


@pytest.fixture
def simple_engine():
    """An in-memory single-process gas boiler facility (1 t production)."""

    def _build(*, production: Decimal | None = Decimal("1000"), include_factor: bool = True):
        from engine.service import EcoLeakEngine

        facility = Facility(
            id=new_id(),
            organization_id=new_id(),
            name="Simple Facility",
            country="India",
            annual_production=production,
            production_unit="tonne",
            created_at=NOW,
            updated_at=NOW,
        )
        period = ReportingPeriod(
            id=new_id(),
            facility_id=facility.id,
            period_type=PeriodType.ANNUAL,
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            created_at=NOW,
        )
        process = Process(
            id=new_id(),
            facility_id=facility.id,
            name="Boiler",
            sequence_no=1,
            process_category="Utilities",
            created_at=NOW,
        )
        activity = ActivityData(
            id=new_id(),
            facility_id=facility.id,
            process_id=process.id,
            reporting_period_id=period.id,
            activity_category=ActivityCategory.FUEL,
            activity_subcategory="Natural gas - stationary combustion",
            normalized_value=Decimal("1000"),
            normalized_unit="m3",
            original_value=Decimal("1000"),
            original_unit="m3",
            created_at=NOW,
        )
        factors = []
        if include_factor:
            factors.append(
                EmissionFactor(
                    id=new_id(),
                    factor_code="EF-FUEL-NG",
                    category="FUEL",
                    subcategory="Natural gas",
                    item_name="Natural gas - stationary combustion",
                    scope=Scope.SCOPE_1,
                    input_unit="m3",
                    total_co2e_factor=Decimal("2.0"),
                    source_name="Test",
                    source_year=2023,
                    version="1.0",
                    confidence_level=ConfidenceLevel.HIGH,
                    active=True,
                    created_at=NOW,
                )
            )
        ds = InMemoryDataSource(
            facilities=[facility],
            reporting_periods=[period],
            processes=[process],
            activity_data=[activity],
            emission_factors=factors,
        )
        engine = EcoLeakEngine(data_source=ds)
        return engine, facility, period, process

    return _build
