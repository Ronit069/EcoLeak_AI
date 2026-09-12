# Phase 4 — Bugs Found (P4 demo/polish pass)

**Owner:** P4 · **Date:** 2026-09-12 · **Base:** `main` @ `d4a5ee8`
**Rule:** functional bugs are logged here, not silently fixed. Only presentation copy was changed
in this branch (`phase4-p4`), and it is called out as FIXED below.

| ID | Sev | Area | Summary | Status |
|---|---|---|---|---|
| BUG-4-01 | **MEDIUM** | Reports (live mode) | Unresolved-factor rows render without category/unit in the judge-facing report | OPEN — owner P1 (UI) / P2 (payload) |
| BUG-4-02 | **MEDIUM** | J2 vs K1 | Per-intervention CO₂ saving differs between recommendation cards and simulator detail | OPEN — known P3-15 |
| BUG-4-03 | LOW | Explanations | Stale/awkward copy in the deterministic explanation template | **FIXED (copy-only, this branch)** |
| BUG-4-04 | LOW | Dashboard vs K1 | "Potential saving" on the dashboard is a standalone sum; K1 is interaction-aware — different numbers | OPEN — display semantics; script explains |
| BUG-4-05 | LOW | Demo artifact | Committed live artifact uses fixture baselines while the API derives baselines from activity data (<1% delta) | OPEN — owner P4 |
| BUG-4-06 | **HIGH** | Dashboard (live mode) | Clicking a process bar in the Carbon Leak Map crashes the page (activity-level reads `dataset.activity_data`, absent in live mode) | **FIXED (read-path wiring, this branch)** |
| BUG-4-08 | **HIGH (demo) / MEDIUM (logic)** | K1 simulator | CAPEX does not scale with adoption; adoption=0 keeps the capital cost, so sliders can never fit a scenario to budget | OPEN — owner P3 (logged, not fixed) |
| BUG-4-09 | MEDIUM | Reports (live mode) | Provenance list slices the first 8 rows while unresolved rows are appended last, hiding the very rows the notice points to | **FIXED (ordering, this branch)** |

Already-fixed Phase-3 P4 findings (not re-logged, cross-ref `docs/phase3/final_audit_summary.md`):
P4-C1/GA-01 (non-demo facility 500s), P4-H1 (negative-net recycling crash), P4-H2 (Module P mock
financials), P4-M1 (invalid `feedback_type` 500).

---

## BUG-4-01 — MEDIUM — Report unresolved rows lose their labels in live mode

**Location:** `frontend/src/pages/Reports.tsx:143-145` reads `p.activity_category` and
`p.normalized_unit` at the top level of a provenance entry; the **live** payload
(`backend/app/services/engine_bridge.py::real_inventory` appends
`{"status": "UNRESOLVED", **u.to_issue()}`, where `to_issue()` nests
`details: {activity_category, activity_subcategory}`) has no top-level category/unit.
The mock path (`backend/app/services/reports.py::_factor_provenance`) *does* provide top-level
keys, which is why the issue is invisible in mock mode.

**Observed (PG, clean seed):** the two unresolved entries carry
`details.activity_category` = `MATERIAL` (dyeing chemicals) and `WASTE` (wastewater), but the
report page would render `UNRESOLVED —  ()` because the top-level keys are absent.
Probe output captured in `var/p4_j2_explanations.txt` session log.

**Suggested fix (one line, UI):** in `Reports.tsx` use
`p.activity_category ?? p.details?.activity_category` and
`p.normalized_unit ?? p.details?.normalized_unit` (or flatten the issue in the bridge).
No contract change. Owner: P1 (reader) with P2 (payload) — not fixed in this audit branch.

## BUG-4-02 — MEDIUM — J2 card saving vs K1 simulator saving use different bases

**Location:** `p4/financial.py` (recommendation estimate) vs `engine/simulator.py` (scenario
simulation). Example on the demo seed: `INT-CAIR-011` shows **22,152 kgCO₂e/yr** on its
recommendation card but **45,309 kg** in the K1 selection detail for the same intervention.

**Effect:** both are deterministic and defensible, but a judge comparing the two screens sees
different per-intervention numbers. Already logged as **P3-15** (MEDIUM) in `docs/phase3/p3_audit.md`.

**Mitigation:** the demo script uses K1 **totals** for scenario claims and J2 **totals** for the
dashboard, never per-item side-by-side. Fix owner: P3 (align saving bases or label them).

## BUG-4-03 — LOW — Explanation template copy (FIXED in this branch)

**Location:** `p4/explainability.py::TemplateExplainer`. Two presentation defects found by the
Phase 4 adversarial pass over all 18 real explanations:

1. The stale assumption sentence "deterministic carbon estimate until the P3 engine supplies
   verified baselines" — the P3 engine **is** live; the sentence undersold the product.
2. "payback 0.00 years" on the zero-CAPEX recommendation — now reads
   "payback immediate (zero CAPEX)".

**Fix:** copy-only string changes (plus a basis-aware price label derived from
`assumptions.data_is_stub`). No numeric logic touched. Verified: 42 P4 tests pass, both demo
artifacts regenerated with shape gates PASS, all explanations re-read.
**Evidence:** `p4/demo/output/demo_explanations.live.md`, `tests/test_explainability.py`.

## BUG-4-04 — LOW — Dashboard "potential saving/reduction" is a standalone sum, not the K1 plan

**Location:** `p4/api.py::_dashboard_payload` sums `impact.estimated_*` across all recommendations
(₹6,699,475 / 317,736 kgCO₂e on the demo seed); the K1 simulator applies interventions
sequentially and yields ₹4,209,868 / 284,640 kgCO₂e for all 18 at 100%. Both are honest but
different semantics.

**Effect:** a sharp judge could ask why the dashboard and scenario numbers differ.
**Mitigation:** the script answers it explicitly ("upper-bound sum vs non-double-counted
simulation"). Consider labelling the gauge "sum of standalone estimates" in a later pass.
Owner: P4.

## BUG-4-05 — LOW — Committed live artifact is fixture-context, API is activity-derived

**Location:** `p4/demo/output/demo_recommendation_output.live.json` is generated by
`python -m p4.demo.run_demo --use-mock-data false`, which passes the fixture `demo_context.json`,
while the merged API's `build_facility_context` aggregates resource baselines from live
`activity_data`. Values differ by <1% (e.g., steam-trap saving ₹484,450 artifact vs ₹481,950 API).

**Effect:** P1/P4 referencing the artifact may quote numbers a few rupees off from the live app.
**Suggested fix:** add an API-path artifact generator (or document the artifact as
fixture-context only). Owner: P4, later pass.

## BUG-4-06 — HIGH — Carbon Leak Map activity drill crashes in live mode (FIXED here)

**Location:** `frontend/src/pages/Dashboard.tsx` (passes only `dataset` to `DrillMap`) +
`frontend/src/components/DrillMap.tsx:96` (`dataset.activity_data.filter(...)`).

**What's wrong:** live mode bootstraps `dataset` from `GET /api/context`
(`frontend/src/lib/api.ts::fetchDataset`), whose payload has no `activity_data` field
(only `organization`, `facilities`, `reporting_periods`). Clicking a process bar switches
the map to activity level, `dataset.activity_data` is `undefined`, the `.filter` call
throws, and React unmounts the dashboard. Mock mode is unaffected (frozen dataset has
`activity_data`), which is why the Phase 3 closure probe (process view only) passed.

**Observed:** Playwright live dry run — after facility click the process view renders;
after the first process-bar click the `<svg>` disappears and the page loses the app
(`locator.textContent: Timeout … waiting for svg`), no explicit error shown to the user.

**Fix (this branch):** Dashboard now merges the already-fetched `activities` group into the
dataset passed to `DrillMap` (`activity_data: activities ?? dataset.activity_data`).
Read-path wiring only; no calculation or contract change. Verified by the automated dry
run reaching the activity view and asserting `Activities under Boiler` + gas/diesel rows.

**Why it matters:** a judge clicking the leak map in the live demo would blank the dashboard.
Severity HIGH per the demo-safety rule; logged before the fix as required.

---

## BUG-4-08 — HIGH (demo) / MEDIUM (logic) — K1 CAPEX ignores adoption; sliders can't reach a budget

**Location:** `engine/simulator.py:226` (`total_capex = sum(s.capex …)`) and `:448-450`
(`capex = capex_override or _capex_point(iv)`; no multiplication by `adoption_percentage`).
Adoption correctly scales the resource fractions (`:389-407`) but not capital.

**Observed (executed, JWT live stack):**

| Scenario sent to K1 | capex | annual saving | projected | payback | over_budget (5M) |
|---|---|---|---|---|---|
| all 18 recommendations @100% | ₹19,040,000 | ₹4,209,868 | 6,919,020.5 kg | 4.52 y | true |
| all 18, 7 big-ticket at **0%** | ₹19,040,000 | ₹3,051,271 | 6,997,741.3 kg | 6.24 y | **true** |
| only the 11 quick wins (removed from the list) | ₹4,540,000 | ₹3,051,271 | 6,997,741.3 kg | 1.49 y | false |

The first two rows have **identical CAPEX** while savings/projection move — adoption scales the
operating benefit, not the capital. (An engine-direct probe including the one non-recommended
intervention shows ₹19,390,000; the UI/K1 total for the 18 recommendations is ₹19,040,000.)

**What the docs say:** Module K "Adoption = 0% → No change"; the UI promise is that adoption
sliders let a factory fit a plan to its budget. At 0% the intervention is not happening, so its
capital cost should not be charged (or the UI needs a remove/deselect control).

**Impact:** the demo cannot show an in-budget plan by lowering sliders — the cap stays ~₹1.9 cr.
The demo script was reworked to the working flow (raise the budget to the plan's true size and
show the engine-verified numbers; adoption ramp shown separately). Owner: **P3** (simulator
capex semantics) — logged, not fixed in this closeout pass.

---

## BUG-4-07 — MEDIUM — Live tenant reads (processes/activities) fall back for the browser

**Location:** `frontend/src/lib/api.ts` (sends only optional `Authorization`; no
`X-Organization-Id`/`X-Role` stub headers) vs `backend/app/services/access.py::require_org_access`
(rejects a principal with `organization_id=None`), while engine/P4 guards explicitly allow
the anonymous stub principal.

**Observed:** in stub mode the demo-data banner lists `processes, activities` even with
PostgreSQL up; in JWT mode (token sent) all groups are live. P1's UI is correct for JWT
deployments; a stub-mode demo shows a partial-fallback banner.

**Suggested fix / decision:** deployment should run `AUTH_MODE=jwt` with a token (P2's
`deployment.md`) — then this disappears; or P2 makes stub-mode tenant reads default to the
seeded tenant exactly as the engine guards do. Not fixed here (P1/P2-owned; logged).

---

*Process note (not a bug):* `GA-03` — branch protection on `main` — was applied and verified on
2026-09-12 (PR required, 1 approval, 4 required CI checks, no bypass, no force-push/delete).
