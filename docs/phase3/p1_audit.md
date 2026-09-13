# P1 — Phase 3 Hardening Audit (Frontend & UX)

| Field | Value |
|---|---|
| **Role** | P1 — Frontend / UX |
| **Base commit** | `origin/main` @ `944ea10` (P2 + P3 audit logs merged) |
| **Method** | Live walkthrough of the built SPA (headless Chromium via `playwright-core`) against the merged API on **real PostgreSQL** with `USE_MOCK_DATA=false` and `AUTH_MODE=jwt` (real Bearer token baked via `VITE_API_TOKEN`); raw-API cross-check; fixture facilities for empty/large states; fallback and total-outage runs. No code changed. |
| **Upstream logs read** | `docs/phase3/p2_audit.md`, `docs/phase3/p2_audit_fasttrack.md`, `docs/phase3/p3_audit.md`. **`docs/phase3/p4_audit.md` does not exist** (not on `main`, `phase3-p2-audit`, or any remote) → every P4-dependent item below is marked **provisional — pending upstream P4 audit**. |
| **Reference doc** | `Industrial_Emission_Database_Security_Edge_Cases.md`; `contracts/api_contract.md` |

Legend: **CRITICAL** breaks the demo/displayed truth · **HIGH** correctness/honesty gap with real exposure · **MEDIUM** edge-case/UX gap · **LOW** cosmetic/wording.

---

## 0. Summary

| ID | Sev | Area | One-line |
|---|---|---|---|
| P1-01 | **HIGH** | Dashboard | Headline "TOTAL EMISSIONS" is all-scope (includes Scope 3) while the header says "SCOPE 1 + SCOPE 2"; hotspot shares use the operational (S1+S2) denominator |
| P1-02 | MEDIUM | Dashboard fallback | KPI strip mixes live and mock sources: total 0 with reduction 185 t / saving ₹19.7 L from mock recs |
| P1-03 | LOW | Dashboard | Division-by-zero renders `∞% of baseline` on a zero-emission facility |
| P1-04 | MEDIUM | API/UI boundary | 5xx responses carry **no CORS / security / X-Request-Id** headers → browser shows `ERR_FAILED`, UI cannot read the frozen error body and mislabels server errors as "API unavailable" (owner P2, P1 impact) |
| P1-05 | MEDIUM | Honesty | Unresolved emission factors (P3 reports 2 for the demo facility) are never surfaced in the UI — and `inventory-summary` doesn't expose them — so totals read as complete |
| P1-06 | MEDIUM | Coverage | No compliance/report screen at all: the SPA has 6 routes, none for Module P report/export, despite the impact goal "support regulatory compliance" |
| P1-07 | LOW | Wording | Process/Dashboard copy says "mock" while showing live data ("from hotspot mock", "in the mock", "the mock showed 5") |
| P1-08 | LOW | Wording | Two different "quality" numbers (81.88 vs 78.4) shown without distinguishing their sources |
| P1-09 | MEDIUM (provisional) | Product/UX | The UI bootstraps only `facilities[0]` — no facility selector, so only one tenant's facility is ever viewable; non-demo facilities hit GA-01 and fall back |

---

## 1. End-to-end walkthrough (live main, real data)

Built with `VITE_API_URL=http://127.0.0.1:8021`, `VITE_USE_MOCK_DATA=auto`, a real `VITE_API_TOKEN`; API on real PG (`USE_MOCK_DATA=false`, `AUTH_MODE=jwt`); served over HTTP (SPA fallback, mocks reachable). Demo facility `0a1b2c3d-0002…`.

| Journey step | Route | Live API calls | Banner | Result |
|---|---|---|---|---|
| Factory profile | `/profiling` | `/api/context` 200 | none | ✅ renders live org/facility/period |
| Process mapper | `/processes` | `/processes` 200, `/activity` 200 | none | ✅ 6 processes; severity/hotspot join live (wording issue P1-07) |
| Data entry | `/data` | `/activity` 200 | none | ✅ 13 records; C1 form present |
| Dashboard | `/` | `/context`,`/processes`,`/activity`,`/hotspots`,`/recommendations`,`/dashboard` all **200** | none | ✅ N1 live; accurate numbers (with scope-label issue P1-01) |
| Hotspot drill-down | `/` | same | none | ✅ rail + table + D3 drill; severity badges word+icon |
| Recommendations | `/recommendations` | `/recommendations` 200 | F-8 fixture-financials notice | ✅ 18 recs, top INT-SCRAP-004 final 77.4 |
| Scenario simulator | `/scenarios` | `POST /simulate` **200** | none | ✅ "Engine-verified simulation (K1) — computed_via=engine"; over-budget notice |
| Compliance report | — | — | — | ❌ **no UI route** (P1-06) |

All requests were `200` with **zero `/mocks/` fetches and zero console errors** on the demo facility → the walkthrough is genuinely live, not mocks.

---

## 2. Detailed findings

### P1-01 — HIGH — Dashboard mixes scope boundaries on the headline KPI
- **Location:** `frontend/src/pages/Dashboard.tsx:154-201` (header scope label vs KPI strip).
- **What's wrong (executed):** header reads `SCOPE 1 + SCOPE 2`; the "TOTAL EMISSIONS" gauge shows N1 `total_kgco2e` = **7,203,660.8 kg** which includes **Scope 3 (6,637,300 kg)**. The largest-leak sub-line (`39.8% of total · 225,561 kg`) is computed against the **operational** denominator (566,360.8 kg, Scope 1+2 from G2). A reader sees 39.8% next to a total ~12.7× larger than the value the percentage is relative to.
- **What the doc says:** cross-cutting rule "Never mix Scope 1/2/3 without labels"; the compliance/reporting goal requires an explicit, labelled boundary. P2's audit item 5 verified the ledger split; P3-04 flags accounting-methodology concerns.
- **Suggested fix:** label the KPI by boundary ("Total incl. Scope 3") or add an operational Scope 1+2 KPI; make the largest-leak sub-line say "of Scope 1+2 (566,361 kg)". Use N1 `scope_breakdown` to drive the label.

### P1-02 — MEDIUM — KPI strip mixes live and mock sources under fallback
- **Location:** `frontend/src/pages/Dashboard.tsx:129-144, 191-200`.
- **What's wrong (executed):** with a non-demo facility (P4-C1 → `recommendations`/`dashboard` 500) the strip shows `TOTAL EMISSIONS 0 tCO₂e` (live, empty) **and** `POTENTIAL REDUCTION 185 tCO₂e` / `POTENTIAL SAVING ₹19,70,000` (from the **mock** recommendation payload). The demo banner names the fallen-back groups, but the strip presents cross-source numbers as one coherent story.
- **What the doc says:** problem goal "every number must be auditable/reproducible"; the banner is the only provenance signal.
- **Suggested fix:** when `sources` are not uniform, derive potential reduction/saving only from live data (or label each KPI "demo data"), and disable the derived math on mismatch.

### P1-03 — LOW — `∞%` on a zero-emission facility
- **Location:** `frontend/src/pages/Dashboard.tsx:194` (`potential_reduction / total_kgco2e`).
- **What's wrong (executed):** empty facility → `TOTAL 0` and `POTENTIAL REDUCTION … | ∞% of baseline`.
- **Suggested fix:** guard `total > 0`; render "—".

### P1-04 — MEDIUM — 5xx responses have no CORS/security/request-id headers (owner P2; P1 impact)
- **Location:** merged API error path (generic `Exception` handler runs at Starlette `ServerErrorMiddleware`, outside `CORSMiddleware` and the security-headers middleware).
- **What's wrong (executed):** `GET …/recommendations` (P4-C1, non-demo) with `Origin: http://127.0.0.1:5174` returns `500` with **no `access-control-allow-origin`** and **no `x-request-id`/security headers**, while the same call returning `200` has them. Browser therefore reports `net::ERR_FAILED` (opaque), the UI cannot read the frozen error JSON, and its banner says "live API unavailable" rather than showing the actual server error. This also means F-14's request-id is absent on the 5xx responses themselves.
- **Suggested fix (P2):** ensure CORS/security headers are applied to handler-generated 5xx (e.g. raise as an HTTP response inside the middleware chain, or set headers in the exception handler / move handlers inside CORS).
- **Provisional?** No — independent of P4's missing log.

### P1-05 — MEDIUM — Unresolved factors are invisible in the UI
- **Location:** Dashboard/Data pages; merged `GET …/inventory-summary` (no unresolved field).
- **What's wrong (executed):** the engine honestly reports unresolved rows (`EMISSION_FACTOR_NOT_FOUND` MATERIAL, `NO_MATCHING_FACTOR` WASTE for the demo facility), and F2 excludes them, but nothing in the SPA says so and `/inventory-summary` doesn't expose the count. The headline total therefore reads as complete.
- **What the doc says:** problem goal "every number auditable/reproducible"; P3-07/P2-05 require provenance for unresolved inputs.
- **Suggested fix:** expose unresolved counts (extend N1 or F3) and show a badge/list ("2 activities unresolved — factors missing") linking to provenance.

### P1-06 — MEDIUM — No compliance/report screen
- **Location:** `frontend/src/App.tsx:98-106` (routes: `/`, `/recommendations`, `/processes`, `/data`, `/profiling`, `/scenarios`).
- **What's wrong:** Module P report generation/fetch/export exists in the API and is exercised by CI, but there is **no route/UI** to generate, view, or download a report. One of the four problem-statement impact goals ("support regulatory compliance") has no UI surface.
- **Suggested fix:** add a Reports page (generate, list, view provenance/quality, export JSON/CSV) or explicitly declare the report out of UI scope in the contract.

### P1-07 — LOW — Stale "mock" wording in live mode
- **Location:** `frontend/src/pages/Processes.tsx:83` (`'from hotspot mock'`), `:106` ("No hotspot for this process in the mock"), `:195` ("hotspot severity shown where the mock matches"); `Dashboard.tsx:258` ("the mock showed 5").
- **What's wrong:** under live data the UI still narrates itself as mock-driven, undermining trust in provenance.
- **Suggested fix:** neutral wording ("from hotspot", "no hotspot for this process") or source-aware copy.

### P1-08 — LOW — Two "quality" numbers, no source distinction
- **Location:** `Dashboard.tsx:160` ("quality 81.88/100" = G2 `data_quality_score`) vs `DataInput` page ("D2 quality 78.4" = period DQ assessment).
- **Suggested fix:** label each ("hotspot data quality" vs "period data completeness").

### P1-09 — MEDIUM (provisional — pending P4 audit) — Single-facility bootstrap; no tenant/facility selector
- **Location:** `frontend/src/lib/api.ts::fetchBootstrapIds` (uses `facilities[0]`), no switcher in `App.tsx`.
- **What's wrong (executed):** the UI only ever shows the first facility returned by `/api/context`. For a non-demo first facility, P4-C1 (`GA-01`) makes J2/N1 500 and the UI falls back to mocks with a banner; other facilities are unreachable from the UI. The product goal's "emission sources visible and actionable" is single-facility only.
- **Suggested fix:** facility/period selector driven by `/api/context`; surface per-group errors distinctly (see P1-04).

---

## 3. Cross-check of upstream findings (resolution status at `944ea10`)

| Upstream item | P1 relevance | Re-check result |
|---|---|---|
| **P2-01** unauth KB reads | none (no UI impact) | resolved in JWT mode per general audit; residual stub-mode only |
| **P2-02** 404-not-401 | none | resolved in JWT mode |
| **P2-03** partial factor audit snapshots | not UI-visible | open (P2) |
| **P3-01** K1 mock-path id coverage | UI: in pure `mock`/offline mode, scenario sliders show local math | UI **does** label `computed_via=local_fallback` (verified in the total-outage run) — honest, but the underlying gap (GA-06) remains |
| **P3-05** period lock on F1 | not UI-visible | open (P3) |
| **P3-07** no calc/hotspot persistence | UI shows recomputed numbers; provenance partial | open (P3/P2); contributes to P1-05 |
| **P4-C1/GA-01** non-demo 500s | **yes** | **live**: non-demo `recommendations`/`dashboard` → 500 → UI falls back with banner; source-mixing bug P1-02; provisional pending P4 log |
| GA-02 stub-in-prod | none (deploy) | open (P2) |

---

## 4. Accessibility re-check (real hotspot data)

- Severity is **not colour-only**: every badge renders an inline SVG **plus the uppercase word** and a `title` (`SeverityBadge`, `badges.tsx:22-33`). Executed sample under live data: `{text:"HIGH", title:"Severity: High", svg:true}`, plus MODERATE/LOW/CRITICAL. ✅
- The ranked rail and the tabular fallback both repeat the severity word; the modal has `aria-hidden` on decorative icons; `role="region"`/`aria-label` present on the KPI strip; `aria-live` on the scenario panel. ✅
- Residual: the drill-down node sizes encode contribution but are `aria-hidden` (decorative); the contribution is repeated in text. Acceptable.

## 5. Empty / large-data states (real data)

- **Zero processes:** `/processes` shows "0 processes" (empty, no crash); `/data` "0 activity records"; dashboard honest `0 tCO₂e · no data yet`, intensity "—", largest "none yet", circularity "Unavailable". ✅ — except P1-02/P1-03 (mock-rec mixing and `∞%`).
- **100+ processes:** facility with **121 processes** rendered fully; the "Filter processes" control is present; no console errors beyond the P4-C1 500s. ✅ (No virtualisation; acceptable at 121, could degrade at thousands.)

## 6. Mock-fallback flag

- **Live path:** no banner, zero `/mocks/` fetches, all `200`. ✅ not silently on.
- **Partial fallback:** demo banner shown, naming the fallen-back groups (`recommendations, dashboard`); mock payloads fetched `200`. ✅
- **Total outage (API down):** banner names all six groups; app renders fully from mocks (`/mocks/mock_dataset.json` etc. `200`). ✅ clear safety net.
- **Distinct from the F-8 notice:** the Recommendations page additionally shows the fixture-financial-baselines notice (`data_is_stub=true`) — correctly labelled, not the fallback banner.

## 7. Displayed-vs-raw number cross-check (demo facility)

| KPI | Raw API | Displayed | Match |
|---|---|---|---|
| Total | `total_kgco2e` 7,203,660.8 | `7,203.7 tCO₂e` / `72,03,661 kgCO₂e` | ✅ (scope label issue P1-01) |
| Carbon intensity | `7203.6608` | `7203.7` | ✅ |
| Largest leak | Boiler, 39.8263%, 225,560.8 kg | `#1 Boiler · 39.8% · 2,25,561 kgCO₂e` | ✅ |
| Circularity | `0` | `0.0` | ✅ |
| Potential reduction | `317788.75` (= Σ J2 `estimated_co2_saving_kg`) | `317.8 tCO₂e · 4.4%` | ✅ |
| Potential saving | `7036275` (= Σ J2 `estimated_annual_saving`) | `₹70,36,275` | ✅ |
| Budget / CAPEX | `null` / Σ capex `19,040,000` | `—` / `₹1,90,40,000` | ✅ |
| Scenario projected | K1 `assessment.projected` 6,918,356.2 | `6,919 tCO₂e` (baseline `7,203.7`) | ✅ |

No rounding/mislabel beyond P1-01; no stale-cache drift observed (all fetches hit the API; `mockCalls=[]`).

---

## 8. Notifications

- **P4 —** none new beyond **GA-01/P4-C1** (non-demo 500s); the UI impact is P1-09/P1-02. Tracked by issue #5.
- **P2 —** **P1-04** (5xx missing CORS/security/request-id headers) and **P1-05** (expose unresolved counts). P1-04 also affects any browser API consumer.
- **P3 —** P1-05 depends on surfacing unresolved inputs (P3-07 provenance); no new P3 item.
- **P1 owner of record —** P1-01, P1-02, P1-03, P1-06, P1-07, P1-08, P1-09.

---

## 9. End-to-end status verdict

**NOT safe to present beyond the seed demo as-is.** The seeded demo facility flow is genuinely live and numerically accurate (all API `200`, no mocks, no console errors; every KPI cross-checks), so a **demo of the seed facility** is presentable today with the scope-label caveat (P1-01). But the *full* journey is not production/demo-safe for real tenants:

1. **Upstream fix required first:** **GA-01 / P4-C1** — any non-demo facility gives 500 on Recommendations/Dashboard; the UI then falls back but mixes mock recs with live zeros (P1-02) and prints `∞%` (P1-03).
2. **Fix before a real demo:** P1-01 (scope-boundary mislabel) and P1-04 (5xx header/CORS gap that hides real errors).
3. **Product gaps to schedule:** P1-06 (no compliance report UI), P1-09 (no facility selector), P1-05 (unresolved factors invisible).

All P4-dependent conclusions are **provisional** until `docs/phase3/p4_audit.md` exists.
