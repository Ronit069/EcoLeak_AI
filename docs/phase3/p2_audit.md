# P2 Phase 3 Audit — Backend Platform & Data Engine

**Owner:** P2
**Branch:** `phase3-p2-audit` (based on `main` @ `a0dfd01`)
**Audited revision:** `main` @ `a0dfd01` (Phase 1 + Phase 2 + remediation merged)
**Reference doc:** `Industrial_Emission_Database_Security_Edge_Cases.md`
**Step 0 (must read first):** `docs/phase3/p2_audit_fasttrack.md` — P4-C1/P4-H2 verdict.
**Method:** live PostgreSQL (`ecoleak` / `ecoleak_test`) schema introspection + executed
API/service probes; full suites re-run. No production code changed in this pass
(fixes are a follow-up pass, per the phase rules).

> **Upstream / cross-check note.** P3 has already posted a *provisional* audit at
> `docs/phase3/p3_audit.md` (it started before P2 posted, as permitted, and is
> marked "pending upstream P2 audit"). Prior audits exist at repo root
> (`PHASE1_AUDIT.md`, `PHASE2_AUDIT.md`); `/docs/audit/` still does not exist
> (recorded process drift). Findings already logged there are cross-checked in
> §4, not re-litigated.

---

## 1. Checklist results (one row per required item)

| # | Checklist item | Result | Evidence | Severity of fail |
|---|---|---|---|---|
| 1 | Schema constraints enforced in the **live** Phase 2 schema (not just the migration) | **PASS** | `pg_constraint`/`pg_indexes` on `ecoleak`: **29** domain CHECKs, **4** UNIQUE, **43** FKs, all **7** doc indexes (`idx_activity_facility_period`, `idx_activity_process`, `idx_emission_factor_lookup`, `idx_emission_calc_activity`, `idx_hotspot_facility_period`, `idx_recommendation_facility`, `idx_audit_entity`). Every doc constraint present incl. `factories`: working_days 0–366, hours 0–24, production ≥ 0, `(organization_id, facility_code)` UNIQUE; `reporting_periods.end_date >= start_date`; `process_links.source <> target`; `activity_data` category/source/measured enums + non-negativity + confidence/DQ 0–100; `emission_factors` scope/confidence/source_year/valid-dates + factor_code UNIQUE. Enforced by `tests/test_schema_constraints.py` (9 tests). Nothing loosened in integration. | — |
| 2 | Validation severities correct under **real ingested data volume** | **PASS** | 450-row messy import (`tools`-equivalent, scale=50): accepted **200**, rejected **250**, warnings **50**; severities `INFO 100 / ERROR 250 / WARNING 50`; codes `UNIT_CONVERTED 100, NEGATIVE_VALUE 50, MISSING_VALUE 50, INVALID_UNIT 50, DUPLICATE_IN_FILE 50, PERIOD_MISMATCH 50, IMPLAUSIBLE_MAGNITUDE 50` — exactly the deterministic expectation. `CONFIRMATION_REQUIRED` verified on `POST /api/units/normalize` (5×). Original 108-row run also PASS. | — |
| 3 | Audit-log completeness with **correct before/after** | **PARTIAL** | Sampled live transactions: `ACTIVITY_CREATED` (old=null, new=full), `ACTIVITY_UPDATED` (**old=full, new=full**), `EMISSION_FACTOR_CREATED` (old=null, new=partial `{factor_code,version}`), `EMISSION_FACTOR_VERSIONED` (old=partial `{factor_code,active:false}`, new=partial). Import path writes `FILE_IMPORT` + one `ACTIVITY_IMPORTED` per accepted row (48/48). Every write has a row with correct `organization_id`/`entity_id`. Gap: factor change entries are not full snapshots. | **MEDIUM** |
| 4 | Every live emission factor has **source, version, year** | **PASS** (LOW note) | `emission_factors`: 18 rows, **0** missing `source_name`, **0** missing `version`, **0** missing `source_year`. 8 rows (the mock fixtures) have NULL `source_url` — provenance trio complete, so not CRITICAL. | **LOW** |
| 5 | Double-counting: on-site generation vs purchased grid **under real data** | **PASS** | Live ingested grid 1000 kWh + rooftop-solar self-consumption 400 kWh + export 200 kWh (factor 0.5): `scope2=500`, `onsite=200`, `export=100`, `total == scope1+scope2` → True; separate ledgers, excluded from totals. `tests/test_double_counting.py` also passes. | — |
| 6 | 8-point API security on **every live endpoint** | **PARTIAL / FAIL** | Writes: 403 unauth (activity, factor, org, report); tenant isolation 403; payload 422; locked/dup/overlap 409; frozen error shape; audit on writes. **FAIL:** `GET /api/emission-factors`, `GET /api/emission-factors/{id}`, `GET /api/interventions` return **200 with no credentials**; `GET /api/ingestion/batches/{id}` and `GET /api/reports/{id}` return **404 (auth not challenged first)**. (Engine/P4 read routes also unauth — P3/P4 owners.) | **HIGH** |
| 7 | Reporting-period integrity under real entry patterns | **PASS** | `end<start` → 422; malformed date → 422; overlapping period → 409 `CONFLICT`; write to `LOCKED` period → 409 `PERIOD_LOCKED`; DB `end_date >= start_date` CHECK live. | — |

Suites re-run: backend `pytest` **54 passed**; root `pytest tests` **164 passed**;
`ruff` clean; `validate_mocks.py` **9/9**.

---

## 2. Detailed findings (fails / partials)

### P2-01 — HIGH — Unauthenticated read access to global KB endpoints
- **Location:** `backend/app/routers/factors.py` (`GET /api/emission-factors`, `GET /api/emission-factors/{factor_id}`), `backend/app/routers/interventions.py` (`GET /api/interventions`).
- **What's wrong:** With no `X-Organization-Id`/`Authorization`, all three return **200**. The stub principal resolves to an anonymous caller and these handlers never assert credentials (they are not tenant-scoped, so no ownership check fires either).
- **What the doc says:** DB doc §24 / `api_contract.md` require point **1. Authentication** on every endpoint (E1/E2/I1 are explicitly marked AuthN). Uploaded-factor KB and intervention library are currently world-readable.
- **Suggested fix:** require an authenticated principal on these routers (401 when absent), or add a documented "public reference data" exception to the contract if intentional; factor/version writes are already admin-gated.

### P2-02 — MEDIUM — Authentication is not evaluated before existence/ownership on some reads
- **Location:** `backend/app/routers/activity.py` (`GET /api/ingestion/batches/{import_id}`), `backend/app/routers/reports.py` (`GET /api/reports/{report_id}`, `/export`, list) — returns **404** rather than 401/403 for anonymous callers; same pattern on P3/P4 read routes.
- **What's wrong:** The contract's 8-point order is auth → authz → tenant. A 404 leak is benign here (no data exposure), but the auth check is skipped when the row is absent, and anonymous callers can probe for existence timing.
- **What the doc says:** §24 "Every API endpoint should verify: 1. Authentication … 3. Tenant ownership".
- **Suggested fix:** apply the authentication dependency at the router/route level (runs before the DB lookup) so unauthenticated requests always get 401.

### P2-03 — MEDIUM — Emission-factor audit entries are not full before/after snapshots
- **Location:** `backend/app/routers/factors.py` (`create_factor`, `create_new_version`).
- **What's wrong:** `EMISSION_FACTOR_CREATED.new_value = {factor_code, version}` and `EMISSION_FACTOR_VERSIONED.old_value = {factor_code, active:false}`, `new_value = {factor_code, version}`. The prior factor's value/source/unit/scope and the new full row are not captured, so a factor change cannot be reconstructed from `audit_logs` alone.
- **What the doc says:** §17 `audit_logs` has `old_value`/`new_value` JSONB for exactly this; §6.1/§7.1 require historical calculations remain reproducible after factor updates; problem goal "every number auditable/reproducible". (Activity updates already store full old/new.)
- **Suggested fix:** store the full serialized factor row in `new_value` and the full superseded row in `old_value` on create/version (redact nothing sensitive here).

### P2-04 — LOW — 8 emission factors have NULL `source_url`
- **Location:** `backend/app/seed/real_factors.json` / mock fixtures → `emission_factors.source_url` NULL for 8 rows.
- **What's wrong:** Provenance trio (source/version/year) is complete (hence not CRITICAL), but 8 factors — the Phase-1 `(mock)` fixtures — carry no URL, weakening independent verification. The 10 real CEA/DEFRA/IPCC factors do carry URLs.
- **What the doc says:** §6.1 `source_url` is nullable but source/version/year are mandatory; problem goal "auditable".
- **Suggested fix:** populate URLs for fixture factors or mark them `source_name … (mock)` consistently and exclude them from compliance-facing provenance.

### P2-05 — MEDIUM (cross-ref P3-07) — No persisted calculations/hotspots, no `CALCULATION_RERUN` audit
- **Location:** `engine/` is stateless; P2 owns tables `emission_calculations`, `emission_hotspots`, `audit_logs` (all present, empty).
- **What's wrong:** F/G recompute on every call; nothing is written to the calculation/hotspot tables and no `CALCULATION_RERUN` audit event exists, so reproduction relies on unchanged inputs.
- **What the doc says:** §7.1 must preserve activity value/factor id/version/formula/assumptions/timestamp; §17 lists "calculation rerun" as a required audit event.
- **Owner:** P3 (primary) + P2 (tables). **Already logged as P3-07 — recorded here for completeness, not re-litigated.**

### P2-06 — HIGH (cross-ref P3-05) — Period lock enforced at P2 but not on F1 calculations
- **Location:** P2 activity/scenario writes enforce `LOCKED/CLOSED` → 409 `PERIOD_LOCKED` (verified). P3's `POST …/calculations` does not read `ReportingPeriod.status`.
- **What the doc says:** `api_contract.md` F1: "period not LOCKED/CLOSED unless versioned"; DB doc integrity rule #2.
- **Owner:** P3. P2 side verified correct; no P2 defect.

---

## 3. Per-endpoint 8-point matrix (P2-owned surface)

| Endpoint group | 1 AuthN | 2 AuthZ | 3 Tenant | 4 Payload | 5 Business | 6 Rate | 7 Audit | 8 Safe err |
|---|---|---|---|---|---|---|---|---|
| A organizations/facilities/periods | ✅ | ✅ admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B processes | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (soft-delete) | ✅ |
| C/D activity + import | ✅ | ✅ | ✅ | ✅ | ✅ (lock/dup) | ✅ upload | ✅ | ✅ |
| D units normalize | ✅ | ✅ | n/a | ✅ | ✅ (ambiguity) | ✅ | n/a (read) | ✅ |
| E factors read | ❌ **P2-01** | n/a | n/a | ✅ | n/a | ✅ | n/a | ✅ |
| E factors write | ✅ | ✅ admin | ✅ | ✅ | ✅ | ✅ | ⚠️ partial (P2-03) | ✅ |
| I interventions read | ❌ **P2-01** | n/a | n/a | ✅ | n/a | ✅ | n/a | ✅ |
| I interventions write | ✅ | ✅ admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| P reports write | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| P reports read/export | ⚠️ 404-not-401 (P2-02) | n/a | ✅ (on hit) | ✅ | ✅ | ✅ | n/a | ✅ |
| Ops `/api/health` | ⚠️ public by design | n/a | n/a | n/a | n/a | ✅ | n/a | ✅ |

Non-P2 routes (engine F/G/H/K/L, P4 J/M/N/Q) are not P2-owned; the sweep observed
`/health`, `/api/context`, `/api/recommendations/{id}/feedback` returning 200
without credentials, and data routes returning 404-not-401 — flagged for **P3/P4**.

---

## 4. Cross-check of prior findings (no re-litigation)

| Prior item | Source | P2 re-check @ `a0dfd01` |
|---|---|---|
| P2 PG-only runtime paths never executed in shared env | `PHASE2_AUDIT.md` A6 / remaining #3 | ✅ **Resolved here**: full backend suite **54/54 on PostgreSQL**, 450-row ingestion, audit sampling, ledger check. |
| `jwt` placeholder `change-me-in-production` | `PHASE2_AUDIT.md` B4 / remediation | ✅ Closed by remediation, but it then contradicted the shipped `.env.example` (app refused to start from `backend/`). Fixed on this branch: `.env.example` now ships a blank `JWT_SECRET` + guidance. |
| Direct-to-main hygiene (P2/P3) | `PHASE2_AUDIT.md` A1 / remaining #1 | 📝 Recorded process debt; no functional impact. |
| N1 additive `production_unit` | `PHASE2_AUDIT.md` A4/B3 | ✅ Closed (formalized in contract). |
| K1 id coverage on mock path | `PHASE2_AUDIT.md` remaining #2 → P3-01 | Not a P2 data-integrity defect; owned by P3/P4. P2 seeded 19 interventions in SQL (verified). |
| H2/H3, Q persistence | `PHASE2_AUDIT.md` remaining #10 | Accepted backlog; P2 owns Q persistence/FK (see P2-05 for calculation persistence). |
| `/docs/audit/` absent | `PHASE2_AUDIT.md` A1 | Still absent; audit artifacts at repo root + `docs/phase3/`. Process drift (LOW). |

---

## 5. Notifications

- **P3 — none required.** No CRITICAL P2 finding affects calculation inputs:
  factor provenance trio is complete for all 18 live factors (item 4 PASS), the
  factor table is intact, and double-counting is correct (item 5 PASS). P3-05
  (period lock on F1) and P3-07 (calculation persistence) remain P3-owned and are
  cross-referenced, not introduced by P2.
- **P4 — none from this pass.** P2-01/P2-02 are P2-owned endpoints; the P4-C1
  500s were handed to P4 in the Step 0 file.
- **P1 —** the unauth read finding (P2-01) does not change response shapes; no
  frontend action.

## 6. Verdict

**P2 data-integrity: PASS.** Every doc CHECK/UNIQUE/FK/index is live and enforced;
severities hold at 450-row volume; double-counting is correct under real data;
all factors carry source/version/year; reporting-period integrity holds. Two
security gaps to fix in the follow-up pass — **P2-01 (HIGH, unauth KB reads)** and
**P2-02 (MEDIUM, auth-not-first on 404s)** — plus **P2-03 (MEDIUM, partial factor
audit snapshots)**. No CRITICAL P2 finding; nothing blocks P3's calculation inputs.
The demo-breaking CRITICAL (P4-C1) is owned by P4 per `p2_audit_fasttrack.md`.
