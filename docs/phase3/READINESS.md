# Phase 3 Readiness — Evidence Ledger

**Branch:** `phase3-readiness` · **PR:** https://github.com/Ronit069/EcoLeak_AI/pull/1
**Date:** 2026-09-12 · **Baseline:** full-system verification of `10c2b9f`
(`docs/verification/FULL_SYSTEM_VERIFICATION.md`)

This document is the gate. Every claim below was executed in this pass and is
reproducible from the commands/URLs cited; nothing is inherited from an older
document. Where a prior "verified" claim could not be independently re-produced
it is called out in §5.

---

## 1. Gate checklist (7 items)

| # | Gate item | Status | Evidence |
|---|---|---|---|
| 1 | CI runs on every push/PR with real job output, PG service included | **CLOSED** | Push run `34694031430` (green, 1m35s): 4 jobs populated — `P2 migration + seed smoke` 59s, `K1 red/green adversarial` 1m32s, `Lint + naive pytest entrypoint` 40s, `Backend + engine suites` 1m9s. Before the fix, all 6 historical runs failed in 0s with `jobs: []` |
| 2 | JWT auth bypass (T0-2) closed, red/green proven | **CLOSED** | Red: JWT mode, no `Authorization`, `POST /api/units/normalize` -> **200** with real conversion output. Green: 28/28 auth-matrix checks pass (401 missing/malformed/expired/non-Bearer; 200 valid; stub mode intact). Permanent tests: `backend/tests/test_auth_regression.py` |
| 3 | Unauthenticated engine/P4 surface (T0-3) closed, red/green proven, two-tenant test | **CLOSED** | Red: 7 engine/P4 endpoints -> **200** with zero credentials. Green: same endpoints -> **401**; own-tenant token -> 200; foreign-tenant token/header -> **403**; unknown facility -> 404. Tests: `test_auth_regression.py::{test_two_tenant_isolation_jwt,test_two_tenant_isolation_stub_headers}` |
| 4 | Postgres-backed paths executed for the first time, wired into CI | **CLOSED** | Real PostgreSQL 16.2 (embedded, `127.0.0.1:53202`): `alembic upgrade head` (2 revisions), `run_seed` (1 org / 13 activities / 18 factors / 19 interventions), engine smoke **op = 566360.800000, 19 interventions**, backend suite **72 passed**, messy ingestion (7200 rows), Module P report + audit trail. CI runs the same paths against a `postgres:16` service every push |
| 5 | All "fix before Phase 3" findings closed with evidence | **CLOSED** | F-4/F-5/F-6/F-7/F-8/F-13/F-14/F-15 — see §3 |
| 6 | Final composed e2e trace on PG + auth enabled | **CLOSED** | 25-step trace, **25/25 PASS** (§4). Includes the explicit `AUTH: no token -> 401` step inside the composed run |
| 7 | Timestamped readiness doc reconstructable by a skeptic | **CLOSED** | This file + `docs/phase3/backlog.md` + probe scripts in `docs/verification/scripts/` |

**Open gate item (blocking the final verdict): branch protection on `main`.**
The acting GitHub account (`Aryan-B-Parikh`) is push-only; `gh api
repos/Ronit069/EcoLeak_AI/branches/main/protection` returns **404 — no
protection configured** as of this writing. Required settings (owner
`Ronit069`):

```
Settings -> Branches -> Add branch protection rule
  Branch name pattern: main
  [x] Require a pull request before merging
      [x] Require approvals: 1
  [x] Require status checks to pass before merging
      Required checks (workflow "EcoLeak CI"):
        P2 migration + seed smoke (PostgreSQL 16 service)
        Backend + engine suites (PostgreSQL 16 service)
        K1 red/green adversarial (fixed + broken dual-state)
        Lint + naive pytest entrypoint
  [x] Do not allow bypassing the above settings
  [ ] Allow force pushes  (leave OFF)
  [ ] Allow deletions    (leave OFF)
```

---

## 2. Blocker 1 — CI (T0-1), red/green chain

| Stage | Run | Result |
|---|---|---|
| Historical (pre-fix) | 6 runs, all `<workflow file issue>` | **failure, 0s, `jobs: []`** — no test ever ran |
| Fix 1: valid job id + actionlint-clean YAML | `34690981015` | workflow now parses and starts; jobs populated; surfaced a real latent bug: `pip` rejects extras in a constraints file |
| Fix 2: single pinned install (`-r requirements.lock`) | `34691050688` | **P2 migration + seed smoke PASSED (51s) and Backend PG suite PASSED (1m13s)** — first real PG execution; K1 job failed at the UI probe (constraints: CORS allow-list lacks `:5174/:5175`) |
| Fix 3: root `playwright-core` + CORS allow-list + test-expectation fixes | `34694031430` | **ALL 4 JOBS GREEN** (1m35s) |
| RED PROOF (throwaway branch `ci-red-proof`, PR #2) | `34694250628` | **FAILURE** — job `Lint + naive pytest entrypoint` failed at `Root suite via configured testpaths (naive pytest)` on the deliberate `assert False`; the other 3 jobs passed. Branch + PR closed without merging |
| GREEN PROOF (clean branch) | `34694031430` | 4/4 jobs green, same workflow, same head family |

CI content verified inside the runs (log excerpts): `PG smoke OK: op =
566360.800000 | interventions = 19`, `env baking guard PASS`, `K1 STRICT: ALL
CHECKS PASS`, `PASS fixed-UI shows engine label and nothing else`, `PASS
broken-UI shows fallback label + banner, never engine`, `All checks passed!`
(ruff), `ALL CHECKS PASSED (9/9)` (mock gate), `ALL SHAPE CHECKS PASSED`.

---

## 3. Silent-correctness closures (F-4 … F-15)

| Finding | Fix | Executed evidence |
|---|---|---|
| **F-4** health lied `ok` with DB down | `/api/health` probes DB + engine, bounded 4 s, 503 frozen shape with component detail; `X-Request-Id` on healthy path | DB down: `503` in ~4 s, `HEALTH_DEPENDENCY_UNAVAILABLE`; DB up: `200 {"database":"ok","engine":"ok"}` (the connect-timeout was added after the first probe showed a 10 s hang) |
| **F-5** naive `pytest` failed collection | root `pytest.ini` (`testpaths = tests`) + CI job `Lint + naive pytest entrypoint` | local `pytest` -> **164 passed**; CI job green |
| **F-6** M1 404 used raw `{"detail":…}` | `NotFoundError` (frozen shape) | live: 404 `{error_code,message,severity,details}`; `test_f6_unknown_recommendation_frozen_404` |
| **F-7** F2/J3 documented but unserved | F2 `GET …/calculations` served (derived on demand, identical to F1 POST); J3 `PATCH /api/recommendations/{id}` served with in-memory status store + transition rule (422/409/404 frozen) | `test_f7_f2_get_calculations_matches_f1_post`, `test_f7_j3_status_transitions_and_negatives`; contract + addendum updated |
| **F-8** live mode silently used fixture financials | machine-readable `impact.assumptions.data_is_stub` (from `FacilityContext.is_fixture`) + visible frontend notice | `test_f8_data_is_stub_label_present`; live J2 items carry `data_is_stub=true` |
| **F-13** bad input -> raw 500 | UUID path params across P2 routers; enum/numeric validation -> 422 frozen | live: malformed UUID -> 422 (was 500); invalid `reason_code` -> 422 (was 500); bad numeric -> 422; 3 tests |
| **F-14** zero application logging | `ecoleak` logger configured; per-request INFO line (method/path/status/request_id/elapsed_ms); 500 handler logs cause + traceback + request id | captured live: `request method=GET path=/api/health status=200 request_id=… elapsed_ms=…`; `unhandled error path=… request_id=…` + `ValueError` traceback |
| **F-15** unpinned deps, no lockfile | `requirements.lock` (pip-compile); CI installs `-r requirements.lock` only | CI installs from the lock; clean-install version drift (fastapi/starlette/numpy) removed |

---

## 4. Gate item 6 — composed trace on real PG with auth ON

Environment: merged API against `postgresql+psycopg://postgres:@127.0.0.1:53202/ecoleak`
(engine DSN = same PG), `USE_MOCK_DATA=false`, `AUTH_MODE=jwt`, Bearer token with
`organization_id = 0a1b2c3d-0001-…`. Result: **25/25 PASS**.

```
[PASS] C4 ingestion (7200 messy rows, PG): 202 status=PARTIAL issues=9600 (17626ms)
[PASS] C4 batch fetch: 200 status=PARTIAL issues=9600
[PASS] D1 normalize / D2 data-quality: 200
[PASS] F1 calculations (POST) / F2 (GET): 200 rows=2412
[PASS] F3 inventory-summary: 200
[PASS] G1 detect / G2 hotspots: 200 hotspots=6
[PASS] I1 interventions: 200 rows=19
[PASS] J2 recommendations / J1 generate: 200/202 recs=18
[PASS] M1 explanation / J3 transition / Q1 / Q2: 200/200/201/200
[PASS] K1 simulate (all live ids): 200
[PASS] H1 anomalies / L1 circularity: 200
[PASS] N1 dashboard / N2 leak-map: 200
[PASS] P1 report generate (PG): 202; P2 fetch 200; P3 export 200
[PASS] AUTH: no token -> 401
```

PostgreSQL write-path read-back (real PG): `activity_data` **3213** (13 seeded +
3200 imported), `ingestion_errors` **9600** (ERROR 4000 / WARNING 4000 / INFO
1600), `audit_logs` **3203** (`ACTIVITY_IMPORTED` 3200, `FILE_IMPORT` 1,
`REPORT_GENERATED` 1, `DATA_QUALITY_ASSESSED` 1), `reports` 1 (DRAFT v1).

Note — the SQLite substitution used in the full-system verification did **not**
hide a PG-specific failure: everything exercised on SQLite also passed on real
PG here (the only differences were test-expectation details: Decimal-as-string
serialization and per-call `calculated_at` timestamps).

---

## 5. Re-examined prior claims

| Prior claim | This pass |
|---|---|
| "PG-verified suites + permanent CI" (PHASE2_REMEDIATION R5) | Now **actually true** — but only after fixing the workflow. The historical CI never ran (6/6, 0 s, `jobs: []`) |
| "backend 54/54 on PostgreSQL 16.6" | Re-produced with **72 passed** (54 original + 18 new) on PG 16.2; CI runs the same suite on `postgres:16` |
| "K1 all-18 live ids → 200" | Re-verified in the composed PG trace (200) and in CI (`K1 STRICT: ALL CHECKS PASS`) |
| "Playwright dual-state UI probe PASS" | Now executed in CI for the first time; required fixing the CORS allow-list for `:5174/:5175` — the probe as originally written could never have passed in CI |
| "placeholder jwt guard verified" | Re-verified; additionally the JWT-mode **fallback bypass** it did not cover is now closed (T0-2) |

---

## 6. New findings discovered during this pass (recorded, not blocking)

1. **D1 unit labelling:** `POST /api/units/normalize` with an explicit different
   `to_unit` converts the value to that unit but labels the response with the
   family base unit (e.g. `1 kWh → to_unit=MWh` returns value `0.001` labelled
   `kWh`). Not in the verification finding set; recorded in
   `docs/phase3/backlog.md` for a contract-semantics decision.
2. **Environment note (not a code defect):** the host's PostgreSQL 18 `initdb`
   fails with `STATUS_DLL_NOT_FOUND` and the Windows service requires admin;
   Blocker 4 was executed with an embedded real PostgreSQL 16.2 instance
   (pgserver) on a user port. CI uses the official `postgres:16` service.

---

## 7. Deferred (owned, in `docs/phase3/backlog.md`)

F-9 provenance polish · F-10 distributed rate limiting · F-11 query
timeouts/pool sizing · F-12 LLM narrative guardrail hardening · F-16 lint debt ·
F-17 `npm run validate` path · F-18 loosely-typed contract subtrees · J3/Q
persistence · Module H2/H3 + anomaly persistence.

---

## 8. Verdict

All six executable gate items (1–6) are closed with fresh executed evidence,
and gate item 7 is this document. The **only** remaining gate condition is the
branch-protection rule on `main`, which requires repo-owner admin rights and is
not yet configured (`gh api …/branches/main/protection` -> 404 at the time of
writing).

**Status: NOT READY — Phase 3 blocked on: branch protection on `main`**
(settings in §1). Everything else is closed; once the owner applies the rule
and this document's branch merges with all four CI checks green, the gate is
satisfied.
