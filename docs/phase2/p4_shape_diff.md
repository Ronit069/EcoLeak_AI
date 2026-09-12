# P4 Phase 2 — Shape Diff (mock baseline vs live P3 hotspots on real data)

- Generated: `2026-09-12T12:00:00+00:00`
- Diff is **shape-only** (keys + scalar types); numeric values are expected to differ.
- Baseline: `mocks/mock_hotspot_output.json` + mock factors (Phase 1 logic).
- Real: P3 Engine G over `SQLActivityDataSource` (P2 table names) seeded with `backend/app/seed/real_factors.json` — the `USE_MOCK_DATA=false` path.
- Ranker inputs are identical except the hotspot envelope and the derived resource factors.

## Section shape diff

| Section | Shape | Mismatches |
|---|---|---|
| `meta` | IDENTICAL | - |
| `J_recommendations` | IDENTICAL | - |
| `diagnostics` | IDENTICAL | - |

## Factor selection notes (live KB)

- `diesel_per_litre`: EF-FUEL-DIESEL-BLEND-DEFRA2023, EF-FUEL-DIESEL-MINERAL-DEFRA2023 — identical priority; deterministic tie-break is `factor_code` ascending (logged, not silent).

## Real-data edge checks

| Edge case | Result | Detail |
|---|---|---|
| budget=0 returns no-CAPEX action (no crash) | PASS | 1 recommendation(s), all zero-CAPEX=True, codes=['INT-NOCAPEX-019'] |
| duplicate recommendations deduplicated | PASS | 18 unique codes; duplicates_removed=['INT-CAIR-011 (x4 hotspots, kept best CO2e saving)', 'INT-LED-008 (x4 hotspots, kept best CO2e saving)', 'INT-NOCAPEX-019 (x5 hotspots, kept best CO2e saving)', 'INT-RAIN-013 (x2 hotspots, kept best CO2e saving)', 'INT-SOLAR-002 (x4 hotspots, kept best CO2e saving)', 'INT-VFD-007 (x2 hotspots, kept best CO2e saving)'] |
| unknown LLM intervention rejected, ranking unchanged | PASS | explanation_sources={'template_fallback': 18} |
| validated LLM narratives used, ranking unchanged | PASS | explanation_sources={'llm': 18} |
| contradictory number rejected for every item, regenerated, ranking unchanged | PASS | contradicted=18, regenerated=18, explanation_sources={'llm': 18} |
| prompt injection in untrusted text ignored | PASS | explanation_sources={'template_fallback': 18} |

## Result

**PASS — no shape drift and all real-data edge checks pass.** The recommendation envelope P1 consumes is unchanged on live P3 hotspot input.
