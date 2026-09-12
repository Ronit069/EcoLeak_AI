# P4 — Phase 2 Integration Log

**Role:** P4 (AI Recommendation & Explainability — Modules I/J/M/Q)
**Branch:** `Ronit` (Phase 2 work), base `a0a6aa9` (`main`, Phase 1 + P2/P3 Phase 2)
**Audience:** P1, P2, P3, and the Phase 1 auditor
**Status legend:** **STABLE** · **FLAG-GATED** · **DEVIATION** · **FIXED**

Read before coding (done): `contracts/schemas.py`, `contracts/api_contract.md`,
`PHASE1_AUDIT.md` (no `/docs/audit/` folder exists),
`docs/phase2/p2_integration_log.md`, `docs/phase2/p3_integration_log.md`,
`docs/phase2/contract_changes.md`.

---

## 1. What Phase 2 changed (P4)

| # | Deliverable | Status | Where |
|---|---|---|---|
| 1 | Phase 1 mock baseline re-run as regression reference | ✅ | `docs/phase2/p4_baseline_output.json` |
| 2 | Hotspot input swapped to P3 live output behind `USE_MOCK_DATA` | ✅ FLAG-GATED | `p4/data_source.py`, `p4/demo/run_demo.py`, `p4/api.py` (merged API already live) |
| 3 | Real-data run + key/type shape diff vs baseline | ✅ | `tools/phase2_p4_shape_diff.py`, `docs/phase2/p4_real_data_output.json`, `docs/phase2/p4_shape_diff.md` |
| 4 | Phase 1 J/M edge cases re-run on real data | ✅ | `tests/test_p4_phase2_integration.py` (20 tests) |
| 5 | Module P (P2 report) live-J stability confirmed | ✅ | `test_module_p_bridge_returns_live_recommendations`, §7 |
| 6 | Estimator factor selection made explicit (not arbitrary) | ✅ FIXED | `p4/data_source.py::factor_selection_notes`, §6 |

**No frozen contract change.** `contracts/schemas.py` and `contracts/api_contract.md`
were not touched. Recommendation JSON shape is field-for-field identical (see §4).

---

## 2. The config flag (`USE_MOCK_DATA`)

`p4.data_source.resolve_use_mock_data` mirrors P3's engine resolver and P2's
`Settings.use_mock_data` so all three components agree:

| Priority | Setting | Result |
|---|---|---|
| 1 | explicit `use_mock_data=` argument | wins over everything |
| 2 | `USE_MOCK_DATA` env (P2 pydantic-settings name) | `true` → mock, `false` → live |
| 3 | `ECOLEAK_USE_MOCK_DATA` env (P3 engine name) | same mapping |
| 4 | unset | legacy: `ECOLEAK_SQL_DSN`/`ENGINE_DSN` present → live, else **mock** (safe default) |

Every endpoint and runner goes through `p4.data_source.load_hotspots(...)`, which
also offers `fallback_to_mock=True`: if the live path raises (no DSN, DB down,
engine error) the frozen mock envelope is returned with explicit `mock_fallback`
provenance plus a warning, so `main` stays demo-able mid-audit.

**Instant rollback:** `USE_MOCK_DATA=true` (or unset the DSN) restores Phase 1's
known-good behavior with no code change.

---

## 3. How "real data" is exercised here

Same approach as P3 (P2's runtime contract is the DB, not an HTTP hop): the
runner seeds a portable SQLite image of P2's table names
(`tests/test_sql_source.py::_seed`) with P2's **real** seed factors
(`backend/app/seed/real_factors.json`) and runs the live P3 Engine G through
`SQLActivityDataSource`. P4 then consumes exactly what `USE_MOCK_DATA=false`
serves in production:

```
P2 tables (SQLite image / PostgreSQL)
      → P3 Engine G  → HotspotDetectionResult (live)
      → P4 Module J  → RecommendationGenerationResult (frozen shape)
      → P4 Module M  → explanation (template or validated LLM)
```

Live demo smoke (proves the runner path, not just tests):

```powershell
python -c "…seed var/p4_live.sqlite3 with real factors…"
$env:ECOLEAK_SQL_DSN="sqlite+pysqlite:///var/p4_live.sqlite3"
python -m p4.demo.run_demo --use-mock-data false
# Hotspot source: live · Baseline: 566,361 kgCO2e · Shape check vs mock: PASS
```

---

## 4. Baseline vs real — results (values differ, shape does not)

Artifacts: `docs/phase2/p4_baseline_output.json` (mock hotspots + mock factors),
`docs/phase2/p4_real_data_output.json` (live hotspots + real factors). Fixed
`generated_at`, so both are reproducible. Sections diffed: `meta`,
`J_recommendations`, `diagnostics` → **all IDENTICAL** (keys + scalar types).

### Inputs

| Input | Mock baseline | Real (live P3 + real factors) |
|---|---|---|
| Hotspot envelope | `mocks/mock_hotspot_output.json` | P3 Engine G over P2 SQL tables |
| Operational emissions | 565,050 kgCO2e | 566,360.8 kgCO2e |
| Data-quality score | 78.4 | 89.33 |
| Severity by process | Boiler CRITICAL · Dyeing HIGH · Drying HIGH · Finishing MODERATE · Packaging LOW | Boiler HIGH · Dyeing MODERATE · Drying LOW · Finishing LOW · Packaging LOW |
| Estimator factor slots | 6 (electricity, gas, diesel, water, waste, packaging) | 3 (electricity 0.71, natural gas 2.0384, diesel 2.5121) |

### Ranking movement (values change; shape does not)

| Intervention | Mock rank (score) | Real rank (score) |
|---|---|---|
| INT-SCRAP-004 | 1 (77.26) | 10 (60.78) |
| INT-WASTESEG-015 | 2 (76.91) | 6 (63.07) |
| INT-STEAMTRAP-006 | 3 (71.57) | 1 (71.86) |
| INT-CAIR-011 | 4 (69.84) | 2 (70.17) |
| INT-PKG-005 | 5 (67.28) | 9 (60.84) |
| INT-NOCAPEX-019 | 6 (67.12) | 3 (67.44) |
| INT-WHR-001 | 7 (65.69) | 4 (65.98) |
| INT-FILM-017 | 8 (65.64) | 8 (61.02) |
| INT-CONDENSATE-009 | 9 (62.87) | 5 (63.17) |
| INT-SOLAR-002 | 10 (61.68) | 7 (62.01) |

Move explained by the factor gap, not by a bug: P2's real seed has no
water/waste/material/recycling factors, so 6 of 18 recommendations fall back to
the hotspot-share CO2 basis (recorded per recommendation in
`impact.assumptions.co2_saving_basis`), while the other 12 stay resource-based.
Waste-loop recs (scrap, segregation, packaging) lose relative carbon score until
P2 seeds Scope-3 factors. Severity label changes (Boiler HIGH vs CRITICAL) do
not affect P4 scoring — severity is explanation-only.

---

## 5. Edge cases re-verified against real data

All six Phase 1 guardrails were re-run on the live envelope; results are also
asserted in `tests/test_p4_phase2_integration.py` and printed by
`python -m tools.phase2_p4_shape_diff`.

| Edge case | Expected | Observed on real data |
|---|---|---|
| LLM suggests an intervention outside Module I | rejected, template fallback, ranking untouched | ✅ 18/18 `template_fallback`, unknown code absent, ids/ranks/scores identical |
| budget = 0 | no-CAPEX action, never an empty crash | ✅ 1 recommendation (`INT-NOCAPEX-019`), `estimated_capex == 0` |
| Duplicate recommendations | deduplicated, one per intervention | ✅ 18 unique codes; 6 multi-hotspot interventions collapsed |
| Prompt injection in uploaded notes | ignored, not executed | ✅ hostile `hotspot.explanation` isolated in `untrusted_data`; injected `INT-HACK` rejected, ranking identical |
| LLM contradicts a calculated value | reject → regenerate → never emit | ✅ **18/18** first attempts rejected as numeric contradictions, 18/18 regenerated, all final narratives from the LLM, ranking identical |
| LLM must not touch the numeric ranking | only `explanation` text changes | ✅ validated-LLM run vs template run: same UUIDs, ranks, scores |

---

## 6. LLM guardrail findings and fixes

### FIXED — dual module identity (`schemas` vs `contracts.schemas`)
Phase 2 tests caught that P4's shim loaded a **second copy** of the contract
models: `isinstance(engine_hotspots, p4.contracts.HotspotDetectionResult)` was
`False` even though the data was identical. Any future `isinstance`/type-tagged
validation across the P3→P4 boundary would have failed silently. Fixed in
`p4/contracts.py`: it now imports `contracts.schemas` (same module object as
engine/backend). No field or shape change; `test_live_hotspot_source_returns_frozen_contract_envelope`
now locks the shared identity.

### FIXED — arbitrary estimator-factor tie-break
`ResourceEmissionFactors` derivation used to pick the alphabetically first
candidate, silently choosing DEFRA *diesel average biofuel blend* (2.5121) over
*100% mineral diesel* (2.6594). Now an explicit, documented priority applies
(region match → source_year → version → factor_code asc) and ambiguous slots are
reported by `factor_selection_notes()` in `docs/phase2/p4_shape_diff.md`.

Residual (logged, not silent): both DEFRA diesel factors tie on all four
priorities; the deterministic tie-break selects the blend, while P3's
activity-text matching selects mineral for the boiler diesel activity. Impact is
a ~5.5% delta on diesel fuel savings only. **Recommended P2 action:** mark a
preferred factor in the KB (`supplier_specific`/preferred flag) or seed an India
diesel factor; P4 needs no shape change.

### Not a failure — honest fallback on missing Scope-3 factors
Real seed has no water/waste/material factors. P4 never fabricates: the affected
savings use the hotspot-share basis and say so in each assessment's
`assumptions`. Waste-loop recommendations rank lower until P2 seeds those
factors. **Recommended P2 action**, not a P4 blocker.

### Confirmed behavior — strictness is intentional
Numbers copied from the untrusted hotspot narrative that are not in stored
evidence are rejected as contradictions (conservative by design). The
deterministic `TemplateExplainer` remains the default and always succeeds.

---

## 7. Module P (P2 compliance report) — confirmed stable

P2's `backend/app/services/engine_bridge.py::real_recommendations` already calls
the P4 ranker with live P3 hotspots and degrades to `UNAVAILABLE` on error.
Phase 2 evidence: `test_module_p_bridge_returns_live_recommendations` calls the
bridge with the live engine and asserts a non-empty frozen J2 payload (no
`__unavailable__`). No shape coordination was needed; P2's log asked P4 to
"confirm J stability", which this test does.

One P2-owned improvement is recommended (no shape change): the bridge currently
derives `ResourceEmissionFactors` from the mock dataset even in real mode.
Switching to
`p4.data_source.resource_factors_from_factors(engine.data_source.get_emission_factors(), region_country=facility.country)`
would align the estimator with the live factor KB. P4 will not edit P2-owned
code without a request.

---

## 8. Contract changes

**None.** `contracts/schemas.py` field names, enum values, endpoint paths and
`mocks/mock_recommendation_output.json` are untouched. The P4 section was
appended to `docs/phase2/contract_changes.md` as an additive status note.

---

## 9. How to run / rollback

```powershell
# Phase 1 mock behavior (default; no DB needed)
python -m pytest tests -q
python -m p4.demo.run_demo

# Full Phase 2 proof: baseline + live-hotspot run + shape diff + edge checks
python -m tools.phase2_p4_shape_diff

# Live demo against P2 tables (PostgreSQL)
$env:USE_MOCK_DATA="false"; $env:ECOLEAK_SQL_DSN="postgresql+psycopg://user:pass@host/ecoleak"
python -m p4.demo.run_demo --use-mock-data false

# Rollback: unset the DSN or set USE_MOCK_DATA=true
```

---

## 10. Verification evidence

| Command | Result |
|---|---|
| `python -m pytest tests -q` | **160 passed** (140 pre-existing + 20 new P4 Phase 2) |
| `python validate_mocks.py` | 9/9 PASS |
| `python validate_against_mock.py` | ALL SHAPE CHECKS PASSED |
| `python -m tools.phase2_p4_shape_diff` | 3/3 sections identical; 6/6 real-data edge checks PASS |
| `python -m p4.demo.run_demo` (mock) | shape PASS; ranking values unchanged vs committed Phase 1 artifact |
| `python -m p4.demo.run_demo --use-mock-data false` (SQLite + real factors) | shape PASS; live source, 566,361 kgCO2e baseline |

---

## 11. Known divergences / risks (values, not shape)

1. **Scope-3 factor gap** — P2's real seed resolves no water/waste/material
   factors; 6/18 estimator bases fall back to hotspot share. Honest and recorded;
   P2 action to seed factors.
2. **Diesel factor ambiguity** — blend vs mineral tie; P3 and P4 each pick one.
   Logged; P2 action to mark preference.
3. **Rank order changes on real data** — expected (factors + data quality), and
   the reason `p4_baseline_output.json` exists as a regression reference for
   values, while `p4_shape_diff.md` locks the shape.
4. **P1 severity badges** — live severities differ from the frozen mock
   (pre-existing Phase 1 B3 decision); P4 explanations carry the live severity,
   scoring does not use it.
5. **Module P bridge factor source** — still mock-derived (P2-owned); see §7.
