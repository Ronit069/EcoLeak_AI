# EcoLeak AI — Phase 1 Technical Audit

**Audit date:** 2026-09-12
**Scope:** All four Phase 1 workstreams: P1 (Frontend/UX), P2 (Backend Platform & Data Engine), P3 (Carbon Accounting Engine), P4 (Circular Alternative KB + Recommendation Engine)
**Method:** Every claim verified against actual code + executed where possible (P3/P4 tests run, shape validators run, severity reproduction executed). P2 DB tests require live PostgreSQL + `psycopg` (not installed in audit env) — reviewed at code level only.

---

## Verdict summary

- Shape-level contract fidelity is excellent and verifiably enforced (two `ALL SHAPE CHECKS PASSED` runs; mock ⇄ live engine field-for-field match).
- The two **blocking** items: (1) the P2 ⇄ P3 database coupling gap, and (2) N1/N2/J2 endpoints not being served by any live server yet.
- Several severity/unit-semantic drifts are real but fail-soft (explicit unresolved states, no fabricated numbers).

---

## 1. Contract / Interface Consistency Check

**Shared contract exists and is the single source of truth:** `contracts/schemas.py` + `contracts/api_contract.md` + `mocks/*`.

- P2 imports the frozen schemas via `backend/app/contracts_compat.py`; `backend/app/enums.py` re-exports live from `contracts.schemas` ("exactly one definition").
- P3 imports `contracts.schemas` directly (`engine/carbon.py:14-26`).
- P4 imports through a `p4/contracts.py` shim (adds `contracts/` to `sys.path`).
- P1 mirrors in TS/Zod (`frontend/src/lib/contracts.ts`, `zod.ts`).

**One canonical artifact, no silent divergence** — validated live:

| Check | Result | Evidence |
|---|---|---|
| P1 mock ⇆ live P3 hotspot **shape** | ✅ PASS field-for-field | `validate_against_mock.py` → `[PASS] hotspot shape (field-for-field)` |
| P1 mock ⇆ live P4 recommendation **shape** | ✅ PASS (keys identical top-level + per-item) | `p4/demo/run_demo.py` shape check; `RecommendationGenerationResult.model_validate(demo)` OK; `keys(demo)==keys(mock)` at both levels |
| P3 assumes exact P2 schema | ⚠️ PARTIAL | P3 consumes `contracts.schemas` models, not P2 tables — cannot drift on column names. But P3 has **no SQL-backed reader** (§3) and its unit table (`engine/units.py._CONVERSIONS`) **merges m³ and litre into one "volume" dimension**, while P2 Pint keeps `VOLUME_LIQUID` ≠ `VOLUME_GAS` (`backend/app/services/units.py` `_FAMILIES`). Cross-dimension L→kg is blocked in both (pass on the diesel case) |
| P4 consumes P3's hotspot output | ⚠️ PARTIAL (numeric drift) | P4 demo runs on `mocks/mock_hotspot_output.json` as required, but the **live P3 engine does not reproduce mock severity/scores** (below). Ranks match, scores don't |

### Concrete severity drift (executed, not assumed)

```
Mock (frozen):     Boiler CRITICAL 88.5 · Dyeing HIGH 74.2 · Drying HIGH 61.4 · Finishing MODERATE 47.9 · Packaging LOW 28.3
Live P3 engine:    Boiler HIGH 76.36 · Dyeing MODERATE 52.02 · Drying LOW 31.93 · Finishing LOW 26.66 · Packaging LOW 8.71
Contribution %:    IDENTICAL (39.6868 / 26.3870 / 18.8479 / 10.0522 / 5.0261)  ✅
```

`engine/config.py` comments claim thresholds "80/60/40 reproduce the mock's CRITICAL/HIGH/MODERATE/LOW", but a real run shows Boiler 76.36 < 80 → **HIGH, not CRITICAL**. This contradicts the CONTRACTS_README framing of the mock as ground truth: P1's severity badges and P4's confidence inputs will shift when G2 goes live. Not a shape break — a **semantic drift** that must be acknowledged in the swap checklist.

---

## 2. P2 — Database Schema & Ingestion

| Item Checked | Status | Evidence (file/line) | Fix Required |
|---|---|---|---|
| Entity flow Org→Facility→Process→Activity→Calculation→Hotspot→Recommendation→Scenario (+Factor, masters, AuditLog) | ✅ PASS | `models/core.py`, `process.py`, `activity.py`, `calculation.py`, `analytics.py`, `recommendation.py`, `intervention.py`, `scenario.py`, `master.py` (EnergySource, Material, WasteType, IndustryBenchmark), `audit.py` | — |
| CHECK constraints at DB layer (not only Pydantic) | ✅ PASS | `Facility`: `production_nonnegative`, `working_days_range` (≤366), `working_hours_range` (≤24); `organizations.organization_size_valid`; `activity_data` non-negative + `confidence_range`; `scenario.adoption_range`, `budget_nonnegative`, `target_reduction_range`; factor `total_factor_nonnegative` + `source_year_range`; **29 `sa.CheckConstraint`** carried into migration `926d27b15553` | — |
| UNIQUE + FK | ✅ PASS | `UniqueConstraint(organization_id, facility_code)` `uq_org_facility_code`; FKs everywhere; `process_links.no_self_loop`; `uq_activity_source_row` on `(facility, period, source_row_hash)` | — |
| Factor table columns (id/category/item/region/unit/value/source/year/scope/confidence/version) | ✅ PASS | `models/factor.py` — all present, incl. `supplier_specific` override + `factor_code UNIQUE`; versioning deactivates old rows, never updates (`factors.py:150` `old_factor.active = False`) | — |
| 5–10 REAL GHG Protocol/CEA factors seeded (not placeholders) | ✅ PASS | `seed/real_factors.json` = **10 real**: CEA India grid FY24-25 (0.71, v21.0) + FY23-24 (0.727, v20.0); DEFRA 2023 diesel (2.6594 / 2.5121), natural gas (2.0384), LPG (1.5571), petrol (2.09747), UK grid (0.20707); IPCC AR5 R-134a (1430), R-410A (2088) — all with source citation + year | — |
| Alembic migrations for every schema change | ✅ PASS | `alembic/versions/926d27b15553_initial_schema.py`, `80126bccb7c4_add_reports_table.py`; no raw-SQL table edits found | — |
| Ingestion validates via Pandera AND Pydantic | ✅ PASS | `ingestion.py:196-215` `_pandera_schema().validate(frame, lazy=True)`; API DTOs `schemas/requests.py` (StrictRequest `extra="forbid"`) | — |
| Original uploaded values preserved separately from normalized | ✅ PASS | `activity_data` stores both `original_value/original_unit` and `normalized_value/normalized_unit`; ingestion inserts both (`ingestion.py:396-397`); C1 router keeps originals | — |
| No hard-coded factors in source code | ✅ PASS | Factors only in `seed/real_factors.json`; no factor literals in service code | — |
| P2 tests executed in audit env | ⚠️ NOT EXECUTED | `backend/tests/conftest.py` needs live PostgreSQL + `psycopg` (unavailable here). 9 contract-parity + 9 schema-constraint tests present, unverified here | CI with PG service |

**Gap:** P2 has **no F/G/J/K/O/N endpoints** — routers cover A/B/C/D(1-2)/E/I/P only (`main.py:20-27`). Module F/G serving is owned by P3's separate `engine/api.py` wrapper. Fine for Phase 1, but P2's DB is not yet the runtime for calculations.

---

## 3. P3 — Carbon Accounting Engine

| Item Checked | Status | Evidence (file/line) | Fix Required |
|---|---|---|---|
| CO₂e = Activity Data × Emission Factor (Module F) | ✅ PASS | `carbon.py:369`: `co2e = q6(to_decimal(value) * factor.total_co2e_factor)`; fixture reproduced exactly: scope1 224,250 / scope2 340,800 / operational 565,050 | — |
| Scope 1/2/3 segregation | ✅ PASS | `scope_total/scope1/scope2/scope3` + `operational` (S1+S2); scope inherited from factor | — |
| On-site generation vs purchased grid — no double count | ✅ PASS | `_ledger_for()`: "solar/onsite/self-consum/captive/rooftop pv" → `ONSITE`; "export/feed-in/surplus" → `EXPORT`; excluded from `scope_total`. Test `test_onsite_generation_and_export_kept_in_separate_ledgers`: sc2=500 while onsite=1000, export=250 | — |
| Missing factor → explicit `EmissionFactorNotFoundError`, never fabricated/defaulted | ✅ PASS | `EmissionFactorNotFoundError` + `UnresolvedActivity[]{code, reason}`; `select_factor` returns None → unresolved row; `total` excludes fabricated values. Test `test_missing_factor_is_unresolved_not_fabricated` | — |
| Decimal (not float) downstream of money; Pint + ambiguous conversions blocked | ⚠️ PARTIAL | All arithmetic `Decimal` (`q6`, `to_decimal`). But P3 engine uses **hand-rolled `engine/units.py`** (not Pint). Cross-dimension L→kg raises `InvalidUnitError` ✅; however its "volume" dimension **treats m³ == litre** (`1 m3 = 1000 l`) while P2 Pint separates gas vs liquid volume — a silent m³↔L factor-match risk | Align P3 unit table with P2 Pint families (esp. VOLUME_GAS vs VOLUME_LIQUID) |
| Runs standalone without P2 live API | ⚠️ PARTIAL | ✅ runs standalone — against **`mocks/mock_dataset.json`** (`data_source.py` `load_mock_data_source`, zero SQL deps). ❌ "runnable on seed SQL" is **not implemented**: no SQL-backed `ActivityDataSource` exists; P3 never reads P2's seeded DB | Add P2-DB-backed DataSource in Phase 2 |
| Aggregations: facility/process/source/scope/period | ✅ PASS | `by_process`, `by_source`, `by_category`, `scope_total`; `test_aggregations_by_scope_process_source_category` asserts sums == total | — |
| pytest + Hypothesis property-based edge tests | ⚠️ PARTIAL | 74 pytest tests pass standalone (negative/zero/missing-factor/units/onsite-export). **No Hypothesis anywhere** (`@given` grep empty) | Add Hypothesis property tests |
| Live severity reproduces mock | ❌ FAIL (soft) | Boiler 76.36 → HIGH vs mock CRITICAL 88.5 (see §1). Rank order preserved; contribution exact | Recalibrate weights/thresholds or re-label mock as "reference only" |

---

## 4. P4 — Circular Alternative KB (I) + Recommendation Ranking (J)

| Item Checked | Status | Evidence (file/line) | Fix Required |
|---|---|---|---|
| KB captures all Module I fields (industry, process, material applicability, CAPEX, OPEX, CO₂, waste, energy, implementation time, complexity, technical requirements, risk, references) | ✅ PASS | `intervention_library.json` (19 entries): `industry_sector`, `process_category`, `applicable_*`, `min/max_capex`, `opex_impact` + `opex_change_pct`, `expected_co2/energy/waste/water_reduction`, `implementation_months`, `complexity`, `risk_level`, `technical_requirements`, `evidence_source` | — |
| Recycling NOT assumed zero-emission (explicit field/logic) | ⚠️ NEEDS REVIEW | Waste CO₂ savings = `waste_kg × waste_per_kg` (`financial.py:190`) = landfill-avoidance basis (recorded in assumptions). **No field/logic for the recycling process's own emissions** (`ResourceEmissionFactors` has no "recycling process factor" slot) | Add documented `recycling_processing_emission_factor` or explicit statement |
| Ranking formula 0.30/0.25/0.15/0.15/0.10/0.05 exact | ✅ PASS | `scoring.py:WEIGHTS` exact + `weighted_final_score()` rounds to 2dp; ties → CO₂ desc → code | — |
| Hard feasibility filters BEFORE ranking; budget respected | ✅ PASS | `engine.py`: `_pre_candidate_filter` (industry/scale/currency/excluded/locally-unavailable/complexity) → `_process_matches`/`_resource_signal` → hard budget filter (`estimated_capex > budget` → filtered) → then ranking; `strict_budget_filter` flag | — |
| Confidence reduced when input data incomplete | ✅ PASS | `scoring.py:confidence_score` = 0.6·DQ + 0.4·evidence − 10 when `context_available=False` | — |
| Zero upstream runtime dependency | ✅ PASS | `p4/*.py` imports only stdlib + `pydantic` + frozen `contracts/schemas`. Demo reads `mocks/mock_dataset.json` + `mocks/mock_hotspot_output.json`. 19 tests pass standalone | — |

---

## 5. P1 — Dashboard Audit

| Item Checked | Status | Evidence (file/line) | Fix Required |
|---|---|---|---|
| Renders against CURRENT mock JSON | ✅ PASS | Runs; `validate_mocks 9/9`; `tsc` clean; Playwright-verified drill-down + CSV import | — |
| Swap to live API: auth headers, loading/error states | ⚠️ PARTIAL | `api.ts` centralized swap (`USE_MOCKS` → fetch + Zod parse); skeleton loading; error notice. **No auth header wiring** (P2 `auth_mode=stub→jwt`); P1 only calls synchronous G2/J2 (fine — live G1/J1/F1 return 202 job IDs but are not used) | Add auth header layer + 401 handling at swap time |
| KPI cards per Module N (total, intensity, largest hotspot, circularity, reduction, saving) | ⚠️ PARTIAL | 6 gauge cards in `Dashboard.tsx` ✅. **Intensity is a proxy** from `largest_hotspot.carbon_intensity` (not facility N1 value); **circularity = "Unavailable (Module L)"** — honest placeholder | Replace proxies when N1 lives |
| Charts per Module N (Sankey, Pareto, Scope donut, waterfall, MAC) | ⚠️ PARTIAL | Only D3 drill-down + ranked rails + contribution bars. **No Sankey/Pareto/donut/waterfall/MAC.** Spec says keep dashboard action-oriented ("avoid excessive charts") — partial credit | Defer to Phase 2; record in change requests |
| Color is not the only severity indicator | ✅ PASS | `SeverityBadge` = SVG icon + uppercase word; rail line-form (CRITICAL doubled / HIGH solid / MODERATE dashed / LOW dotted) + table fallback | — |
| Hardcoded "clean data" assumptions that break on real data | ⚠️ PARTIAL | Optional chaining handles nulls well; `?? 0` on `contribution_percent` (`Dashboard.tsx:104,126`) renders 0% bars for nulls (cosmetic); local-only status state machine in `RecommendationPlate`; `hotspots[0]` guarded by `empty_state`; **unknown severity defaults to LOW color `#3A7D44`** (`DrillMap.tsx:63`) | Add severity-mapped fallback + null-safe contribution display |
| Scope copy "Scope 1+2 operational" hardcoded | ⚠️ | `Dashboard.tsx` hardcoded; live response carries `scope_boundary[]` | Read from response at swap |

---

## 6. Cross-Cutting Validation Pipeline

Spec order: Frontend Zod → FastAPI boundary → Pydantic → Pandera (file upload) → Pint normalization → business-rule validation → SQLAlchemy transaction → PostgreSQL constraints → Carbon Engine.

| Stage | Status | Evidence |
|---|---|---|
| Frontend Zod | ✅ | `zod.ts` `.strict()` (extra-forbid, mirrors ranges) |
| FastAPI + Pydantic | ✅ | `schemas/requests.py` `StrictRequest(extra="forbid")` + shared enums |
| Pandera on file upload | ✅ | `ingestion.py run_pandera` (lazy, per-row issues) |
| Pint normalization | ✅ (P2) | `services/units.py` — Pint registry, family-aware, ambiguity → `ConfirmationRequiredError` |
| Business-rule validation | ✅ | magnitude ceilings, period mismatch, in-file + DB duplicates, plausibility limits (`ingestion.py`) |
| SQLAlchemy transaction + PG constraints | ✅ | single-transaction insert; constraints in migration |
| Carbon Engine (F) | ⚠️ | Engine runs **only standalone on mocks** (`engine/data_source.py` mock impl); no live call path P2→P3; P1 swap targets (G2/J2/N1) have **no live server endpoint yet** |

**Pipeline implemented per-workstream but not assembled end-to-end.** Every stage exists in at least one place; the missing links are the P2→P3 DB reader and the merged API surface.

---

## 7. Security & Edge-Case Checklist

| Item Checked | Status | Evidence |
|---|---|---|
| Negative / zero / null handling on numeric fields | ✅ | DB CHECKs + Pydantic `ge=0` + engine explicit `NEGATIVE_ACTIVITY` unresolved + tests |
| Enum validation (scope, severity, status, activity type) | ✅ | DB CHECKs (`scope_valid`, `activity_category_valid`, `confidence_level_valid`, `complexity_valid`, `organization_size_valid`) + shared Python enums |
| Duplicate detection in ingestion | ✅ | in-file `DUPLICATE_IN_FILE`; DB `DUPLICATE_ACTIVITY` (3-column match) + `source_row_hash` unique index + file-hash duplicate-import reject |
| Reproducibility via stored factor version | ✅ | `emission_calculations.assumptions` retains `factor_code/version/source/source_year/formula/calculation_version`; factor rows deactivated, never overwritten (E4) |
| Custom exception classes (not raw Exception/HTTPException) | ✅ | `backend/errors.py` `PlatformError` hierarchy (NotFound/Conflict/Duplicate/`InvalidUnitError`/`EmissionFactorNotFoundError`/`PeriodLockedError`/…) + registered handlers → frozen error shape; `engine/errors.py` mirrors. **Minor:** `engine/api.py:102,114` uses raw `HTTPException` in 2 spots |
| No secrets hardcoded; config via pydantic-settings | ⚠️ PARTIAL | `config.py` pydantic-settings + `.env` (gitignored) ✅. **Dev-default `jwt_secret = "dev-only-secret-change-in-production"`** baked into code; `auth_mode="stub"` — acceptable for dev, flag for Phase 2 | Swap in env-only secret + drop default |

---

## 8. Blocking Risk Report (priority order)

### Phase 2 blockers

1. **No live G2/J2/N1/N2 endpoint served by any server.** P2 serves A–E/I/P; P3's wrapper serves F/G/K/L but is standalone; nothing serves P1's swap targets (J2, N1, N2, O/J/P/Q CRUD). P1's "one-file swap" is real, but there is nowhere to point it yet.
2. **P3 has no SQL-backed data source.** The declared "runnable on seed SQL" is actually "runnable on mock JSON". P2's seeded DB and P3's engine are not yet coupled; contract-parity CI (P2) and engine tests (P3) never exercise each other.
3. **Factor-set divergence at swap.** P2 seeds real CEA/DEFRA/IPCC factors; P3/P4 compute on mock factors (`CEA India (mock) v2023.1`, `IPCC 2006 (mock)`). Grid 0.71 matches the new CEA FY24-25 exactly, but natural gas 2.022 vs DEFRA 2.0384 and diesel 2.68 vs 2.6594 will shift totals/severity at integration. Not wrong — but the baseline 565,050 / CRITICAL story will change.

### Silent-correctness risks

4. **P3 unit "volume" dimension merges m³ and L** (engine) while P2 Pint separates liquid/gas volume; combined with `SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK` (`allow_single_candidate_fallback`) in `select_factor`, a lone factor can be silently applied on a weak description match. Gated + recorded in assumptions, but worth a config re-check.
5. **P4 recycling-loop emissions not modeled.** Waste CO₂ savings treat landfill avoidance only; no field for the recycling process's own emissions — conflicts with "recycling is not zero-emission" at the margin.
6. **Hotspot severity drift** vs the frozen mock (Boiler HIGH vs CRITICAL, etc.) — P1/P4 will inherit silently if the swap ships without recalibration.

### Cosmetic / deferrable

7. Sankey/Pareto/donut/waterfall/MAC charts not built; circularity KPI placeholder; raw `HTTPException` in `engine/api.py`; dev jwt secret default; P1 `?? 0` contribution bars; P2 tests require a PG CI service.

---

## Phase 1 Exit Readiness

**Conditional GO.**

Per-workstream quality is high — verified identical JSON shapes (two green shape gates), exact fixture reproduction (565,050), correct Decimal arithmetic, working Pint/Pandera hygiene, honest unresolved-factor states, and exact Module J weights — so the four builds are individually Phase-2-receivable.

The team should **not** start Phase 2 integration until three items close:

1. A single merged FastAPI app (or router contract) that actually serves **G2/J2/N1/N2**.
2. A **P2-DB-backed `ActivityDataSource`** so P3 consumes the seeded schema — which also surfaces the factor-set delta.
3. An explicit decision on **hotspot severity recalibration** vs mock labels, recorded in CONTRACTS_README under the existing Phase 1 change-requests section.

Everything else (P4 recycling-basis note, engine-unit alignment with Pint, Hypothesis property tests, CI-with-PG for P2) is an early-Phase-2 task, not a Phase-1 gate.