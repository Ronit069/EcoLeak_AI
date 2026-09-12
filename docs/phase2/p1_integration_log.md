# P1 — Phase 2 Integration Log

**Role:** P1 (Frontend & UX — Modules A/B/C/N/O frontends)
**Branch:** `phase2-p1-integration` (base: `main`)
**Audience:** P2, P3, P4, and the Phase 1 auditor
**Status legend:** **STABLE** (tested, contract-shaped) · **FLAG-GATED** (real path behind a config flag, mock is default/fallback) · **INCOMPLETE** · **DEVIATION** (documented in `docs/phase2/contract_changes.md`)

Read before coding (done): `contracts/schemas.py`, `contracts/api_contract.md`,
`PHASE1_AUDIT.md` (no `/docs/audit/` folder exists — audit notes live in
`PHASE1_AUDIT.md` + `docs/phase2/contract_changes.md`), and the Phase 2 logs of
the other three teams (`docs/phase2/p2_integration_log.md`,
`docs/phase2/p3_integration_log.md`, `docs/phase2/p4_integration_log.md`,
`docs/phase2/contract_changes.md`).

---

## 1. Inventory: every mock read in the Phase 1 frontend (recorded before changes)

| # | Location | Mock read | Consumed by | Phase 2 live replacement |
|---|---|---|---|---|
| 1 | `frontend/src/lib/api.ts` `fetchDataset()` | `GET /mocks/mock_dataset.json` (via `public/mocks/`) | All pages via `usePhase1Data()` (org/facility/period/processes/activities) | `GET /api/context` (engine router, merged API) + per-group A5/A9/B2/C3 |
| 2 | `frontend/src/lib/api.ts` `fetchHotspots()` | `GET /mocks/mock_hotspot_output.json` | Dashboard, leak map, Processes detail panel | `GET /api/facilities/{id}/reporting-periods/{id}/hotspots` (G2) |
| 3 | `frontend/src/lib/api.ts` `fetchRecommendations()` | `GET /mocks/mock_recommendation_output.json` | Recommendations page, Dashboard "Act first" | `GET .../recommendations` (J2) + `GET /api/recommendations/{id}/explanation` (M1) |
| 4 | `frontend/src/lib/api.ts` `deriveDashboard()` | Derived from mock hotspots+recs (N1 surrogate) | Dashboard KPI strip | `GET .../dashboard` (N1, p4 router) with fallback to derivation |
| 5 | `frontend/src/lib/api.ts` `simulateAdoption()` | Local math (K1 surrogate) | Scenarios page | `POST /api/scenarios/{scenario_id}/simulate` (K1, engine router) |
| 6 | `frontend/src/pages/Processes.tsx` | `dataset.processes` (from 1) | Process mapper table + flow | `GET /api/facilities/{id}/processes` (B2) |
| 7 | `frontend/src/pages/DataInput.tsx` | `dataset.activity_data` (from 1) | Seed records table | `GET .../activity` (C3) |
| 8 | `frontend/src/pages/Profiling.tsx` | `dataset.organization/facilities/reporting_periods` (from 1) | Profile read-only display | `GET /api/organizations/{id}` (A2) + `GET .../facilities` (A5) + `GET .../reporting-periods` (A9) |
| 9 | `frontend/public/mocks/*.json` | Static copies | All of the above in mock mode | Kept as fallback payloads (never deleted) |
| 10 | `frontend/src/lib/api.ts` `DEMO_IDS` | Hardcoded facility/period UUIDs | All API paths | Moved to "bootstrap IDs" resolved from `/api/context` first, hardcoded UUIDs only as mock-mode fallback |

No other direct mock reads exist in `frontend/src`.

---

## 2. The config flag (`USE_MOCK_DATA`) — P1 side

P1 mirrors the shared Phase 2 gate; resolution precedence:

| Priority | Setting | Result |
|---|---|---|
| 1 | localStorage `ecoleak.useMockData` (runtime override, demo toggle in the banner) | `mock` → force mocks; `live` → force live, no fallback |
| 2 | `VITE_USE_MOCK_DATA` build-time env | `true`→mock, `false`→live, `auto`→live-then-fallback |
| 3 | Legacy `VITE_USE_MOCKS` (Phase 1 flag, kept for compat) | `true`→mock, `false`→live |
| 4 | unset | **`auto`** (live first, instant mock fallback per endpoint group) — `main` stays demo-able even if a live endpoint is down |

**Fallback rule (never a blank/crashed screen):** every endpoint group call goes
through `liveOrMock(group, liveFetch, mockFallback)`; in `auto` mode a live
failure (network, 4xx/5xx, Zod shape failure) falls back to the Phase 1 mock
payload for THAT GROUP ONLY and records the group in a shared fallback registry.
`<DemoDataBanner>` renders "Using demo data — live API unavailable for: …" when
any group has fallen back, with a button to force live or force mock mode for
the session.

**Instant rollback:** `localStorage.setItem('ecoleak.useMockData','mock')` (or
`VITE_USE_MOCK_DATA=true` build) restores Phase 1-known-good behavior with no
code change.

---

## 3. Swap status (endpoint group by group)

| Group | Phase 2 live endpoint | Status | Test evidence |
|---|---|---|---|
| 3.1 Dataset/bootstrap | `GET /api/context` (+ A2/A5/A9 reads of those IDs) | **FLAG-GATED** (STABLE in auto) | §5.1 |
| 3.2 Profiling (Module A display) | A2/A5/A9 via context IDs | **FLAG-GATED** | §5.2 |
| 3.3 Process mapper (Module B) | B2 `GET /api/facilities/{id}/processes` | **FLAG-GATED** | §5.3 |
| 3.4 Dashboard / hotspots (Module N+G) | G2 `.../hotspots`, N1 `.../dashboard`, N2 `.../leak-map` | **FLAG-GATED** | §5.4 |
| 3.5 Recommendations (Module J/M) | J2 `.../recommendations`, M1 explanation | **FLAG-GATED** | §5.5 |
| 3.6 Scenario simulator (Module O/K) | K1 `POST /api/scenarios/{id}/simulate`; O1–O7 CRUD **not served by the merged surface** → logged in `contract_changes.md` | **FLAG-GATED** (simulate only) | §5.6 |

---

## 4. Real-data differences handled (beyond hand-authored mocks)

- **18+ recommendations** (real J2 emits the full ranked library) vs 5 in the mock — UI renders arbitrary counts; no `slice(0,3)` on the Recommendations page; dashboard shows top 3 as before.
- **More nulls**: live `contribution_percent`/`carbon_intensity`/`confidence_score` can be `null` — every render path already null-guards (`fmtPct/fmtKg/?? '—'`), Pareto skips null rows with an explicit "unavailable" note (D1 work).
- **Severity labels differ from mock** (Phase 1 B3 decision: Boiler HIGH vs mock CRITICAL) — icons+labels render whatever the API returns; unknown values get the neutral UNKNOWN state.
- **Wider value ranges** (e.g. all-scope totals) — KPI formatting uses Indian numbering; no fixed-width assumptions.
- **P2 PG-table endpoints fail without a live PostgreSQL** — treated as falling back per-group by design (§2), so a partial backend is safe.

---

## 5. Per-group verification (executed, branch `phase2-p1-integration`)

Environment: merged API on `:8000` served with `ECOLEAK_SQL_DSN` → SQLite image of
P2's tables (tools/seed_sql_lite.py). No live PostgreSQL in this env, so P2
DB-backed routers (A2/A5/A9, B2, C3) hang at connect — **exactly the failure
class the per-group fallback exists for**. Playwright E2E scripts:
`tests/e2e_phase2_smoke.mjs` (live + fallback legs) and the per-page probes
below. Screenshots: `.impeccable/review/p2-live.png`, `p2-fallback.png`.

| Group | Live endpoint | Live result (API up) | Fallback result (API down / P2-DB down) |
|---|---|---|---|
| 3.1 Dataset/bootstrap | `GET /api/context` | ✅ 200, org/facility/period consumed | ✅ mock_dataset.json via `/mocks/` — full dataset incl. processes/activities |
| 3.2 Profiling (A) | A2/A5/A9 via context IDs | ✅ org "Shakti Textiles… Surat" rendered, source labelled | ✅ same page, demo-data provenance |
| 3.3 Process mapper (B) | B2 `.../processes` | ✅ when PG present; **this env: connect hangs → fallback** | ✅ 6 processes render, flow chips, hotspot detail (Boiler), banner lists `processes` |
| 3.4 Dashboard (N/G) | G2 hotspots, N1 dashboard, N2 leak-map | ✅ 7/7: Boiler, N1 live badge, all-scope total `72,02,350 kgCO₂e`, scope label from response, live J2 cards | ✅ 7/7: derived KPIs `5,65,050 kgCO₂e`, Boiler rail, Pareto, mock recs |
| 3.5 Recommendations (J/M) | J2 + M1 | ✅ 18 ranked cards render (live library size, not mock's 5); explanation endpoint consumed | ✅ mock 5 cards render |
| 3.6 Scenario simulator (O/K) | K1 `POST /api/scenarios/{id}/simulate` | ✅ "K1 live simulation" notice + 18 sliders + projected gauges | ✅ "Local Module-K math" notice, same rules |

**Mode legs (executed):**
- `LIVE MODE (auto, API up)` — 7/7 PASS (`live-leg`).
- `FALLBACK MODE (auto, API down)` — 7/7 PASS; banner text:
  `live API unavailable for: dataset, hotspots, recommendations, processes, activities, dashboard`
  then mocks render with zero page errors.
- `FORCED MOCK` (localStorage `ecoleak.useMockData=mock`) — banner labels
  "USE_MOCK_DATA is forced to mock mode", frozen payloads render.
- Per-page probes (all 5 routes, real data): no page errors; /scenarios
  K1 notice + 18 sliders; /processes Dyeing+Boiler+Packaging; /data seed rows;
  /recommendations 18 RANK chips; /profiling org row.

---

## 6. Accessibility & empty-state re-test on real data volumes

- **Color never alone (re-tested on real G2/N2/J2 output):** every severity
  render carries `SeverityBadge` (SVG icon + uppercase word) + line-form rail;
  live severities include HIGH/MODERATE/LOW — all render with icon+label.
- **Real-data nulls:** live `contribution_percent` / `carbon_intensity` /
  `confidence_score` nulls are guarded (`?? '—'`, "share unavailable",
  Pareto skips null rows) — no NaN/blank cells observed in 18-recs rendering.
- **Scale:** 18 recommendations + 18 scenario sliders render without layout
  breakage; processes filter operates on any list length (100+ benchmark
  covered in Phase 1; no virtualization needed at Phase 2 scale — Phase 3
  candidate).
- **Empty-state paths** (no hotspots / no recs): existing notices and Pareto
  "data unavailable" message; unreachable with live data in this env — unit
  logic unchanged from Phase 1.

---

## 7. Issues found during integration (with resolution/owner)

| # | Issue | Resolution | Owner |
|---|---|---|---|
| 7.1 | P2 DB-backed routers (A/B2/C3) **hang** (>15 s) instead of failing fast when PostgreSQL is absent (firewalled port) | P1 added a 5 s `AbortController` timeout on every live call; aborted groups fall back to mocks. A hung backend can no longer freeze the UI (`frontend/src/lib/api.ts` `FETCH_TIMEOUT_MS`) | P1 (fixed); note for P2: fail-fast DB connect check would help |
| 7.2 | `GET /api/context` returns only org/facility/period — **no `processes`/`activity_data` keys**; initial fallback used it and produced empty lists | Fallbacks for B2/C3 now read the frozen `mocks/mock_dataset.json` directly (mock truth), never the context endpoint | P1 (fixed) |
| 7.3 | A non-API origin returning SPA HTML with 200 made the live path "succeed" with junk JSON (when `VITE_API_URL` unset during dev) | `getJson` rejects `content-type: text/html` as an ApiError → auto-fallback engages | P1 (fixed) |
| 7.4 | Live N1 `total_kgco2e` = all-scope 7,202,350 vs dashboard derivation = G2 operational boundary 565,050 | Two different, both-correct boundaries; the UI shows whichever source serves it (`N1 live` badge when N1, else `N1 derived`), and the number is labelled. Logged here for cross-team awareness | P1/P4 (info) |
| 7.5 | O1–O7 scenario CRUD still not served by the merged surface | Logged in `docs/phase2/contract_changes.md` §P1; Phase 2 covers K1 simulate only (+ local math fallback) | P2/P4 (merge decision in progress) |