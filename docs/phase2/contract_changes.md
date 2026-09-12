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
