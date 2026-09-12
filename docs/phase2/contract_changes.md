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
