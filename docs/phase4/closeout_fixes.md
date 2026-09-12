# Phase 4 Closeout — Fix Log (`closeout_fixes.md`)

**Branch:** `phase4-closeout` (from `phase4-p4`, merged with `main` @ `f10c59d`)
**Scope:** only BUG-4-01, the two pending links, and demo-safety read-path fixes logged before
being applied. No calculation, ranking, contract, or dependency changes.

## Fixes applied in this closeout

| # | Bug | File(s) | Change | Type |
|---|---|---|---|---|
| FIX-1 | BUG-4-01 (MEDIUM) | `frontend/src/pages/Reports.tsx` | Live report payload nests unresolved-row category/subcategory under `details`; the UI read top-level keys and rendered empty labels. Now reads both shapes (`p.activity_category ?? p.details?.activity_category`, same for unit; falls back to the subcategory) | **read-path only** |
| FIX-2 | BUG-4-09 (MEDIUM) | `frontend/src/pages/Reports.tsx` | The bridge appends UNRESOLVED rows last and the list sliced the first 8, so the rows the notice points to were hidden. Unresolved rows are now shown first (still capped at 8) | **display ordering only** |
| FIX-3 | BUG-4-06 (HIGH) | `frontend/src/pages/Dashboard.tsx` | Live mode bootstraps `dataset` from `/api/context` (no `activity_data`); clicking a process bar called `dataset.activity_data.filter(...)` and crashed the page. Dashboard now merges the separately-fetched `activities` group into the dataset passed to `DrillMap` | **read-path wiring only** |

### What evidence caused each fix

- **BUG-4-01 / BUG-4-09:** live report payload has `factor_provenance` entries
  `{code, field, status, message, severity, details:{activity_category, activity_subcategory}}`
  (`backend/app/services/engine_bridge.py` appends `u.to_issue()`); `contracts/api_contract.md`
  only requires a "full report payload" and does not formalize the entry, so the backend shape
  was left untouched and the frontend read path was corrected. Playwright dry run now finds
  `UNRESOLVED — MATERIAL · Dyeing chemicals…` and `UNRESOLVED — WASTE · Wastewater…`.
- **BUG-4-06:** `frontend/src/lib/api.ts::fetchDataset` live branch returns `GET /api/context`
  (`{organization, facilities, reporting_periods}`); `DrillMap` activity level requires
  `activity_data`. Verified by the dry run reaching `Activities under Boiler` with gas + diesel.

## Pending-link status (checked 2026-09-12)

- **P2 `docs/phase4/deployment.md`: NOT LANDED** (`docs/phase4/` is still absent on `origin/main`;
  no `phase4-p2` branch exists). The live-URL placeholder in `demo_script.md` is retained and
  marked; the demo has been verified on a production-like local stack instead (JWT + PostgreSQL
  + built frontend). When the URL lands: paste it into `demo_script.md` §Header and §3, then run
  the 5-step smoke in `final_verification_report.md` §5.
- **P3 `docs/phase4/trust_summary.md`: NOT LANDED.** `pitch_appendix.md` §2 continues to cite the
  merged Phase 3 audits (`final_audit_summary.md`, `fix_report.md`, `p3_audit.md`) and carries a
  one-line note to swap in the direct link when P3 publishes.

## Confirmed-only (no change, per instructions)

- **BUG-4-02 / P3-15:** J2 per-item CO₂ saving vs K1 per-item saving use different bases
  (e.g. `INT-CAIR-011`: 22,152 vs 45,309 kg). Confirmed open on current main; correctly logged
  as a known non-blocking item. The demo script avoids showing both side by side.
- **BUG-4-08:** K1 CAPEX ignores adoption (identical capex at 100% and 0%: ₹19,040,000).
  Logged with executed evidence; the demo script was reworked to the verified budget-raise flow.
- **BUG-4-07:** stub-mode tenant reads fall back for the browser (P2 `require_org_access` vs
  anonymous stub principal); disappears under `AUTH_MODE=jwt` (verified all groups live).

## Verification of the fixes (executed)

| Check | Result |
|---|---|
| `npm --prefix frontend run build` (tsc + vite) | PASS |
| Full UI dry run (JWT, PG, built frontend) | **all steps PASS**, `JS issues: none` — see `final_verification_report.md` §5 |
| Report unresolved labels on screen | PASS (`evidence/05-reports-unresolved-fixed.png`) |
| Drill-down activity view on screen | PASS (`evidence/02-drill-activity.png`) |
| Root suite (clean clone + fresh venv) | 191 passed |
| Backend suite (fresh PG) | 80 passed |

**No dependency drift:** `frontend/package.json`, `frontend/package-lock.json`,
`package.json`, `requirements.lock` are byte-identical to `main` (an npm `--prefix` artifact that
briefly added a self-referential `ecoleak-root-tools` dependency was reverted before commit).
