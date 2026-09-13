# EcoLeak AI — REST API Contract (Phase 0)

**Status:** Frozen for Phase 1. Field names come from `contracts/schemas.py`, which mirrors
`Industrial_Emission_Database_Security_Edge_Cases.md` (single source of truth).
**Base path:** `/api` (matches the example in DB doc §24). No auth is implemented in Phase 0.
**All request/response bodies are JSON** unless noted (`multipart/form-data` for imports).

## Security checklist applied to EVERY endpoint (DB doc §24)

Each endpoint below carries this comment in the "Security" row; it is a Phase 1 implementation
requirement, not implemented now:

```
1. Authentication          5. Business validation
2. Authorization           6. Rate limit
3. Tenant ownership        7. Audit requirement
4. Payload schema          8. Safe error response
```

Error shape (DB doc §28 / Library doc §28):

```json
{
  "error_code": "EMISSION_FACTOR_NOT_FOUND",
  "message": "No compatible emission factor is available.",
  "severity": "WARNING",
  "details": {}
}
```

Validation issues (DB doc §23) use `ValidationIssue` with severity
`ERROR | WARNING | INFO | CONFIRMATION_REQUIRED`.

---

## Module A — SME / Factory Profiling

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| A1 | `POST /api/organizations` | `Organization` (without `id`, timestamps) | `201 Organization` | AuthN, AuthZ, payload schema, business validation, rate limit, audit, safe errors |
| A2 | `GET /api/organizations/{organization_id}` | — | `Organization` | AuthN, tenant ownership, safe errors |
| A3 | `PATCH /api/organizations/{organization_id}` | Partial `Organization` | `Organization` | AuthN, AuthZ, tenant ownership, payload schema, business validation, audit, safe errors |
| A4 | `POST /api/facilities` | `Facility` (without `id`, timestamps) | `201 Facility` | AuthN, AuthZ, tenant ownership, payload schema, business validation (`working_days_per_year <= 366`, `working_hours_per_day <= 24`, `annual_production >= 0`), rate limit, audit, safe errors |
| A5 | `GET /api/organizations/{organization_id}/facilities` | — | `Facility[]` | AuthN, tenant ownership, safe errors |
| A6 | `GET /api/facilities/{facility_id}` | — | `Facility` | AuthN, tenant ownership, safe errors |
| A7 | `PATCH /api/facilities/{facility_id}` | Partial `Facility` | `Facility` | AuthN, AuthZ, tenant ownership, payload schema, business validation, audit, safe errors |
| A8 | `POST /api/facilities/{facility_id}/reporting-periods` | `ReportingPeriod` (without `id`, timestamps) | `201 ReportingPeriod` | AuthN, AuthZ, tenant ownership, payload schema, `end_date >= start_date`, audit, safe errors |
| A9 | `GET /api/facilities/{facility_id}/reporting-periods` | — | `ReportingPeriod[]` | AuthN, tenant ownership, safe errors |

Business rule (edge cases A): production `= 0` is allowed on the profile but blocks intensity
calculations later; negative production, working days `> 366`, hours `> 24` are rejected.

---

## Module B — Industrial Process Mapper

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| B1 | `POST /api/facilities/{facility_id}/processes` | `Process` (without `id`, `created_at`) | `201 Process` | AuthN, AuthZ, tenant ownership, payload schema, `sequence_no > 0`, duplicate-name/code business rule, audit, safe errors |
| B2 | `GET /api/facilities/{facility_id}/processes` | — | `Process[]` | AuthN, tenant ownership, safe errors |
| B3 | `GET /api/processes/{process_id}` | — | `Process` | AuthN, tenant ownership, safe errors |
| B4 | `PATCH /api/processes/{process_id}` | Partial `Process` | `Process` | AuthN, AuthZ, tenant ownership, payload schema, business validation, audit, safe errors |
| B5 | `DELETE /api/processes/{process_id}` | — | `204` (soft delete only if calculations exist) | AuthN, AuthZ, tenant ownership, soft-delete business rule, audit, safe errors |

Process links (Sankey / carbon graph) belong to Phase 2 (DB doc §3.2); the `process_links`
table prevents self-loops with `source_process_id <> target_process_id`.

---

## Modules C/D — Data Input, Unit Normalization & Data Quality

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| C1 | `POST /api/facilities/{facility_id}/activity` | `ActivityData` (without `id`, `created_at`) | `201 ActivityData` | AuthN, AuthZ, tenant ownership, payload schema, non-negative values, unit allow-list, period editable/not locked, duplicate detection, audit, safe errors |
| C2 | `PUT /api/facilities/{facility_id}/activity/{activity_id}` | `ActivityData` (full) | `ActivityData` | AuthN, AuthZ, tenant ownership, facility/activity ownership, payload schema, period editable, unit/value valid, audit, safe errors |
| C3 | `GET /api/facilities/{facility_id}/activity` | Query: `reporting_period_id`, `process_id`, `activity_category` | `ActivityData[]` | AuthN, tenant ownership, safe errors |
| C4 | `POST /api/facilities/{facility_id}/activity/import` | `multipart/form-data`: `file` (.csv/.xlsx), `reporting_period_id`, sheet name (optional) | `202 ImportJob { import_id, status, row_issues: ValidationIssue[] }` | AuthN, AuthZ, tenant ownership, file size/type allow-list, MIME check, CSV header validation (Pandera), duplicate import hash, rate limit, audit, safe errors |
| D1 | `POST /api/units/normalize` | `{ value, from_unit, to_unit }` | `{ original_value, original_unit, normalized_value, normalized_unit, conversion_factor, conversion_source }` | AuthN, unit allow-list (Pint), ambiguous conversion business rule, safe errors |
| D2 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/data-quality` | — | `{ completeness_score, source_quality_score, factor_quality_score, temporal_quality_score, unit_quality_score, total_score, issues: ValidationIssue[] }` | AuthN, tenant ownership, safe errors |

Import rules (edge cases C/D): reject empty/corrupt/password-protected files, flag mixed units,
flag kg-vs-tonne magnitude anomalies, and mark OCR-derived values `ESTIMATED` with lower
`confidence_score`.

---

## Module E — Emission Factor Knowledge Base

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| E1 | `GET /api/emission-factors` | Query: `category`, `subcategory`, `region_country`, `region_state`, `scope`, `active`, `source_year` | `EmissionFactor[]` | AuthN, payload schema, safe errors |
| E2 | `GET /api/emission-factors/{factor_id}` | — | `EmissionFactor` | AuthN, safe errors |
| E3 | `POST /api/emission-factors` | `EmissionFactor` (admin only) | `201 EmissionFactor` | AuthN, AuthZ (admin role), payload schema, `total_co2e_factor >= 0`, version uniqueness, factor-change audit, rate limit, safe errors |
| E4 | `POST /api/emission-factors/{factor_id}/new-version` | New factor body | `201 EmissionFactor` (old version set `active=false`, never overwritten) | AuthN, AuthZ (admin role), versioning business rule, audit, safe errors |

Versioning rule (DB doc §6.1): historical calculations keep pointing at the original factor;
old rows are deactivated, never updated or deleted.

---

## Module F — Carbon Accounting Engine

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| F1 | `POST /api/facilities/{facility_id}/reporting-periods/{period_id}/calculations` | `{ activity_ids?: UUID[], calculation_version: str }` (omit to calculate all) | `202 EmissionCalculation[]` | AuthN, AuthZ, tenant ownership, period not LOCKED/CLOSED unless versioned, missing-factor handling, duplicate calculation prevention, business validation, audit, safe errors — **Phase 3:** LOCKED/CLOSED now enforced live: `409 PERIOD_LOCKED` (frozen shape) |
| F2 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/calculations` | — | `EmissionCalculation[]` (each keeps factor id/version/source) — **Phase 3:** served on the merged router; calculations are derived deterministically on demand (identical payload to F1) rather than read from a persisted job list | AuthN, tenant ownership, safe errors |
| F3 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/inventory-summary` | — | `{ scope1_kgco2e, scope2_kgco2e, scope3_kgco2e, total_kgco2e, carbon_intensity, production_unit, generated_at }` | AuthN, tenant ownership, safe errors |

Formula (DB doc §7.1): `CO2e = normalized_activity_value × emission_factor`. Negative activity is
rejected; missing factor produces an explicit "incomplete" state, never a fabricated value.

---

## Module G — Emission Leak-Point / Hotspot Detector

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| G1 | `POST /api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots/detect` | `{ scope_boundary?: Scope[], weights?: object }` | `202 HotspotDetectionResult` (see `mocks/mock_hotspot_output.json`) | AuthN, AuthZ, tenant ownership, payload schema, business validation (total emissions > 0 for percentages), audit, safe errors |
| G2 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots` | — | `HotspotDetectionResult` | AuthN, tenant ownership, safe errors |

`HotspotDetectionResult` is an API envelope: `facility_id`, `reporting_period_id`, `generated_at`,
`scope_boundary`, `total_emissions_kgco2e`, `data_quality_score`, and `hotspots[]`, where each
item is an `EmissionHotspot` plus `rank`, `process_name`, `activity_category`.
Hotspot score (Req doc §20): `w1(Carbon Contribution) + w2(Carbon Intensity) + w3(Inefficiency)
+ w4(Waste Ratio) + w5(Improvement Potential)`; severity `LOW | MODERATE | HIGH | CRITICAL`.

---

## Module H — Anomaly & Inefficiency Detector

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| H1 | `POST /api/facilities/{facility_id}/anomalies/detect` | `{ process_id?: UUID, reporting_period_id: UUID, model_version?: str }` | `{ anomalies: [{ id, process_id, activity_data_id, model_name, model_version, anomaly_score, threshold, is_anomaly, explanation, confidence_score, detected_at }] }` | AuthN, AuthZ, tenant ownership, payload schema, "insufficient history" business rule, audit, safe errors |
| H2 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/anomalies` | — | `AnomalyResult[]` | AuthN, tenant ownership, safe errors |
| H3 | `PATCH /api/anomalies/{anomaly_id}/acknowledge` | `{ acknowledged: true, note?: str }` | `200 {note, acknowledged_at, facility_id, reporting_period_id}` | AuthN, AuthZ, tenant ownership (resolved BEFORE any write), audit, safe errors |

ML only (IsolationForest); with too little history the engine must return rules-only results
without an ML certainty claim.

---

## Module I — Circular Alternative Knowledge Base

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| I1 | `GET /api/interventions` | Query: `industry_sector`, `process_category`, `complexity`, `active` | `CircularIntervention[]` | AuthN, payload schema, safe errors |
| I2 | `GET /api/interventions/{intervention_id}` | — | `CircularIntervention` | AuthN, safe errors |
| I3 | `POST /api/interventions` | `CircularIntervention` (admin only) | `201 CircularIntervention` | AuthN, AuthZ (admin role), payload schema, range validators, audit, safe errors |

Applicability mapping (`intervention_applicability`) is Phase 2 (DB doc §11.2); hard feasibility
filters run before ranking (Module J).

---

## Modules J/M — Recommendation Engine & Explainability

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| J1 | `POST /api/facilities/{facility_id}/reporting-periods/{period_id}/recommendations/generate` | `{ hotspot_ids?: UUID[], budget_limit?: Decimal, constraints?: object }` | `202 RecommendationGenerationResult` (see `mocks/mock_recommendation_output.json`) | AuthN, AuthZ, tenant ownership, payload schema, business validation (budget >= 0, known hotspots/interventions only), rate limit (LLM quota), audit, safe errors |
| J2 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/recommendations` | Query: `status`, `rank_max` | `RecommendationGenerationResult` | AuthN, tenant ownership, safe errors |
| J3 | `PATCH /api/recommendations/{recommendation_id}` | `{ status: RecommendationStatus }` | `Recommendation` — **Phase 3:** served on the merged router with an in-memory status store + transition rule (invalid status 422, invalid transition 409, unknown id 404, frozen shape). SQLAlchemy persistence is Phase-3 backlog | AuthN, AuthZ, tenant ownership, payload schema, status transition rule, audit, safe errors |
| M1 | `GET /api/recommendations/{recommendation_id}/explanation` | — | `{ recommendation_id, summary, evidence: object, assumptions: object, confidence_score, generated_by }` | AuthN, tenant ownership, safe errors (LLM narrative labeled separately from deterministic values) |

Ranking formula (Req doc §20): `0.30 Carbon Saving + 0.25 Financial Return + 0.15 Feasibility
+ 0.15 Circularity + 0.10 Implementation Speed + 0.05 Confidence`.
LLM may explain only; it must never invent factors, CO2e, CAPEX, savings, payback, or
compliance claims.

**Phase 3 note (F-8):** every J1/J2/M1 recommendation carries a machine-readable
degraded-mode label at `impact.assumptions.data_is_stub` (bool). It is `true`
while the P4 demo tariff fixture supplies resource baselines/tariffs; it flips
to `false` automatically when a real `FacilityContext` is wired in. Additive key
inside the free-form `assumptions` object only — no envelope key changed.

---

## Modules K/L/O — Impact Simulator, Circularity, What-If

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| O1 | `POST /api/facilities/{facility_id}/scenarios` | `Scenario` (without `id`, `created_at`) | `201 Scenario` | AuthN, AuthZ, tenant ownership, payload schema, `budget_limit >= 0`, `target_reduction_pct 0..100`, audit, safe errors |
| O2 | `GET /api/facilities/{facility_id}/scenarios` | — | `Scenario[]` | AuthN, tenant ownership, safe errors |
| O3 | `GET /api/scenarios/{scenario_id}` | — | `Scenario` + included `ScenarioIntervention[]` | AuthN, tenant ownership, safe errors |
| O4 | `PATCH /api/scenarios/{scenario_id}` | Partial `Scenario` | `Scenario` | AuthN, AuthZ, tenant ownership, payload schema, business validation, audit, safe errors |
| O5 | `DELETE /api/scenarios/{scenario_id}` | — | `204` | AuthN, AuthZ, tenant ownership, soft delete, audit, safe errors |
| O6 | `POST /api/scenarios/{scenario_id}/interventions` | `ScenarioIntervention` (`adoption_percentage 0..100`) | `201 ScenarioIntervention` | AuthN, AuthZ, tenant ownership, payload schema, duplicate/incompatible-intervention rule, audit, safe errors |
| O7 | `DELETE /api/scenarios/{scenario_id}/interventions/{scenario_intervention_id}` | — | `204` | AuthN, AuthZ, tenant ownership, audit, safe errors |
| K1 | `POST /api/scenarios/{scenario_id}/simulate` | `{ recalculation_version?: str }` (body also accepts `facility_id`, `reporting_period_id`, `interventions[]`, `budget_limit` for direct calls) | `ScenarioSimulationEnvelope { scenario_id, assessment: ImpactAssessment, interventions[], payback_status, payback_reason, over_budget, issues[] }` (HTTP 200, synchronous in Phase 2) — **Phase-2 canonical decision:** the wrapper envelope is the served shape (addendum in `contracts/schemas.py` + `docs/phase2/contract_changes.md`); the 202-async semantics remain reserved for job-based endpoints (F1/G1/J1) | AuthN, AuthZ, tenant ownership, payload schema, interaction/double-counting validation, audit, safe errors |
| K2 | `GET /api/scenarios/{scenario_id}/impact` | — | `ImpactAssessment` | AuthN, tenant ownership, safe errors |
| K3 | `GET /api/scenarios/compare?scenario_ids=id1,id2` | Query: `baseline_scenario_id?` | `{ comparisons: ImpactAssessment[] , deltas: object }` | AuthN, tenant ownership (all scenarios), safe errors |
| L1 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/circularity-score` | — | `{ recycled_input_score, waste_recovery_score, energy_recovery_score, water_reuse_score, reuse_score, total_score (0..100), methodology_version, calculated_at }` | AuthN, tenant ownership, incomplete-score business rule, safe errors |

Simulator rules (Module K): `payback = CAPEX / annual_saving` is null when `annual_saving <= 0`;
`projected_emissions_kg` is floored at 0; `total_co2_saving_kg` may be negative (report as
additional emissions); adoption `> 100` rejected.
Circularity rule (Module L): score outside `0..100` is rejected/capped.

---

## Modules N/P/Q — Dashboard, Reports, Feedback

| # | Endpoint | Request | Response | Security |
|---|---|---|---|---|
| N1 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/dashboard` | — | `{ total_kgco2e, scope_breakdown, carbon_intensity, production_unit?, largest_hotspot, circularity_score, potential_reduction_kgco2e, potential_annual_saving, last_calculated_at, empty_state?: bool, unresolved_count? }` — **Phase 2 addendum:** `production_unit` formally added; **Phase 3 addendum:** `unresolved_count` (additive, ≥0) counts activity rows with no matching emission factor so the UI can flag that totals exclude them | AuthN, tenant ownership, safe errors |
| N2 | `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/leak-map` | — | `{ nodes: [{ process_id, process_name, emissions_kgco2e, contribution_percent, severity }], links: [] }` | AuthN, tenant ownership, safe errors (color is not the only severity indicator) |
| P1 | `POST /api/facilities/{facility_id}/reporting-periods/{period_id}/reports` | `{ template_version: str, include_scope3?: bool }` | `202 Report { report_id, status, version, generated_at, report_hash }` | AuthN, AuthZ, tenant ownership, payload schema, block while calculations incomplete, versioning rule, report-generation throttling, audit, safe errors |
| P2 | `GET /api/reports/{report_id}` | — | Full report payload (profile, boundary, factor provenance, Scope 1/2/3, hotspots, circularity, recommendations, financials, roadmap, assumptions, data-quality score) | AuthN, tenant ownership, confidentiality access control, safe errors |
| P3 | `GET /api/reports/{report_id}/export` | Query: `format=pdf` (Phase 2) | `application/pdf` or `501` in Phase 1 | AuthN, AuthZ, tenant ownership, rate limit, safe errors |
| Q1 | `POST /api/recommendations/{recommendation_id}/feedback` | `RecommendationFeedback` (`feedback_type`, `reason`, `actual_*`) | `201 RecommendationFeedback` | AuthN, AuthZ, tenant ownership, payload schema, spam/rate-limit validation, physical-plausibility flag, audit, safe errors |
| Q2 | `GET /api/recommendations/{recommendation_id}/feedback` | — | `RecommendationFeedback[]` (latest state + history) | AuthN, tenant ownership, safe errors |


> **Phase 3 final-gap addendum (Module O — now served by `p4/o_routes.py`):**
> `POST /api/facilities/{id}/scenarios` (O1, 201 `Scenario`) · `GET /api/facilities/{id}/scenarios` (O2, `{scenarios: Scenario[]}`) ·
> `GET /api/scenarios/{id}` (O3, `{scenario, scenario_interventions[]}`) · `PATCH /api/scenarios/{id}` (O4) ·
> `DELETE /api/scenarios/{id}` (O5, 204 soft) · `POST /api/scenarios/{id}/interventions` (O6, 201 `ScenarioIntervention`; duplicate + adoption 0..100 guards) ·
> `DELETE /api/scenarios/{id}/interventions/{sid}` (O7, 204) ·
> `POST /api/scenarios/{id}/clone` (201, independent copy) · `POST /api/scenarios/{id}/restore` (reverts to creation-time baseline) ·
> `GET /api/scenarios/compare?scenario_ids=a,b` (K3: `{comparisons: [], deltas: {}}` over the K1 engine; at least 2 ids).
> All routes AuthN + tenant ownership (facility -> organization, resolved before any write); store is session-scoped,
> persistence Phase-4 backlog (owner P2). Scenario shapes are the frozen `Scenario` / `ScenarioIntervention` models.

---

## Cross-cutting rules

- **Tenant isolation:** every path containing a `facility_id`, `process_id`, `activity_id`,
  `scenario_id`, `recommendation_id`, or `report_id` must be resolved to its `organization_id`
  and checked against the caller's organization (DB doc §19 rule 10, §24).
- **Reporting period lock:** mutations on activity/scenarios/calculations must verify the period
  is not `LOCKED`/`CLOSED` without an explicit unlock audit event.
- **Auditability:** factor change, calculation rerun, activity edit, recommendation override,
  scenario creation, report generation, and file import all write `audit_logs`.
- **HTTP status codes:** `201` create, `202` accepted async job, `204` delete, `400/422`
  validation, `401/403` auth, `404` not found, `409` conflict/duplicate, `429` rate limited,
  `5xx` generic error only — never stack traces.

> **Phase 3 final-gap addendum (H2):** `GET /api/facilities/{facility_id}/reporting-periods/{period_id}/anomalies` returns the latest stored detection with per-anomaly `acknowledged` / `acknowledged_note` / `acknowledged_at` merged (session-scoped registry; persistence is Phase-4 backlog, owner P3).
