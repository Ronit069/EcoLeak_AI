from __future__ import annotations

import json
from pathlib import Path

from contracts.schemas import ImpactAssessment

from engine.serialization import to_jsonable
from validate_against_mock import compare, shape_of

ROOT = Path(__file__).resolve().parent.parent


def test_hotspot_shape_matches_mock(mock_engine):
    engine, facility_id, period_id = mock_engine
    engine_output = to_jsonable(engine.detect_hotspots(facility_id, period_id).result)
    mock = json.loads((ROOT / "mocks" / "mock_hotspot_output.json").read_text(encoding="utf-8"))
    mismatches: list[str] = []
    compare(shape_of(mock), shape_of(engine_output), "root", mismatches)
    assert mismatches == []


def test_impact_assessment_shape_matches_contract(mock_engine):
    from engine.simulator import InterventionSelection

    engine, facility_id, period_id = mock_engine
    ivs = engine.data_source.get_interventions()
    result = engine.simulate(facility_id, period_id, [InterventionSelection(ivs[0])], scenario_id="s")
    payload = result.assessment.model_dump(mode="json")
    assert set(payload.keys()) == set(ImpactAssessment.model_fields.keys())
