from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from contracts.schemas import (
    ActivityCategory,
    ActivityData,
    EmissionFactor,
    Facility,
    Process,
    ReportingPeriod,
    PeriodType,
    Scope,
)
from engine.data_source import InMemoryDataSource
from engine.service import EcoLeakEngine

NOW = datetime(2026, 4, 5, tzinfo=timezone.utc)


def test_fixture_baseline_reproduced(mock_engine):
    engine, facility_id, period_id = mock_engine
    inv = engine.calculate_inventory(facility_id, period_id)
    assert inv.scope1_kgco2e == Decimal("224250")
    assert inv.scope2_kgco2e == Decimal("340800")
    assert inv.operational_kgco2e == Decimal("565050")
    assert inv.scope3_kgco2e > 0


def test_calculation_carries_factor_provenance(mock_engine):
    engine, facility_id, period_id = mock_engine
    inv = engine.calculate_inventory(facility_id, period_id)
    resolved = [r for r in inv.records if r.calculation is not None]
    assert resolved, "expected resolved calculations"
    for record in resolved:
        assumptions = record.calculation.assumptions
        assert assumptions["factor_version"]
        assert assumptions["factor_source"]
        assert assumptions["calculation_version"] == engine.config.calculation_version
    assert inv.factor_provenance()


def test_missing_factor_is_unresolved_not_fabricated(simple_engine):
    engine, facility, period, _process = simple_engine(include_factor=False)
    inv = engine.calculate_inventory(str(facility.id), str(period.id))
    assert inv.total_kgco2e == Decimal("0")
    assert len(inv.unresolved) == 1
    assert inv.unresolved[0].code == "EMISSION_FACTOR_NOT_FOUND"


def test_zero_activity_gives_zero_emission(simple_engine):
    engine, facility, period, process = simple_engine()
    activity = ActivityData(
        id=str(__import__("uuid").uuid4()),
        facility_id=facility.id,
        process_id=process.id,
        reporting_period_id=period.id,
        activity_category=ActivityCategory.FUEL,
        activity_subcategory="Natural gas - stationary combustion",
        normalized_value=Decimal("0"),
        normalized_unit="m3",
        original_value=Decimal("0"),
        original_unit="m3",
        created_at=NOW,
    )
    ds = InMemoryDataSource(
        facilities=[facility],
        reporting_periods=[period],
        processes=[process],
        activity_data=[activity],
        emission_factors=engine.data_source.get_emission_factors(),
    )
    inv = EcoLeakEngine(data_source=ds).calculate_inventory(str(facility.id), str(period.id))
    assert inv.total_kgco2e == Decimal("0")
    assert not inv.unresolved


def test_negative_activity_is_flagged():
    # Contract forbids negative values; construct one bypassing validation to
    # prove the engine still refuses to calculate it.
    negative = ActivityData.model_construct(
        id="11111111-1111-4111-8111-111111111111",
        facility_id="22222222-2222-4222-8222-222222222222",
        reporting_period_id="33333333-3333-4333-8333-333333333333",
        process_id=None,
        activity_category=ActivityCategory.FUEL,
        activity_subcategory="Natural gas - stationary combustion",
        normalized_value=Decimal("-10"),
        normalized_unit="m3",
        original_value=Decimal("-10"),
        original_unit="m3",
        source_name=None,
        notes=None,
        confidence_score=None,
        created_at=NOW,
    )
    facility = Facility(
        id="22222222-2222-4222-8222-222222222222",
        organization_id="44444444-4444-4444-8444-444444444444",
        name="F",
        country="India",
        created_at=NOW,
        updated_at=NOW,
    )
    factor = EmissionFactor(
        id="55555555-5555-4555-8555-555555555555",
        factor_code="EF-NG",
        category="FUEL",
        subcategory="Natural gas",
        item_name="Natural gas - stationary combustion",
        scope=Scope.SCOPE_1,
        input_unit="m3",
        total_co2e_factor=Decimal("2"),
        source_name="t",
        source_year=2023,
        version="1",
        active=True,
        created_at=NOW,
    )
    from engine.carbon import CarbonAccountingEngine

    inv = CarbonAccountingEngine().calculate(
        facility=facility,
        reporting_period_id=str(facility.id),
        activity_data=[negative],
        emission_factors=[factor],
    )
    assert inv.total_kgco2e == Decimal("0")
    assert inv.unresolved and inv.unresolved[0].code == "NEGATIVE_ACTIVITY"


def test_onsite_generation_and_export_kept_in_separate_ledgers():
    facility = Facility(
        id="22222222-2222-4222-8222-222222222222",
        organization_id="44444444-4444-4444-8444-444444444444",
        name="Solar Co",
        country="India",
        annual_production=Decimal("100"),
        production_unit="tonne",
        created_at=NOW,
        updated_at=NOW,
    )
    period = ReportingPeriod(
        id="33333333-3333-4333-8333-333333333333",
        facility_id=facility.id,
        period_type=PeriodType.ANNUAL,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        created_at=NOW,
    )
    proc = Process(id="66666666-6666-4666-8666-666666666666", facility_id=facility.id, name="Grid", created_at=NOW)
    factor = EmissionFactor(
        id="55555555-5555-4555-8555-555555555555",
        factor_code="EF-ELEC",
        category="ELECTRICITY",
        subcategory="Purchased electricity",
        item_name="Grid electricity",
        scope=Scope.SCOPE_2,
        input_unit="kWh",
        total_co2e_factor=Decimal("0.5"),
        source_name="t",
        source_year=2023,
        version="1",
        active=True,
        created_at=NOW,
    )

    def activity(sub, val):
        return ActivityData(
            id=str(__import__("uuid").uuid4()),
            facility_id=facility.id,
            process_id=proc.id,
            reporting_period_id=period.id,
            activity_category=ActivityCategory.ELECTRICITY,
            activity_subcategory=sub,
            normalized_value=val,
            normalized_unit="kWh",
            original_value=val,
            original_unit="kWh",
            created_at=NOW,
        )

    rows = [
        activity("Purchased grid electricity", Decimal("1000")),
        activity("Solar on-site self-consumption", Decimal("2000")),
        activity("Exported electricity to grid", Decimal("500")),
    ]
    ds = InMemoryDataSource(
        facilities=[facility], reporting_periods=[period], processes=[proc],
        activity_data=rows, emission_factors=[factor],
    )
    inv = EcoLeakEngine(data_source=ds).calculate_inventory(str(facility.id), str(period.id))
    assert inv.scope2_kgco2e == Decimal("500.000000")  # only purchased grid counted
    assert inv.onsite_generation_kgco2e == Decimal("1000.000000")
    assert inv.exported_electricity_kgco2e == Decimal("250.000000")
    assert inv.exported_electricity_count == 1


def test_aggregations_by_scope_process_source_category(mock_engine):
    engine, facility_id, period_id = mock_engine
    inv = engine.calculate_inventory(facility_id, period_id)
    assert set(inv.by_category().keys()) >= {"ELECTRICITY", "FUEL", "MATERIAL", "WASTE", "WATER", "TRANSPORT"}
    by_process = inv.by_process()
    assert sum(by_process.values(), Decimal("0")) == inv.total_kgco2e
    assert sum(inv.by_source().values(), Decimal("0")) == inv.total_kgco2e
