# EcoLeak AI — Frontend Phase 1 (Operate)

Vite + React 18 + TypeScript + Zod + React Router + React Hook Form + D3. Renders frozen Phase 0 mocks; swaps to live P2/P3/P4 API without component rewrites.

## Routes

| Route | Module | Source (Phase 1) | Live swap |
|---|---|---|---|
| `/` Dashboard + leak map | N (+G) | `mock_hotspot_output.json` + derived from `mock_recommendation_output.json` | G2 hotspots, J2 recommendations, N1 dashboard, N2 leak-map |
| `/recommendations` | J/M | `mock_recommendation_output.json` | J2 + J3 PATCH + M1 explanation |
| `/processes` | B | `mock_dataset.json.processes` + hotspot mock (D3 flow builder, node detail panel, `carbon_impact_level` stub) | B1–B5 |
| `/data` | C/D | `mock_dataset.json.activity_data` + local queue + client CSV preview | C1–C4, D1, D2 |
| `/profiling` | A | `mock_dataset.json` org/facility/period, React Hook Form + Zod profile form | A1–A9 |
| `/scenarios` | O/K | local adoption math (Module K rules) | O1–O7, K1–K3 |

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (mocks from public/mocks/)
npm run build    # tsc + vite build → dist/
npm run preview  # serve dist
```

Mock mode is default (`VITE_USE_MOCKS=true`). Live: set `VITE_USE_MOCKS=false` + `VITE_API_URL` — only `src/lib/api.ts` changes.

## Still mocked (Phase 1)

| Piece | Mocked endpoint that replaces it when live |
|---|---|
| Hotspots (dashboard, leak map, process details) | `GET /api/facilities/{id}/reporting-periods/{id}/hotspots` (G2) |
| Recommendations / cards / shortlist | `GET .../recommendations` (J2), `PATCH /api/recommendations/{id}` (J3), `GET .../explanation` (M1) |
| Dashboard summary KPIs | `GET .../dashboard` (N1) — circularity card is "Unavailable" until `L1` ships; intensity is proxied from largest hotspot until N1/F3 |
| Leak map | `GET .../leak-map` (N2) — `links` stay `[]` in Phase 1; drill-down (facility→process→activity) is client-side D3 over hotspots + `activity_data` |
| Profile CRUD (A1/A3/A7/A8), process CRUD (B1–B5), scenario (O1–O7/K1–K3), data import (C4), normalize (D1), data-quality (D2) | All local — see `CONTRACTS_README.md` under **Phase 1 change requests** |
| Reports PDF | `P3` returns `501` in Phase 1 |

## Contract fidelity

- `src/lib/contracts.ts` mirrors `contracts/schemas.py` field names.
- `src/lib/zod.ts` mirrors ranges/enums (`confidence 0–100`, `adoption 0–100`, `end_date ≥ start_date`, `working_days ≤ 366`, `working_hours ≤ 24`, `currency ^[A-Z]{3}$`, strict unknown-key rejection + `asset_id`).
- `profileFormSchema` + React Hook Form validate Module A client-side exactly like Pydantic.
- Only `rank`, `process_name`, `intervention_code/title`, `explanation`, `impact` are treated as response-only.
- Import preview renders the `ValidationIssue[]` shape (severity, code, message) from §23 — no server parsing.
- Simulator rules: `payback = CAPEX/saving (null when ≤ 0)`, projected floored at 0.

## Verification

- `npx tsc --noEmit` clean, `npm run build` clean.
- `python ../validate_mocks.py` → 9/9 PASS (contracts untouched).
- Functional passes (Playwright): D3 drill facility→process→activity, CSV preview + validation issues, all six routes no console errors.
- Captures in `.impeccable/review/`: `desktop.png`, `mobile.png`, per-route desktop shots, `desktop-drill.png`, `desktop-import.png`.
