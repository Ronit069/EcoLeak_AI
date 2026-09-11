# EcoLeak AI — Backend Platform & Data Engine (P2, Phase 1)

FastAPI + PostgreSQL backend implementing the frozen Phase 0 contracts in
`../contracts/schemas.py` and `../contracts/api_contract.md`. Field names, enum
values and response shapes are **not** changed here; `tests/test_contract_parity.py`
fails the build if a serializer drifts from the contract.

## What is implemented (Phase 1)

| Module | Status | Notes |
|---|---|---|
| DB schema | ✅ all 27 doc tables + `ingestion_batches`, `ingestion_errors`, `reports` | SQLAlchemy 2.x + Alembic; every CHECK / UNIQUE index from the DB doc |
| Module C — ingestion | ✅ manual entry + CSV/Excel upload | pandas + openpyxl + Pandera; negatives, missing units, duplicates, period mismatch rejected; implausible magnitude = WARNING; original value/unit preserved |
| Module D — units & quality | ✅ Pint normalization + Carbon Data Quality Score | ambiguous conversions → `CONFIRMATION_REQUIRED` (never silent); per-record score + per-period assessment |
| Module E — emission factors | ✅ versioned KB + 10 real source-cited factors | geography/year/source priority, supplier overrides, explicit `EMISSION_FACTOR_NOT_FOUND` state |
| Module P — reports | ✅ stubbed against `/mocks` | real profile/boundary/factor-provenance/quality + stub hotspot & recommendation sections; `?format=pdf` → 501 until Phase 2 |
| Modules F/G/H/I/J/K/L/M/N/O | schema + seed only | owned by P3/P4; `emission_calculations` table is present but no calculation endpoint (per Phase 1 scope) |

## Real emission factors seeded (`app/seed/real_factors.json`)

| Factor | Value | Unit | Scope | Source |
|---|---|---|---|---|
| Indian grid FY2024-25 | 0.710 | kgCO2/kWh | 2 | CEA CO2 Baseline DB v21.0 |
| Indian grid FY2023-24 | 0.727 | kgCO2/kWh | 2 | CEA CO2 Baseline DB v20.0 (superseded) |
| Diesel (100% mineral) | 2.6594 | kgCO2e/L | 1 | UK DESNZ/DEFRA 2023 |
| Diesel (avg biofuel blend) | 2.5121 | kgCO2e/L | 1 | UK DESNZ/DEFRA 2023 |
| Natural gas | 2.0384 | kgCO2e/m3 | 1 | UK DESNZ/DEFRA 2023 |
| LPG | 1.5571 | kgCO2e/L | 1 | UK DESNZ/DEFRA 2023 |
| Petrol | 2.09747 | kgCO2e/L | 1 | UK DESNZ/DEFRA 2023 |
| UK grid electricity | 0.20707 | kgCO2e/kWh | 2 | UK DESNZ/DEFRA 2023 |
| R-134a fugitive | 1430 | kgCO2e/kg | 1 | IPCC AR5 GWP100 |
| R-410A fugitive | 2088 | kgCO2e/kg | 1 | IPCC AR5 GWP100 |

Per-gas (CO2/CH4/N2O) splits are only stored where the source publishes them; they
are left null otherwise and never invented. The 8 fixture factors from
`mocks/mock_dataset.json` are also seeded verbatim (frozen UUIDs) so P1/P3/P4
fixtures resolve.

> Lookup priority prefers the newer real factors over the `(mock)` fixture
> factors (e.g. natural gas resolves to DEFRA 2023 2.0384, not the mock 2.022).
> P3's deterministic fixture must keep referencing the mock factors by their
> frozen IDs/codes, not by `/emission-factors/lookup`.

## Setup

```bash
# 1) Python deps
pip install -r requirements.txt

# 2) Create databases (PostgreSQL)
#    CREATE DATABASE ecoleak;  CREATE DATABASE ecoleak_test;

# 3) Configure
copy .env.example .env    # then set DATABASE_URL / TEST_DATABASE_URL

# 4) Migrate + seed (mock fixture + real factors + quality scores)
python -m alembic upgrade head
python -m app.seed.run_seed

# 5) Run
python -m uvicorn app.main:app --reload --port 8000
# OpenAPI: http://localhost:8000/docs
```

## Authentication (Phase 1 stub)

Every endpoint runs the 8-point checklist (auth → authz → tenant ownership →
payload schema → business validation → rate limit → audit → safe error response).
`AUTH_MODE=stub` uses trusted headers; Phase 2 flips `AUTH_MODE=jwt` and the
dependency internals change only (`PyJWT` + `pwdlib/argon2` are already wired).

```
X-Organization-Id: <organization uuid>   # tenant scope
X-Role: SYSTEM_ADMIN | ORGANIZATION_ADMIN | SUSTAINABILITY_ANALYST |
        FACTORY_OPERATOR | VIEWER | REGULATOR_READ_ONLY
X-Actor-Id: <user uuid>                  # optional, for audit_logs.actor_id
```

`SYSTEM_ADMIN` and `REGULATOR_READ_ONLY` are global; all other roles are scoped
to their organization.

## Key endpoints

- `POST /api/organizations`, `GET/PATCH /api/organizations/{id}`
- `POST /api/facilities`, `GET /api/organizations/{id}/facilities`,
  `GET/PATCH /api/facilities/{id}`
- `POST/GET /api/facilities/{id}/reporting-periods`
- `POST/GET /api/facilities/{id}/processes`, `GET/PATCH/DELETE /api/processes/{id}`
- `POST /api/facilities/{id}/activity`, `PUT/DELETE`-style updates,
  `GET /api/facilities/{id}/activity`
- `POST /api/facilities/{id}/activity/import` (multipart `file`, `reporting_period_id`, `sheet`, `dry_run`)
- `GET /api/ingestion/batches/{import_id}`
- `GET /api/facilities/{id}/reporting-periods/{period_id}/data-quality`
- `POST /api/units/normalize`
- `GET /api/emission-factors`, `GET /api/emission-factors/lookup`,
  `GET /api/emission-factors/{id}`, `POST /api/emission-factors`,
  `POST /api/emission-factors/{id}/new-version`
- `GET/POST /api/interventions`, `GET /api/interventions/{id}`
- `POST /api/facilities/{id}/reporting-periods/{period_id}/reports`,
  `GET /api/reports/{id}`, `GET /api/reports/{id}/export?format=json|csv|pdf`

Errors always use the frozen shape:
```json
{ "error_code": "...", "message": "...", "severity": "ERROR", "details": {} }
```

## Sample import

`sample_data/activity_template.csv` and `.xlsx` use the accepted headers
(aliases are case/spacing-insensitive). Rows are validated, normalized with Pint,
de-duplicated and quality-scored; each accepted row and each issue is persisted
to `ingestion_errors` for the `ImportJob` report.

## Tests

```bash
python -m pytest -q     # runs against ecoleak_test
```

Covers: contract field parity, DB CHECK/UNIQUE enforcement, Pint conversions and
ambiguous-unit refusal, ingestion accept/reject/warn/dry-run/duplicate, factor
versioning & lookup priority, auth/tenant isolation, period locks, and the report
flow including the PDF 501 stub.

## Additive (non-contract) changes

These do not alter any frozen field name or endpoint shape:

- New tables: `ingestion_batches`, `ingestion_errors`, `reports`.
- New additive columns: `activity_data.carbon_data_quality_score`,
  `activity_data.source_row_hash`, `activity_data.deleted_at`,
  `processes.deleted_at`, `scenarios.deleted_at`,
  `anomaly_results.acknowledged[_note|_at]`,
  `emission_factors.supplier_id`, `emission_factors.supplier_specific`.
- New additive endpoint: `GET /api/emission-factors/lookup`.
