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
