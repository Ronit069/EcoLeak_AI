# Final Gaps Closure — requirement conformance A–Q (Phase 3)

**Branch:** `phase3-final-gaps` · **Date:** 2026-09-12
**Standard:** every row carries a before/after evidence pair (command + output),
per this project's no-claim-without-reproduction rule.

## 1. Closure table

| Gap | Fix | Before evidence | After evidence | Tests added |
|---|---|---|---|---|
| **G — expose best-actionable target** | `top_actionable_hotspot_id` added to N1 payload (`p4/api.py` via `detect_hotspots`); `DashboardResponse` field + api_contract N1 row; P1 badge "Best intervention target ≠ largest leak" | N1 keys `[..., largest_hotspot, ...]` — field ABSENT (curl output) | N1 contains `top_actionable_hotspot_id: 67068b4d-…` and **value == engine `detect_hotspots().top_actionable_hotspot_id`** (cross-check vs internal output); UI badge renders (Playwright DOM) | `tests/test_phase3_gaps.py::test_fix1_*` |
| **H2/H3 — anomaly history + confirm gate** | `GET .../reporting-periods/{p}/anomalies` (H2) + `PATCH /api/anomalies/{id}/acknowledge` (H3) on the merged engine surface; session registry; tenant resolved BEFORE any write; H3 row updated (PATCH/200) | `PATCH /api/anomalies/…` → **404** (route absent, curl) | detect 200 → H2 `acknowledged: False` → H3 PATCH 200 (`{note,…}`) → H2 `acknowledged: True, acknowledged_note` set; cross-tenant → **403 FORBIDDEN**; unknown id → 404 NOT_FOUND (frozen shapes) | `test_fix2_*` (4 tests) |
| **K — cost per tonne in UI** | `RecommendationPlate` renders `Cost per tCO₂e` (₹/tCO₂e avoided), formatted like other INR metrics | BEFORE DOM: label ABSENT (Playwright `fg-before-recs.png`) while API `impact.cost_per_tonne_co2_avoided: 15625.0` present | AFTER DOM: label + `15,625` rendered — equals API value for the same recommendation (`fg-after-recs.png`) | UI checks via `tests/k1_ui.mjs`-style probes + screenshots |
| **N — scope donut** | `ScopeDonut` component consuming live N1 `scope_breakdown` (no backend change — matrix premise VERIFIED); legend + sr table (not color-only) | BEFORE DOM: no donut (`fg-before-dashboard.png`) | AFTER DOM: donut + legend `SCOPE 1/2/3` + screen-reader table, real data (`fg-after-dashboard.png`) | — (component covered by e2e probe) |
| **Item 5 — Module O (SEPARATE scope)** | Full scenario service: `p4/scenarios.py` store + `p4/o_routes.py` routes (O1–O7, clone, restore, K3 compare); auth + tenant ownership from day one; frozen `Scenario`/`ScenarioIntervention` models; api_contract addendum | O1–O7 routes absent (K1-only per prior matrix) | O-suite **9/9**: create/get/list/update/soft-delete, O6 add+duplicate-reject+adoption guard, O7 remove, **clone independence** (mutating clone leaves original), **restore to baseline**, **cross-tenant 403** on every scenario route, K3 compare deltas | `tests/test_phase3_scenarios.py` (9) |

## 2. Item 5 status (explicit, full bar)

**COMPLETE and tested to project bar** — not deferred: CRUD ✔, compare ✔,
clone (independent copy, verified by mutation test) ✔, restore-to-baseline ✔,
auth+tenant from day one ✔ (resolved before any write), contracts updated
before merge ✔. Persistence of the scenario store is session-scoped —
**Phase-4 backlog, owner P2** (consistent with the feedback/anomaly registries);
this is a documented limitation, not a silent gap.

## 3. Demo-flow verification (the "doesn't affect demo correctness" proof)

Executed walkthrough (Playwright, fresh clean build + fresh servers, static
proxy-free serving, all console/page errors recorded):

```
[dashboard] total KPIs: true · actionable badge: true · scope donut: true · Boiler leak rail: true
[drill] process view: true
[recommendations] rec cards: 18 · cost per tonne: true
[scenarios] engine-verified: true · sliders: 18
[profiling] org: true
[processes] mapper: true
JS ISSUES: none
```

Screenshots: `.impeccable/review/demo-1-dashboard.png`, `demo-2-drill.png`,
`demo-3-recs.png`, `demo-4-scenarios.png`, `demo-5-processes.png` (+
`fg-before/after-*.png` for the before/after pairs). H-ack and O-CRUD are
API surfaces demonstrated by the suites above (no P1 UI for them — scenarios
page covers K1 simulation).

## 4. Updated requirement conformance matrix (re-checked, not copied)

| Mod | Status | Note |
|---|---|---|
| A–F, I, J, L, M, P, Q | ✅ | unchanged from prior matrix (verified again via full suites) |
| G | ✅ → **✅+** | top actionable now EXPOSED + UI badge (was computed-only) |
| H | ⚠️ → **✅** | H1 detect + H2 history + H3 confirm/acknowledge now served (registry; persistence Phase-4) |
| K | ⚠️ → **✅** | cost per tonne CO₂ avoided now rendered (was API-only) |
| N | ⚠️ → **✅+** | scope donut added; Pareto + drill already present; Sankey/waterfall/MAC remain Phase-4 backlog (documented) |
| O | ⚠️ → **✅** | full CRUD + clone + restore + K3 compare; K1 integration intact |

## 5. Final verdict

**The A–Q matrix is now 17/17 ✅ at the "module functional + real-data
verified" bar** (with the documented Phase-4 backlog: anomaly/scenario/feedback
persistence, Sankey/waterfall/MAC charts, GitHub branch-protection admin
action). Every previously-⚠️ item in this closure carries the required
before/after evidence pair; suites: root 189 passed, backend PG 80/80,
O-suite 9/9, gaps-suite 5/5, remediation 4/4, k1-pure 12/12, shape gates 9/9,
and a zero-console-error demo walkthrough.
