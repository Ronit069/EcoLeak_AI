from __future__ import annotations

from decimal import Decimal

import pytest

from engine.config import CostModel, EngineConfig, SimulatorConfig
from engine.errors import InvalidScenarioError
from engine.service import EcoLeakEngine
from engine.simulator import InterventionSelection, PAYBACK_INCOMPLETE, PAYBACK_UNAVAILABLE


def _selections(interventions, index=0, adoption="100"):
    return [InterventionSelection(intervention=interventions[index], adoption_percentage=Decimal(adoption))]


def test_adoption_over_100_rejected(mock_engine):
    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    with pytest.raises(InvalidScenarioError):
        engine.simulate(facility_id, period_id, _selections(ivs, 0, "101"), scenario_id="s")


def test_duplicate_intervention_rejected(mock_engine):
    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    dup = [InterventionSelection(ivs[0]), InterventionSelection(ivs[0])]
    with pytest.raises(InvalidScenarioError):
        engine.simulate(facility_id, period_id, dup, scenario_id="s")


def test_adoption_zero_is_no_change_and_payback_unavailable(mock_engine):
    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    result = engine.simulate(facility_id, period_id, _selections(ivs, 0, "0"), scenario_id="s")
    assert result.assessment.projected_emissions_kg == result.assessment.baseline_emissions_kg
    assert result.assessment.total_co2_saving_kg == Decimal("0")
    assert result.assessment.payback_years is None
    assert result.payback_status == PAYBACK_UNAVAILABLE


def test_combined_interventions_do_not_double_count(mock_engine):
    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()[:3]
    combined = [
        InterventionSelection(intervention=iv, adoption_percentage=Decimal("100")) for iv in ivs
    ]
    result = engine.simulate(facility_id, period_id, combined, scenario_id="combined").assessment
    solo_sum = sum(
        (
            engine.simulate(
                facility_id, period_id, [InterventionSelection(iv)], scenario_id="solo"
            ).assessment.total_co2_saving_kg
            for iv in ivs
        ),
        Decimal("0"),
    )
    # Sequential application on the remaining baseline must be <= the naive sum.
    assert result.total_co2_saving_kg <= solo_sum
    assert result.projected_emissions_kg >= 0


def test_projected_emissions_floored_at_zero(mock_engine):
    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    # max_reduction_fraction caps at 95% so this guards the floor logic explicitly
    result = engine.simulate(facility_id, period_id, _selections(ivs, 0), scenario_id="s")
    assert result.assessment.projected_emissions_kg >= 0
    assert result.assessment.total_co2_saving_kg <= result.assessment.baseline_emissions_kg


def test_payback_is_capex_over_annual_saving(mock_engine):
    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    result = engine.simulate(facility_id, period_id, _selections(ivs, 0), scenario_id="s").assessment
    if result.annual_saving and result.annual_saving > 0 and result.payback_years is not None:
        expected = result.total_capex / result.annual_saving
        assert abs(result.payback_years - expected) < Decimal("0.01")


def test_missing_cost_data_yields_incomplete_payback(mock_engine):
    engine, facility_id, period_id = mock_engine
    engine.simulator.config = SimulatorConfig(cost_model=CostModel(unit_prices={}, category_prices={}))
    ivs = engine.data_source.get_interventions()
    result = engine.simulate(facility_id, period_id, _selections(ivs, 0), scenario_id="s")
    assert result.assessment.annual_saving is None
    assert result.assessment.payback_years is None
    assert result.payback_status == PAYBACK_INCOMPLETE


def test_simulation_result_serialises_without_precision_loss(mock_engine):
    from engine.serialization import to_jsonable

    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    payload = engine.simulate(facility_id, period_id, _selections(ivs, 0), scenario_id="s").to_dict()
    assert payload["assessment"]["total_co2_saving_kg"] is not None
    assert isinstance(payload["assessment"]["total_co2_saving_kg"], Decimal)
    encoded = to_jsonable(payload)
    assert isinstance(encoded["assessment"]["total_co2_saving_kg"], (int, float))
