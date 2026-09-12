# EcoLeak AI — Frontend Rebuild: Integration & Requirements

**Audience:** whoever builds the fresh UI from scratch.
**Status:** requirements + connections only. **No visual/UX design is prescribed here**
(no layouts, colors, components, or wireframes). This document defines every
connection, contract, config, and functional rule the new UI must satisfy.

**Source of truth:** `contracts/schemas.py`, `contracts/api_contract.md`, and the
running backend. When this document and the code disagree, the code + contracts win.

---

## 1. Repository map & how to run

| Part | Path | Notes |
|---|---|---|
| Backend (FastAPI) | `backend/` | single merged app: P2 platform + P3 engine (`engine/`) + P4 ranker (`p4/`) |
| Contracts (frozen) | `contracts/schemas.py`, `contracts/api_contract.md` | field names/enums/shapes are frozen; additive changes must be logged |
| Mocks (source of truth for demo) | `mocks/*.json` and `frontend/public/mocks/*.json` | identical payloads served to the browser |
| Engine / ranker | `engine/`, `p4/` | imported by `backend/app/main.py` |
| Current frontend | `frontend/` | being replaced; keep its run/config conventions unless noted |

```bash
# Backend (from backend/)
pip install -r requirements.txt          # or requirements.lock at repo root
python -m alembic upgrade head
python -m app.seed.run_seed              # seeds demo org/facility/period/factors
python -m uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/)
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc --noEmit && vite build
```

Backend needs PostgreSQL. `DATABASE_URL` must point at a seeded DB for live mode.
JWT secret rule: `JWT_SECRET` must **not** be a placeholder (e.g. `change-me…`,
`dev-only…`) even in development; a blank value is allowed only while
`AUTH_MODE=stub` and `ENVIRONMENT=development`. See `backend/.env.example`.

---

## 2. Runtime configuration

### 2.1 Frontend env (Vite — only `VITE_`-prefixed vars are exposed to the browser)

| Variable | Values | Meaning |
|---|---|---|
| `VITE_API_URL` | URL or empty | API origin. Empty → same-origin (use the dev proxy). |
| `VITE_API_TOKEN` | string or empty | If set, sent as `Authorization: Bearer <token>`. Required for `AUTH_MODE=jwt`. |
| `VITE_USE_MOCK_DATA` | `true` \| `false` \| `auto` | Shared mock gate: `true`=mock only, `false`=live only (no fallback), `auto`=live-first with per-group fallback. |
| `VITE_USE_MOCKS` | `true` \| `false` | Legacy alias (`false`→live, else mock). Keep for compatibility. |

**Runtime override (must be preserved for demos):** `localStorage` key
`ecoleak.useMockData` = `auto` \| `mock` \| `live`, taking precedence over env.
The UI must expose a way to switch mode and to show which mode is active.

Resolution precedence: `localStorage` → `VITE_USE_MOCK_DATA` → `VITE_USE_MOCKS` →
`auto`.

### 2.2 Backend env (`.env` in `backend/`)

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | postgres `ecoleak` | platform DB |
| `TEST_DATABASE_URL` | `ecoleak_test` | tests only |
| `ENVIRONMENT` | `development` | non-dev requires a real `JWT_SECRET` |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173,http://localhost:3000` | comma-separated; **add your dev origin** (e.g. `:5174`, `:5175`) |
| `MAX_UPLOAD_BYTES` | `10485760` | upload cap (10 MB) |
| `MAX_IMPORT_ROWS` | `20000` | import row cap |
| `RATE_LIMIT_PER_MINUTE` | `120` | general API limit per client |
| `UPLOAD_RATE_LIMIT_PER_MINUTE` | `10` | upload limit per client |
| `USE_MOCK_DATA` | `true` | P2 Module P / report engine source gate |
| `ENGINE_DSN` / `ECOLEAK_SQL_DSN` | unset | DSN the carbon engine reads; else `DATABASE_URL` |
| `AUTH_MODE` | `stub` | `stub` (headers) or `jwt` (strict Bearer) |
| `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | — | JWT mode only |

### 2.3 Base URL & proxy

- API base path is **`/api`** (not `/api/v1`). All routes below are relative to it.
- Vite dev proxy currently forwards `/api` → `http://localhost:8000`
  (`frontend/vite.config.ts`, target overridable via `ECOLEAK_API_URL`).
  A rebuilt UI may instead call `VITE_API_URL` directly.
- Health:
  - `GET /api/health` — platform health; returns `{status, app, environment, use_mock_data, components{database, engine}}`; `503` with frozen error shape when a dependency is down.
  - `GET /health` — engine-only `{status, engine_version}`.
- Every response carries `X-Request-Id`; security headers (`X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, CSP) are set by the backend.

---

## 3. Authentication & required headers

Auth is enforced by a single dependency with two modes (`backend/app/security.py`):

**`AUTH_MODE=stub` (dev/demo):** trusted headers, no token verification.
| Header | Required | Use |
|---|---|---|
| `X-Organization-Id` | optional at auth layer | tenant scope; a *present but wrong* org is rejected (403) |
| `X-Role` | optional (default `SUSTAINABILITY_ANALYST`) | authorization; unknown role → 401 |
| `X-Actor-Id` | optional | audit `actor_id` |

**`AUTH_MODE=jwt` (production):** `Authorization: Bearer <jwt>` is **required** on
every guarded route; missing/malformed/expired →401. Token claims: `sub`,
`organization_id`, `role`, `iat`, `exp`, `jti`.

**Roles:** `SYSTEM_ADMIN`, `ORGANIZATION_ADMIN`, `SUSTAINABILITY_ANALYST`,
`FACTORY_OPERATOR`, `VIEWER`, `REGULATOR_READ_ONLY`. `SYSTEM_ADMIN` and
`REGULATOR_READ_ONLY` are global (bypass tenant check); all others are scoped to
their organization.

**Rules the UI must implement**
- Send `X-Organization-Id` (stub) or the Bearer token (`VITE_API_TOKEN`) on every call.
- Handle `401` (not authenticated) and `403` (wrong tenant / insufficient role) distinctly.
- Never store secrets/tokens in places that leak to other users; token comes from env.
- **Known gap (documented, not to be assumed away):** `GET /api/emission-factors`,
  `GET /api/emission-factors/{id}` and `GET /api/interventions` currently return
  `200` without credentials (global reference data). Do not rely on these to prove
  a session is valid.

---

## 4. Error contract (every endpoint)

Frozen shape:
```json
{ "error_code": "STRING", "message": "STRING", "severity": "ERROR|WARNING|INFO|CONFIRMATION_REQUIRED", "details": {} }
```
| HTTP | When |
|---|---|
| `400/422` | schema/business validation; `details.issues[]` is `ValidationIssue[]` |
| `401` | missing/invalid credentials |
| `403` | wrong tenant or insufficient role |
| `404` | not found (also used to avoid cross-tenant existence leaks) |
| `409` | conflict: duplicate activity/import, overlapping period, locked period |
| `429` | rate limited |
| `500` | generic only; never a stack trace |
| `501` | PDF export not implemented |
| `503` | `/api/health` dependency unavailable |

`ValidationIssue` = `{ severity, code, message, field?, details? }` where severity
is `ERROR | WARNING | INFO | CONFIRMATION_REQUIRED`. The UI must surface these
per-row/per-field, including `details.row_number` for imports.

---

## 5. JSON wire conventions (critical)

- **Numbers:** most P2 routes and the engine/ranker return JSON **numbers**
  (`Decimal` is encoded to number). The one exception is the **Module P report
  payload** (`GET /api/reports/{id}` → `payload`): it is persisted as JSONB after
  `json.dumps(..., default=str)`, so its numeric values arrive as **strings**.
  Coerce there (e.g. `Number(x)` / Zod `.coerce.number()`), and validate types.
- **Dates/times:** ISO 8601 strings.
- **UUIDs:** strings.
- **Enums:** the exact uppercase string values listed in §10.1.
- **Optional fields:** `null` means "not available/unresolved" — never render as 0.
- Server rounds for display only; keep full precision in state and format at render.

---

## 6. Bootstrap / context flow (must happen first)

1. `GET /api/context` (engine) → `{ organization, facilities[], reporting_periods[] }`.
   There is **no** `processes` key here.
2. Resolve IDs: `organization.id`, `facilities[0].id`, `reporting_periods[0].id`.
3. Fallback demo IDs when in mock mode / live context empty:
   - org `0a1b2c3d-0001-4001-8001-000000000001`
   - facility `0a1b2c3d-0002-4002-8002-000000000002`
   - period `0a1b2c3d-0003-4003-8003-000000000003`
4. All facility/period-scoped calls use these IDs.

`/api/context` is an **additive** endpoint (not in the original api_contract.md);
it is the live replacement for reading `mock_dataset.json` for org/facility/period.

---

## 7. Mock data & per-group fallback (required behavior)

- Mock files (served from `frontend/public/mocks/`):
  - `mock_dataset.json` — organization, facilities, reporting_periods, processes, activity_data, emission_factors, circular_interventions.
  - `mock_hotspot_output.json` — `HotspotDetectionResult`.
  - `mock_recommendation_output.json` — `RecommendationGenerationResult`.
- In `auto` mode the UI must attempt live first, and on failure fall back **per
  group** (not globally), recording the group name. Groups used by the current
  frontend: `dataset`, `processes`, `activities`, `hotspots`, `dashboard`,
  `leak-map`, `recommendations`, `explanation`, `scenario-simulate`.
- The UI **must** display that demo/mock data is in use and, ideally, which groups
  fell back. This is a functional transparency requirement, not a design choice.
- In `live` mode there is no fallback: failures must surface as errors.
- A `200` response whose `Content-Type` is `text/html` must be treated as a failed
  live call (SPA fallback), not parsed as JSON.

---

## 8. Endpoint catalog

Legend: **Auth** = `none` (no auth dependency), `auth` (principal required),
`write` (write role required), `admin` (admin role required). All are relative to
`/api`. Response references §9/§10.

### Cross-cutting / bootstrap
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/api/health` | none | — | platform health (see §2.3) |
| GET | `/health` | none | — | engine health |
| GET | `/api/context` | auth | — | `{organization, facilities[], reporting_periods[]}` |

### Module A — Organization / Facility / Period
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/organizations` | admin | `OrganizationCreate` (see §10.2) | `201 Organization` |
| GET | `/organizations/{organization_id}` | auth | — | `Organization` |
| PATCH | `/organizations/{organization_id}` | admin | partial Organization | `Organization` |
| POST | `/facilities` | write | `FacilityCreate` | `201 Facility` |
| GET | `/facilities/{facility_id}` | auth | — | `Facility` |
| PATCH | `/facilities/{facility_id}` | write | partial Facility | `Facility` |
| GET | `/organizations/{organization_id}/facilities` | auth | — | `Facility[]` |
| POST | `/facilities/{facility_id}/reporting-periods` | write | `ReportingPeriodCreate` | `201 ReportingPeriod` |
| GET | `/facilities/{facility_id}/reporting-periods` | auth | — | `ReportingPeriod[]` |

### Module B — Process
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/facilities/{facility_id}/processes` | write | `ProcessCreate` | `201 Process` |
| GET | `/facilities/{facility_id}/processes` | auth | — | `Process[]` |
| GET | `/processes/{process_id}` | auth | — | `Process` |
| PATCH | `/processes/{process_id}` | write | partial Process | `Process` |
| DELETE | `/processes/{process_id}` | write | — | `204` (soft delete) |

### Modules C/D — Activity, Ingestion, Units, Quality
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/facilities/{facility_id}/activity` | write | `ActivityCreate` | `201 ActivityData` |
| PUT | `/facilities/{facility_id}/activity/{activity_id}` | write | `ActivityUpdate` | `ActivityData` |
| GET | `/facilities/{facility_id}/activity` | auth | query `reporting_period_id`, `process_id`, `activity_category` | `ActivityData[]` |
| POST | `/facilities/{facility_id}/activity/import` | write (upload rate limit) | multipart: `file` (.csv/.xlsx), `reporting_period_id`, `sheet?`, `dry_run?` | `202 ImportJob` |
| GET | `/ingestion/batches/{import_id}` | auth | — | `ImportJob` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/data-quality` | auth | — | `DataQuality` |
| POST | `/units/normalize` | auth | `{value, from_unit, to_unit}` | `NormalizeResult` or `422 CONFIRMATION_REQUIRED` |

### Module E — Emission Factors
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/emission-factors` | **none** | query `category,subcategory,region_country,region_state,scope,active,source_year` | `EmissionFactor[]` |
| GET | `/emission-factors/{factor_id}` | **none** | — | `EmissionFactor` |
| GET | `/emission-factors/lookup` | none | query `category, activity_subcategory, normalized_unit, scope?, region_country?, region_state?, on_date?, supplier_id?` | `EmissionFactor` or `422 EMISSION_FACTOR_NOT_FOUND` (additive endpoint) |
| POST | `/emission-factors` | admin | `EmissionFactorCreate` | `201 EmissionFactor` |
| POST | `/emission-factors/{factor_id}/new-version` | admin | `EmissionFactorCreate` | `201 EmissionFactor` (old row deactivated, never overwritten) |

### Module I — Circular Interventions
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/interventions` | **none** | query `industry_sector,process_category,complexity,active` | `CircularIntervention[]` |
| GET | `/interventions/{intervention_id}` | **none** | — | `CircularIntervention` |
| POST | `/interventions` | admin | `CircularInterventionCreate` | `201 CircularIntervention` |

### Modules F/G/H/K/L — Engine (auth + tenant guards)
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/inventory-summary` | — | `InventorySummary` (Scope 1/2/3 totals, intensity) |
| POST | `/facilities/{facility_id}/reporting-periods/{period_id}/calculations` | `{activity_ids?, calculation_version?}` | `202 EmissionCalculation[]` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/calculations` | — | `EmissionCalculation[]` |
| POST | `/facilities/{facility_id}/reporting-periods/{period_id}/hotspots/detect` | `{scope_boundary?, weights?}` | `202 HotspotDetectionResult` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/hotspots` | — | `HotspotDetectionResult` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/circularity-score` | — | `CircularityScore` |
| POST | `/scenarios/{scenario_id}/simulate` | `{facility_id?, reporting_period_id?, interventions[], budget_limit?, target_reduction_pct?, scope_boundary?}` | `ScenarioSimulationEnvelope` |
| POST | `/facilities/{facility_id}/anomalies/detect` | `{process_id?, reporting_period_id?, model_version?}` | `{anomalies: AnomalyResult[]}` |

> `scenario_id` in `/scenarios/{scenario_id}/simulate` is supplied by the client
> (the current UI uses a fixed placeholder UUID); the engine treats it as a label.

### Modules J/M/N/Q — Recommendations, Dashboard, Feedback (auth + tenant guards)
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/facilities/{facility_id}/reporting-periods/{period_id}/recommendations/generate` | `{hotspot_ids?, budget_limit?, constraints?}` | `202 RecommendationGenerationResult` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/recommendations` | query `status?, rank_max?` | `RecommendationGenerationResult` |
| PATCH | `/recommendations/{recommendation_id}` | `{status}` | `Recommendation` |
| GET | `/recommendations/{recommendation_id}/explanation` | — | `{recommendation_id, summary, evidence, assumptions, confidence_score, generated_by}` |
| POST | `/recommendations/{recommendation_id}/feedback` | `RecommendationFeedback` (`feedback_type`, `reason?`, `reason_code?`, `actual_*?`) | `201 FeedbackEvent` |
| GET | `/recommendations/{recommendation_id}/feedback` | — | `{recommendation_id, latest_state, history[]}` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/dashboard` | — | `DashboardResponse` |
| GET | `/facilities/{facility_id}/reporting-periods/{period_id}/leak-map` | — | `{nodes: LeakMapNode[], links: []}` |

### Module P — Reports
| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/facilities/{facility_id}/reporting-periods/{period_id}/reports` | write | `{template_version, include_scope3?}` | `202 ReportReceipt {report_id,status,version,generated_at,report_hash}` |
| GET | `/reports/{report_id}` | auth | — | `{report_id,status,version,report_hash,generated_at,payload}` (payload keys in §9.12) |
| GET | `/reports` | auth | query `facility_id?, reporting_period_id?` | `ReportReceipt[]` |
| GET | `/reports/{report_id}/export` | auth | query `format=json\|csv\|pdf` | `json`/`csv` download; `pdf` → `501` |

> Modules **H2/H3 (list/acknowledge anomalies)** and full **O scenario CRUD** are
> not on the merged surface yet (accepted backlog). The UI must not assume them.

---

## 9. Key response shapes (the actual connections)

1. **Organization**: `{id, name, industry_sector, industry_subtype, country, state, city, currency_code, organization_size, created_at, updated_at}`
2. **Facility**: `{id, organization_id, name, facility_code, country, state, city, latitude, longitude, annual_production, production_unit, working_days_per_year, working_hours_per_day, active, created_at, updated_at}`
3. **ReportingPeriod**: `{id, facility_id, period_type, start_date, end_date, status, created_at}`
4. **Process**: `{id, facility_id, name, process_code, sequence_no, description, process_category, active, created_at}`
5. **ActivityData**: `{id, facility_id, process_id, asset_id, reporting_period_id, activity_category, activity_subcategory, source_name, original_value, original_unit, normalized_value, normalized_unit, data_source_type, measured_or_estimated, confidence_score, notes, created_at}`. *Never mutate `normalized_*` client-side; send `original_*` and let the server normalize.*
6. **ImportJob**: `{import_id, status, row_issues: ValidationIssue[]}`. `status ∈ {RECEIVED, PROCESSING, COMPLETED, PARTIAL, FAILED, DRY_RUN}`; each issue's `details` carries `{row_number, raw_row}`.
7. **NormalizeResult**: `{original_value, original_unit, normalized_value, normalized_unit, conversion_factor, conversion_source}`.
8. **DataQuality**: `{completeness_score, source_quality_score, factor_quality_score, temporal_quality_score, unit_quality_score, total_score, issues: ValidationIssue[]}`.
9. **EmissionFactor**: `{id, factor_code, category, subcategory, item_name, region_country, region_state, scope, input_unit, output_unit, co2_factor, ch4_factor, n2o_factor, total_co2e_factor, source_name, source_url, source_year, valid_from, valid_to, methodology, confidence_level, version, active, created_at}`.
10. **InventorySummary**: `{scope1_kgco2e, scope2_kgco2e, scope3_kgco2e, total_kgco2e, carbon_intensity, production_unit, generated_at}`.
11. **EmissionCalculation**: `{id, activity_data_id, emission_factor_id, calculation_version, scope, co2e_kg, calculation_formula, assumptions, confidence_score, calculated_at}`.
12. **Report payload** (`payload` keys): `report_meta{template_version, include_scope3, generated_at, use_mock_data, data_is_stub, stub_sources[]}`, `profile{organization, facility, reporting_period}`, `boundary{scopes[]}`, `factor_provenance[]`, `scope_summary{scope1_kgco2e, scope2_kgco2e, scope3_kgco2e, total_kgco2e, carbon_intensity?, production_unit?, onsite_generation_kgco2e?, exported_electricity_kgco2e?, note}`, `data_quality_score{total_score, components{completeness,source,factor,temporal,unit}, issues[]}`, `hotspot_analysis{status, total_emissions_kgco2e, hotspots[]}`, `circularity_assessment{status,...}`, `recommendations{status, budget_limit, items[]}`, `financial_assessment{total_capex, total_annual_saving, total_co2_saving_kg}`, `roadmap[]{rank,intervention_code,intervention_title,payback_years}`, `assumptions[]`, `disclaimer`. Section `status ∈ {STUB, REAL, UNAVAILABLE}`.
13. **CircularityScore**: `{recycled_input_score, waste_recovery_score, energy_recovery_score, water_reuse_score, reuse_score, total_score, methodology_version, calculated_at, is_internal_metric, not_a_certified_standard, disclaimer, score_complete, component_sources, issues[]}` — must be labelled an internal metric.
14. **HotspotDetectionResult**: `{facility_id, reporting_period_id, generated_at, scope_boundary[], total_emissions_kgco2e, data_quality_score, hotspots: HotspotOutputItem[]}`; each item = `EmissionHotspot` + `{rank, process_name, activity_category}`.
15. **EmissionHotspot**: `{id, facility_id, reporting_period_id, process_id, asset_id, hotspot_type, emissions_kgco2e, contribution_percent, carbon_intensity, inefficiency_score, waste_ratio_score, improvement_potential_score, hotspot_score, severity, explanation, created_at}`.
16. **RecommendationGenerationResult**: `{facility_id, reporting_period_id, generated_at, budget_limit, recommendations: RecommendationOutputItem[]}`; each item = `Recommendation` + `{intervention_code, intervention_title, explanation, impact}`.
17. **Recommendation**: `{id, facility_id, reporting_period_id, hotspot_id, intervention_id, rank, carbon_saving_score, financial_return_score, feasibility_score, circularity_score, implementation_speed_score, confidence_score, final_score, status, generated_at}`; `status ∈ {SUGGESTED, SHORTLISTED, REJECTED, PLANNED, IMPLEMENTED}`.
18. **RecommendationAssessment** (`impact`): `{id, recommendation_id, estimated_capex, estimated_annual_opex_change, estimated_annual_saving, estimated_co2_saving_kg, estimated_energy_saving, estimated_waste_reduction, payback_years, cost_per_tonne_co2_avoided, assumptions, confidence_score}`. `payback_years` is `null` when saving ≤ 0.
19. **ScenarioSimulationEnvelope** (K1): `{scenario_id, assessment: ImpactAssessment, interventions[], payback_status?, payback_reason?, over_budget, issues[]}`. **Note the wrapper** — the assessment is nested under `assessment`, not top-level.
20. **ImpactAssessment**: `{id, scenario_id, baseline_emissions_kg, projected_emissions_kg, total_co2_saving_kg, reduction_percent, total_capex, annual_saving, payback_years, generated_at}`.
21. **DashboardResponse** (N1): `{total_kgco2e, scope_breakdown{SCOPE_1,SCOPE_2,SCOPE_3}, carbon_intensity, production_unit, largest_hotspot, circularity_score, potential_reduction_kgco2e, potential_annual_saving, last_calculated_at, empty_state}`.
22. **LeakMap**: `{nodes:[{process_id, process_name, emissions_kgco2e, contribution_percent, severity}], links: []}`.
23. **RecommendationFeedback**: `{id, recommendation_id, feedback_type, reason, actual_capex, actual_annual_saving, actual_co2_saving_kg, submitted_at}`; `feedback_type ∈ {USEFUL, NOT_APPLICABLE, CONSIDER_LATER, IMPLEMENTED, REJECTED}` (REJECTED requires a structured `reason_code`).
24. **Explanation**: `{recommendation_id, summary, evidence{hotspot_id, intervention_id, scores{...}, impact}, assumptions, confidence_score, generated_by}`.

---

## 10. Reference tables

### 10.1 Enums (exact wire values)

| Enum | Values |
|---|---|
| OrganizationSize | `SMALL`, `MEDIUM` |
| PeriodType | `MONTHLY`, `QUARTERLY`, `ANNUAL`, `CUSTOM` |
| ReportingPeriodStatus | `DRAFT`, `LOCKED`, `CLOSED` |
| ActivityCategory | `ELECTRICITY`, `FUEL`, `MATERIAL`, `WATER`, `TRANSPORT`, `WASTE`, `REFRIGERANT`, `STEAM`, `OTHER` |
| DataSourceType | `MANUAL`, `CSV`, `EXCEL`, `API`, `SENSOR`, `OCR` |
| MeasuredOrEstimated | `MEASURED`, `ESTIMATED` |
| Scope | `SCOPE_1`, `SCOPE_2`, `SCOPE_3` |
| ConfidenceLevel | `HIGH`, `MEDIUM`, `LOW` |
| HotspotSeverity | `LOW`, `MODERATE`, `HIGH`, `CRITICAL` |
| RecommendationStatus | `SUGGESTED`, `SHORTLISTED`, `REJECTED`, `PLANNED`, `IMPLEMENTED` |
| FeedbackType | `USEFUL`, `NOT_APPLICABLE`, `CONSIDER_LATER`, `IMPLEMENTED`, `REJECTED` |
| ValidationSeverity | `ERROR`, `WARNING`, `INFO`, `CONFIRMATION_REQUIRED` |
| InterventionComplexity | `LOW`, `MEDIUM`, `HIGH` |
| RiskLevel | `LOW`, `MEDIUM`, `HIGH` |

### 10.2 Request field rules (client → server)

- `OrganizationCreate`: `{name, industry_sector, industry_subtype?, country, state?, city?, currency_code='INR' (ISO 3 uppercase), organization_size}`.
- `FacilityCreate`: `{organization_id?, name, facility_code?, country, state?, city?, latitude? (-90..90, 6dp), longitude? (-180..180, 6dp), annual_production? (≥0), production_unit?, working_days_per_year? (0..366), working_hours_per_day? (0..24), active}`.
- `ReportingPeriodCreate`: `{facility_id?, period_type, start_date, end_date, status}` with `end_date ≥ start_date`; overlapping periods are rejected `409`.
- `ProcessCreate`: `{facility_id?, name (unique per facility), process_code? (unique per facility), sequence_no? (>0), description?, process_category?, active}`.
- `ActivityCreate/Update`: `{facility_id?, process_id?, asset_id?, reporting_period_id, activity_category, activity_subcategory, source_name?, original_value? (≥0), original_unit, normalized_value?, normalized_unit?, data_source_type, measured_or_estimated, confidence_score? (0..100), notes?}`.
- `EmissionFactorCreate`: all §9.9 fields except `id`/`created_at`; `total_co2e_factor ≥ 0`; `valid_to ≥ valid_from`; `factor_code` unique.
- Reject unexpected fields (Pydantic `extra="forbid"`); the client should send only known keys.

### 10.3 Business rules the UI must honor

- **Locked periods:** `status ∈ {LOCKED, CLOSED}` blocks activity/scenario/calculation mutation → `409 PERIOD_LOCKED`. Disable editing and explain why.
- **Duplicates:** identical activity → `409 DUPLICATE_ACTIVITY`; identical file upload → `409 DUPLICATE_IMPORT`.
- **Ambiguous units:** `POST /units/normalize` with cross-dimension (e.g. L→kg) → `422 CONFIRMATION_REQUIRED`; never convert silently in the UI.
- **Unresolved factors:** appear as `UNRESOLVED` provenance entries; the report is labelled `DRAFT`. Surface them; do not substitute a default.
- **Double counting:** on-site generation and exported electricity are separate ledgers (`onsite_generation_kgco2e`, `exported_electricity_kgco2e`) and are excluded from Scope totals. Do not add them into `total_kgco2e`.
- **Payback:** `null` when `annual_saving ≤ 0`; `0` CAPEX = immediate; adoption must be `0..100`.
- **Imports:** `dry_run=true` returns `status=DRY_RUN` and persists nothing. `row_issues` severity must be rendered per row (`details.row_number`).
- **Reports:** creation returns `202` (async-style receipt); then `GET /reports/{id}`. Each generation increments `version`. `report_meta.data_is_stub` tells you whether mock or live engine data was used.
- **PDF export** is `501` in this phase; offer JSON/CSV.
- **Circularity** is an internal metric — display the provided disclaimer/`not_a_certified_standard` flag.

### 10.4 Limits

- Upload: extensions `.csv`, `.xlsx`; MIME allow-list enforced; ≤ `MAX_UPLOAD_BYTES` (10 MB default); ≤ `MAX_IMPORT_ROWS` (20k default); `sheet?` selects an Excel sheet; `dry_run?` optional.
- Rate limits: general `120/min`, upload `10/min` per client → handle `429`.

---

## 11. Contract governance (do not violate)

- Field names, enum values and endpoint paths in `contracts/schemas.py` /
  `contracts/api_contract.md` are **frozen**. Do not rename or repurpose them in the
  UI layer; maps to local view-models are fine.
- Additive keys exist and are allowed. Known additive items: `/api/context`,
  `/api/health`, `/api/emission-factors/lookup`, `GET /api/ingestion/batches/{id}`,
  `GET /api/reports`, dashboard `production_unit`, `ScenarioSimulationEnvelope`
  wrapper, `X-Request-Id`.
- The live engine emits `HotspotSeverity`/scores that differ from the illustrative
  Phase 0 mock labels; treat mocks as reference shapes, not exact values.
- If a shape must change, log it in `docs/phase2/contract_changes.md` first.

---

## 12. Fresh-build acceptance checklist (functional, not visual)

- [ ] Bootstraps IDs from `/api/context`, falling back to the demo IDs.
- [ ] Sends auth headers / Bearer token and handles 401 vs 403 correctly.
- [ ] Implements `auto` / `mock` / `live` mode with `localStorage` override.
- [ ] Per-group mock fallback in `auto`, with a visible "demo data" indicator.
- [ ] Renders all severity levels (`ERROR/WARNING/INFO/CONFIRMATION_REQUIRED`).
- [ ] Handles 409 (locked/duplicate/overlap), 422 (with issues), 429, 404, 501.
- [ ] Uploads CSV/Excel with dry-run and shows per-row `ImportJob.row_issues`.
- [ ] Shows Scope 1/2/3 + total and keeps on-site/export separate.
- [ ] Shows hotspot rank/contribution/severity/process and the leak-map nodes.
- [ ] Shows recommendations with component scores, `final_score`, `impact`, and explanation.
- [ ] Runs the scenario simulator and distinguishes live (`computedVia`) vs local math.
- [ ] Generates a report (202 → poll) and renders provenance, data-quality, boundary, sections' `status`.
- [ ] Surfaces unresolved factors and data-quality issues rather than hiding them.
- [ ] Coerces the report payload's string numbers and validates shape.
- [ ] Never exposes secrets in the browser; no token in URLs/logs.
- [ ] Passes `npm run build` (tsc + vite) with no type errors.

---

## 13. Reference files

| Topic | File |
|---|---|
| Frozen models/enums | `contracts/schemas.py` |
| Endpoint security notes | `contracts/api_contract.md` |
| Backend app + route mounting | `backend/app/main.py` |
| Auth dependency | `backend/app/security.py` |
| Tenant guards (engine/P4) | `backend/app/guards.py` |
| Settings/defaults | `backend/app/config.py`, `backend/.env.example` |
| Error shape/handlers | `backend/app/errors.py` |
| Ingestion rules/limits | `backend/app/services/ingestion.py` |
| Unit normalization | `backend/app/services/units.py` |
| Module P report payload | `backend/app/services/reports.py` |
| Engine numeric encoding | `engine/serialization.py` |
| Engine/P4 routes | `engine/api.py`, `p4/api.py` |
| Mock payloads | `mocks/`, `frontend/public/mocks/` |
| Current frontend data layer | `frontend/src/lib/api.ts` |
| Phase 2 change log | `docs/phase2/contract_changes.md` |
| Phase 3 readiness/audit | `docs/phase3/` |
