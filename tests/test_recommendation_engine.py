"""Module J - engine, ranking formula, determinism, and output shape tests."""

import json
from datetime import datetime

from p4.demo.run_demo import _shape_diff
from p4.engine import generate_recommendations
from p4.explainability import LLMExplainer
from p4.models import ScoreBreakdown
from p4.scoring import WEIGHTS, weighted_final_score
from p4.serialization import to_api_dict
from tests import helpers


def test_weights_match_requirements_doc_exactly():
    assert WEIGHTS == {
        "carbon_saving": 0.30,
        "financial_return": 0.25,
        "feasibility": 0.15,
        "circularity": 0.15,
        "implementation_speed": 0.10,
        "confidence": 0.05,
    }
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-12


def test_weighted_formula_matches_manual_computation():
    scores = ScoreBreakdown(
        carbon_saving=70.0,
        financial_return=90.0,
        feasibility=80.0,
        circularity=60.0,
        implementation_speed=88.0,
        confidence=84.0,
    )
    expected = (
        0.30 * 70.0 + 0.25 * 90.0 + 0.15 * 80.0 + 0.15 * 60.0 + 0.10 * 88.0 + 0.05 * 84.0
    )
    assert weighted_final_score(scores) == round(expected, 2)


def test_output_shape_matches_phase0_mock_exactly():
    run = helpers.run_engine()
    generated = to_api_dict(run.result)
    expected = helpers._load(helpers.MOCKS_DIR / "mock_recommendation_output.json")
    problems = _shape_diff(generated, expected)
    assert not problems, problems


def test_serialized_numeric_types_match_phase0_mock():
    generated = to_api_dict(helpers.run_engine().result)
    mock = helpers._load(helpers.MOCKS_DIR / "mock_recommendation_output.json")
    rec = generated["recommendations"][0]
    mock_rec = mock["recommendations"][0]

    score_keys = (
        "carbon_saving_score",
        "financial_return_score",
        "feasibility_score",
        "circularity_score",
        "implementation_speed_score",
        "confidence_score",
        "final_score",
    )
    for key in score_keys:
        assert isinstance(rec[key], float) and isinstance(mock_rec[key], float), key
    assert isinstance(rec["rank"], int) and isinstance(mock_rec["rank"], int)

    for key in (
        "estimated_capex",
        "estimated_annual_saving",
        "estimated_co2_saving_kg",
        "estimated_energy_saving",
        "estimated_waste_reduction",
        "payback_years",
        "cost_per_tonne_co2_avoided",
    ):
        assert rec["impact"][key] is None or isinstance(rec["impact"][key], float), key

    assert isinstance(rec["generated_at"], str)
    assert datetime.fromisoformat(rec["generated_at"])
    assert isinstance(rec["id"], str)


def test_ranking_is_sorted_and_ranks_are_sequential():
    run = helpers.run_engine()
    scores = [float(rec.final_score) for rec in run.result.recommendations]
    assert scores == sorted(scores, reverse=True)
    assert [rec.rank for rec in run.result.recommendations] == list(
        range(1, len(run.result.recommendations) + 1)
    )


def test_engine_is_deterministic_with_fixed_clock():
    first = helpers.run_engine().result.model_dump(mode="json")
    second = helpers.run_engine().result.model_dump(mode="json")
    assert first == second


def test_recommendation_ids_are_stable_uuid5():
    first = helpers.run_engine().result
    second = helpers.run_engine().result
    assert [rec.id for rec in first.recommendations] == [rec.id for rec in second.recommendations]


def test_llm_explainer_cannot_change_numeric_ranking():
    baseline = helpers.run_engine(explainer=None).result

    def evidence_aware_llm(prompt: str) -> str:
        payload = json.loads(prompt)
        evidence = payload["evidence"]
        code = evidence["intervention_code"]
        parts = []
        if evidence.get("hotspot_contribution_percent") is not None:
            parts.append(
                f"The targeted hotspot contributes {evidence['hotspot_contribution_percent']}% of operational emissions."
            )
        if evidence.get("estimated_co2_saving_kg") is not None:
            parts.append(
                f"Estimated saving is {evidence['estimated_co2_saving_kg']} kgCO2e per year."
            )
        parts.append(
            f"Confidence {evidence['confidence_score']} of 100; treats estimates as uncertain."
        )
        return json.dumps({"explanation": " ".join(parts), "cited_intervention_codes": [code]})

    with_llm = helpers.run_engine(explainer=LLMExplainer(evidence_aware_llm))
    result = with_llm.result
    assert [rec.final_score for rec in baseline.recommendations] == [
        rec.final_score for rec in result.recommendations
    ]
    assert [rec.rank for rec in baseline.recommendations] == [
        rec.rank for rec in result.recommendations
    ]
    assert [rec.id for rec in baseline.recommendations] == [
        rec.id for rec in result.recommendations
    ]
    llm_used = with_llm.diagnostics.explanation_sources.get("llm", 0)
    assert llm_used == len(result.recommendations), (
        "all validated LLM narratives must be used, yet ranking stays deterministic"
    )


def test_dedupe_keeps_one_recommendation_per_intervention():
    run = helpers.run_engine()
    codes = [rec.intervention_code for rec in run.result.recommendations]
    assert len(codes) == len(set(codes))
    assert any("INT-SOLAR-002" in item for item in run.diagnostics.duplicates_removed)


def test_tie_breaker_prefers_lower_intervention_code():
    entries = [
        helpers.make_entry(
            id="0a1b2c3d-0e0a-4e0a-8e0a-000000000e0a",
            intervention_code="INT-TIE-B",
            title="Tie B",
        ),
        helpers.make_entry(
            id="0a1b2c3d-0e0b-4e0b-8e0b-000000000e0b",
            intervention_code="INT-TIE-A",
            title="Tie A",
        ),
    ]
    run = helpers.run_engine(library=helpers.make_library(entries))
    codes = [rec.intervention_code for rec in run.result.recommendations]
    assert codes == ["INT-TIE-A", "INT-TIE-B"]
    assert float(run.result.recommendations[0].final_score) == float(
        run.result.recommendations[1].final_score
    )


def test_top_recommendation_is_attached_to_a_real_hotspot():
    run = helpers.run_engine()
    hotspot_ids = {item.id for item in helpers.hotspot_envelope().hotspots}
    for rec in run.result.recommendations:
        assert rec.hotspot_id in hotspot_ids
        assert rec.id not in {other.id for other in run.result.recommendations if other is not rec}
        assert rec.explanation and rec.explanation.strip()


def test_public_function_returns_contract_shape_only():
    result = generate_recommendations(helpers.hotspot_envelope(), helpers.facility())
    assert not hasattr(result, "diagnostics")
    assert result.recommendations
    assert all(rec.impact.assumptions is not None for rec in result.recommendations)
    assert all(rec.explanation for rec in result.recommendations)


def test_high_saving_low_feasibility_ranks_lower():
    entry_a = helpers.make_entry(
        id="0a1b2c3d-0e21-4e21-8e21-000000000e21",
        intervention_code="INT-FEAS-A",
        title="Moderate saving, easy",
        expected_co2_reduction_min_pct=8,
        expected_co2_reduction_max_pct=8,
        complexity="LOW",
        risk_level="LOW",
        implementation_months_min=1,
        implementation_months_max=2,
    )
    entry_b = helpers.make_entry(
        id="0a1b2c3d-0e22-4e22-8e22-000000000e22",
        intervention_code="INT-FEAS-B",
        title="High saving, hard",
        expected_co2_reduction_min_pct=15,
        expected_co2_reduction_max_pct=15,
        complexity="HIGH",
        risk_level="HIGH",
        implementation_months_min=10,
        implementation_months_max=14,
    )
    run = helpers.run_engine(library=helpers.make_library([entry_b, entry_a]), use_factors=False)
    order = [rec.intervention_code for rec in run.result.recommendations]
    assert order == ["INT-FEAS-A", "INT-FEAS-B"]
    hard = next(rec for rec in run.result.recommendations if rec.intervention_code == "INT-FEAS-B")
    assert float(hard.carbon_saving_score) > float(run.result.recommendations[0].carbon_saving_score)
