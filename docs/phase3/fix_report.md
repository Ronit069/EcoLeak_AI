# Phase 3 Audit — Fix Report

**Branch:** `phase3-fixes` (based on `origin/main` @ `4b2eb9e`)
**Date:** 2026-09-12 · **Method:** fixes applied + executed evidence; full suites
re-run; live re-verification against real PostgreSQL.

Findings are from `docs/phase3/general_audit.md` (GA-*), `docs/phase3/p1_audit.md`
(P1-*), `docs/phase3/p2_audit*.md` (P2-*), `docs/phase3/p3_audit.md` (P3-*).

---

## 1. Closed in this pass

| Finding | Sev | Fix | Executed evidence |
|---|---|---|---|
| **GA-01 / P4-C1 / P4-H2** | CRITICAL | `p4/api.py::_run_ranker` + `engine_bridge.real_recommendations` now use live `load_facility_dataset` / `build_facility_context` / `resource_factors_from_factors` (mock demo facility/context removed) | non-demo facility: `recommendations` **200** (was 500), `dashboard` **200**, report recommendations section `REAL` |
| **GA-02** | HIGH | `AUTH_MODE=stub` refused when `ENVIRONMENT != development` unless `ALLOW_STUB_AUTH=true` | `test_ga02_stub_refused_in_production`, `test_ga02_stub_allowed_with_explicit_opt_in` |
| **GA-04 / P3-05 / P2-06** | MEDIUM | F1 `POST …/calculations` refuses `LOCKED`/`CLOSED` → `409 PERIOD_LOCKED`; F2 GET unaffected | live: LOCKED → **409**, DRAFT → 200; `test_ga04_locked_period_refuses_calculation`, `test_ga04_draft_period_still_calculates` |
| **GA-05** | MEDIUM | `units.normalize` labels the actual target unit when `to_unit` supplied | `test_explicit_target_unit_label` (1 kWh→MWh ⇒ value 0.001, unit **MWh**) |
| **GA-06 / P3-01** | LOW | `mocks/mock_dataset.json` now contains the full **19**-entry library | `test_ga06_mock_dataset_carries_full_library`; `validate_mocks.py` 9/9 |
| **GA-07** | LOW | `contracts/README.md` points to the real spec file | file added |
| **P1-01** | HIGH | Dashboard: total labelled "ALL SCOPES" with the Scope 1+2 value shown; largest-leak share labelled "of Scope 1+2" | live walkthrough; frontend build |
| **P1-02 / P1-03** | MEDIUM/LOW | Fallback KPIs labelled `(demo recs)`; division-by-zero → "baseline unavailable" (no more `∞%`) | live empty-facility run |
| **P1-04** | MEDIUM | 5xx response re-applies CORS + security headers + `X-Request-Id` | `test_p1_04_5xx_carries_cors_and_request_id` |
| **P1-05** | MEDIUM | `DashboardResponse.unresolved_count` (additive) + UI notice | live `unresolved_count=2`; `test_p1_05_n1_exposes_unresolved_count` |
| **P1-06** | MEDIUM | New `/reports` page (generate / list / provenance+quality / JSON+CSV export) | frontend build; route wired in `App.tsx` |
| **P1-07 / P1-08** | LOW | Stale "mock" wording removed; "quality" disambiguated (hotspot vs period) | frontend build |
| **P1-09** | MEDIUM | Facility selector (persisted) + active-facility display fixed on Dashboard/Profiling/DrillMap | frontend build |
| **P2-03** | MEDIUM | Factor create/version audit rows store full JSON-safe snapshots | backend suite **77/77** |

**Suites after fixes:** root `pytest` **167 passed**; backend `pytest` on PostgreSQL **77 passed**; `ruff check app` clean; `validate_mocks` 9/9; `validate_against_mock` ALL SHAPE PASS; p3/p4 shape-diff PASS (regenerated artifacts committed).

---

## 2. Re-verified earlier closures (still hold)

- **P2-01 / P2-02** — unauthenticated KB reads and 404-before-401 are closed in **JWT mode** (live: 401). Residual: in **stub** mode (dev only) anonymous reads remain, which GA-02 now prevents in any non-development environment.
- **T0-2 / T0-3** — JWT strictness and engine/P4 auth+tenant guards remain green (backend auth regression tests pass).

---

## 3. Not implemented in this pass (explicit, with reasons)

These P3 findings change **calculation semantics or methodology** and need a
product/requirements decision plus their own test coverage; silently changing
them would risk producing wrong numbers (contrary to the audit goal). They stay
open with owners in `docs/phase3/backlog.md`.

| Finding | Why deferred |
|---|---|
| P3-02 factor validity window | Needs a policy on out-of-window usage + warning semantics |
| P3-03 region specificity scoring | Changes factor selection for existing data |
| P3-04 renewable/on-site scope classification | Accounting-methodology decision (location- vs market-based; captive fossil) |
| P3-06 confidence penalty on fallback matches | Numeric semantics; affects every score |
| P3-07 calculation/hotspot persistence + `CALCULATION_RERUN` audit | Cross-team (P3+P2) schema write path |
| P3-08 sourced/versioned cost data | Needs a P2 cost feed (no tariff entity in contract) |
| P3-09…P3-25 | Biogenic, feedstock, GWP ambiguity, reweight policy, currency, baselines, L-projection, severity vocabulary, H2/H3, etc. — each changes semantics or needs a methodology decision |

Also open: **GA-03** branch protection (requires repo-owner admin — settings in
`docs/phase3/READINESS.md` §1); **P2-04** (populate fixture `source_url`);
**P2-05/J3-Q persistence** (Phase-3 backlog).

---

## 4. Verdict

The four production blockers and every **concrete, deterministic** audit finding
(CRITICAL/HIGH/MEDIUM/LOW that is a defect rather than a methodology choice) are
now closed with executed evidence. The remaining items are methodology/scope
decisions queued with owners; they were **not** silently altered. Non-demo
facilities are now functional end-to-end, so the UI is no longer restricted to
the seed demo.
