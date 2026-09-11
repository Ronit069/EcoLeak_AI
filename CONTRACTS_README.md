# EcoLeak AI — Phase 0 Contract Lock (READ ME FIRST)

This folder contains the frozen Phase 0 contracts for 4-way parallel work.
Nothing here is business logic: it is schema + endpoint definition + stable mock payloads.

| File | What it is |
|---|---|
| `contracts/schemas.py` | Pydantic v2 models mirroring the DB design doc (field names, ranges, enums) |
| `contracts/api_contract.md` | Every REST endpoint for Modules A–Q, with per-endpoint security checks as comments |
| `mocks/mock_dataset.json` | Synthetic textile SME (Shakti Textiles): org, facility, FY25-26 period, 6 processes, 13 activity records, 8 emission factors, 5 circular interventions |
| `mocks/mock_hotspot_output.json` | Module G output envelope (`HotspotDetectionResult`) |
| `mocks/mock_recommendation_output.json` | Module J output envelope (`RecommendationGenerationResult`) |
| `validate_mocks.py` | Loads every mock through its Pydantic model; prints PASS/FAIL |

Run validation: `python validate_mocks.py` (requires `pydantic>=2`).

---

## Phase 1 change requests (P1 Frontend)

Recorded per the freeze rule — **no contract files were modified**; these are open questions for the P2–P4 sync, not silent changes.

1. **Module B `carbon_impact_level` (PROPOSED, additive optional field).** P1 needs a per-process Low/Moderate/High/Critical visual state on the Process Mapper nodes. Phase 0 `Process` has no such field; P1 currently stubs it from the hotspot mock severity where a `process_id` matches and defaults to `Low` otherwise, leaving the field name free for the FROZEN-table change in Phase 2. Request: add `carbon_impact_level` to `Process` (or accept P1 mapping severity → node color). No Zod/Pydantic drift until decided.
2. **Module L circularity score has no mock.** N1 lists `circularity_score`; P3/L1 has no fixture. P1 renders the KPI as "Unavailable (Module L)" instead of inventing a number. Request: a mock `mock_circularity_output.json` or explicit `null` contract so the KPI can light up.
3. **`annual_production` boundary.** Requirements doc says "production > 0" but `Facility.annual_production` is `ge=0` (zero allowed, blocks intensity). P1 follows the Pydantic contract (`>= 0`), treats zero as intensity-blocking, and flags this doc/contract mismatch for confirmation.
4. **N2 leak-map drill-down.** ROLE asks facility → process → activity drill-down. N2 returns flat `nodes[]` + `links[]` (links empty in Phase 1). P1 implements the drill-down client-side from hotspots + `activity_data` (D3) and keeps N2 surface unchanged; if the drill should be API-driven, propose an N2 extension in Phase 2.
5. **C4 client-side import preview.** C4 is `multipart/form-data` → `202 ImportJob`. P1 adds a client-only CSV header/value preview rendering `ValidationIssue[]` shape; the file is never parsed or stored until P2 wires the real endpoint.
6. **Mock hotspot/recommendation outputs are ILLUSTRATIVE references (decided, B3).** The live P3/P4 engines do not reproduce the mock's numeric severity labels — real-factor run pins Boiler `HIGH 76.41` vs mock `CRITICAL 88.5`, Dyeing `MODERATE 51.83` vs `HIGH 74.2`, etc. Rank order and contribution % are preserved; P1 severity badges and P4 confidence inputs will reflect live values after the G2/J2 swap. Pinned by `tests/test_real_factors.py` and `validate_against_mock.py` (shape-only). No threshold change was made; `engine/config.py` comment corrected.
7. **B1 merged API surface.** Single served app (`backend/app/main.py`) now includes P3 engine router (F/G/H/K/L) + P4 router (J1/J2/M1/N1/N2); verified by `tests/test_merged_api.py`. Engine domain errors share the frozen error shape (raw `HTTPException` removed from `engine/api.py`).
8. **B2 SQL-backed engine source.** `engine/sql_source.py` reads P2 tables (same names/columns); enabled via `ECOLEAK_SQL_DSN`, mock remains default/fallback. Verified by `tests/test_sql_source.py` (SQLite image of P2 schema).
9. **Real-factor delta (B3).** With P2's real seed factors (CEA FY24-25 0.71, DEFRA 2023 NG 2.0384/diesel 2.6594/LPG 1.5571/petrol 2.09747, IPCC AR5 R-134a 1430/R-410A 2088): operational emissions = 566,360.8 kgCO₂e (+0.23% vs mock 565,050; grid identical). Scope-3 categories (MATERIAL/WATER/WASTE/TRANSPORT) are explicitly `EMISSION_FACTOR_NOT_FOUND` until Phase 2 seeds scope-3 factors.
10. **Phase-1 completion items (post-audit, all executed):**
    - C1: engine VOLUME_LIQUID ≠ VOLUME_GAS (m³ never silent-converts to L; single-candidate fallback same-dimension only) — `tests/test_unit_dimensions.py`.
    - C2: `ResourceEmissionFactors.recycling_processing_emission_factor` nets recycling-pathway emissions against landfill avoidance (recycling not zero-emission) — `tests/test_recycling_emissions.py`.
    - C3: Hypothesis property tests (negatives always rejected, zero production never divides, missing factor always unresolved, no silent cross-dim conversion) — `tests/test_properties.py`.
    - D1: `api.ts` Bearer auth + 401 handling; Pareto chart; null contribution renders "unavailable"; unknown severity gets a neutral visual state; scope label from response `scope_boundary`. Verified by live-API E2E smoke (`final-smoke-live.png`).
    - D2: `jwt_secret` has no default — `Settings` raises at load when `auth_mode=jwt` without an env secret.
    - D3 (deferred, Phase-2 backlog, owner: P2/Mahima): backend's 18 tests (9 parity + 9 constraint) need live PostgreSQL. Environment has no docker/psql/initdb, and `postgresql.JSONB` cannot compile on SQLite (`CompileError: can't render element of type JSONB`). Run `python -m pytest tests -q` under `backend/` against a PG service (or GH Actions `postgres` service) — tests are written and present.

---

## P1 — Frontend / UX

Build Phase 1 screens against the two mock output files and the field names in `contracts/schemas.py`.
The Dashboard, Carbon Leak Map, recommendation cards, and scenario slider prototype should read
`mocks/mock_hotspot_output.json` (hotspots are pre-ranked; `severity`, `contribution_percent`,
`carbon_intensity`, `hotspot_score`, `process_name`, `activity_category` drive the leak map) and
`mocks/mock_recommendation_output.json` (rank, `final_score`, the six component scores,
`intervention_code`/`intervention_title`, `explanation`, and the nested `impact` object with
CAPEX, annual saving, CO2 saving, payback, and confidence). Mirror the same ranges and enums in
your Zod schemas (`ActivityCategory`, `HotspotSeverity`, `RecommendationStatus`, confidence 0–100,
adoption 0–100, `end_date >= start_date`). In Phase 1 these files are replaced by
`GET .../hotspots` (G2), `GET .../recommendations` (J2), and `GET .../dashboard` (N1) from
`contracts/api_contract.md`; only `rank`, `process_name`, `intervention_code`/`title`, `explanation`,
and `impact` are response-only fields, everything else is a DB field.

## P2 — Backend Platform & Data Engine

Treat `contracts/schemas.py` as the ORM/Pydantic contract: create SQLAlchemy 2.x models and Alembic
migrations with the same table/column names as the DB doc (the table names in the doc are
`organizations`, `facilities`, `reporting_periods`, `processes`, `activity_data`, `emission_factors`,
`emission_calculations`, `emission_hotspots`, `circular_interventions`, `recommendations`,
`scenarios`, `scenario_interventions`, plus `scenario_results`). Seed your local database from
`mocks/mock_dataset.json`; every `id` there is a reusable UUID so the other teams' mocks resolve.
Implement the endpoints in `contracts/api_contract.md` and honor the comment block on each endpoint
(auth, tenant ownership, payload schema, business validation, rate limit, audit, safe errors) —
none of it is implemented in Phase 0. In Phase 1, mock files stop being the source of truth and the
DB/API becomes it; the JSON shapes must not change.

## P3 — Carbon Accounting & Simulation Engine

Build the calculation, hotspot, and simulator services against `EmissionFactor`, `ActivityData`,
`EmissionCalculation`, `EmissionHotspot`, `Scenario`, `ScenarioIntervention`, and `ImpactAssessment`
in `contracts/schemas.py`. Use `mocks/mock_dataset.json` as your deterministic fixture: 13 activity
records with `original_value`/`original_unit` and `normalized_value`/`normalized_unit` (kg/tonne and
m3 exercises the Pint path; the diesel record is the litre case), 8 versioned factors with
`scope`, `source_year`, and `version`. Expected fixture totals (Scope 1+2 operational):
grid electricity 340,800 kgCO2e, natural gas 192,090 kgCO2e, diesel 32,160 kgCO2e, total
565,050 kgCO2e — this is exactly the baseline in `mocks/mock_hotspot_output.json`, so a correct
engine reproduces that file. Formula: `CO2e = normalized_value x total_co2e_factor`; hotspot
`contribution = emissions / total x 100`; simulator `payback = CAPEX / annual_saving` (null when
saving <= 0). In Phase 1 the real engine output replaces the mock hotspot/impact JSON, but the
`HotspotDetectionResult`/`ImpactAssessment` shapes stay frozen.

## P4 — AI Recommendation & Explainability

Build ranking, applicability filtering, and explanation generation against `CircularIntervention`,
`Recommendation`, `RecommendationAssessment`, and the two output DTOs
(`HotspotDetectionResult`, `RecommendationGenerationResult`) in `contracts/schemas.py`. Use
`mocks/mock_hotspot_output.json` (5 ranked hotspots) and `mocks/mock_recommendation_output.json`
(5 ranked recommendations) as the ground-truth shape; each recommendation's `final_score` is the
weighted sum from the requirements doc (`0.30 carbon + 0.25 financial + 0.15 feasibility +
0.15 circularity + 0.10 speed + 0.05 confidence`). The intervention fixtures in
`mocks/mock_dataset.json` provide CAPEX ranges, CO2/energy/waste reduction ranges, complexity, and
risk for hard feasibility filters. The `explanation` field is yours to generate (Module M), but it
must reference stored evidence and confidence, never fabricate numbers. In Phase 1 this is called by
`POST .../recommendations/generate` (J1) and `GET /recommendations/{id}/explanation` (M1).

---

## FROZEN UNTIL PHASE 2

**Schema field names, enum values, endpoint paths, and mock JSON shapes must not change once
Phase 1 starts without a full team sync (all P1–P4) and a versioned update to
`contracts/schemas.py` + `contracts/api_contract.md`.** Additive changes (new optional field) also
require a sync because P1's Zod schemas and P2's migrations depend on the exact shape. If a change
is unavoidable, bump a `contract_version` and update the mocks and validator in the same change.
