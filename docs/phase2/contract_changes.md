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
