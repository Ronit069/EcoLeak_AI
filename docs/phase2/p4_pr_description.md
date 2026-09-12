# PR: P4 Phase 2 — recommendation engine stable on live P3 hotspot input

**Branch:** `Ronit` → `main`
**Role:** P4 (Modules I/J/M/Q)
**Phase 2 integration log:** `docs/phase2/p4_integration_log.md`
**Shape proof:** `docs/phase2/p4_shape_diff.md`

## Summary

- **Mock-to-real swap behind the shared flag.** `p4/data_source.py` resolves
  `USE_MOCK_DATA` (explicit arg → `USE_MOCK_DATA` → `ECOLEAK_USE_MOCK_DATA` →
  legacy DSN rule) and serves the P4 ranker either the frozen mock hotspot
  envelope or P3's live Engine G output. If the live path raises, it falls back
  to the mock with explicit provenance, so `main` stays demo-able mid-audit.
  Instant rollback: `USE_MOCK_DATA=true` (or unset the DSN).
- **Baseline regression reference.** Phase 1 J/M logic re-run against
  `mocks/mock_hotspot_output.json` and frozen output saved to
  `docs/phase2/p4_baseline_output.json`.
- **Live-data output + shape diff.** `tools/phase2_p4_shape_diff.py` runs the
  `USE_MOCK_DATA=false` path (P3 Engine G over P2 table names in the portable
  SQLite image with P2's real factor seed) and diffs `meta`,
  `J_recommendations`, and `diagnostics` key/type-for-type against the
  baseline: **3/3 sections identical**.
- **All Phase 1 guardrails re-verified on real data** (6/6 PASS): unknown
  intervention rejected, `budget=0` returns the no-CAPEX action instead of
  crashing, duplicates deduplicated, prompt injection ignored, contradictions
  rejected and regenerated for **18/18** recommendations, and LLM narratives
  never change the numeric ranking (same UUIDs/ranks/scores as the template run).
- **Two real issues found and fixed** (details in the log):
  1. P4's contract shim loaded a second copy of the schemas → `isinstance`
     across the P3→P4 boundary was `False`; now both import the same
     `contracts.schemas` module. No shape change.
  2. Estimator factor selection silently picked among ties (DEFRA diesel blend
     vs mineral); now an explicit region → year → version → code priority with
     ambiguous slots reported in the shape-diff artifact. Recommend P2 add a
     preferred-factor flag or an India diesel factor (logged, not blocking).
- **Module P stability confirmed.** `test_module_p_bridge_returns_live_recommendations`
  drives P2's `engine_bridge.real_recommendations` with the live engine and
  asserts a non-empty frozen J2 payload.

## Contract impact

**None.** `contracts/schemas.py`, `contracts/api_contract.md`, and
`mocks/mock_recommendation_output.json` are untouched; the recommendation
envelope P1 consumes is field-for-field identical. `docs/phase2/contract_changes.md`
carries an additive P4 status note only.

## Test plan

```text
python -m pytest tests -q                          # 160 passed (20 new)
python validate_mocks.py                           # 9/9 PASS
python validate_against_mock.py                    # ALL SHAPE CHECKS PASSED
python -m tools.phase2_p4_shape_diff               # 3/3 sections identical, 6/6 edge checks PASS
python -m p4.demo.run_demo                         # mock default, shape PASS
python -m p4.demo.run_demo --use-mock-data false   # live SQLite path, shape PASS
```

## Risk / rollback

- Values legitimately move on real data (factor set, data quality); the frozen
  mock remains the default and the baseline artifact documents the mock values.
- Known P2 actions (not blockers): seed Scope-3 factors, resolve the diesel
  factor ambiguity, optionally switch the Module P bridge to live-derived
  estimator factors. All are logged in `docs/phase2/p4_integration_log.md` §11.
