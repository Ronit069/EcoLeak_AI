# EcoLeak AI — Full System Verification (adversarial, executed pass)

**Date:** 2026-09-12 · **Commit under test:** `10c2b9f` (main HEAD)
**Method:** From-scratch technical verification. Nothing inherited from
PHASE1_AUDIT / PHASE2_AUDIT / PHASE2_REMEDIATION / K1 chain was trusted; every
check below was executed in this pass unless explicitly marked `Unverified`.
**Environment limitations (declared up front):** this host has **no Docker, no
PostgreSQL, no `psql`** (port 5432 closed). PostgreSQL-only behavior is marked
`Unverified` — never as `Pass`. Where a SQLite substitute was used it is labeled
`SQLite-substituted (PG path unverified)` and proves behavior of the Python code,
not of PostgreSQL. Python **3.10.6** (CI claims 3.11); frontend Node 20.12.2.

---

## 0. Tier-0 finding, stated first

### T0-1 · The CI workflow is invalid and has NEVER run. All prior "CI green" claims are false positives.

- `.github/workflows/phase2-ci.yml` declares job id `'P2 migration + seed smoke'`
  (spaces and `+`). GitHub job ids must match `[A-Za-z_][A-Za-z0-9_-]*`; an
  invalid id rejects the **entire workflow file**.
- Reproduced locally: `docs/verification/scripts/verify_ci_jobids.py` →
  `VERDICT: WORKFLOW INVALID -> no jobs run` (checked both historical commits
  `10c2b9f` and `f01c6a5` via `git rev-list --all -- .github/workflows/`).
- Independently confirmed against GitHub itself (`gh run list --workflow
  phase2-ci.yml`): **6/6 runs, conclusion=failure, duration 0s** (run started ==
  run updated, `jobs: []`). Example: run `34682754054` at head `10c2b9f`
  ("This run likely failed because of a workflow file issue").
- Consequence: **no test has ever executed on GitHub CI for this repo.** The
  "PG-verified suites + permanent CI" remediation claim (PHASE2_REMEDIATION §1
  B2 row) is not supported by CI evidence; the local-PG runs claimed there are
  not reproducible here and no CI record exists to corroborate them.

### T0-2 · `AUTH_MODE=jwt` silently degrades to trusted-header stub auth (bypass)

`backend/app/security.py:84-111`: `get_current_principal` only validates a JWT
`if settings.auth_mode == "jwt" and authorization:` — **a request with no
`Authorization` header in JWT mode falls through to the stub branch** and is
authenticated from `X-Role`/`X-Organization-Id` headers (default role
`SUSTAINABILITY_ANALYST`). Executed: server on `:8012` with
`AUTH_MODE=jwt, JWT_SECRET=<real secret>` — `POST /api/units/normalize` with **no
Authorization header** passed authentication (returned 422 json_invalid, i.e. it
reached request validation, not a 401). Production-blocking.

### T0-3 · Engine/P4 endpoints have no auth dependency at all (any mode)

Executed live on both a stub server (`:8013`) and a JWT server (`:8012`), with
zero credentials: `GET /api/context`, `/inventory-summary`, `/hotspots`,
`/recommendations`, `/dashboard`, `/leak-map`, `/circularity-score`,
`POST /calculations`, `POST /hotspots/detect`, `POST /scenarios/{id}/simulate`,
`GET /recommendations/{id}/explanation`, `POST/GET /recommendations/{id}/feedback`
— all `200`. These routers (`engine/api.py`, `p4/api.py`) never call
`get_current_principal` / tenant resolvers. The api_contract.md claims
`AuthN, tenant ownership` for G2/J2/N1/N2/K1/M1/Q1/Q2; the live surface does not
implement them. Production-blocking.

---

## 1. Phase 0 — Inventory & cold start

| Check | Status | Executed evidence |
|---|---|---|
| Services enumerated: single merged FastAPI app (P2 routers A–E/I/P + engine router F/G/H/K/L + P4 router J/M/N/Q) + standalone `engine.api:app`; frontend Vite SPA; **no P4-standalone HTTP service** (P4 is library+router, mounted into the merged app) | Pass | `backend/app/main.py:95-107` includes 10 routers; route dump = **50 routes** (49 + `/health` root) |
| Entrypoints/ports: `python -m uvicorn app.main:app --port 8000` (backend, needs PG or `ENGINE_DSN`); `npm run dev` (5173, vite proxy → `ECOLEAK_API_URL ?? localhost:8000`); `engine.api` standalone | Pass | files read; probes below |
| **Clean checkout** cold install: `git clone` to `C:\Temp\opencode\verify\clean` (no node_modules/dist/var/pycache), `pip install` + `npm ci` (exit 0) | Pass | `pip_install.log` (`Successfully installed ... fastapi-0.141.1 starlette-1.6.0 numpy-2.2.6`), `npm_ci.log` (148 packages) |
| Cold boot (clean env, **no Postgres**): merged app **boots and serves `/api/health` 200 `status:ok`** | Pass (with defect) | boot log `boot_pg.log`; **defect F-4: health does not check DB** — reported `ok` with Postgres down and everything but engine paths broken |
| Boot against DB-less env with `ENGINE_DSN` (SQLite seed image): all engine/dashboard/J endpoints serve real output | Pass | live probes `:8011` below |
| `.env.example` copied verbatim (`JWT_SECRET=change-me-in-production`) → **boot fails loudly** (placeholder rejected) | Pass | executed: `Settings()` raises `ValidationError` "jwt_secret must not be a placeholder value even in development" |
| `AUTH_MODE=jwt` w/o secret → fails loudly; `ENVIRONMENT=production` w/o secret → fails loudly; real secret in jwt mode → boots | Pass | executed: 3× ValidationError / 1× success (exact messages quoted in §5) |
| `USE_MOCK_DATA=false` without DSN → engine raises `ValueError("USE_MOCK_DATA=false requires ECOLEAK_SQL_DSN...")` (loud, not silent) | Pass | executed |
| Alembic migration path (`python -m alembic upgrade head` on PG) | **Unverified** | no PG on host; CI job that would have run it never executed (T0-1) |
| `npm run validate` (declared script) | **Fail** | `ERR_MODULE_NOT_FOUND: ...\frontend\scripts\validate-mocks.ts` — script target does not exist in repo |

**Boot-log warnings (recorded):** `StarletteDeprecationWarning:
HTTP_422_UNPROCESSABLE_ENTITY deprecated` ×3 on every boot (`app/errors.py:75,80,92`);
clean install resolved **fastapi 0.141.1 / starlette 1.6.0 / numpy 2.2.6 / PyJWT
2.14.0** vs dev env's 0.115.0/…/1.26.2 — unpinned `>=` requirements with **no
Python lockfile** ⇒ non-reproducible installs (finding F-15).

---

## 2. Phase 1 — Static & build-level verification

| Check | Status | Executed evidence |
|---|---|---|
| Frontend `npm run build` (= `tsc --noEmit && vite build`) on clean checkout | Pass | `frontend_build_clean.log` exit 0; produced `dist/assets/index-B8U-FiJU.js` |
| Python type-checking (mypy/pyright) | **Unverified** | **no type checker is configured anywhere** (no mypy.ini/pyrightconfig/pyproject); cannot execute what does not exist |
| Type-suppression inventory | Pass (grep) | `# type: ignore`: **12 in 5 files** — engine/anomaly.py ×5, engine/ids.py ×3, engine/simulator.py ×2, engine/carbon.py ×1, engine/units.py ×1. `noqa`: **68 directives / 14 files**. Frontend src: **0** `@ts-ignore`/`@ts-expect-error`/`as any`; **1** `eslint-disable` (Scenarios.tsx:51). With no typechecker configured, the 12 engine suppressions are unpoliced |
| Repo linter as configured: backend `ruff check app` (ruff.toml selects E9+F only) | Pass | `All checks passed!` |
| Broader lint at repo level: `ruff check engine p4 contracts tests` | **Fail — 637 issues** (615 auto-fixable) | `ruff_root.log`: RUF100 unused-noqa, FURB157 verbose Decimal, I001 unsorted imports, F401 unused imports, SIM222, F541, C408. Mostly test-file hygiene; the configured gate (backend/app only) hides all of it |
| Root pytest (engine/p4/contracts suites) | **Fail as documented; Pass when run correctly** | (a) default `pytest` from root: **collection ERROR** `backend/tests - ModuleNotFoundError: No module named 'app'` (conftest bootstrap order); (b) corrected `pytest tests`: **164 passed, 5 warnings** (root_final.log) |
| Backend pytest suite | **Fail — environment-gated, not code** | all **54 tests ERROR at setup**: `assert engine.url.database == "ecoleak_test"` → got `ecoleak` (default DSN; conftest reads `TEST_DATABASE_URL` from backend/.env which does not exist). Postgres unavailable ⇒ suite **Unverified on PG**; nothing on main can run it without PG (same conclusion as PHASE1_AUDIT D3, still true at HEAD) |
| Prior-false-positive pattern grep (loose asserts / getEnv / silent fallbacks) | Pass (findings enumerated) | see §3 pattern list below |

**Pattern inventory (executed greps, full lists):**

- Loose/OR-style assertions in tests: `tests/test_remediation.py:65`
  (`payback_status in {None, "AVAILABLE", "UNAVAILABLE"}` — acceptable 3-value
  union, not the known anti-pattern); `tests/test_p4_phase2_integration.py:57`
  (`load_hotspots().source in {"live","mock_fallback"}` — OR-union of success and
  failure vocabulary, flagged); `tests/test_merged_api.py:43` severity-membership
  check (fine). `tests/k1_strict.mjs:45` asserts `res.status===200 && body.assessment`
  (distinguishing check — OK).
- `getEnv()` indirection: **none** (anti-pattern remediated in `2e41dbe`;
  `frontend/src/lib/api.ts:35-36` uses literal `import.meta.env.VITE_API_URL` /
  `VITE_API_TOKEN` tokens — Vite-bakeable; CI's env-baking guard would have
  checked the bundles had CI ever run — T0-1).
- Silent fallbacks in production code paths: `p4/data_source.py:120-127`
  (`except Exception` → mock_fallback with provenance+warning — labeled, OK);
  `backend/app/services/engine_bridge.py:117-118` (`except Exception` →
  `{"__unavailable__": ...}` in Module P — labeled, OK); `engine/anomaly.py:25-27`
  (sklearn import guard — OK); `frontend/src/lib/api.ts:65,77` `catch { ignore }`
  for localStorage (OK, non-silent path).
- `except Exception` handlers returning degraded-but-labeled states: **12 sites**
  (reports.py 170/178, engine_bridge 117, p4/data_source 120, anomaly 25,
  explainability 365, …) — all labeled; none silently substitutes fabricated
  numbers.

---

## 3. Phase 2 — Contract re-verification (independent)

Method: **fresh** HTTP probes (urllib/curl scripts in
`docs/verification/scripts/full_verify_probe.py`), responses validated
field-by-field against `contracts/schemas.py` models — not via the repo's test
harness. Targets: `:8013` (merged API, `USE_MOCK_DATA=false`, SQLite-substituted
platform DB + SQLite engine seed) and `:8011`/`:8012` (engine-only path).

| Endpoint group | Documented shape | Live result | Status |
|---|---|---|---|
| `GET /api/context` (additive, logged) | org/facilities/periods | exact keys, Pydantic-validated | Pass |
| F3 `inventory-summary` | `{scope1,scope2,scope3,total,carbon_intensity,production_unit,generated_at}` | exact keys; 224,250/340,800/6,637,300/7,202,350 | Pass |
| G1/G2 hotspots | `HotspotDetectionResult` | **model_validate(PASS)**; 5 hotspots, Boiler HIGH 76.36 (severity recalibration decision holds) | Pass |
| J1/J2 recommendations | `RecommendationGenerationResult` | **model_validate(PASS)**; 18 recs, exact envelope+item+impact keys | Pass |
| N1 dashboard | `DashboardResponse` (incl. additive `production_unit`) | **model_validate(PASS)**; scope_breakdown sums == total | Pass |
| N2 leak-map | `{nodes[], links[]}` | exact shape | Pass |
| K1 simulate | `ScenarioSimulationEnvelope` | **model_validate(PASS)**; also **all-18 live J2 ids → HTTP 200** with exact ImpactAssessment keys (baseline 7,202,350 → projected 6,918,356.207628) — remediation claim independently re-executed | Pass |
| L1 circularity | contract keys + internal-metric labelling | validator tool PASS (re-run) | Pass |
| D1 units/normalize | `{original_value,original_unit,normalized_value,normalized_unit,conversion_factor,conversion_source}` | exact keys; MWh→kWh 200 | Pass |
| D1 ambiguous L→m³ | `422 CONFIRMATION_REQUIRED` frozen shape | executed → frozen shape, severity `CONFIRMATION_REQUIRED` | Pass |
| E1 factors list | `EmissionFactor[]` | 18 factors | Pass |
| A2/A5/A9 etc. (P2 DB-backed) | contract shapes | **Unverified (PG)** — only SQLite-substituted partials below |
| Error shape (§28) | `{error_code,message,severity,details}` | verified frozen on: 403 FORBIDDEN (2 variants), 409 DUPLICATE_IMPORT, 429 RATE_LIMITED, 422 CONFIRMATION_REQUIRED, 422 INVALID_UNIT, 422 MISSING_PARAMETER, 422 VALIDATION_ERROR, 404 NOT_FOUND | Pass |
| **Error shape drift** | — | `GET /api/recommendations/{unknown}/explanation` → **404 `{"detail":"recommendation not found"}`** (raw HTTPException, NOT frozen shape — `p4/api.py:176-178`) | **Fail (F-6)** |

**Documented-but-not-served endpoints (route inventory vs api_contract.md):**
`F2` GET calculations (documented) — **absent**; `H2` GET anomalies, `H3`
acknowledge — **absent** (known, Phase-3 backlog); `J3` PATCH recommendations —
**absent**; `O1–O7` scenario CRUD, `K2` impact, `K3` compare — **absent**
(known); P3 export returns 501 by design (documented). PHASE2_AUDIT lists H2/H3
and O-gaps as owned backlog; **F2 and J3 absences are not recorded anywhere in
the prior docs — new finding (F-7)**.

---

## 4. Phase 3 — Real-data pipeline trace

Dataset: generated 7200-row "messy" CSV via the repo's own
`backend/app/seed/messy_dataset.py` (scale=800) — negative values, missing
units, unknown units (furlong), implausible magnitudes, in-file duplicates,
period mismatches, unit conversions — every documented severity triggered.

| Hop | Status | Executed evidence |
|---|---|---|
| C4 ingestion (live POST import) | Pass | 202 `PARTIAL`, **144 issues**: ERROR 60 (NEGATIVE_VALUE 12, MISSING_VALUE 12, INVALID_UNIT 12, DUPLICATE_IN_FILE 12, PERIOD_MISMATCH 12), WARNING 60 (UNKNOWN_PROCESS_CODE 48, IMPLAUSIBLE_MAGNITUDE 12), INFO 24 (UNIT_CONVERTED 12+12); 48 accepted persisted (61 total incl. 13 seeded). CONFIRMATION_REQUIRED severity: not CSV-reachable by design; **live-executed** via D1 (L→m³ → 422 `CONFIRMATION_REQUIRED`). All four documented severities observed live |
| Duplicate imports rejected | Pass | same file again → 409 `DUPLICATE_IMPORT` frozen shape with `existing_import_id` |
| ImportJob retrieval (tenant guard) | Pass | GET batch **without org header** → 404 frozen NOT_FOUND; with header → 200 full job |
| Normalization (Pint) | Pass | tonne→kg, MWh→kWh INFO rows; live D1 200/422 shapes |
| F (carbon calc) | Pass | inventory over SQL source: totals reconcile (scope1 224,250 + scope2 340,800 + scope3 6,637,300 = 7,202,350) |
| G (hotspots) | Pass | exact envelope; contribution %s sum to 100 |
| J (ranking) | Pass | 18 recs, deterministic ids, exact formula fields |
| M (explanations) | Pass (with caveat) | template explanations embed real evidence numbers; **but** `impact.assumptions` in live `USE_MOCK_DATA=false` responses carry `"tariff_source":"P4 demo tariff fixture (mock)"` and `intervention evidence_source` values end with `(mock)` — the recommendation layer's financial baseline is still fixture data **in the live-data mode**, only labeled at the assumption level (F-8) |
| K1 (simulate) | Pass | all-18 → 200 (see §3) |
| P (report) | **Unverified on PG** | report generation requires P2 DB; SQLite-substituted smoke ran only via service code review — not executed here end-to-end on PG |
| Dashboard render (N1/N2) | Pass (API) | exact contract shape served; **browser UI render Unverified** (Playwright legs from prior audit not re-executed here) |
| No step silently drops data | Pass | every rejected row is persisted to `ingestion_errors` (144 rows verified in DB) with raw_row; unresolved activities appear as `UNRESOLVED` provenance (7 rows, real-factor run validator) |
| **Upstream-break tests** | Pass | K1 with unknown intervention_id → **404 NOT_FOUND frozen shape, specific** ("Unknown intervention: {...}"); unknown rec explanation → 404 (but wrong shape, F-6); DB hard-kill mid-import → see §7 |
| computedVia-style provenance | Pass (K1) | frontend `fetchSimulate` returns `computedVia:'engine'\|'local_fallback'`; API itself doesn't emit it (frontend-side only) — K1's own response carries no `computedVia` field; the banner/label mitigation is frontend-only (F-9: server-side provenance signal still absent on other degrade paths, e.g. Module P sections are labeled but J2's fixture-tariff basis is only inside `assumptions`) |

---

## 5. Phase 4 — Concurrency, load, realistic scale

| Check | Status | Executed evidence |
|---|---|---|
| Realistic volume | Pass | 7200-row ingest executed (above); 19-intervention library live; dashboard/J2 at full volume (18 recs) |
| 50 concurrent `/api/health` | Pass | 50/50 → 200, max 43.15 ms, total 71.93 ms |
| 30 concurrent DB writes (org creation) | Pass | 30/30 → **201**, 30 rows persisted, no 500s (SQLite-substituted; **PG behavior Unverified**) |
| Rate limiting | Pass | 130 rapid POSTs `/units/normalize` → **exactly 120×200 then 10×429**, frozen shape `RATE_LIMITED` |
| Rate-limit caveats | Finding (F-10) | in-memory sliding window (`services/ratelimit.py`) — per-process buckets: multi-worker deployments get per-worker limits; no Redis backing despite docstring's "Phase 2 replaces with Redis" |
| N+1 query check | **Unverified** | no query-count instrumentation executed |
| Connection-pool exhaustion / memory growth | **Unverified** | not measured; note `db.py` creates engine with **no pool sizing, no `pool_timeout`** (defaults: QueuePool 5/15); **no DB statement timeout anywhere** → a hung DB query can hang a worker indefinitely (F-11) |
| Timeout sanity | Partial | frontend fetch timeout 5 s (`api.ts:130`) executed in design+build (not re-run live); **server side has no timeouts** (LLM endpoint: none exists in production code — `LLMExplainer` is injection-only; no API-key/LLM client is wired, so "slow LLM call" risk is currently structural, not runtime) |
| Response-shape drift under load | Pass | all concurrent probes returned identical shapes (status_counts all 200/201) |

---

## 6. Phase 5 — Security re-pass

| Check | Status | Executed evidence |
|---|---|---|
| Hardcoded secrets in current source | Pass | grep: no API keys / `sk-` / AKIA / private-key blocks in working tree; only `CHANGE_ME`/`change-me-in-production` placeholders |
| Secrets in **git history** (26 commits) | Pass (with note) | full-history `git grep` across all revs: openai/aws/generic-api-key/private-key patterns = **0 matches**; `postgres:…@localhost` URLs only in `.env.example`/CI/config defaults (dev placeholders); `dev-only-secret-change-in-production` existed in **historical** `config.py` (removed at HEAD; remediation documented). No real secrets ever committed |
| AuthN enforced per endpoint | **Fail** | see T0-2/T0-3: JWT mode fallback bypass (executed); engine/P4 surface entirely unauthenticated (executed); P2 routers *do* enforce role+tenant (live 403s with frozen shapes: admin-gate on org create; tenant 404 on batch GET without org) |
| Role spoofing in stub mode | Pass (by design, risk noted) | `X-Role: SYSTEM_ADMIN` header → 201 (trusted-header stub is the documented Phase-1 design; acceptable only for local dev) |
| VIEWER cannot write | Pass | import as VIEWER → 403 frozen shape |
| LLM guardrails, fresh adversarial strings | **2 new gaps (F-12)** | with high-confidence evidence: (A1) `"saves 2 MtCO2e per year"` → **ACCEPTED** (`source=llm`) — `_NUMBER_UNIT_RE` has no `tCO2e`-prefixed mega-units, numeric checker returns `[]` on `2 MtCO2e`; (A2) `"fully compliance-certified under ISO 14064 … guaranteed to eliminate all emissions"` → **ACCEPTED** (`source=llm`) — qualitative hallucination/compliance claims are not checked at all. With low-confidence evidence all 5 fresh attacks were rejected (via the caveat rule) — i.e. the guard gap is masked exactly when data is weak |
| LLM cannot influence numeric ranking | Pass | data-flow executed: `p4/engine.py:308-314` ranks on `final_score` computed **before** `explainer.explain(evidence)` (engine.py:443); explainer output only fills `outcome.text → explanation`; no LLM client in prod code; executed shape-diff tool: `ranking unchanged` under `explanation_sources={'llm':18}`; contradiction run `contradicted=18, regenerated=18` |
| SQLi | Pass | no raw/dynamic SQL in app code (only parameterized `select()`; grep `text(` hits are conftest TRUNCATE with static names + engine's own `Table` DDL). Live probes: tautology filter → 200/0 rows (control: legit filter → 7 rows); UNION-in-path → 500 (below); quote-in-unit → 422 with value safely echoed |

---

## 7. Phase 6 — Failure & recovery

| Check | Status | Executed evidence |
|---|---|---|
| Kill mid-import | Pass | background 7200-row import → `taskkill /F` at t+0.9 s (request in flight) → client got connection reset; **DB after kill: no batch row, no activity rows, no `PROCESSING` residue** (transaction rolled back cleanly) |
| Restart + re-import | Pass | server restarted → health 200; same file re-imported → new batch `PARTIAL 7200/3152` (48 rows correctly rejected as DB-duplicates of the first import); total accepted 3213 = 61+3152; **0 duplicate `(facility,period,source_row_hash)` groups** |
| Kill/restart mid-calculation | **Unverified** | not executed |
| Error-shape consistency across the merged surface | Pass, with 2 exceptions | frozen 4-key shape verified on 8 error types (§3); **exceptions:** M1 unknown-rec → raw `{"detail":…}` (F-6); malformed UUID path (`…/emission-factors/x' UNION SELECT null--`) → **500 INTERNAL_ERROR** (`UUID()` ValueError unhandled → generic 500; also feedback `reason_code` invalid enum → **500** with raw `ValueError: 'NOT_A_REAL_CODE' is not a valid RejectionReasonCode` in server stderr, `p4/api.py:251`) (F-13) |
| Observability for incident debugging | **Fail (F-14)** | no request-ID/correlation middleware; no `logger`/`logging` usage in `backend/app` at all (grep = 0); the generic 500 handler emits **no log line** — the only trace of the 500 above was uvicorn's stderr ASGI traceback. Production incidents would be undebuggable beyond access logs |

---

## 8. Re-examined prior claims (independent confirmation status)

| Prior claim | This pass |
|---|---|
| "PG-verified suites + permanent CI" (REMEDIATION B2) | **Could not confirm.** CI file invalid (T0-1; 6/6 runs failed 0s, `jobs: []`). Local-PG runs not reproducible here; no independent corroboration exists |
| "backend 54/54 on PostgreSQL 16.6" | Unverified — same basis as above; suite cannot even run locally without PG |
| "K1 all-18 live ids → HTTP 200" | **Independently re-executed and confirmed** (200; exact envelope keys) |
| "placeholder guard fail-fast verified (4-case)" | **Independently re-executed and confirmed** (3 ValidationError cases + real-secret success), plus **new finding**: `.env.example` itself is now non-bootable if copied (dev-friendly but safe-by-default) |
| "Q wired (Q1 201/Q2 200/422 frozen shape)" | Partially confirmed: 422 MISSING_PARAMETER frozen shape live; **Q1 with invalid `reason_code` → 500** (F-13) — the remediation's own contract test does not cover this input |
| "N1 `production_unit` accepted into contract" | Confirmed (model_validate PASS; contract text matches live) |
| "K1 wrapper canonical decision documented" | Confirmed (schema + contract row + live shape) |
| "jwt mode w/o secret fails fast; **secret placeholder 'change-me-in-production' rejected**" | Confirmed. **However T0-2 (JWT-mode fallback to stub) was missed by every prior pass** |
| "Mock fallback never masks silently" | Mostly holds (labeled fallbacks); **but live J2/M1 in `USE_MOCK_DATA=false` still emits `(mock)` evidence sources and mock tariff basis** (F-8), and server-side `computedVia`-equivalent is absent outside the frontend (F-9) |
| "E2E Playwright legs 7/7 + dual-state UI probe" | Unverified here (browser automation not executed this pass); and CI job that would enforce them never ran (T0-1) |
| "164 root tests pass" | Confirmed on clean checkout (`pytest tests` → 164 passed) — but default `pytest` invocation **fails** (backend collection error), and backend/54 remain PG-gated |
| "tsc clean" | Confirmed (build passes tsc + vite) |
| "ruff zero warnings" | Only with the narrow backend `ruff.toml` (E9+F on `app/`); root-lint of engine/tests = **637 findings** (F-16) |

---

## 9. New findings (not previously caught)

- **F-1 (T0-1)** Invalid CI job id ⇒ GitHub rejects whole workflow; 6/6 runs 0s-failed; CI has never run. *Production-blocking.*
- **F-2 (T0-2)** JWT-mode auth falls back to trusted-header stub when `Authorization` absent → full auth bypass in the intended production auth mode. *Production-blocking.*
- **F-3 (T0-3)** Engine/P4 routes have no auth/tenant dependencies at all (contract says AuthN+tenant). *Production-blocking.*
- **F-4** `/api/health` (and `/health`) report `ok` without checking DB/engine dependency. *Silent-correctness/ops.*
- **F-5** Default root `pytest` is broken (backend/tests collected without `app` importable ⇒ ModuleNotFoundError). CI would have caught it… had CI run. *Silent-correctness.*
- **F-6** M1 404 uses FastAPI's raw `{"detail":…}` shape, violating the frozen error shape on the merged surface. *Silent-correctness.*
- **F-7** Contract-documented `F2` (GET calculations) and `J3` (PATCH recommendation) endpoints are not served by the merged app; absence undocumented in any prior doc. *Contract drift.*
- **F-8** In `USE_MOCK_DATA=false`, live J2/M1 payload still labels `tariff_source:"P4 demo tariff fixture (mock)"` and `(mock)` evidence sources — real-data mode runs on fixture financial baselines, labeled only in assumptions. *Silent-correctness.*
- **F-9** `computedVia`-style provenance exists only frontend-side (K1); server responses on degrade paths (Module P sections) use ad-hoc `status/note` keys instead of a uniform provenance field. *Cosmetic-to-silent.*
- **F-10** Rate limiter is per-process in-memory (multi-worker ⇒ multiplied limits); no distributed store. *Ops.*
- **F-11** No `pool_timeout`/statement timeouts configured anywhere → hung query/LLM-adjacent call can hang workers indefinitely. *Ops/production.*
- **F-12** LLM guardrail gaps: `MtCO2e`-style unit evasion accepted; qualitative compliance/guarantee hallucinations accepted (only numeric+citation+low-confidence rules exist). *Silent-correctness (narrative only; ranking untouched).*
- **F-13** Unvalidated `reason_code`/malformed UUID inputs produce 500 (raw ValueError/enum errors), inconsistent with frozen error semantics (should be 422). *Silent-correctness.*
- **F-14** Zero application logging; no request correlation IDs; 500s logged nowhere. *Ops-blocking for incident response.*
- **F-15** No Python lockfile; unpinned `>=` requirements resolved to different majors on a fresh install (numpy 2.x vs 1.26 dev). *Reproducibility.*
- **F-16** Repo-wide ruff (engine/tests/p4): 637 findings (mostly hygiene) hidden by the narrow backend-only ruff config. *Cosmetic.*
- **F-17** `npm run validate` targets a missing file (`frontend/scripts/validate-mocks.ts`). *Cosmetic.*
- **F-18** `dict[str, Any]` contract fields (`largest_hotspot`, `interventions[]`, `issues[]`) are untyped contract surfaces — no schema validation on those subtrees. *Cosmetic-to-silent.*

---

## 10. Blocking Risk Report

**Production-blocking**
1. T0-1 invalid CI (no automated verification has ever run on GitHub).
2. T0-2 JWT-mode auth bypass (silent stub fallback).
3. T0-3 unauthenticated engine/P4 surface.
4. PostgreSQL-only runtime (Module P, ingestion-at-volume, audits, migrations) has **never been executed in this verification pass** and cannot be verified on this host — deployment would be the first-ever PG run of those paths.

**Silent-correctness**
5. F-4 health lie; 6. F-6 M1 error-shape drift; 7. F-7 missing F2/J3 endpoints; 8. F-8 mock-basis data in live mode; 9. F-12 LLM narrative guardrail gaps; 10. F-13 500-on-validation-inputs; 11. F-5 broken default pytest entry.

**Cosmetic / deferrable**
12. F-16 repo lint debt; 13. F-17 broken npm script; 14. F-9/F-18 provenance/typing polish; 15. F-10/F-11 ops hardening (needs Redis + timeouts before scale).

---

## 11. Final verdict

### **NOT VERIFIED — do not deploy, specific reasons listed**

1. The only CI ever configured is invalid and has never executed a single job
   (GitHub-confirmed 6/6 zero-second failures) — the project's automated
   verification claims have no independent foundation.
2. The production auth mode (`AUTH_MODE=jwt`) silently downgrades to a
   trusted-header stub for header-less requests (executed), and the entire
   engine/recommendation surface requires no credentials at all (executed).
3. The PostgreSQL-backed platform paths — ingestion-at-volume, Module P, audit
   trail, Alembic migrations — have never been executed against PostgreSQL by
   anyone whose runs could be reproduced in this verification; on this host they
   cannot even start, so they remain unverified, not passed.
4. Contract and error-shape drift on the live merged surface (raw `detail` 404s,
   500s on malformed inputs, two documented endpoints missing).

What *was* verified to work under SQLite-substitution: the merged API cold-boots,
the F/G/J/M/N/K/L engine path serves contract-exact payloads (all-18 K1 → 200),
ingestion applies every documented validation severity and persists
rejections/audits transactionally, rate limiting and JWT/production secret
fail-fast work as claimed, the LLM cannot touch numeric ranking, and no real
secrets exist anywhere in history. Those verified strengths do **not** offset
the unverified PostgreSQL runtime and the auth blockers above.

**Reproducibility note for reviewers:** every live probe above was executed with
plain HTTP against servers booted from the clean clone at
`C:\Temp\opencode\verify\clean` (`USE_MOCK_DATA=false ENGINE_DSN=sqlite…`,
ports 8011/8012/8013). The probe scripts are committed under
`docs/verification/scripts/` (`full_verify_probe.py`, `verify_ci_jobids.py`);
logs live in `C:\Temp\opencode\verify\*.log`. No production source files were
modified during this pass.
