# EcoLeak AI — Phase 2 Technical Audit (Two-Pass)

**Audit date:** 2026-09-12
**Scope:** PASS A (process/plan conformance of all four Phase 2 workstreams) + PASS B (requirements-doc conformance of the fully-integrated real-data system)
**Method:** Every claim verified by execution where the environment allows: pytest suite (160 tests), per-role flag toggles, live HTTP probes against the merged API (single base URL), shape-diff tools re-run, Playwright live/fallback/forced-mock legs, code inspection with file:line evidence. PostgreSQL-gated P2 runtime tests cannot execute in this environment (no docker/psql/initdb) — explicitly noted per item; P2's test files and recorded outputs are listed as evidence-in-lieu.

---

# PASS A — PROCESS & PLAN CONFORMANCE

## A1. Git hygiene

| Item | Status | Evidence |
|---|---|---|
| P1 Phase 2 committed on branch + merged | ✅ | `6c4f46a` Merge branch `phase2-p1-integration`; tip `2e41dbe` |
| P4 Phase 2 committed on branch + merged | ✅ | `c0bcfbe` Merge branch `Ronit`; tip `6fc3114` |
| P2 Phase 2 committed on branch + merged | ❌ | `7f5ead4` sits on main's **first-parent line** (no merge record). `origin/phase2-p2` points at the same commit — branch created after the fact, work pushed direct to main |
| P3 Phase 2 committed on branch + merged | ❌ | `a0a6aa9` same pattern: direct-to-main, `origin/phase2-p3` points at it |
| Main stayed demo-able at intermediate commits | ✅ | Frontend untouched by P2/P3/P4 Phase-2 commits (file lists: backend/, engine/, p4/, docs/ only). Engine suite at `a0a6aa9` executed via worktree: **11/11 passed**. HEAD gates green (B5) |
| No cross-role production-code touches in Phase 2 | ✅ (note) | P1: frontend/ + docs + tests/e2e only. P2/P3/P4: own dirs. Shared **test** files were modified across roles (`tests/test_sql_source.py` by P3, `tests/helpers.py` by P4) — shared test scaffolding, not owned production code; flag for convention |
| `/docs/audit/` folder | ❌ | Does not exist — audit notes live at repo-root `PHASE1_AUDIT.md` / this file. Per audit instructions this absence is itself a finding (process drift, cosmetic) |

## A2. Mock-fallback flags (per role, toggled, not assumed)

| Role | Flag | Toggle executed | Fallback masks broken real path? |
|---|---|---|---|
| P2 | `Settings.use_mock_data` + `engine_dsn` (`backend/app/config.py:40-41`) | ✅ `USE_MOCK_DATA=true` → `MockDataSource`; `=false + ENGINE_DSN` → `SQLActivityDataSource` (executed via `engine_bridge.build_engine`) | ✅ No — Module P honours the flag (`reports.py:105`) |
| P3 | `ECOLEAK_USE_MOCK_DATA` resolver (`engine/data_source.py:173-209`) | ✅ `tests/test_data_source_flag.py` (passed in the 36-test batch) | ✅ explicit `USE_MOCK_DATA=false requires ECOLEAK_SQL_DSN` error path |
| P4 | `USE_MOCK_DATA`/`ECOLEAK_USE_MOCK_DATA` + `fallback_to_mock=True` (`p4/data_source.py`) | ✅ 20 tests incl. `test_no_flag_and_no_dsn_defaults_to_mock`, `test_flag_false_without_dsn_falls_back_to_mock`, explicit-beats-env | ✅ fallback carries explicit `mock_fallback` provenance + warnings |
| P1 | `VITE_USE_MOCK_DATA` (auto/mock/live) + localStorage override + 5 s timeout + per-group fallback | ✅ Live leg 7/7 · Fallback leg 7/7 · forced-mock 2/2 (Playwright) | ✅ **Banner renders with exact failed groups** ("live API unavailable for: processes, activities — fallen back to Phase 1 mocks"), Force-live/Force-mock/Auto buttons; fallback only on real failure/timeout (verified: with API up, banner lists only the genuinely-PG-bound groups) |

## A3. Integration logs — exist and accurate

| Log | Exists | Verified claims |
|---|---|---|
| `docs/phase2/p1_integration_log.md` | ✅ | Per-group swap table matches re-executed probes; issues 7.1–7.5 all reproduced (timeout, context-keys, HTML-200, boundary, O1–O7) |
| `docs/phase2/p2_integration_log.md` | ✅ | Statuses match code (STABLE rows audited in P2 routers; Module P flag-gated `reports.py`; `messy_ingestion_check` recorded output `stored_activity_rows=48 imported_audit_rows=48`). PG-bound tests NOT re-runnable here (env) — files present: `test_audit_trail.py`, `test_double_counting.py`, `test_ingestion_volume.py`, `test_module_p_real.py` |
| `docs/phase2/p3_integration_log.md` | ✅ | Baseline/real numbers match re-generated outputs; real-factor unresolved set (7, `EMISSION_FACTOR_NOT_FOUND`, MATERIAL/TRANSPORT/WASTE/WATER) reproduced by the shape-diff tool |
| `docs/phase2/p4_integration_log.md` | ✅ | 20 tests re-run: all pass, including LLM guardrail suite and Module P bridge (`test_module_p_bridge_returns_live_recommendations`, line 235) |
| Cross-log contradictions | ✅ none found | P2→P3/P4 dependencies (engine_bridge, Module P live-J) consistent with P3/P4 logs |

## A4. contract_changes.md — shared ground rules

| Check | Status | Evidence |
|---|---|---|
| Frozen schemas untouched | ✅ | `contracts/schemas.py` unchanged through Phase 2 (git: no diff); `validate_mocks.py` 9/9 |
| Every role's log section documents its changes | ✅ | P2/P3/P4/P1 sections present, all "NO frozen contract changes" + additive tables |
| **Undocumented shape deviations found** | ❌ | (1) N1 response carries additive `production_unit` — unknown to `contract_changes.md` until this audit (checked `grep production_unit docs/phase2/*` → absent); (2) K1 HTTP response is a wrapper `{scenario_id, assessment: ImpactAssessment, …}` vs contract `202 ImpactAssessment` — undocumented (originates `engine/api.py`, Phase 1; p3 log documents the ImpactAssessment *model* claim but not the HTTP envelope). **Both logged now** in the POST-AUDIT ADDENDUM; owners flagged: P3 (K1), P4/P1 (N1) |
| A logged-but-unhandled shape change breaks consumers? | ⚠️ | K1 wrapper: P1's `fetchSimulate` expected the flat contract shape → gauges would render undefined values had it not failed to 404 first; P1 now normalizes both shapes (`normalizeSimulate`, `frontend/src/lib/api.ts`). Other consumers of K1: none |

## A5. Sequencing conformance

| Role | Required order | Finding |
|---|---|---|
| P2 (Module P LAST) | Module P real integration in single commit `7f5ead4`, which lands on main **before** P3's real-factor commit `a0a6aa9` | ⚠️ Functional coupling avoided (bridge is flag-selected and reads engine per-request), so no breakage — but the literal "F/J stable before P" timeline is not provable from history; P2 log states the dependency handling |
| P3 (baseline before swap + diff) | `p3_baseline_output.json` + `p3_real_data_output.json` + `p3_shape_diff.md` + swap all in **one commit** `a0a6aa9` | ⚠️ Order not independently provable from git; tool re-run regenerates both files and passes; log documents sequence |
| P4 (baseline before swap + diff) | Same single-commit pattern `6fc3114` | ⚠️ same note; `tools/phase2_p4_shape_diff.py` re-run PASS ("identical shapes", LLM narrative does not change ranking) |
| P1 (one endpoint group at a time) | Swap implemented in one commit `2e41dbe` with per-group verification documented | ⚠️ Commit granularity is single-shot; per-group testing WAS executed group-by-group (log §5 rows each with live/fallback evidence) — evidence-level conformance, commit-level partial |

## A6. Role-specific scope items

| Role | Item | Status | Evidence |
|---|---|---|---|
| P1 | Real-data render of leak map / KPIs / sliders | ✅ | Live leg 7/7 + all 5 pages error-free at real volume (18 recs, 18 sliders, K1 notice, Boiler, N1 badge) |
| P1 | A11y + empty states at real data volume | ⚠️ PARTIAL | Severity icon+word verified on live output; null guards verified (no NaN/blank); **100+ processes not exercised with a >100 dataset** — filter logic unchanged, no virtualization (logged Phase-3 candidate) |
| P2 | Messier/larger ingestion + severities at volume + audit entries + double-count on real data | ⚠️ ENV-GATED | Files + recorded outputs in log (`messy_ingestion_check.py`, 108-row CSV, 48 accepted/48 audited; four severities at volume); `test_double_counting.py` (purchased grid → Scope 2 only); require PG — not executable in audit env |
| P3 | F/G/K/L real-data re-run + shape diff + unresolved re-test | ✅ | `tests/test_phase2_real_source.py` + `test_sql_source.py` executed (in 36-pass batch); shape-diff tool executed; real-table missing-factor → explicit unresolved (7 rows, no fabrication) |
| P4 | LLM guardrails (a) outside-library reject, (b) budget=0, (c) duplicates, (d) injection + regenerate | ✅ | 20/20 passed: `test_real_llm_unknown_intervention_rejected_and_ranking_unchanged`, `test_real_budget_zero_returns_action_not_empty_crash`, `test_real_duplicate_recommendations_deduplicated`, `test_real_prompt_injection_in_untrusted_text_ignored`, `test_real_contradiction_rejected_and_regenerated_for_every_item` |
| P4 | **LLM never touches numeric ranking — hard rule** | ✅ | Code: `p4/engine.py:259` `final_score = weighted_final_score(candidate.scores)`; scores built exclusively by rubric functions (`p4/scoring.py`); `explainer.explain(evidence)` output lands only in `outcome.text` → `explanation` (engine.py:443/467). No openai/anthropic import anywhere in `p4/`; `LLMExplainer` is injection-only (tests), default is `TemplateExplainer` (engine.py:165). Executed: ranking unchanged under LLM narratives/contradictions |

## A7. Phase 1 blockers — actually closed?

| Phase 1 gate | Status | Evidence |
|---|---|---|
| 1. Merged FastAPI surface serving G2/J2/N1/N2 on one base URL/port | ✅ | Single `uvicorn app.main:app` on `:8000`; executed HTTP probes: G2 (exact envelope, 5 hotspots), J2 (18 recs, exact envelope), N1 (9 contract keys + additive `production_unit`), N2 (`{nodes:5, links:[]}`), M1 (6 contract keys), K1 (200) |
| 2. P2-DB-backed ActivityDataSource for P3 | ✅ | `engine/sql_source.py` active when `ECOLEAK_SQL_DSN`/`ENGINE_DSN` set (`default_data_source`, verified toggle → `SQLActivityDataSource`); P2's `engine_bridge` mirrors; mock remains default-safe |
| 3. Severity recalibration decision documented + live output matches | ✅ | CONTRACTS_README item 6: decision (b) — mock = "ILLUSTRATIVE references"; live output Boiler HIGH 76.41 matches recorded expectation; no silent threshold change |

---

# PASS B — REQUIREMENTS DOC CONFORMANCE

## B1. Module coverage matrix (A–Q)

| Module | Implemented? | Real-data verified? | Owner | Evidence |
|---|---|---|---|---|
| A SME Profiling | ✅ | ✅ | P2/P1 | A1–A9 routers; P1 profiling live via context+A reads (page probe OK) |
| B Process Mapper | ✅ | ✅ (fallback in env) | P2/P1 | B1–B5 routers; P1 mapper renders (fallback-list note: B2 needs PG) |
| C Data Input & Ingestion | ✅ | ⚠️ env-gated (P2) / ✅ P1 | P2/P1 | C1–C4 + Pandera+Pydantic+Pint; volume tests present |
| D Unit Normalization & DQ | ✅ | ✅ | P2 | `units/normalize` (Pint, families, ambiguity → CONFIRMATION_REQUIRED), D2 quality endpoint; P1 form |
| E Emission Factor KB | ✅ | ✅ | P2 | 10 real seeded factors (CEA/DEFRA/IPCC), E1–E4 + lookup; real-factor run executed |
| F Carbon Accounting | ✅ | ✅ | P3 | `engine/carbon.py`, Decimal, ledgers; pytest + fixture reproduction |
| G Hotspot Detector | ✅ | ✅ | P3 | `engine/hotspots.py`, G1/G2; live probe exact envelope |
| H Anomaly & Inefficiency | ⚠️ | ❌ | P3 | Code + endpoint + tests exist (Phase 1, `engine/anomaly.py`, `test_anomaly.py`) — **no Phase 2 prompt mentions H** → plan gap (no Phase-2 real-data re-verification) |
| I Circular KB | ✅ | ✅ | P4/P2 | 19-entry library (JSON) + P2 `circular_interventions` table |
| J Recommendation Engine | ✅ | ✅ | P4 | J1/J2 live (18 recs), exact formula weights, budget/hard filters |
| K Cost & CO₂ Simulator | ✅ | ⚠️ shape | P3/P1 | K1 live 200; **HTTP wrapper vs contract ImpactAssessment** (A4); P1 sliders + fallback math |
| L Circularity Score | ✅ | ✅ | P3 | L1 endpoint; `is_internal_metric` labelling (p3 log) |
| M Explainability | ✅ | ✅ | P4 | M1 live, 6 contract keys, template/LLM-injected explanation, evidence-bound |
| N Dashboard & Visualization | ✅ | ✅ | P1/P4 | N1/N2 live + P1 KPIs/leak-map/Pareto |
| O What-If / Digital Twin | ⚠️ | ⚠️ | P1/P3 | **K1 only**; O1–O7 CRUD not served by merged surface → plan gap (documented by P1); P1 scenario UI live+fallback |
| P Compliance & Sustainability Report | ✅ | ⚠️ env-gated | P2 | Router + service; real F/G/J/L via `engine_bridge` when `USE_MOCK_DATA=false`; provenance includes factor `source_name/source_year/version` (`reports.py:78-79`), `data_is_stub` flag, reporting boundary + DQ score |
| Q User Feedback | ⚠️ | ⚠️ | P4 | `p4/feedback.py` + tests exist (Phase 1) — **no router on the merged surface, no Phase 2 prompt item** → plan gap |

**Plan-gap callout (finding on the plan itself):** Modules **H** and **Q** have no Phase-2 prompt item and no live API surface (H has an endpoint; Q has none). Both were built in Phase 1; Phase 2 simply omitted them.

## B2. End-to-end real-data trace (executed, with output)

Environment: SQLite image of P2 tables (real seeded schema names) + merged API at `http://localhost:8000` (`USE_MOCK_DATA=false ENGINE_DSN=...`), P1 frontend built `VITE_USE_MOCK_DATA=auto VITE_API_URL=http://localhost:8000`.

```
$ curl :8000/api/facilities/{f}/reporting-periods/{p}/hotspots
  -> 200, keys=[data_quality_score, facility_id, generated_at, hotspots,
       reporting_period_id, scope_boundary, total_emissions_kgco2e]
  -> hotspots: 5, Boiler HIGH

$ curl :8000/.../recommendations
  -> 200, keys=[budget_limit, facility_id, generated_at, recommendations, reporting_period_id]
  -> recs: 18, top INT-SCRAP-004 final 77.37, explanation 879 chars (M output embedded)

$ curl :8000/.../dashboard
  -> 200, keys=[carbon_intensity, circularity_score, empty_state, largest_hotspot,
       last_calculated_at, potential_annual_saving, potential_reduction_kgco2e,
       production_unit, scope_breakdown, total_kgco2e]   # production_unit = additive (A4)

$ curl :8000/.../leak-map  -> 200 {nodes: 5, links: []}
$ curl :8000/api/recommendations/{id}/explanation -> 200, 6 contract keys

$ curl -X POST :8000/api/scenarios/{id}/simulate {interventions:[INT-WHR 80%]}
  -> 200 {scenario_id, assessment{ImpactAssessment keys}, over_budget, payback_status, ...}

Playwright (P1 @ :5174, live): 7/7 PASS — N1 badge, all-scope total 72,02,350 kgCO₂e,
Boiler rail, live J2 cards, scope label, banner limited to PG-bound groups.
Playwright fallback (API down): 7/7 PASS — banner + frozen mocks, no blank screen.
```

Hops: **ingestion (P2) → normalization → F → G → J → M → N → P1 render** verified live except the P2 PG-bound ingestion hop, which is covered by P2's recorded volume/audit runs (log §2.2, outputs `stored_activity_rows=48 imported_audit_rows=48`) and service code; not executable in this env (no PostgreSQL). Module P hops F/G/J/L verified at code level (`engine_bridge` + `reports.py`); runtime PG-gated.

## B3. Module P specifics

| Check | Status | Evidence |
|---|---|---|
| Factor provenance traces to real seeded factors (source, year, version) | ✅ | `reports.py:48-79` `_factor_provenance` emits `source_name/source_year/version` per factor; real path uses `engine_bridge.real_inventory().factor_provenance` incl. UNRESOLVED entries |
| Data-quality score + reporting boundary present | ✅ | real path: `hotspots_real.data_quality_score` + `scope_summary` (+on-site/export ledgers, p2 log) |
| Pulls REAL F/G/J outputs, not leftover mocks | ✅ | `reports.py:105-176`: `USE_MOCK_DATA=false` → `engine_bridge.build_engine()` (SQL source) + real hotspots/circularity/recommendations; stub path explicit with `data_is_stub: true` |

## B4. Security & edge-case checklist at Phase-2 scale

| Item | Status | Evidence |
|---|---|---|
| Negative/zero/null handling | ✅ | Engine property tests (5 Hypothesis cases) + DB CHECKs + real-factor run (nulls → explicit unresolved) |
| Enum validation | ✅ | Pydantic enums + DB CHECKs unchanged (contract enums) |
| Duplicate detection | ✅ | in-file + DB + file-hash (P2 ingestion), re-verified code; real-data J2 dedup test passes |
| Reproducibility via stored factor version | ✅ | every calc `assumptions` retains factor_code/version/source/year (real run shows provenance); E4 versioning |
| **Custom exception consistency on merged surface** | ✅ | Executed: K1 unknown intervention → 404 `{"error_code":"NOT_FOUND","message":...,"severity":"ERROR","details":{...}}` — same frozen shape as P2's `PlatformError` payloads (errors.py registered handlers), single handler set on the merged app |
| No hardcoded secrets | ✅ (note) | `jwt_secret` default removed (Phase 1 D2; config raises in jwt mode without env); `.env.example` uses `CHANGE_ME` placeholders only. Note: example value `change-me-in-production` passes the jwt validator guard (only `dev-only*` prefix is rejected) — cosmetic hardening item |
| CORS baseline | ✅ (note) | defaults `:5173,:3000`; `:5174` needs env override (used during verification) |

## B5. Regressions vs PHASE1_AUDIT.md

| Phase 1 pass | Phase 2 re-check | Result |
|---|---|---|
| `validate_mocks.py` 9/9 | re-run | ✅ 9/9 |
| `validate_against_mock.py` shape gate | re-run | ✅ ALL SHAPE CHECKS PASSED |
| pytest suite 127 (Phase-1 tip) | HEAD | ✅ **160 passed** (+33 Phase-2 tests, none removed) |
| Unit dims / recycling / property / sql-source / real-factor tests | re-run | ✅ 36/36 (batch) |
| Severity decision documented | re-check | ✅ CONTRACTS_README item 6 intact |
| Frontend tsc + build | re-run | ✅ clean |
| Phase-1 audit "all-scope 7,202,350 vs operational 565,050" boundary | re-check | ✅ still surfaced honestly (N1 live vs N1 derived badges) |
| **Removed during integration:** none | ✅ | No Phase-1 feature/file removed; the only Phase-2-era behavioral change is P4's `p4/contracts.py` imports (documented in contract_changes) |

---

# BLOCKING RISK REPORT

**Three tiers, priority order:**

### Phase-3 / production blockers
1. **K1 response shape deviates from the frozen contract** (`assessment` wrapper vs `ImpactAssessment`, 200 vs 202). P1 normalizes defensively, but every other future consumer and the audit record need P3 to either align `engine/api.py` to the contract or formally re-document the wrapper → opened in the POST-AUDIT ADDENDUM; **owner P3**.
2. **Scenario slider integration is not actually live-tested end-to-end**: P1's K1 call 404s silently on full-library selections (live J2 emits 18 recommendations whose `intervention_id`s mostly do not exist in the engine's data source — only the 5 seed interventions are present). The UI silently falls back to local math. **Fix path (cross-team):** seed the P4 library (19 entries) into P2's DB/seed, or have the merged simulate resolve library ids via the P4 library when the engine source lacks them. **Owners P2/P3/P4** — currently only mitigated by fallback.
3. **P2/PG-only runtime paths (Module P, ingestion volume, audit-at-volume) have never executed in a shared environment.** Their committed tests + recorded outputs exist, but nothing on main can run them without PostgreSQL; Phase-3 CI with a `postgres` service is required before the report pipeline is relied upon.

### Silent-correctness risks
4. **N1 `production_unit` additive key** was undocumented until this audit (now logged); ignore-safe for P1 but violates the additive-change notification rule retroactively.
5. **K1 live-path masking**: because the 404 → local-math fallback is silent *within* the scenario page (no banner entry), a demo could show "K1 live simulation"-adjacent numbers that are actually local math. The banner groups list does include `scenario-simulate` (observed), but the page's own notice is the only indicator — acceptable, must be documented for demo stewards.
6. **`change-me-in-production` jwt placeholder** passes the config guard (only `dev-only*` is rejected) — cosmetic-now, must be tightened before any prod deploy.

### Cosmetic / deferrable
7. `/docs/audit/` folder absent; audit artifacts at repo root (naming drift).
8. Direct-to-main pushes for P2/P3 Phase 2 (recorded for process hygiene; no functional damage).
9. Shared `tests/` files modified cross-role (test scaffolding only).
10. H and Q have no Phase-2 plan item (H: endpoint exists; Q: no router) — real-data re-verification backlog for Phase 3.

---

# FINAL VERDICT

**Conditional GO.**

Phase 2's real integration works where it claims to: the merged single-surface API serves G2/J2/N1/N2/M1/K1 on one base URL with the frozen error shape; the `USE_MOCK_DATA` gate is genuinely togglable in all four roles without masking (P1's banner proves per-group provenance); baseline-vs-real shape diffs were executed and pass; P4's "LLM never touches numbers" hard rule holds by code inspection **and** execution (ranking unchanged under LLM narratives and contradictions, injection ignored, contradicting numbers rejected and regenerated); P3's real-table unresolved behavior is honest; Module P carries real factor provenance; and no Phase-1 regression was found (160 tests, all gates green, all 3 Phase-1 blockers closed).

What must close before Phase 2 is called 100%: **(1)** the K1 shape deviation — P3 aligns to the contract or the wrapper is formally re-documented; **(2)** the scenario-slider live path — seed P4's library into the engine/P2 data source so a real K1 call succeeds from the UI (currently only falls back); **(3)** a PostgreSQL CI service so P2's PG-gated proofs (Module P runtime, ingestion volume/audit) execute in a shared environment. Everything else is logged process debt (direct-push hygiene, single-commit baselines, H/Q plan gaps, N1 additive key) with owners named above.