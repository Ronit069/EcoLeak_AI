# P1 — Phase 2 PR Description

**Branch:** `phase2-p1-integration` → `main`
**Role:** P1 (Frontend & UX)

## What changed

Every mock data call in the Phase 1 frontend is now a **live API call with a
per-group mock fallback** behind the shared Phase 2 `USE_MOCK_DATA` gate — one
endpoint group at a time, tested after each swap (integration log:
`docs/phase2/p1_integration_log.md`).

| Endpoint group | Live endpoint (contracts/api_contract.md) | Swap |
|---|---|---|
| Dataset/bootstrap | `GET /api/context` (merged engine router, additive — logged) | ✅ |
| Profiling | A2/A5/A9 via context IDs | ✅ |
| Process mapper | B2 `GET /api/facilities/{id}/processes` | ✅ |
| Dashboard/leak map | G2 `.../hotspots`, N1 `.../dashboard`, N2 `.../leak-map` | ✅ |
| Recommendations | J2 `.../recommendations`, M1 explanation | ✅ |
| Scenario simulator | K1 `POST /api/scenarios/{id}/simulate` (O1–O7 CRUD not yet served — logged in `contract_changes.md`) | ✅ |

## Key behaviors

- **`USE_MOCK_DATA` flag (P1 side):** `auto` (default) → live first, instant
  mock fallback per group; `mock`/`live` via `VITE_USE_MOCK_DATA` or the
  runtime localStorage override; legacy `VITE_USE_MOCKS` still honored.
- **Never a blank/crashed screen:** every group fetch has a 5 s timeout and a
  frozen-mock fallback; a "Using demo data" banner lists exactly which groups
  fell back, with Force-live / Force-mock / Auto controls.
- **Real-data hardening:** non-JSON responses rejected; N1-vs-derived boundary
  (all-scope vs operational) is surfaced honestly; 18 live recommendations and
  18 scenario sliders render; null severity/contribution/intensity guarded;
  severity stays icon+label (never color-only).
- **Phase 1 flow intact:** `VITE_USE_MOCK_DATA=true` (or the banner toggle)
  restores the frozen-mock demo exactly — `main` stays demo-able mid-audit.

## Verification (executed)

- Live leg (merged API on `:8000`, SQLite-seeded P2 tables): **7/7** checks.
- All 5 page groups on real data: no page errors; 18 rec cards; K1 live notice;
  18 sliders; processes/activities fallback banner correct.
- Fallback leg (API down): **7/7** — dashboard renders mocks + banner.
- Forced-mock mode: banner labels mode, frozen payloads render.
- `tsc --noEmit` clean · `npm run build` clean · backend python suite unaffected.

## Files

`frontend/src/lib/api.ts` (flag, timeout, fallbacks, live endpoints) ·
`frontend/src/pages/Dashboard.tsx` (Phase 2 hook) · `frontend/src/App.tsx`
(DemoDataBanner + mode toggle) · `frontend/src/pages/{Processes,DataInput,
Profiling,Recommendations,Scenarios}.tsx` (live data consumption) ·
`docs/phase2/p1_integration_log.md` · `docs/phase2/contract_changes.md` §P1 ·
`tests/e2e_phase2_smoke.mjs`.

## Notes for the audit / teammates

- P2 routers require live PostgreSQL; without it their groups fall back to
  mocks **by design** — the banner states exactly which.
- No frozen contract shape changed; the only additive endpoints are
  `/api/context` (Phase 1 merged work) and `GET /api/emission-factors/lookup`
  (P2, not consumed yet).
- Scenario CRUD (O1–O7) remains client-side until the merged surface serves it.