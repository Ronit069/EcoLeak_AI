"""Module J and Module K edge cases from the security/DB doc (section 21)."""

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from p4.contracts import ScenarioIntervention
from p4.financial import apply_adoption, compute_payback, project_emissions
from p4.models import RecommendationConstraints
from tests import helpers


# ---------------------------------------------------------------------------
# Module J edge cases
# ---------------------------------------------------------------------------


def test_j_budget_zero_prioritizes_no_capex_interventions():
    run = helpers.run_engine(constraints=RecommendationConstraints(budget_limit=0))
    assert run.result.recommendations, "budget=0 must still surface no-CAPEX actions"
    assert all(
        rec.impact.estimated_capex == Decimal("0")
        for rec in run.result.recommendations
    )
    assert "INT-NOCAPEX-019" in {rec.intervention_code for rec in run.result.recommendations}


def test_j_budget_exceeded_is_filtered_before_ranking():
    entry = helpers.make_entry(min_capex=100_000, max_capex=100_000)
    run = helpers.run_engine(
        library=helpers.make_library([entry]),
        constraints=RecommendationConstraints(budget_limit=50_000),
    )
    assert run.result.recommendations == []
    reasons = {record.reason for record in run.diagnostics.filtered}
    assert "BUDGET_EXCEEDED" in reasons


def test_j_budget_allows_only_affordable_interventions():
    run = helpers.run_engine(constraints=RecommendationConstraints(budget_limit=50_000))
    assert run.result.recommendations, "zero-CAPEX actions must survive an affordable budget"
    assert all(rec.impact.estimated_capex == Decimal("0") for rec in run.result.recommendations)


def test_j_no_feasible_intervention_returns_empty_without_fabrication():
    entry = helpers.make_entry(min_annual_production_tonnes=100_000)
    run = helpers.run_engine(library=helpers.make_library([entry]))
    assert run.result.recommendations == []
    assert any(
        record.reason == "BELOW_MIN_SCALE" for record in run.diagnostics.filtered
    )


def test_j_duplicate_recommendations_are_deduplicated():
    run = helpers.run_engine()
    codes = [rec.intervention_code for rec in run.result.recommendations]
    assert len(codes) == len(set(codes))
    solar_hits = [code for code in codes if code == "INT-SOLAR-002"]
    assert len(solar_hits) == 1
    assert any("INT-SOLAR-002" in item for item in run.diagnostics.duplicates_removed)


def test_j_conflicting_interventions_are_marked_mutually_exclusive():
    run = helpers.run_engine()
    conflict_pairs = [sorted(pair) for pair in run.diagnostics.conflicts]
    assert sorted(["INT-SOLAR-002", "INT-SOLAR-THERMAL-018"]) in conflict_pairs
    solar_recs = [
        rec
        for rec in run.result.recommendations
        if rec.intervention_code in {"INT-SOLAR-002", "INT-SOLAR-THERMAL-018"}
    ]
    assert all("Mutually exclusive" in (rec.explanation or "") for rec in solar_recs)


def test_j_missing_capex_does_not_fabricate_payback_or_cost():
    entry = helpers.make_entry(min_capex=None, max_capex=None, opex_impact="NEUTRAL")
    run = helpers.run_engine(library=helpers.make_library([entry]))
    rec = run.result.recommendations[0]
    assert rec.impact.estimated_capex is None
    assert rec.impact.payback_years is None
    assert rec.impact.cost_per_tonne_co2_avoided is None
    assert float(rec.financial_return_score) == 0.0
    assert "payback_note" in rec.impact.assumptions


def test_j_missing_co2_estimate_stays_qualitative_and_scores_zero_carbon():
    entry = helpers.make_entry(
        expected_co2_reduction_min_pct=None,
        expected_co2_reduction_max_pct=None,
    )
    run = helpers.run_engine(library=helpers.make_library([entry]), use_factors=False)
    rec = run.result.recommendations[0]
    assert rec.impact.estimated_co2_saving_kg is None
    assert float(rec.carbon_saving_score) == 0.0
    assert rec.explanation


def test_j_constraint_change_after_generation_reranks():
    open_run = helpers.run_engine(constraints=RecommendationConstraints(budget_limit=5_000_000))
    tight_run = helpers.run_engine(constraints=RecommendationConstraints(budget_limit=0))
    assert len(open_run.result.recommendations) > len(tight_run.result.recommendations)
    assert [rec.intervention_code for rec in open_run.result.recommendations] != [
        rec.intervention_code for rec in tight_run.result.recommendations
    ]


def test_j_region_unavailability_lowers_feasibility_not_hides_it():
    entry = helpers.make_entry(applicable_regions=["Germany"])
    constraints = RecommendationConstraints(region_country="India", region_state="Gujarat")
    with_mismatch = helpers.run_engine(
        library=helpers.make_library([entry]), constraints=constraints
    )
    without_region = helpers.run_engine(
        library=helpers.make_library([entry]), constraints=RecommendationConstraints()
    )
    mismatch_score = float(with_mismatch.result.recommendations[0].feasibility_score)
    baseline_score = float(without_region.result.recommendations[0].feasibility_score)
    assert mismatch_score == baseline_score - 15.0
    assert any("region" in note for note in with_mismatch.diagnostics.scored[0].feasibility_notes)


def test_j_locally_unavailable_and_user_exclusions_are_hard_filters():
    entry = helpers.make_entry()
    constraints = RecommendationConstraints(locally_unavailable_codes=["INT-TEST-001"])
    run = helpers.run_engine(library=helpers.make_library([entry]), constraints=constraints)
    assert run.result.recommendations == []
    assert run.diagnostics.filtered[0].reason == "LOCALLY_UNAVAILABLE"

    excluded = RecommendationConstraints(excluded_intervention_codes=["INT-TEST-001"])
    run = helpers.run_engine(library=helpers.make_library([entry]), constraints=excluded)
    assert run.diagnostics.filtered[0].reason == "EXCLUDED_BY_USER"


def test_j_max_payback_filter():
    entry = helpers.make_entry(min_capex=2_000_000, max_capex=2_000_000)
    run = helpers.run_engine(
        library=helpers.make_library([entry]),
        constraints=RecommendationConstraints(max_payback_years=Decimal("1")),
    )
    assert run.result.recommendations == []
    assert any(record.reason == "MAX_PAYBACK_EXCEEDED" for record in run.diagnostics.filtered)


def test_j_prerequisites_penalize_or_hard_filter():
    entry = helpers.make_entry(prerequisite_codes=["INT-MISSING-000"])
    relaxed = helpers.run_engine(library=helpers.make_library([entry]))
    candidate = relaxed.diagnostics.scored[0]
    assert candidate.prerequisites_unmet == ["INT-MISSING-000"]
    assert any("prerequisite" in note for note in candidate.feasibility_notes)
    assert relaxed.result.recommendations, "unmet prereq only penalizes in relaxed mode"

    strict = helpers.run_engine(
        library=helpers.make_library([entry]),
        constraints=RecommendationConstraints(require_prerequisites_met=True),
    )
    assert strict.result.recommendations == []
    assert any(
        record.intervention_code == "INT-TEST-001" and record.reason == "PREREQUISITES_UNMET"
        for record in strict.diagnostics.filtered
    )


def test_j_currency_mismatch_kept_separate():
    entry = helpers.make_entry(currency="USD")
    run = helpers.run_engine(library=helpers.make_library([entry]))
    assert run.result.recommendations == []
    assert run.diagnostics.filtered[0].reason == "CURRENCY_MISMATCH"


# ---------------------------------------------------------------------------
# Module K edge cases
# ---------------------------------------------------------------------------


def test_k_annual_saving_zero_gives_no_payback():
    payback, reason = compute_payback(Decimal("1000000"), Decimal("0"))
    assert payback is None
    assert "zero" in reason


def test_k_negative_saving_reports_additional_cost():
    payback, reason = compute_payback(Decimal("1000000"), Decimal("-50000"))
    assert payback is None
    assert "additional annual cost" in reason


def test_k_zero_capex_gives_immediate_payback():
    payback, reason = compute_payback(Decimal("0"), Decimal("120000"))
    assert payback == Decimal("0")
    assert "immediate" in reason


def test_k_adoption_zero_means_no_change():
    assert apply_adoption(Decimal("100000"), Decimal("0")) == Decimal("0")
    projected, saving, notes = project_emissions(Decimal("1000"), [Decimal("0")])
    assert projected == Decimal("1000")
    assert saving == Decimal("0")
    assert notes == []


def test_k_adoption_over_100_is_rejected_by_contract():
    with pytest.raises(ValidationError):
        ScenarioIntervention.model_validate(
            {
                "id": str(UUID(int=1)),
                "scenario_id": str(UUID(int=2)),
                "recommendation_id": str(UUID(int=3)),
                "adoption_percentage": 120,
            }
        )


def test_k_projected_emissions_floored_at_zero_and_saving_capped():
    projected, saving, notes = project_emissions(
        Decimal("100"), [Decimal("150"), Decimal("20")]
    )
    assert projected == Decimal("0")
    assert saving == Decimal("100")
    assert any("capped at the source" in note for note in notes)
    assert not any("floored" in note for note in notes)


def test_k_sequential_application_prevents_double_counting():
    projected, saving, notes = project_emissions(
        Decimal("100"), [Decimal("60"), Decimal("60")]
    )
    assert projected == Decimal("0")
    assert saving == Decimal("100")
    assert notes, "second saving must be reported as capped"
