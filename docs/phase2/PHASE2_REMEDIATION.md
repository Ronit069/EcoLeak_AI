# Phase 2 — Remediation Report (PHASE2_REMEDIATION.md)

**Branch:** `phase2-fixes` · base `4a56f59` (main)
**Date:** 2026-09-12 · **Method:** every row verified by execution (command + output cited).

## 1. Blocker / deviation status table

| Blocker | Root Cause Confirmed | Fix Applied | Verification Evidence | Status |
|---|---|---|---|---|
| **B1-K1 silent fallback** | ✅ Live J2 emits 18 `intervention_id`s; K1's data source knew only 5 → 404 on 13 → UI silently used local math | (a) Full 19-entry P4 library seeded into the simulator data source (`seed_interventions.py` → SQLite seed images + PG production seed); (b) silent fallback removed: `fetchSimulate` returns `computedVia: 'engine'\|'local_fallback'`; UI shows "Engine-verified simulation (K1)" or "Local Module-K math — computed_via=local_fallback"; failed calls also enter the demo-data banner | K1 POST with **all 18 live J2 ids → HTTP 200**, `assessment` == exact `ImpactAssessment` keys; Playwright: engine-verified notice PASS, no NaN, projected 6,918.4 tCO₂e engine-computed; PG seed reports `circular_interventions: 19` | ✅ CLOSED |
| **B2 PG-only paths** | ✅ No PostgreSQL in shared/dev env; "present, unverified" statuses | Portable PG 16.6 stood up locally; Alembic migrations + production seed executed; permanent CI added (`.github/workflows/phase2-ci.yml`, `postgres:16` service) | backend suite on real PG: **54/54 passed** (contract parity 9 + schema constraints 9 + ingestion volume/audit/double-counting/Module P real + rest); P3 SQL source over real PG: op 566,360.8, aggregations reconcile, 19 interventions; CI file attached | ✅ CLOSED |
| **B3 git hygiene** | ✅ `7f5ead4` (P2) + `a0a6aa9` (P3) pushed direct to main; branches after the fact | Recorded in `docs/phase2/process_notes.md`; branch protection **attempted via gh API** — 404, account is push-only → exact required settings documented for owner Ronit069; CI added so future direct pushes still run the PG gates | `gh api` outputs captured in process_notes §2; workflow file attached | ✅ RECORDED (owner action outstanding for GitHub-side enforcement) |
| **B3 placeholder guard** | ✅ `change-me-in-production` default silently runnable | `backend/app/config.py` `_enforce_jwt_secret`: placeholders rejected in ALL envs; non-development without `JWT_SECRET` refuses to start | 4-case execution: prod-no-secret → `ValidationError` (refuses); placeholder even in dev → `ValidationError`; real secret in prod → starts; dev default → starts. Backend suite still 54/54 after change | ✅ CLOSED |
| **B3 sequencing gate** | ✅ baseline+swap+diff were one-commit each (order unprovable) | Re-ran the documented sequence live; timestamped artifacts saved: `p3_baseline_output_verified_20260912-130454.json`, `p3_real_data_output_verified_*.json`, `p4_baseline_output_verified_*.json`, `p4_real_data_output_verified_*.json`; shape diffs regenerated (all sections IDENTICAL) | `tools/phase2_p3_shape_diff.py` + `phase2_p4_shape_diff.py` executed, PASS output captured | ✅ CLOSED |
| **B3 Module H/Q limbo** | ✅ H2/H3 no router; Q no router | Decision: Q1/Q2 **wired** into merged surface (`p4/api.py`, in-memory store, frozen error shape); H2/H3 → Phase-3 backlog owner P3; Q persistence → Phase-3 backlog owner P2 | Q1 201 / Q2 200 / REJECTED-without-reason → 422 `FEEDBACK_VALIDATION` frozen shape (`tests/test_remediation.py` 4/4) | ✅ CLOSED (decisions recorded) |
| **C1 N1 `production_unit`** | ✅ Undocumented additive key | **Accepted into permanent contract**: `DashboardResponse` model added to `contracts/schemas.py`; api_contract.md N1 row updated; P1 TS type updated | `test_remediation.py::test_n1_*` PASS (incl. scope sum == total) | ✅ CLOSED |
| **C2 K1 wrapper shape** | ✅ Undocumented wrapper vs bare ImpactAssessment | **Canonical decision = wrapper envelope**: `ScenarioSimulationEnvelope` formalized in `schemas.py`; api_contract.md K1 row updated (200 synchronous; 202 reserved for job endpoints); P1 coded against canonical shape | `test_remediation.py::test_k1_*` PASS; live curl all-18 → 200 | ✅ CLOSED |

## 2. Stakeholder disclosure — did the K1 silent fallback affect shown output?

**Yes, it fired in every UI run since the Phase-2 P1 swap, and one prior claim was misleading.**

- **What fired:** every scenario-slider interaction in the Phase-2 era sent all 18 live J2 `intervention_id`s to K1; 13 were unknown to the engine's data source → K1 returned 404 → the UI fell back to local Module-K math. So **no engine-verified K1 number was ever displayed by the scenario page** during Phase 2 or the audit.
- **Was it invisible?** Partially visible: the page displayed a "Local Module-K math" notice and the demo-data banner could list `scenario-simulate`, so a careful viewer could detect it. But it was **not** prominent enough and was not surfaced in the completion summary.
- **Prior claim corrected:** the Phase-2 P1 completion summary stated scenarios were verified with a "K1 live…" notice; the underlying check was an OR-match between the two notices and actually matched the *local-math* notice. That summary over-stated verification. Correction in this document.
- **Audit evidence that WAS genuine:** the PHASE2_AUDIT B2 trace's K1 curl used a single engine-known id (INT-WHR `…0011`) and returned genuine engine output (200 + `assessment`) — that record stands.
- **Stakeholder artifacts:** no shipped screenshot/PDF/report ever presented engine-computed scenario numbers; the only rendered artifacts were dashboard captures (`p2-live.png`), which are unaffected.
- **Now:** K1 with all 18 ids returns 200 engine output, `computedVia` is explicit in the UI, and any future failure is banner-visible. This disclosure is also filed in `docs/phase2/contract_changes.md` (R1/R4) and this report.

## 3. Remaining open items (explicit, owned)

| Item | Owner | Why open |
|---|---|---|
| GitHub branch protection applied (admin) | Ronit069 (repo owner) | Requires admin rights; exact config documented in `process_notes.md` §2; CI gate already exists |
| H2 (GET anomalies) + H3 (ack) routers | P3 (Phase 3) | Needs anomaly persistence table in the merged surface |
| Q SQLAlchemy persistence | P2 (Phase 3) | In-memory append-only store wired now; persistence is a P2-owned store swap |

## 4. Final verdict

**Phase 2: 100% COMPLETE** — every blocker and contract deviation in PHASE2_AUDIT.md
is now ✅ with executed evidence (commands and outputs above; suite counts 164 root /
54 PG / 4 remediation contract / 7+7 E2E legs). The only outstanding items are the
three explicitly owned follow-ups in §3, none of which block Phase-2 functionality —
and GitHub-side branch protection, which is an admin action, not a code gap.