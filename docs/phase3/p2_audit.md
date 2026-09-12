# P2 Phase 3 Audit — Backend Platform & Data Engine

**Owner:** P2
**Branch:** `phase3-p2-audit`
**Audited revision:** `main` @ `10c2b9f` (Phase 1 + Phase 2 merged)
**Reference doc:** `Industrial_Emission_Database_Security_Edge_Cases.md`
**Step 0:** see `docs/phase3/p2_audit_fasttrack.md` (posted before this file).

---

## 1. Verification executed

| Check | Command | Result |
|---|---|---|
| Backend suite | `python -m pytest -q` (from `backend/`) | **54 passed** |
| Engine/P4 + K1 suite | `python -m pytest tests -q` (root) | **164 passed** |
| Lint (real errors) | `python -m ruff check app tests tools` | **clean** |
| Frozen contracts | `python validate_mocks.py` | **9/9 PASS** |
| Volume ingestion | `python -m tools.messy_ingestion_check` | **PASS** (108 rows: 48 accepted / 60 rejected / 12 warnings; INFO 24 / ERROR 60 / WARNING 12; 48 imported-audit rows) |
| Live migration head | `SELECT version_num FROM alembic_version` | `80126bccb7c4` |

---

## 2. Checklist results

### A. Schema & constraints — PASS
- 31 tables, **31 CHECK constraints**, 52 UNIQUE, 43 FKs, 43 indexes in `ecoleak`.
- Doc constraints present and enforced by `tests/test_schema_constraints.py` (9 tests): `organization_size`, `working_days_per_year 0..366`, `working_hours_per_day 0..24`, `annual_production >= 0`, `end_date >= start_date`, `process_links.source <> target`, non-negative activity values, `(organization_id, facility_code)` uniqueness, factor non-negativity + `valid_to >= valid_from`.

### B. Validation severity levels — PASS
- ERROR (`NEGATIVE_VALUE`, `MISSING_VALUE`, `INVALID_UNIT`, `DUPLICATE_IN_FILE`, `DUPLICATE_ACTIVITY`, `PERIOD_MISMATCH`) → row rejected, not persisted.
- WARNING (`IMPLAUSIBLE_MAGNITUDE`, `UNKNOWN_PROCESS_CODE`) → imported, flagged (never silently dropped or altered).
- INFO (`UNIT_CONVERTED`) → recorded for MWh→kWh / tonne→kg.
- CONFIRMATION_REQUIRED (`AMBIGUOUS_UNIT`) → explicit 422 from `POST /api/units/normalize`; never a silent conversion. Verified 5 consecutive calls.
- Volume mix matches the deterministic expectation exactly (tool PASS).

### C. Audit log completeness — PASS
- Manual write: `ACTIVITY_CREATED`. Import: one `FILE_IMPORT` (batch) **plus one `ACTIVITY_IMPORTED` per accepted row** (48/48 in the volume check). Factor changes (`EMISSION_FACTOR_CREATED`/`_VERSIONED`), report generation (`REPORT_GENERATED`), data-quality (`DATA_QUALITY_ASSESSED`) also audited.
- Verified by `tests/test_audit_trail.py` and live counts (`audit_logs` populated by report/DQ events; test DB proves import/manual).
- Actor/organization/entity resolution correct; no secrets logged.

### D. Emission factor provenance — PASS
- 17 active factors across 7 categories; per-gas splits stored only where published (null otherwise; never invented).
- Live non-demo resolution verified: 1000 kWh → `EF-ELEC-GRID-IN-CEA21-FY2024-25` (CEA v21, 0.710) → Scope 2 = 710 kgCO2e, **0 unresolved**, factor provenance retained (`factor_code`, `version`, `source_name`, `source_year`).
- Missing factor is an explicit unresolved state (`EMISSION_FACTOR_NOT_FOUND` / `UNRESOLVED`), never a fabricated default.
- Versioning: `new-version` deactivates the old row, never updates/deletes (verified).

### E. Double-counting (on-site generation vs purchased grid) — PASS
- `tests/test_double_counting.py`: purchased grid 1000 kWh → Scope 2 only; on-site self-consumption 400 kWh → `onsite_generation_kgco2e`; exported surplus 200 kWh → `exported_electricity_kgco2e`; both separate ledgers excluded from `total_kgco2e`.

### F. API security checklist (8-point) — PASS
- AuthN: stub principal required (`X-Organization-Id`); JWT-ready (`AUTH_MODE=jwt`) with `pwdlib`/PyJWT.
- AuthZ: role allow-list; admin-only factor/intervention writes (403 otherwise).
- Tenant ownership: cross-org reads/writes rejected (403/404) — `tests/test_api.py`.
- Payload schema: Pydantic `extra="forbid"`; malformed payload → 422 frozen error shape.
- Business validation: locked/CLOSED periods block writes (409 `PERIOD_LOCKED`); duplicate activity (409 `DUPLICATE_ACTIVITY`); overlapping reporting periods (409).
- Rate limit: per-client sliding window (429) on API/upload; in-memory (single-process) — production note below.
- Audit: all business writes emit `audit_logs`.
- Safe errors: single shape `{error_code, message, severity, details}`; generic 500 hides stack traces.

### G. Reporting period integrity — PASS
- `end_date >= start_date` DB CHECK; overlap rejected at create; `LOCKED`/`CLOSED` blocks activity/scenario/calculation mutations until an audit unlock.

---

## 3. Findings register

| ID | Sev | Finding | Owner | Status |
|---|---|---|---|---|
| P2-C1 | **CRITICAL** | J2 (`…/recommendations`) and N1 (`…/dashboard`) return **500** for every non-demo facility: `p4/api.py::_run_ranker` pairs live hotspots with **mock demo facility/org/processes + demo context**, tripping `p4/engine.py:162` (`hotspot envelope facility_id does not match facility.id`). Non-demo `hotspots`/`leak-map` are 200. | **P4** (primary) | Open — handed back; P4 must use `p4/data_source.py` helpers |
| P2-H1 | **HIGH** | `config.py` placeholder-secret guard now rejects the **shipped `.env.example`** (`JWT_SECRET=change-me-in-production`) and a dev `.env` copy, so the app cannot start from `backend/` with the documented setup. Blocked the backend suite (pytest exit 4) until a real local secret was set. | P2 | Open — fix `.env.example` (blank secret + guidance) |
| P2-H2 | **HIGH** | `app/services/engine_bridge.py` (P2) still uses `mocks/mock_dataset.json` resource factors + fixed demo `FacilityContext`; for non-demo facilities `real_recommendations` returns `UNAVAILABLE` (caught, so Module P degrades silently — no 500). Same anti-pattern as P2-C1, P2-owned. | P2 | Queued (not patched — no data-gap exception) |
| P2-M1 | MED | Import writes one `ACTIVITY_IMPORTED` audit row per accepted record; a 20k-row import yields ~20k audit rows in one transaction. Correct but potentially heavy. | P2 | Backlog |
| P2-M2 | MED | Rate limiter is in-memory (single-process); not shared across workers/instances. | P2 | Backlog (Redis) |
| P2-L1 | LOW | Running `pytest` from repo root cannot collect `backend/tests` (`app` not on `sys.path`); backend suite must run from `backend/`. Pre-existing. | P2 | Backlog |
| P2-L2 | LOW | `pandera` FutureWarning in ingestion error formatting; cosmetic. | P2 | Backlog |

### Root-cause note for P2-C1 (from Step 0)
Not a P2 data gap. Non-demo facilities **have** valid emission factors (17 active; live resolution proven) and full activity/process data. Tariffs have no P2 table, but the frozen contract defines no tariff entity — prices are a documented P4/engine simulation assumption, not the cause. Root cause is P4's hardcoded `_facility_and_org`/`_context`; a secondary P2-owned instance exists in `engine_bridge.py`.

---

## 4. Contract integrity
- `contracts/schemas.py` and `contracts/api_contract.md` unchanged in Phase 3; `test_contract_parity.py` passes; `validate_mocks.py` 9/9.
- No migrations added; `alembic_version=80126bccb7c4`.
- Additive-only Phase 2 changes remain as documented in `docs/phase2/contract_changes.md`.

## 5. Notifications
- **P3:** none. No CRITICAL finding affects calculation inputs (factor resolution and double-counting are correct). No action required.
- **P4:** P2-C1 handed back with exact traceback and the required fix (use `p4/data_source.load_facility_dataset` + `resource_factors_from_factors` + a context keyed to `facility_id`; keep the engine guard).
- **P1:** J2/N1 safe only for the seeded demo UUID until P4 fixes P2-C1; `USE_MOCK_DATA=true` keeps the demo green.

## 6. Verdict
P2 Phase 3 data-integrity posture is **sound**: constraints enforced, severities correct at volume, audit complete, factor provenance intact and available for real facilities, no double-counting, 8-point API security satisfied, reporting-period integrity held. No P2 calculation-input CRITICAL. The two actionable P2 items are the `.env.example` secret mismatch (P2-H1, fix below) and the `engine_bridge` demo hardcode (P2-H2, queued). The demo-breaking CRITICAL belongs to P4.
