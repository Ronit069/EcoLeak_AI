# Phase 3 — General (cross-cutting) Audit

> **Scope note.** This is a **general pass**, not one of the four role audits.
> The shared context arrived without a role-specific prompt, so this file
> intentionally avoids the reserved names (`p2_audit.md`, `p3_audit.md`,
> `p4_audit.md`, `p1_audit.md`) and covers **cross-cutting / resolution**
> questions only. A role-specific audit follows separately.

| Field | Value |
|---|---|
| **Base revision** | `main` @ `1d27f20` (PR #1 merged; includes the T0-1/T0-2/T0-3 auth + CI + health work) |
| **Role audits cross-checked** | `docs/phase3/p2_audit.md`, `docs/phase3/p2_audit_fasttrack.md` (branch `phase3-p2-audit`), `docs/phase3/p3_audit.md` (merged, PR #3) |
| **Reference doc** | `Industrial_Emission_Database_Security_Edge_Cases.md` (repo root — the shared-context path `/contracts/Database_Security_Edge_Cases` does not exist; see GA-07) |
| **Method** | Live merged API against real PostgreSQL 16.2 with `AUTH_MODE=jwt`; executed non-demo facility reproduction; executed auth probes in JWT and stub modes; executed F1-on-LOCKED-period; executed mock-path K1; config boot probe. No code changed. |
| **Revision caveat** | Both role audits were produced **before** the readiness fixes merged (`p2` at `a0dfd01`, `p3` at `10c2b9f`). Their security findings are therefore re-checked here at `1d27f20`. |

Legend: **CRITICAL** breaks a downstream module or is demo/compliance-breaking ·
**HIGH** correctness/security gap with real exposure · **MEDIUM** edge-case or
deployment-risk · **LOW** documentation/process.

---

## 0. Summary

| ID | Sev | Area | One-line | Status |
|---|---|---|---|---|
| **GA-01** | **CRITICAL** | P4 (`p4/api.py`) + P2 (`engine_bridge.py`) | Non-demo facilities: `GET …/recommendations` and `GET …/dashboard` → **500**; Module P recommendations section silently `UNAVAILABLE` | **Still open at `1d27f20`** (re-confirmed) |
| **GA-02** | **HIGH** | Auth config | Production can boot with `AUTH_MODE=stub` → trusted-header auth in prod, no fail-closed guard | Open |
| **GA-03** | **HIGH** | Governance | Branch protection on `main` still not configured even though PR #1 merged | Open |
| **GA-04** | **MEDIUM** | P3 F1 | Calculation endpoint recalculates a `LOCKED` period (cross-ref P3-05) | **Still open at `1d27f20`** |
| **GA-05** | **MEDIUM** | P2 D1 | `POST /api/units/normalize` labels the family base unit when an explicit different `to_unit` is given | Open (not in P2 log) |
| **GA-06** | **LOW** | P3/P4 K | Default mock path still cannot simulate library-only intervention ids (cross-ref P3-01) | **Still open at `1d27f20`** |
| **GA-07** | **LOW** | Process/docs | Shared-context contract path is wrong; `/docs/audit/` still absent | Recorded |

---

## 1. Detailed findings

### GA-01 — CRITICAL — Non-demo facilities break J2/N1 and lose the Module P recommendations section
- **Location:** `p4/api.py:75` (`_facility_and_org()` → `mocks/mock_dataset.json`), `p4/api.py:105,112` (`_run_ranker` passes mock facility + `demo_context.json`), `p4/api.py:71` (`_context()`); secondary instance `backend/app/services/engine_bridge.py:94,96`.
- **What's wrong (executed at `1d27f20`, real PG, JWT auth):** created a genuinely non-demo org/facility/period/process/activity; then
  - `GET …/hotspots` → **200**, `GET …/leak-map` → **200** (engine paths fine)
  - `GET …/recommendations` → **500 `INTERNAL_ERROR`**
  - `GET …/dashboard` → **500 `INTERNAL_ERROR`**
  - `POST …/reports` → 202, but the report's `recommendations.status` = **`UNAVAILABLE`** with `ValueError: context.facility_id does not match facility.id`
  - Demo facility control calls remained **200** (`recs=18`).
  Root cause (already diagnosed by P2 fast-track): `_run_ranker` pairs **live** hotspots for the requested facility with the **mock demo** facility/context, so `p4/engine.py:162` correctly raises. P4 shipped the correct helpers (`p4/data_source.py::load_facility_dataset`, `resource_factors_from_factors`) but `p4/api.py` does not call them.
- **What the doc says:** Module J/N must serve any facility (contract J2/N1 are tenant-scoped, not demo-scoped); Module P report must carry recommendations; problem statement goal "emission sources visible and actionable" fails for any non-seed facility; auditability goal fails because the section silently disappears (P2 secondary logs no reason into the user-facing report beyond `UNAVAILABLE`).
- **Impact / downstream:** blocks P4's own module for real tenants; P1's Recommendations/Dashboard pages show errors or fall back; Module P reports omit recommendations for every non-demo tenant.
- **Suggested fix:** in `p4/api.py::_run_ranker`, resolve org/facility/processes via `p4/data_source.load_facility_dataset(get_engine(), facility_id)` and resource factors via `resource_factors_from_factors(engine.data_source.get_emission_factors(), facility.country)`, and build/derive the `FacilityContext` for the requested facility (or pass `None` to use the engine's documented fallback). Keep the `p4/engine.py:162` guard. Apply the same to `backend/app/services/engine_bridge.py::real_recommendations`. Add a regression test using a second facility.
- **Cross-ref:** `p2_audit_fasttrack.md` P4-C1/P4-H2 (owner P4 primary, P2 secondary). **Still unfixed at HEAD.**

### GA-02 — HIGH — Production can boot with `AUTH_MODE=stub` (no fail-closed guard)
- **Location:** `backend/app/config.py` (`Settings._enforce_jwt_secret`).
- **What's wrong (executed):** `ENVIRONMENT=production AUTH_MODE=stub JWT_SECRET=<real>` → `Settings()` **boots** with `auth_mode=stub`. The validator only enforces a secret for `jwt` mode and for non-development without a secret; it never rejects `stub` outside development. Combined with the stub branch of `get_current_principal` (trusted `X-Role` / `X-Organization-Id` headers), a production deployment that omits `AUTH_MODE=jwt` accepts spoofed identity — including `X-Role: SYSTEM_ADMIN` admin writes (verified earlier in the full-system pass).
- **What the doc says:** DB doc §24 requires real authentication on every endpoint; the shared Phase-2/3 rule is that `stub` is a Phase-1 dev device, and the readiness work made JWT the production path.
- **Suggested fix:** refuse to start when `environment != "development"` and `auth_mode == "stub"` (optionally behind an explicit `ALLOW_STUB_AUTH=true` escape hatch for demos), mirroring the existing JWT-secret fail-fast.
- **Owner:** P2 (config/security). **Cross-cutting** (all routers).

### GA-03 — HIGH (process/control) — Branch protection on `main` still not configured
- **Location:** GitHub repository settings (`main`).
- **What's wrong (executed):** `gh api repos/Ronit069/EcoLeak_AI/branches/main/protection` → **404**, including after PR #1 merged (`1d27f20`). Nothing prevents force-pushes/deletions or merging with red checks.
- **What the doc/process says:** `docs/phase3/READINESS.md` §1 records the exact required rule (require PR + 1 approval + the four `EcoLeak CI` checks; block force-push/deletions) as the one open readiness gate item.
- **Suggested fix:** repo owner applies the rule (settings in `READINESS.md` §1). Acting account is push-only.
- **Owner:** Ronit069.

### GA-04 — MEDIUM — F1 recalculates a LOCKED reporting period (cross-ref P3-05)
- **Location:** `engine/api.py` `POST …/calculations`; `ReportingPeriod.status` never read by the engine.
- **What's wrong (executed at `1d27f20`):** set the seeded period to `LOCKED` directly in PG, then `POST /api/facilities/…/reporting-periods/<locked>/calculations` → **200** (should be blocked). Status restored to `DRAFT` afterwards.
- **What the doc says:** `api_contract.md` F1 — "period not LOCKED/CLOSED unless versioned"; DB doc integrity rule #2.
- **Suggested fix:** read the period; reject with the frozen error shape (`409 PERIOD_LOCKED`) unless an explicit versioned override is supplied; record the event.
- **Owner:** P3 (already logged as P3-05; re-confirmed open at HEAD).

### GA-05 — MEDIUM — D1 normalize mislabels explicit target units
- **Location:** `backend/app/services/units.py` `normalize()` — `label = _FAMILIES[to_family][0]` is the family **base** label, while the value is converted to the requested `to_unit`.
- **What's wrong (executed):** `POST /api/units/normalize {"value":1,"from_unit":"kWh","to_unit":"MWh"}` → `{"normalized_value":"0.001","normalized_unit":"kWh"}` — value in MWh, label says kWh. Silent 1000× misinterpretation risk for any consumer that trusts the label.
- **What the doc says:** D1 response contract includes `normalized_unit` as the unit of `normalized_value`; DB doc §4 requires original/normalized pairs to be unambiguous.
- **Suggested fix:** label with the actual target unit (`to_unit`) when one is supplied; keep the family base label only for implicit normalization; add a test asserting value/unit consistency.
- **Owner:** P2 (not in `p2_audit.md`).

### GA-06 — LOW — Mock-path K1 cannot simulate library-only ids (cross-ref P3-01)
- **Location:** `mocks/mock_dataset.json` (`circular_interventions`: 5) vs `p4/interventions/intervention_library.json` (19); `engine/api.py::simulate` resolves against `data_source.get_interventions()`.
- **What's wrong (executed at HEAD, `USE_MOCK_DATA=true`):** simulate with library-only id `0a1b2c3d-0025-4025-8025-000000000025` → **404 `NOT_FOUND`**; mock-known id `0a1b2c3d-0011-4011-8011-000000000011` → **200**. So the default mock fallback still drops 14 of 19 ids and P1 falls back to local math.
- **What the doc says:** shared Phase-2 rule — the demo must be able to drop to the known-good mock instantly; K1 contract expects the scenario's interventions to resolve.
- **Suggested fix:** mirror the 19-entry library into `mocks/mock_dataset.json`, or resolve unknown ids from the P4 library in `simulate`; assert `computedVia == 'engine'` on the **mock** leg.
- **Owner:** P3/P4 (already logged as P3-01; re-confirmed open at HEAD).

### GA-07 — LOW — Documentation/process hygiene
- The shared context references `/contracts/Database_Security_Edge_Cases`; no such path exists. The authoritative file is repo-root `Industrial_Emission_Database_Security_Edge_Cases.md` (`contracts/` contains `api_contract.md` and `schemas.py`). Anyone following the context literally would fail to find the reference doc.
- `/docs/audit/` still does not exist (audit artifacts live at repo root and `docs/phase3/`). Already recorded by P2 and P3; noted, not re-litigated.

---

## 2. Upstream-finding resolution matrix (at `1d27f20`)

Only items this pass actually executed are rated; the rest are marked
"not re-checked" to avoid over-claiming.

| Upstream item | Audited at | Re-check at `1d27f20` | Result |
|---|---|---|---|
| P2-01 unauth KB reads (`/emission-factors`, `/interventions`) | `a0dfd01` | Executed, JWT mode: **401** `UNAUTHORIZED` | **Resolved in JWT (production) mode.** Residual: still `200` in `stub` mode (dev) → see GA-02 |
| P2-02 auth-not-first (404 vs 401 on `/reports/{id}`, `/ingestion/batches/{id}`) | `a0dfd01` | Executed, JWT mode: **401** for both | **Resolved in JWT mode** |
| P2-03 partial factor audit snapshots | `a0dfd01` | not re-checked | Open per P2 log |
| P2-04 NULL `source_url` on 8 fixtures | `a0dfd01` | not re-checked | Open per P2 log |
| P2-05 / P3-07 calc+hotspot persistence, no `CALCULATION_RERUN` | `a0dfd01` | not re-checked | Open per P2/P3 logs |
| P2-06 / P3-05 period lock not on F1 | `a0dfd01` | Executed: LOCKED period → **200** | **Still open** (GA-04) |
| P3-01 K1 mock-path id coverage | `10c2b9f` | Executed: library-only id → **404** | **Still open** (GA-06) |
| P3-02…P3-25 (remaining) | `10c2b9f` | not re-checked this pass | Rely on `p3_audit.md` |
| P4-C1 / P4-H2 (fast-track) | `10c2b9f` | Executed: non-demo recommendations/dashboard → **500**; report recs `UNAVAILABLE` | **Still open** (GA-01) |

---

## 3. Notifications (per the CRITICAL rule)

- **P4 — CRITICAL (GA-01, owner):** `p4/api.py::_run_ranker`/`_facility_and_org`/`_context` hardcode the demo facility/context; every non-demo tenant gets 500 on J2/N1. Fix with the existing `p4/data_source.py` helpers. Tracking: **issue #5**, PR #4.
- **P1 — CRITICAL (consumer):** Recommendations/Dashboard are only safe for the seeded demo UUID until GA-01 is fixed; non-demo renders will error or fall back. The mock banner keeps the demo green in the interim.
- **P2 — HIGH/MEDIUM:** GA-01 secondary instance (`engine_bridge.real_recommendations` loses the Module P recommendations section for non-demo facilities); GA-02 (fail-closed auth mode for non-development); GA-05 (D1 unit labeling).
- **P3 — MEDIUM/LOW:** GA-04 (F1 period lock, your P3-05) and GA-06 (mock-path K1 id coverage, your P3-01) re-confirmed open at HEAD.

---

## 4. Verdict (general pass)

- One **CRITICAL** is live at current `main`: **GA-01** (non-demo facilities break `recommendations`/`dashboard` and silently lose the report's recommendations section). It blocks P4's and P1's real-tenant paths and should be fixed first in the follow-up pass.
- Two **HIGH**: **GA-02** (production can boot with stub auth) and **GA-03** (branch protection still unapplied).
- One **MEDIUM** silent-correctness gap not previously logged: **GA-05** (D1 unit mislabel).
- Two re-confirmed open upstream issues: **GA-04** (P3-05) and **GA-06** (P3-01).
- P2's two security findings (**P2-01**, **P2-02**) are **resolved in JWT mode**; their residual exposure is folded into GA-02.

This general pass is complete. The role-specific audits (P4, then P1, then joint
synthesis) remain outstanding per the ORDER.
