# PR: P2 Phase 2 — Backend Platform & Data Engine

**Branch:** `phase2-p2` → `main`
**Base:** `de22e60` (Phase 1 merged)
**Scope:** Phase 2 for P2 (dependency root). No direct pushes to `main`.

## Summary

1. **Integration log** for P1/P3/P4: `docs/phase2/p2_integration_log.md`.
2. **Mock-to-real gate:** `USE_MOCK_DATA` (default `true`) so `main` can fall back
   to Phase 1's known-good mock behavior instantly. Exposed on `GET /api/health`.
3. **Module P real integration** behind the flag: pulls live F (inventory),
   G (hotspots), J (recommendations) and L (circularity); each section degrades
   independently to `UNAVAILABLE` instead of breaking the report.
4. **Volume + edge-case verification** of ingestion/normalization/factors:
   108-row messy dataset → 48 accepted, 60 rejected, 12 warnings,
   24 INFO conversions; all four severities explicit.
5. **Audit verification** on real ingested data: `FILE_IMPORT` +
   `ACTIVITY_IMPORTED` per accepted row + `ACTIVITY_CREATED` on manual entry.
6. **Double-counting re-verified:** on-site generation and exported electricity
   stay in separate ledgers and out of Scope 1/2/3 totals.

## Contract

- **No frozen contract changes** (`contracts/schemas.py`, `contracts/api_contract.md`
  untouched). Details in `docs/phase2/contract_changes.md`.
- Additive-only: `/api/health`, `/api/emission-factors/lookup`,
  `/api/ingestion/batches/{import_id}`, `GET /api/reports`, INFO `UNIT_CONVERTED`,
  `ACTIVITY_IMPORTED` audit event, extra `report_meta`/`scope_summary` keys.

## Audit-ready endpoints

Stable: A1–A9, B1–B5, C1–C4, D1–D2, E1–E4, I1–I3, P2, P3 (json/csv), plus additive
lookup/import-batch/report-list/platform-health.

## Flagged unstable / incomplete

- `P3 export?format=pdf` → `501` (Phase 3).
- Module P `recommendations` section → `UNAVAILABLE` if P4 ranker raises
  (report still generates; P4 to confirm J stability).
- Auth is the Phase 1 stub (JWT out of scope).

## Verification

- `python -m pytest -q` → **54 passed** (backend, `ecoleak_test`).
- `python -m tools.messy_ingestion_check` → **PASS**
  (`total=108 accepted=48 rejected=60 warnings=12`, `imported_audit_rows=48`).
- `python validate_mocks.py` → **9/9**.

## Rollback

Set `USE_MOCK_DATA=true` (default) — Module P returns to Phase 1 mock behavior
with no code change. No migrations added in this PR.
