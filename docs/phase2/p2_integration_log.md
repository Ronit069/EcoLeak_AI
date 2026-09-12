# P2 — Phase 2 Integration Log

**Role:** P2 (Backend Platform & Data Engine)
**Branch:** `phase2-p2`
**Base:** `de22e60` (Phase 1 merged to `main`)
**Audience:** P1, P3, P4 — read this before wiring into P2. Accuracy first.

Status legend: **STABLE** (tested, contract-shaped) · **FLAG-GATED** (real path behind
`USE_MOCK_DATA=false`, mock is default) · **INCOMPLETE** · **DEVIATION** (documented in
`contract_changes.md`).

---

## 1. Phase 1 P2 endpoint inventory

All routes follow the frozen `contracts/schemas.py` field names and
`contracts/api_contract.md` error shape `{error_code, message, severity, details}`.
Auth is the Phase 1 stub (`X-Organization-Id` + `X-Role` + optional `X-Actor-Id`).

### Module A — Organization / Facility

| Endpoint | Status | Notes |
|---|---|---|
| `POST /api/organizations` | STABLE | admin roles; audited |
| `GET /api/organizations/{organization_id}` | STABLE | tenant-scoped |
| `PATCH /api/organizations/{organization_id}` | STABLE | audited |
| `POST /api/facilities` | STABLE | business validation (days ≤ 366, hours ≤ 24, production ≥ 0) |
| `GET /api/facilities/{facility_id}` | STABLE | tenant-scoped |
| `PATCH /api/facilities/{facility_id}` | STABLE | audited |
| `GET /api/organizations/{organization_id}/facilities` | STABLE | tenant-scoped |
| `POST /api/facilities/{facility_id}/reporting-periods` | STABLE | rejects overlapping periods |
| `GET /api/facilities/{facility_id}/reporting-periods` | STABLE | |

### Module B — Process

| Endpoint | Status | Notes |
|---|---|---|
| `POST /api/facilities/{facility_id}/processes` | STABLE | duplicate name/code rejected |
| `GET /api/facilities/{facility_id}/processes` | STABLE | excludes soft-deleted |
| `GET /api/processes/{process_id}` | STABLE | |
| `PATCH /api/processes/{process_id}` | STABLE | audited |
| `DELETE /api/processes/{process_id}` | STABLE | soft delete only (204) |

### Modules C/D — Activity, Ingestion, Units, Quality

| Endpoint | Status | Notes |
|---|---|---|
| `POST /api/facilities/{facility_id}/activity` | STABLE | duplicate + locked-period guards; audited |
| `PUT /api/facilities/{facility_id}/activity/{activity_id}` | STABLE | full replace; audited old/new |
| `GET /api/facilities/{facility_id}/activity` | STABLE | filters `reporting_period_id`, `process_id`, `activity_category` |
| `POST /api/facilities/{facility_id}/activity/import` | STABLE | 202 ImportJob; pandas/openpyxl/Pandera; dry-run |
| `GET /api/ingestion/batches/{import_id}` | **DEVIATION (additive)** | not in api_contract.md; fetch import report |
| `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/data-quality` | STABLE | facility/period aggregate |
| `POST /api/units/normalize` | STABLE | ambiguous unit → 422 `CONFIRMATION_REQUIRED` |

**Ingestion validation issue codes** (shape is the frozen `ValidationIssue`; codes are P2-owned):

| Severity | Codes |
|---|---|
| ERROR | `NEGATIVE_VALUE`, `MISSING_VALUE`, `INVALID_UNIT`, `DUPLICATE_IN_FILE`, `DUPLICATE_ACTIVITY`, `PERIOD_MISMATCH` |
| WARNING | `IMPLAUSIBLE_MAGNITUDE`, `UNKNOWN_PROCESS_CODE` |
| INFO | `UNIT_CONVERTED` (**new in Phase 2**, see §4) |
| CONFIRMATION_REQUIRED | `AMBIGUOUS_UNIT` (import path) / D1 ambiguous conversion |

### Module E — Emission Factors

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/emission-factors` | STABLE | filters category/subcategory/region/scope/active/source_year |
| `GET /api/emission-factors/lookup` | **DEVIATION (additive)** | prioritized lookup; 422 `EMISSION_FACTOR_NOT_FOUND` when unresolved |
| `GET /api/emission-factors/{factor_id}` | STABLE | |
| `POST /api/emission-factors` | STABLE | admin; `factor_code` uniqueness; audited |
| `POST /api/emission-factors/{factor_id}/new-version` | STABLE | deactivates old, never overwrites/deletes |

### Module I — Interventions

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/interventions` | STABLE | global KB (not tenant-scoped by design) |
| `GET /api/interventions/{intervention_id}` | STABLE | |
| `POST /api/interventions` | STABLE | admin; audited |

### Module P — Reports

| Endpoint | Status | Notes |
|---|---|---|
| `POST /api/facilities/{facility_id}/reporting-periods/{period_id}/reports` | **FLAG-GATED** | 202 receipt; mock default, real when `USE_MOCK_DATA=false` |
| `GET /api/reports/{report_id}` | STABLE | tenant-scoped; full payload |
| `GET /api/reports/{report_id}/export?format=json\|csv` | STABLE | CSV/JSON |
| `GET /api/reports/{report_id}/export?format=pdf` | INCOMPLETE | 501 `PDF_EXPORT_NOT_IMPLEMENTED` (Phase 3) |
| `GET /api/reports` | **DEVIATION (additive)** | list receipts, tenant-scoped |

### Ops

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/health` | **DEVIATION (additive)** | platform health + `use_mock_data`. `/health` now belongs to the P3 engine router (merge collision) |

---

## 2. Phase 2 additions

### 2.1 `USE_MOCK_DATA` flag (shared Phase 2 requirement)
- Config: `backend/app/config.py` → `use_mock_data: bool = True`, `engine_dsn: Optional[str]`.
- Default `true` keeps Phase 1 mock behavior **byte-for-byte** for reports; flipping to
  `false` makes Module P pull live F/G/J/L. Exposed on `GET /api/health`.
- Engine reads this app's `DATABASE_URL` by default; override with `ENGINE_DSN`.

### 2.2 Module P real integration (behind the flag)
`backend/app/services/engine_bridge.py` builds a **fresh** `EcoLeakEngine` per report
against a data source selected by the flag — it never mutates the merged app's global
engine singleton. Sections and their degradation:

| Report section | Source | On failure |
|---|---|---|
| `scope_summary` (Scope 1/2/3, intensity) | Module F `calculate_inventory` | report still returns, sections marked `UNAVAILABLE` |
| `factor_provenance` | Module F provenance + UNRESOLVED markers | falls back to P2 match-based provenance |
| `hotspot_analysis` | Module G `hotspot_result` | `status: UNAVAILABLE` |
| `circularity_assessment` | Module L `circularity_score` | `status: UNAVAILABLE` |
| `recommendations` + `roadmap` + `financial_assessment` | Module J (P4 ranker) | `status: UNAVAILABLE` (tested) |
| `data_quality_score` | P2 `quality.assess_period` | always present |

`report_meta` now carries `use_mock_data`, `data_is_stub`, `stub_sources`
(additive keys inside the P2-owned report payload; no frozen contract involved).

---

## 3. Verification evidence (Phase 2)

Command: `python -m pytest -q` (backend, against `ecoleak_test`) → **54 passed**.

Volume check: `python -m tools.messy_ingestion_check` (108-row messy CSV):

```
status=PARTIAL total=108 accepted=48 rejected=60 warnings=12
severities: {'INFO': 24, 'ERROR': 60, 'WARNING': 12}
issue codes: {'UNIT_CONVERTED': 24, 'NEGATIVE_VALUE': 12, 'MISSING_VALUE': 12,
              'INVALID_UNIT': 12, 'IMPLAUSIBLE_MAGNITUDE': 12,
              'DUPLICATE_IN_FILE': 12, 'PERIOD_MISMATCH': 12}
stored_activity_rows=48 imported_audit_rows=48
RESULT: PASS
```

All four severities behave at volume: ERROR rejects, WARNING imports with a flag,
INFO records conversions, CONFIRMATION_REQUIRED is explicit on ambiguous units.

Audit trail (real ingested data): every import writes one `FILE_IMPORT`
(`ingestion_batch`) row **and** one `ACTIVITY_IMPORTED` (`activity_data`) row per
accepted record; manual entry writes `ACTIVITY_CREATED`. Verified in
`tests/test_audit_trail.py`.

Double-counting (security-doc edge case): re-verified under real ingested data in
`tests/test_double_counting.py` — purchased grid 1000 kWh → Scope 2 only;
on-site self-consumption 400 kWh and exported surplus 200 kWh stay in separate
ledgers (`onsite_generation_kgco2e`, `exported_electricity_kgco2e`) and are excluded
from `total_kgco2e`.

---

## 4. Deviations & notices

1. **No frozen contract change.** `contracts/schemas.py` field names and the
   `api_contract.md` response shapes are unchanged. See `contract_changes.md`.
2. **Additive endpoints** (not in `api_contract.md`): `/api/emission-factors/lookup`,
   `/api/ingestion/batches/{import_id}`, `GET /api/reports`, `/api/health`.
3. **`/health` collision:** the P3 engine router owns `/health`; the P2 platform
   health moved to `/api/health`.
4. **`INFO UNIT_CONVERTED`** is a new P2 issue code emitted on ingestion when Pint
   normalizes a value (e.g. MWh→kWh, tonne→kg). Shape unchanged.
5. **Per-activity import audit** (`ACTIVITY_IMPORTED`) is new in Phase 2 to satisfy
   "every write to activity_data creates an AuditLog entry".
6. **Engine SQL source dependency:** P3's `SQLActivityDataSource` mirrors P2 table
   columns. Any P2 schema change must be announced before merge (see the
   dependency table above and `contract_changes.md`).

## 5. Flagged unstable / incomplete

- `GET /api/reports/{id}/export?format=pdf` → 501 (planned).
- Module P `recommendations` section is `UNAVAILABLE` when the P4 ranker raises;
  the report still generates. Not a blocker, but P4 should confirm J stability.
- Auth remains the Phase 1 stub; JWT is out of P2 Phase 2 scope.
