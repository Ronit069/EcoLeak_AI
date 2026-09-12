# PR — P3 Phase 2: P2 real-data swap behind `USE_MOCK_DATA` (branch `phase2-p3`)

## Summary

Swap P3's (Modules F/G/K/L) data source from the Phase 0/1 mock JSON to P2's real
runtime data (the P2 tables read by `SQLActivityDataSource`), behind an explicit
`USE_MOCK_DATA` flag that **defaults to the Phase 1 mock**. No frozen contract
field or response shape changed.

- Base: `main` @ `7f5ead4`
- Branch: `phase2-p3`
- Rollback: set `ECOLEAK_USE_MOCK_DATA=true` (or leave no DSN) → byte-identical
  Phase 1 mock behavior, no code change.

## What's in this PR

| Area | Change |
|---|---|
| Flag | `ECOLEAK_USE_MOCK_DATA` + `build_engine()`; default mock; legacy DSN behavior preserved |
| Baseline | `docs/phase2/p3_baseline_output.json` (Phase 1 mock run) |
| Real run | `docs/phase2/p3_real_data_output.json` (P2 tables + real factors) |
| Proof | `tools/phase2_p3_shape_diff.py` → `docs/phase2/p3_shape_diff.md` |
| Edge cases | missing-factor/unresolved re-verified on real factors |
| Docs | `docs/phase2/p3_integration_log.md`, this file |
| Tests | `tests/test_data_source_flag.py`, `tests/test_phase2_real_source.py` |

## Shape stability (why P1/P4 are unaffected)

Shape diff is **field-for-field identical** across `F_carbon`, `G_hotspots`,
`K_simulation`, `L_circularity` between the mock baseline and the real-data run.
`HotspotDetectionResult` still validates against the frozen contract. `validate_mocks.py`
9/9 and `validate_against_mock.py` ALL PASS.

## Module G stability statement (for P4)

> G's `HotspotDetectionResult` envelope and per-item field set are unchanged from
> Phase 1. On the real factor set the hotspot **rank order is identical**
> (Boiler → Dyeing → Drying → Finishing → Packaging), contributions still sum to
> 100%, and the top hotspot remains Boiler. Numeric scores/severity bands shift
> only because real DEFRA/CEA factors differ from the illustrative mock — this is
> the Phase 1 B3 decision already recorded in `PHASE1_AUDIT.md`, not new drift.
> P4 can consume the live G2 output with no code change; it should key on
> `rank`, `contribution_percent`, and `hotspot_score`, not on the mock's numeric
> severity labels.

## Known, documented divergences (values only)

1. P2's real Phase-2 seed has **no Scope-3 factors** → 7 Scope-3 activities resolve
   to explicit `unresolved` (never fabricated). Operational Scope 1+2 total moves
   565,050 → 566,360.8 (+0.23%). **Follow-up for P2** to seed Scope-3 factors.
2. Hotspot severity numeric labels differ from the frozen mock (Phase 1 decision).
3. SQLite image used for the local proof; P2's PostgreSQL CI remains authoritative.

## Test plan

```powershell
python -m pytest tests -q                    # 140 passed
python validate_mocks.py                     # 9/9
python validate_against_mock.py              # ALL PASS
python -m tools.phase2_p3_shape_diff         # all sections IDENTICAL
```

## Checklist

- [x] Do not touch `main` (branch only)
- [x] Swap behind a config flag, mock default
- [x] No frozen contract change; drift would be logged in `contract_changes.md`
- [x] Integration log written (`docs/phase2/p3_integration_log.md`)
- [x] G output confirmed stable for P4
- [x] Module H flagged STRETCH (unchanged)
