# P3 Phase 2 — Shape Diff (mock baseline vs P2 real data)

- Generated: `2026-09-12T12:00:00+00:00`
- Diff is **shape-only** (keys + scalar types); numeric values are expected to differ.
- Baseline: `mocks/mock_dataset.json` (Phase 1 engine output).
- Real: `SQLActivityDataSource` over P2 table names, seeded with `backend/app/seed/real_factors.json` (the `USE_MOCK_DATA=false` path).

## Section shape diff

| Section | Shape | Mismatches |
|---|---|---|
| `meta` | IDENTICAL | - |
| `F_carbon` | IDENTICAL | - |
| `G_hotspots` | IDENTICAL | - |
| `K_simulation` | IDENTICAL | - |
| `L_circularity` | IDENTICAL | - |

## Edge cases re-verified on real data

- Unresolved calculations present: **True** (`7` rows) — missing factors produce explicit `unresolved`, never fabricated values.
- Unresolved issue codes: `['EMISSION_FACTOR_NOT_FOUND']`
- Unresolved activity categories: `['MATERIAL', 'TRANSPORT', 'WASTE', 'WATER']`
- Every resolved factor carries provenance (id/code/version/source/year): **True**

## Result

**PASS — no shape drift.** The live P2-data path is field-for-field compatible with the Phase 1 mock output that P1/P4 consume.
