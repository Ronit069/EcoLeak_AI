from __future__ import annotations

from decimal import Decimal

from contracts.schemas import HotspotSeverity, Scope
from engine.config import HotspotConfig, HotspotWeights
from engine.service import EcoLeakEngine


def test_mock_rank_order_and_contributions(mock_engine):
    engine, facility_id, period_id = mock_engine
    analysis = engine.detect_hotspots(facility_id, period_id)
    names = [h.process_name for h in analysis.result.hotspots]
    assert names == ["Boiler", "Dyeing", "Drying", "Finishing", "Packaging"]
    assert analysis.result.total_emissions_kgco2e == Decimal("565050.000000")
    # Contributions sum to ~100%
    total = sum((h.contribution_percent for h in analysis.result.hotspots), Decimal("0"))
    assert abs(total - Decimal("100")) < Decimal("0.01")
    # Carbon intensity (kgCO2e / production tonne) matches the fixture values
    assert analysis.result.hotspots[0].carbon_intensity == Decimal("224.25")
    assert analysis.result.hotspots[0].severity in HotspotSeverity
    assert analysis.top_actionable_hotspot_id is not None


def test_weights_are_configurable(mock_engine):
    engine, facility_id, period_id = mock_engine
    only_contribution = HotspotWeights(
        carbon_contribution=1.0, carbon_intensity=0.0, inefficiency=0.0,
        waste_ratio=0.0, improvement_potential=0.0,
    )
    analysis = engine.detect_hotspots(facility_id, period_id, weights=only_contribution)
    boiler = analysis.result.hotspots[0]
    # With only the contribution weight active, score == contribution (to rounding).
    assert abs(boiler.hotspot_score - boiler.contribution_percent) < Decimal("0.01")


def test_missing_production_skips_intensity_gracefully(mock_engine):
    engine, facility_id, period_id = mock_engine
    # Rebuild inventory with zero production via a custom engine config is not
    # needed - override the data source facility.
    facility = engine.facility(facility_id)
    facility = facility.model_copy(update={"annual_production": Decimal("0")})
    engine.data_source._facilities[facility_id] = facility  # noqa: SLF001 (test seam)
    analysis = engine.detect_hotspots(facility_id, period_id)
    assert all(h.carbon_intensity is None for h in analysis.result.hotspots)
    assert any(i["code"] == "INTENSITY_SKIPPED" for i in analysis.issues)
    assert analysis.result.hotspots  # ranking still produced


def test_zero_total_emissions_no_percentage(simple_engine):
    engine, facility, period, process = simple_engine()
    from contracts.schemas import ActivityData, ActivityCategory

    zero = ActivityData(
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
        created_at=__import__("datetime").datetime(2026, 1, 1),
    )
    from engine.data_source import InMemoryDataSource

    ds = InMemoryDataSource(
        facilities=[facility], reporting_periods=[period], processes=[process],
        activity_data=[zero], emission_factors=engine.data_source.get_emission_factors(),
    )
    eng = EcoLeakEngine(data_source=ds)
    analysis = eng.detect_hotspots(str(facility.id), str(period.id))
    assert analysis.result.total_emissions_kgco2e == Decimal("0")
    assert all(h.contribution_percent is None for h in analysis.result.hotspots)
    assert any(i["code"] == "ZERO_TOTAL_EMISSIONS" for i in analysis.issues)


def test_missing_benchmark_reweights_components(mock_engine):
    engine, facility_id, period_id = mock_engine
    config = HotspotConfig()
    config.inefficiency_strategy = "UNAVAILABLE"
    engine.hotspots.config = config
    analysis = engine.detect_hotspots(facility_id, period_id)
    # Score still produced from remaining components
    assert all(h.hotspot_score is not None for h in analysis.result.hotspots)
    assert all(h.inefficiency_score is None for h in analysis.result.hotspots)


def test_scope_boundary_filters(mock_engine):
    engine, facility_id, period_id = mock_engine
    only_scope2 = engine.detect_hotspots(facility_id, period_id, scope_boundary=[Scope.SCOPE_2])
    # Only electricity processes: Dyeing, Drying, Finishing, Packaging
    names = {h.process_name for h in only_scope2.result.hotspots}
    assert names == {"Dyeing", "Drying", "Finishing", "Packaging"}
    assert only_scope2.result.total_emissions_kgco2e == Decimal("340800.000000")
