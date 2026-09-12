# P4 — AI Recommendation, Explainability & Demo (Phase 1)

> **Phase 2:** the hotspot input is now swapped to P3's live Engine G output
> behind the shared `USE_MOCK_DATA` flag (mock remains the default and instant
> fallback). See `docs/phase2/p4_integration_log.md`, `docs/phase2/p4_shape_diff.md`,
> and run `python -m tools.phase2_p4_shape_diff`.
>
> **Phase 4 (demo-ready):** click-by-click judge script in `docs/phase4/demo_script.md`,
> defensibility appendix in `docs/phase4/pitch_appendix.md`, and the Phase 4 bug log in
> `docs/phase4/bugs_found.md`.

Callable, dependency-light Python package implementing Modules I, J, M, Q plus the
full textile SME demo and the Module J/K edge-case suite. The frozen Phase 0
contracts in `contracts/` and `mocks/` were **not modified** (`python validate_mocks.py`
still passes 9/9).

## What is where

| Path | Module | What it does |
|---|---|---|
| `p4/interventions/intervention_library.json` | I | 19 validated interventions (energy, heat recovery, materials, water, waste, packaging, chemicals), each with CAPEX/OPEX, CO2/energy/waste/water reductions, implementation time, complexity, risk, technical requirements, applicability, prerequisites/conflicts, evidence source |
| `p4/library.py` | I | Loader + query API (`InterventionLibrary`, `default_library()`) |
| `p4/scoring.py` | J | Deterministic sub-score rubrics + the exact requirements-doc weighted formula |
| `p4/engine.py` | J | Candidate generation → hard feasibility filters → dedupe → ranking → output envelope |
| `p4/financial.py` | J/K | Resource savings, payback, adoption, sequential projection (K-safe) |
| `p4/explainability.py` | M | Evidence builder, LLM output validation, numeric contradiction checker, template fallback |
| `p4/feedback.py` | Q | Append-only feedback store, latest + full history, structured rejection reasons |
| `p4/demo/demo_context.json` | demo | Process-level resource baselines, tariffs, conversion factors |
| `p4/serialization.py` | J/P2 | FastAPI-compatible JSON serializer (Decimal -> number, ISO datetimes, UUID strings) |
| `p4/demo/run_demo.py` | demo | Runs the full scenario offline and verifies shape against `mocks/mock_recommendation_output.json` |
| `p4/demo/output/` | demo | Generated `demo_recommendation_output.json` + `demo_explanations.md` |
| `tests/` | — | 55 tests covering I, J, M, Q and the J/K edge cases |

## Run it

```bash
python -m pytest tests -q          # 55 passed
python -m p4.demo.run_demo         # shape check PASS + ranked table + artifacts
```

## Deterministic pipeline (LLM cannot touch numbers)

```
hotspots + facility + context + constraints
        │  applicability match (industry/process/activity/resource signal)
        │  hard filters: excluded, local availability, complexity limit, scale,
        │  currency, budget ceiling, max payback, prerequisites
        │  dedupe (one rec per intervention, best hotspot)
        ▼
sub-scores 0..100  →  final = 0.30·carbon + 0.25·financial + 0.15·feasibility
                              + 0.15·circularity + 0.10·speed + 0.05·confidence
        ▼
rank (tie-break: CO2 saving desc, intervention code asc)
        ▼
Module M: evidence → LLM narrative (validated) → template fallback
        ▼
RecommendationGenerationResult  (shape identical to the Phase 0 mock)
```

- CO2 saving is **resource-based** when emission factors are supplied (quantity saved ×
  versioned factor); otherwise it falls back to the intervention's reduction-range midpoint
  applied to the targeted hotspot. The basis is recorded in `impact.assumptions`.
- Financial estimates use the demo tariff fixture and process resource baselines with static
  prices; each resource line, tariff source, and conversion factor is written into
  `impact.assumptions` for auditability.
- LLM touchpoint is one injected callable (`LLMExplainer(explain_fn)`). Output must be
  JSON matching `{explanation, cited_intervention_codes}`, may only cite allowed codes,
  and its numbers are checked against stored evidence. On failure it retries, then falls
  back to the deterministic template. See tests `test_llm_explainer_cannot_change_numeric_ranking`,
  `test_unknown_intervention_citation_is_rejected`, `test_contradictory_numbers_are_rejected_and_regenerated`,
  `test_prompt_injection_in_untrusted_text_is_isolated_and_rejected`.

## Demo result (baseline 565,050 kgCO2e, Scope 1+2, data quality 78.4/100)

| # | final | CAPEX | saving/yr | payback | CO2e kg/yr | code |
|---|---|---|---|---|---|---|
| 1 | 77.26 | 500,000 | 244,800 | 2.04 | 32,000 | INT-SCRAP-004 |
| 2 | 76.91 | 140,000 | 192,000 | 0.73 | 25,600 | INT-WASTESEG-015 |
| 3 | 71.57 | 275,000 | 484,450 | 0.57 | 17,966 | INT-STEAMTRAP-006 |
| 4 | 69.84 | 200,000 | 285,600 | 0.70 | 22,152 | INT-CAIR-011 |
| 5 | 67.28 | 425,000 | 1,020,600 | 0.42 | 12,128 | INT-PKG-005 |
| … | | | | | | (18 ranked, 1 filtered, 6 deduped, 1 conflict pair marked) |

Full ranked list and explanations: `p4/demo/output/`.

## Edge cases tested (all PASS, 55/55)

Module J (security doc §21) — tests in `tests/test_edge_cases_j_k.py`, `test_recommendation_engine.py`:

| Edge case | Handling verified | Test |
|---|---|---|
| LLM suggests unknown intervention | rejected by code allow-list, fallback to template | `test_unknown_intervention_citation_is_rejected` |
| User budget = 0 | only zero-CAPEX actions survive | `test_j_budget_zero_prioritizes_no_capex_interventions` |
| No feasible intervention | empty result, honest diagnostic (no fabrication) | `test_j_no_feasible_intervention_returns_empty_without_fabrication` |
| Recommendation exceeds budget | filtered **before** ranking (`BUDGET_EXCEEDED`) | `test_j_budget_exceeded_is_filtered_before_ranking` |
| Very high saving but low feasibility | ranks lower than easy moderate saving | `test_high_saving_low_feasibility_ranks_lower` |
| Duplicate recommendations | one per intervention, best hotspot kept | `test_j_duplicate_recommendations_are_deduplicated` |
| Conflicting interventions | marked mutually exclusive in explanation/diagnostics | `test_j_conflicting_interventions_are_marked_mutually_exclusive` |
| Missing CAPEX | no fabricated payback / cost-per-tonne | `test_j_missing_capex_does_not_fabricate_payback_or_cost` |
| Missing CO2 estimate | stays qualitative, carbon score 0 | `test_j_missing_co2_estimate_stays_qualitative_and_scores_zero_carbon` |
| Constraint change after generation | re-run re-ranks/filters deterministically | `test_j_constraint_change_after_generation_reranks` |
| Technology unavailable regionally | feasibility reduced (not hidden) | `test_j_region_unavailability_lowers_feasibility_not_hides_it` |
| Local unavailability / user exclusion | hard filter with explicit reason | `test_j_locally_unavailable_and_user_exclusions_are_hard_filters` |
| Payback ceiling | filtered with `MAX_PAYBACK_EXCEEDED` | `test_j_max_payback_filter` |
| Prerequisite intervention | feasibility penalty by default, hard filter in strict mode | `test_j_prerequisites_penalize_or_hard_filter` |
| Currency mismatch | kept separate (never silently combined) | `test_j_currency_mismatch_kept_separate` |
| Prompt injection in uploaded notes | isolated as untrusted data, cannot alter ranking | `test_prompt_injection_in_untrusted_text_is_isolated_and_rejected`, `test_prompt_injection_cannot_change_the_deterministic_ranking` |
| Malformed LLM JSON | schema validation + retry + template fallback | `test_malformed_json_retries_then_falls_back_to_template` |

Module K (security doc §21) — `tests/test_edge_cases_j_k.py`:

| Edge case | Handling verified | Test |
|---|---|---|
| Annual saving = 0 | payback unavailable with reason | `test_k_annual_saving_zero_gives_no_payback` |
| Annual saving < 0 | reported as additional annual cost, no payback | `test_k_negative_saving_reports_additional_cost` |
| CAPEX = 0 | immediate payback when saving positive | `test_k_zero_capex_gives_immediate_payback` |
| Adoption = 0% | no change | `test_k_adoption_zero_means_no_change` |
| Adoption > 100% | rejected by contract constraint | `test_k_adoption_over_100_is_rejected_by_contract` |
| Negative projected emissions | floored at 0 | `test_k_projected_emissions_floored_at_zero_and_saving_capped` |
| Saving exceeds source emissions | capped + flagged | `test_k_projected_emissions_floored_at_zero_and_saving_capped` |
| Combined interventions double-count | sequential application on remaining baseline | `test_k_sequential_application_prevents_double_counting` |

Module M extra: `test_contradictory_numbers_are_rejected_and_regenerated`,
`test_low_confidence_claim_requires_explicit_uncertainty`,
`test_template_explanation_covers_evidence_and_passes_contradiction_check`.
Module Q: `tests/test_feedback.py` (history, structured rejection reason, self-reported
implementations, negative outcomes).
Module I: `tests/test_intervention_library.py` (15–20 entries, unique codes, loop coverage,
reference + technical requirements on every entry).

## Integration notes for the team

- **P1** consumes `p4/demo/output/demo_recommendation_output.json` (shape-frozen). Fields
  `intervention_code`, `intervention_title`, `explanation`, `impact` are response-only.
- **P2** wires `generate_recommendations(...)` / `generate_with_diagnostics(...)` into
  `POST /api/facilities/{id}/reporting-periods/{pid}/recommendations/generate` and the
  feedback store into `POST /api/recommendations/{id}/feedback`. Replace
  `p4/demo/demo_context.json` with real activity/tariff data when available.
- **P3** replaces the hotspot envelope / resource baselines; keep the shapes. When the real
  carbon engine is live, pass `emission_factors` from the versioned factor KB and the
  resource-based CO2 path activates automatically.
- **LLM key**: `LLMExplainer(explain_fn)` accepts any callable; no vendor SDK is imported in
  Phase 1, and the template fallback keeps the demo working offline.

## Phase 1 verification audit

- **Serializer defect found and fixed**: `model_dump(mode="json")` rendered `Decimal` as JSON
  strings (`"77.26"`), unlike the Phase 0 mock and FastAPI's `jsonable_encoder`. P4 now emits
  through `p4.serialization.to_api_dict` (Decimal → number, datetime → ISO string, UUID → str),
  and `test_serialized_numeric_types_match_phase0_mock` locks the types.
- **Dead code removed**: 7 unused imports (ruff `--select F401`) and two unused parameters in
  `p4/engine.py`; `python -m ruff check p4 tests --select F,E9` is clean.
- **LLM ranking test strengthened**: the fake LLM now echoes actual evidence values and the test
  asserts every validated narrative is used (`explanation_sources["llm"] == len(recommendations)`)
  while scores, ranks, and IDs stay identical to the template run.
- **Determinism**: two engine runs with a fixed clock produce identical results; IDs are UUID5,
  so `generated_at` is the only run-dependent field.
- **Boundaries re-verified**: `python validate_mocks.py` 9/9 (Phase 0 untouched) and
  `python -m p4.demo.run_demo` shape check PASS.

## Assumptions / limitations

- P4 metadata not present in the frozen DB schema (OPEX impact, water reduction, technical
  requirements, applicability, prerequisites/conflicts) lives in `InterventionEntry`
  (an additive P4-local extension), not in `contracts/schemas.py`. A contract sync is
  needed before P2 persists these columns.
- `impact.assumptions` is free-form JSONB, so the shape checker treats it as opaque.
- No wastewater emission factor exists in the Phase 0 factor mock, so wastewater savings
  contribute to financial value but not to resource-based CO2 until a factor is added.
- Full Module K scenario engine (intervention interaction modelling across a whole
  scenario) remains P3's; P4 implements the per-recommendation financial checks plus a
  sequential projection helper with tests.
