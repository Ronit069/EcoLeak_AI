# Phase 2 — Contract Changes (P2)

**Status: NO frozen contract changes.**

P2 Phase 2 did **not** modify `contracts/schemas.py` or the request/response shapes
in `contracts/api_contract.md`. Field names, enum values, endpoint paths and the
error shape are unchanged, so P1 (dashboard/Zod), P3 (engine input) and P4
(recommendation input) require no changes to consume P2.

Evidence: `backend/tests/test_contract_parity.py` asserts every serializer emits
exactly the field set of the corresponding frozen model, and the full backend
suite (54 tests) passes against the merged main.

`validate_mocks.py` still passes 9/9.

---

## Additive-only changes (no existing shape altered)

These additions do not remove or rename anything; consumers that ignore unknown
keys are unaffected.

| Area | Change | Old shape | New shape | Reason |
|---|---|---|---|---|
| Config | `Settings.use_mock_data`, `Settings.engine_dsn` | absent | optional booleans/strings | shared Phase 2 `USE_MOCK_DATA` mock-to-real gate |
| Platform health | new `GET /api/health` | — | `{status, app, environment, use_mock_data}` | `/health` is owned by the P3 engine router after the merge; add platform health on a non-colliding path |
| Emission factors | new `GET /api/emission-factors/lookup` | — | `EmissionFactor` or 422 `EMISSION_FACTOR_NOT_FOUND` | prioritized lookup helper; not in api_contract.md |
| Ingestion | new `GET /api/ingestion/batches/{import_id}` | — | `ImportJob` | fetch import report; not in api_contract.md |
| Reports | new `GET /api/reports` | — | `Report[]` receipts | list generated reports; not in api_contract.md |
| Report payload (P2-owned) | `report_meta` gains `use_mock_data`, `data_is_stub`, `stub_sources`; `scope_summary` gains real Scope 1/2/3, intensity, on-site/export ledgers | mock-only keys | additive keys | surface real F/G/J/L provenance; report payload is not a frozen contract model |
| Validation | new INFO issue code `UNIT_CONVERTED` | — | `ValidationIssue{severity: INFO, code: UNIT_CONVERTED}` | DB doc §23 INFO example ("converted MWh to kWh"); shape unchanged |
| Audit | new event `ACTIVITY_IMPORTED` per accepted imported activity | import wrote one `FILE_IMPORT` row | one `FILE_IMPORT` + one `ACTIVITY_IMPORTED` per row | Phase 1 constraint "every write to activity_data creates an AuditLog entry" |

## Notifications (dependency root)

Because nothing frozen changed, no blocking notification is required. Still, the
following consumers should be aware of additive items:

- **P1:** `/health` is now the engine's; use `/api/health` for platform status.
  Report payload has extra `report_meta` keys — ignore-safe.
- **P3:** no table/column changes in P2. The engine's `SQLActivityDataSource`
  still reads the same columns.
- **P4:** no change to J1/J2 input. Module P consumes the ranker output only when
  `USE_MOCK_DATA=false` and degrades to `UNAVAILABLE` on error.

---

# P3 — Phase 2 (branch `phase2-p3`)

**Status: NO frozen contract changes.**

P3 Phase 2 swapped the engine's data source to P2's real runtime tables behind the
`USE_MOCK_DATA` gate. `contracts/schemas.py` field names and the
`api_contract.md` F/G/K/L/H response shapes are unchanged. `HotspotDetectionResult`
from the real-data run is field-for-field identical to the mock baseline
(`docs/phase2/p3_shape_diff.md`), so P1 and P4 need no changes.

## Additive-only changes (no existing shape altered)

| Area | Change | Old shape | New shape | Reason |
|---|---|---|---|---|
| Config | `ECOLEAK_USE_MOCK_DATA` env flag + `default_data_source(use_mock_data)` | DSN-presence only | explicit boolean gate, default stays mock | shared Phase 2 mock-to-real rule |
| Bootstrap | `engine.service.build_engine(use_mock_data, dsn, config)` | `EcoLeakEngine(data_source=...)` only | optional factory (constructor unchanged) | one place to select mock vs real |
| Artifacts | `docs/phase2/p3_baseline_output.json`, `p3_real_data_output.json`, `p3_shape_diff.md`; `tools/phase2_p3_shape_diff.py` | — | new files | baseline regression + shape proof |
| Tests | `tests/test_data_source_flag.py`, `tests/test_phase2_real_source.py` | — | new tests | pin flag behavior + real-factor gaps |

No response envelope, field name, enum value, or endpoint path changed. No
dependency or consumer of P3's JSON output is affected.

---

# P4 — Phase 2 (branch `Ronit`)

**Status: NO frozen contract changes.**

P4 swapped the recommendation engine's hotspot input to P3's live Engine G
output behind the shared `USE_MOCK_DATA` gate (mock remains the default). The
J2/M1 response envelope is field-for-field identical to the mock baseline
(`docs/phase2/p4_shape_diff.md`), so P1 and P2 need no changes.

## Additive-only changes (no existing shape altered)

| Area | Change | Old shape | New shape | Reason |
|---|---|---|---|---|
| Config | `USE_MOCK_DATA` / `ECOLEAK_USE_MOCK_DATA` resolution in `p4.data_source` | mock-only hotspot loader | explicit flag + mock fallback | shared Phase 2 mock-to-real rule |
| Bootstrap | `p4.data_source.load_hotspots(...)` returns `HotspotSource(envelope, source, engine, warnings)` | — | new helper type | provenance + instant rollback |
| Estimator | `resource_factors_from_factors(..., region_country=...)` + `factor_selection_notes()` | factor-code map | priority-based selection + ambiguity report | no silent factor pick among ties |
| Artifacts | `docs/phase2/p4_baseline_output.json`, `p4_real_data_output.json`, `p4_shape_diff.md`; `tools/phase2_p4_shape_diff.py` | — | new files | baseline regression + shape proof |
| Tests | `tests/test_p4_phase2_integration.py` (20) | — | new tests | flag gate, live source, J/M guardrails on real data |
| Imports | `p4/contracts.py` now imports `contracts.schemas` | second `schemas` module | shared module identity | fixes `isinstance` across P3→P4; no field change |

No response envelope, field name, enum value, or endpoint path changed. P1's
dashboard and P2's report consumer require no changes.

**Notifications:** P2 — two optional non-blocking actions logged in
`docs/phase2/p4_integration_log.md` §11 (seed Scope-3 factors; resolve the DEFRA
diesel blend/mineral tie or mark a preferred factor). P1 — no change; live-mode
severity labels differ from the frozen mock (pre-existing Phase 1 B3 decision).

---

# P1 — Phase 2 (branch `phase2-p1-integration`)

**Status: NO frozen contract changes.** P1 does not change `contracts/schemas.py`
or any request/response shape in `contracts/api_contract.md`. All swaps consume
existing endpoints (A5/A9/B2/C3/G2/J2/M1/N1/N2/K1) as documented.

## Additive / observational entries (no existing shape altered)

| Area | Change | Old shape | New shape | Reason |
|---|---|---|---|---|
| Dataset bootstrap | new `GET /api/context` consumed by P1 (endpoint added during Phase 1 merged-API work, `engine/api.py`) | mock JSON read | `{organization, facilities[], reporting_periods[]}` | P1 needs org/facility/period rows in live mode without P2 PG routers; additive, ignore-safe |
| Scenario CRUD | `O1–O7` (create/edit/delete scenario + interventions) are **not served** by the currently merged surface (no `scenarios` router mounted) | — | — | P1 Phase 2 covers `K1` simulate only; scenario CRUD stays client-side state. Flagged to P2/P4: merge decision in progress |
| Fallback config | `VITE_USE_MOCK_DATA` / localStorage `ecoleak.useMockData` runtime gate in `frontend/src/lib/api.ts` | `VITE_USE_MOCKS` build-time only | runtime `auto/mock/live` + per-group fallback registry + demo banner | shared Phase 2 `USE_MOCK_DATA` rule applied to the browser client |

**Notifications:** P2 — `GET /api/facilities/{id}/processes`, `.../activity`, and A2/A5/A9
require a live PostgreSQL; when P2's DB is down those groups fall back to mocks in
P1 (by design, §2 of the P1 log). P3/P4 — no change required; J2/N1/N2/G2 shapes
consumed as-is, verified by the running P4 router outputs.

---

# Phase 2 POST-AUDIT ADDENDUM (P1, audit pass)

Two additive/response-shape observations found during the executed Phase 2
audit probe of the merged surface (single base URL `http://localhost:8000`):

| Area | Change | Old shape (contract) | New shape (live) | Reason / status |
|---|---|---|---|---|
| N1 dashboard | additive key `production_unit` in `GET .../dashboard` response | contract lists `total_kgco2e, scope_breakdown, carbon_intensity, largest_hotspot, circularity_score, potential_reduction_kgco2e, potential_annual_saving, last_calculated_at, empty_state?` | same + `production_unit` | additive; ignored by P1 (no Zod strict parse on N1) — **undocumented until now**; owners: P4/P1 merged gateway |
| K1 simulate | response is a wrapper, not the frozen `ImpactAssessment` | `202 ImpactAssessment` | `{scenario_id, assessment: ImpactAssessment, interventions, payback_status, payback_reason, over_budget, issues}` | originates in `engine/api.py` (Phase 1); P1 normalizes defensively (`normalizeSimulate`); **P3 to confirm/align or re-document**; additive keys, agency of the frozen model intact inside `assessment` |
| K1 simulate | HTTP status | `202` accepted-async | `200` synchronous | works (deterministic engine); note for P2/P3 API-conformance pass |

Consumers notified: P1 (adapted + logged), P3 (owner of `engine/api.py` —
flagged for confirmation), P4 (N1 owner — flagged).

---

# Phase 2 REMEDIATION DECISIONS (branch `phase2-fixes`, post-audit)

| # | Item | Decision | Contract impact | Verification |
|---|---|---|---|---|
| R1 | K1 response shape (BLOCKER 1) | **Wrapper envelope is canonical**: `ScenarioSimulationEnvelope { scenario_id, assessment: ImpactAssessment, interventions, payback_status, payback_reason, over_budget, issues }` @ HTTP 200. Formal model added (`schemas.py`), T1 reserved 202 semantics for job endpoints only | api_contract.md K1 row updated; `contracts/schemas.py` addendum; P1 consumes the canonical shape (`normalizeSimulate` + `computedVia`) | `tests/test_remediation.py::test_k1_*` PASS; live curl with all 18 J2 ids → 200, zero 404 |
| R2 | N1 additive `production_unit` | **Accepted into the permanent contract** (P1/P2 acting decision). Formalized as `DashboardResponse.production_unit` | api_contract.md N1 row + `schemas.py` `DashboardResponse`; P1 TS `DashboardPayload.production_unit` | `test_remediation.py::test_n1_*` PASS (scope breakdown sums == total) |
| R3 | K1 intervention id coverage | **(a) chosen**: full 19-entry P4 library seeded into the simulator data source (SQLite test/seed images + PG production seed via `seed_interventions.py`) | none (additive rows) | PG seed = 19; SQL source over PG returns 19; K1 all-18 ids → 200 |
| R4 | Silent K1 fallback | **Removed/visibilized**: `fetchSimulate` returns `computedVia: 'engine' \| 'local_fallback'`; UI labels "Engine-verified simulation (K1)" vs "Local Module-K math — computed_via=local_fallback"; failed live calls also list `scenario-simulate` in the demo-data banner | none | Playwright: engine-verified notice PASS, no NaN |
| R5 | PG-only runtime paths | **Executed against real PostgreSQL 16.6**; CI added (`.github/workflows/phase2-ci.yml`, postgres:16 service) | none | backend suite **54/54**, P3 SQL-source on PG totals reconcile, seed smoke asserts 566,360.8 + 19 interventions |
| R6 | jwt placeholder guard | **Placeholders rejected in ALL environments**; prod-like start without `JWT_SECRET` refuses to start | none (config only) | 4-case verification executed (prod-no-secret raises, placeholder raises even in dev, real secret OK, dev default OK) |
| R7 | Module Q | **Q1/Q2 wired into merged surface** (in-memory store; frozen error shape (`FEEDBACK_VALIDATION` 422)); SQL persistence → Phase-3 backlog owner P2 | additive endpoints (not in api_contract.md originally — now served; catalogued in `process_notes.md` §4) | Q1 201 / Q2 200 / guard 422 frozen shape |
| R8 | Module H2/H3 | **Phase-3 backlog, owner P3** (needs anomaly persistence) | none | `process_notes.md` §4 |
| R9 | Branch protection | Admin-gated — required config documented for repo owner (Ronit069); CI rule added so tests must pass | none | `process_notes.md` §2 + `.github/workflows/phase2-ci.yml` |

---

# PHASE 3 READINESS ADDENDUM (branch `phase3-readiness`, executed 2026-09-12)

Closures for the full-system verification findings, with no frozen key renamed
or removed:

| # | Item | Change | Contract impact | Verification |
|---|---|---|---|---|
| R10 | F2 `GET .../calculations` (documented, was unserved) | Implemented on the merged engine router. Calculations are derived deterministically on demand, so GET returns the identical `EmissionCalculation[]` payload as F1 (no persisted job list exists) | api_contract.md F2 row annotated (was documented; now served) | live GET -> 200 `EmissionCalculation[]`, same values as POST |
| R11 | J3 `PATCH /api/recommendations/{id}` (documented, was unserved) | Implemented with an in-memory status store + transition rule (SUGGESTED -> SHORTLISTED/PLANNED/REJECTED, SHORTLISTED -> PLANNED/REJECTED, PLANNED -> IMPLEMENTED/REJECTED). Invalid status -> 422, invalid transition -> 409, unknown id -> 404 (all frozen shape). SQLAlchemy persistence -> Phase-3 backlog (same deferral decision as Q feedback) | api_contract.md J3 row annotated | live PATCH transitions + negative cases |
| R12 | F-8 machine-readable degraded-mode label | `impact.assumptions.data_is_stub` (bool) on every J1/J2/M1 recommendation, sourced from `FacilityContext.is_fixture` (default True while the P4 demo tariff fixture supplies baselines). Additive key inside the free-form `assumptions` object only - no envelope key added, no Zod strict-parse change | api_contract.md J1/J2 note; no frozen shape change | live J2 items carry `data_is_stub=true`; frontend notice rendered |
| R13 | F-4 health | `GET /api/health` now probes DB (`SELECT 1`, bounded 4s) + engine data source; 503 frozen shape (`HEALTH_DEPENDENCY_UNAVAILABLE`) with per-component detail when unhealthy; adds `components` and `X-Request-Id` | additive keys on the healthy path | live: 503 in ~4s with DB down; 200 `{database: ok, engine: ok}` with DB up |
| R14 | F-13 malformed input | UUID path params typed as `UUID` across P2 routers (FastAPI -> frozen 422); invalid `reason_code` and non-numeric feedback/simulate fields -> 422 frozen shape (no raw 500) | none (error semantics only) | live: malformed UUID -> 422; invalid reason_code -> 422; bad numeric -> 422 |
| R15 | F-14 observability | Structured request logging (method/path/status/request_id/elapsed_ms) + 500 handler logs cause with request id + traceback; `X-Request-Id` response header | none | live log lines captured; 500 traceback captured with request id |

---

# PHASE 3 AUDIT FIX ADDENDUM (branch `phase3-fixes`, executed 2026-09-12)

Closures for the Phase-3 audit findings (general + P1). No frozen key removed.

| # | Item | Change | Contract impact | Verification |
|---|---|---|---|---|
| R16 | GA-01 / P4-C1 (CRITICAL) | `p4/api.py::_run_ranker` + `engine_bridge.real_recommendations` now resolve facility/org/processes/context from the LIVE data source (`p4/data_source.build_facility_context`, `load_facility_dataset`, `resource_factors_from_factors`); the mock demo facility/context is no longer hardcoded | none (behavior fix) | non-demo facility: recommendations/dashboard 200; report recommendations section REAL |
| R17 | GA-02 | `AUTH_MODE=stub` refused when `ENVIRONMENT != development` unless `ALLOW_STUB_AUTH=true` | none (config) | tests `test_ga02_*` |
| R18 | GA-04 / P3-05 | F1 `POST .../calculations` refuses `LOCKED`/`CLOSED` periods with `409 PERIOD_LOCKED` (frozen shape); GET (F2) remains a read | api_contract F1 row annotated | live 409; `test_ga04_*` |
| R19 | GA-05 | `units.normalize` labels the ACTUAL target unit when `to_unit` is supplied (was family base) | D1 semantics corrected | `test_explicit_target_unit_labels_target` |
| R20 | GA-06 / P3-01 | `mocks/mock_dataset.json` now carries the full 19-entry intervention library (was 5) | none (fixture) | `test_ga06_mock_dataset_carries_full_library`; K1 mock path resolves library-only ids |
| R21 | P1-04 | 5xx handler re-applies CORS + security headers + `X-Request-Id` (Starlette runs it outside CORSMiddleware) | none | `test_p1_04_5xx_carries_cors_and_request_id` |
| R22 | P1-05 | `DashboardResponse.unresolved_count` (additive) + UI notice; `p4` emits `len(inventory.unresolved)` | api_contract N1 row annotated | live `unresolved_count=2`; `test_p1_05_*` |
| R23 | P1-01/P1-02/P1-03/P1-07/P1-08 | Dashboard: all-scope total labelled + Scope 1+2 denominator shown, division-by-zero guarded, mock-source KPIs labelled, "quality" disambiguated; Processes stale "mock" wording removed | none | frontend build + live run |
| R24 | P1-06 | New Reports page (`/reports`): generate, list, inspect provenance/quality, export JSON/CSV | new UI route | frontend build |
| R25 | P1-09 | Facility selector (persisted; bootstrap honours it); active-facility display fixed on Dashboard/Profiling/DrillMap | none | frontend build |
| R26 | P2-03 | Emission-factor create/version audit rows now store full JSON-safe before/after snapshots | none | backend suite 77/77 |

---

# PHASE 3 P4 AUDIT FIX ADDENDUM (branch `phase3-fixes`, after PR #8)

Closures for `docs/phase3/p4_audit.md`. No frozen key renamed/removed.

| # | Item | Change | Contract impact | Verification |
|---|---|---|---|---|
| R27 | P4-H1 (HIGH) | Negative-net recycling no longer crashes the ranker: `estimated_co2_saving_kg` is floored at 0 and the signed value is recorded in `impact.assumptions.net_co2_saving_kg_signed`, with `additional_emissions_kg` when negative | none (assumptions additive; frozen field stays ge=0) | `test_p4_h1_negative_net_recycling_does_not_crash` |
| R28 | P4-M1 | `feedback_type` validated at the boundary -> `422 VALIDATION_ERROR` (was 500) | none | `test_p4_m1_invalid_feedback_type_is_422_frozen` |
| R29 | P4-M3 | Feedback (Q1/Q2) for a recommendation id that is not in the current ranking -> `404 NOT_FOUND` (frozen) | none | `test_p4_m3_feedback_for_unknown_recommendation_is_404` |
| R30 | P4-L6 | J2 `status`/`rank_max` query params validated -> 422 instead of silent empty 200 | none | `test_p4_l6_invalid_filters_are_422` |
| R31 | P4-M2 | Q1 superset fields and Q2 `{recommendation_id, latest_state, history}` are the **served** shapes; documented here rather than reshaping (additive; no consumer breakage) | documented | p4_audit §2 P4-M2 |

---

# PHASE 3 ENGINE AUDIT FIXES (branch `phase3-fixes`, ranked list)

Additive `assumptions` keys only — no frozen field changed.

| # | Item | Change | Verification |
|---|---|---|---|
| R32 | P3-04 | Electricity ledger classification no longer routes `captive`/bare-`renewable` text to the ONSITE ledger: only genuine on-site self-consumption (on-site/onsite/self-consum/rooftop/behind-the-meter) is kept separate; captive fossil generation is counted (Scope 1/2), purchased renewable is no longer silently zeroed; `ledger_methodology` recorded | `test_p3_04_*` |
| R33 | P3-02 | Factor `valid_from`/`valid_to` compared to the reporting period; in-window factors preferred; `factor_validity` + penalty recorded | `test_p3_02_*` |
| R34 | P3-03 | Facility country/state compared to `factor.region_country/state`; region matches preferred; `factor_region_match` = MATCH/GENERIC/NATIONAL_FALLBACK/MISMATCH recorded | `test_p3_03_*` |
| R35 | P3-06 | Effective confidence = activity confidence − penalties (fallback 15, region mismatch 10 / national fallback 5, out-of-window 10), recorded as `confidence_penalty` / `effective_confidence`; used for `EmissionCalculation.confidence_score` and data-quality weighting | `test_p3_06_*` |
| R36 | P3-08 | Cost model carries `price_source`/`price_version`/`price_valid_year`, surfaced in every simulation intervention's `assumptions` | `test_p3_08_*` |
