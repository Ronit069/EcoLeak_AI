# P3 — Phase 2 Integration Log

**Role:** P3 (Carbon Accounting & Simulation Engine — Modules F/G/K/L, stretch H)
**Branch:** `phase2-p3`
**Base:** `7f5ead4` (`main`, Phase 1 merged + P2 Phase 2 groundwork)
**Audience:** P1, P2, P4, and the Phase 1 auditor
**Status legend:** **STABLE** · **FLAG-GATED** · **STRETCH** · **DEVIATION**

Read first (done before coding): `docs/phase2/p2_integration_log.md`,
`docs/phase2/contract_changes.md`, `PHASE1_AUDIT.md`. No `/docs/audit/` folder
exists; the Phase 1 audit lives at repo-root `PHASE1_AUDIT.md`.

---

## 1. What Phase 2 changed (P3)

| # | Deliverable | Status | Where |
|---|---|---|---|
| 1 | Phase 1 mock baseline captured as regression reference | ✅ | `docs/phase2/p3_baseline_output.json` |
| 2 | P3 mock-to-real swap behind an explicit boolean flag | ✅ FLAG-GATED | `engine/data_source.py`, `engine/service.py` |
| 3 | Real-data run + field-for-field shape diff vs baseline | ✅ | `tools/phase2_p3_shape_diff.py`, `docs/phase2/p3_real_data_output.json`, `docs/phase2/p3_shape_diff.md` |
| 4 | Missing-factor / unresolved re-verified on real data | ✅ | `tests/test_phase2_real_source.py` |
| 5 | Module H (Anomaly) — stretch, not blocking | ✅ STRETCH (unchanged from Phase 1) | `engine/anomaly.py` |

**No frozen contract change.** `contracts/schemas.py` and `contracts/api_contract.md`
were not touched. See §6.

---

## 2. The config flag (`USE_MOCK_DATA`)

Phase 1 (via `engine/data_source.default_data_source`) selected the source purely
by `ECOLEAK_SQL_DSN` presence, which is not an explicit on/off gate. Phase 2 adds a
real boolean flag without breaking the Phase 1 behavior:

Precedence in `engine/data_source.resolve_use_mock_data`:

1. explicit argument to `default_data_source(...)` / `build_engine(...)`
2. `ECOLEAK_USE_MOCK_DATA` env (`1/true/yes/on` = mock, `false/no/off` = real)
3. **unset → legacy Phase 1 rule**: DSN present → SQL, else mock

| Setting | Result |
|---|---|
| `ECOLEAK_USE_MOCK_DATA=true` | Phase 1 mock fixture — **even if a DSN is set** |
| `ECOLEAK_USE_MOCK_DATA=false` | `SQLActivityDataSource` over P2 tables (requires `ECOLEAK_SQL_DSN`/`ENGINE_DSN`); raises if no DSN |
| unset, no DSN | mock (safe default — `main` stays demo-able) |
| unset, DSN set | SQL (legacy behavior preserved) |

`engine.service.build_engine(use_mock_data=..., dsn=..., config=...)` is the single
bootstrap entry point. `backend/app/services/engine_bridge.py` (P2-owned) continues
to use `Settings.use_mock_data`; its real path picks `ENGINE_DSN or DATABASE_URL`
and constructs the same `SQLActivityDataSource`. P3's flag and P2's flag agree.

**Instant rollback:** `USE_MOCK_DATA=true` (or just don't set a DSN) restores
Phase 1's known-good mock behavior with no code change.

---

## 3. How "real data" is exercised here

P2's runtime contract is the **database** (P2 tables), not an HTTP hop:
`engine_bridge` builds a fresh `EcoLeakEngine` over `SQLActivityDataSource`, which
reads the same table/column names as `backend/app/models/*`.

This environment has no PostgreSQL, so the integration run seeds a **portable
SQLite image of those exact tables** with:

- facility / process / activity rows from the frozen dataset, and
- **P2's real seeded emission factors** (`backend/app/seed/real_factors.json`:
  CEA India grid, DEFRA diesel/NG/LPG/petrol, UK grid, IPCC AR5 refrigerants).

That is the identical code path the merged API takes when `USE_MOCK_DATA=false`;
only the DB engine differs (SQLite vs PostgreSQL). Evidence for the SQL path is
also pinned by existing `tests/test_sql_source.py` (6 tests).

---

## 4. Baseline vs real — results (values differ, shape does not)

Artifacts: `docs/phase2/p3_baseline_output.json` (mock) and
`docs/phase2/p3_real_data_output.json` (real factors). Fixed `generated_at` so the
baseline is reproducible.

### Module F — Carbon Accounting

| Metric | Mock baseline | Real factors | Note |
|---|---|---|---|
| Scope 1 | 224,250 | 225,560.8 | DEFRA NG 2.0384 vs mock 2.022; DEFRA diesel 2.6594 vs mock 2.68 |
| Scope 2 | 340,800 | 340,800 | CEA 0.71 == mock 0.71 |
| Scope 3 | 6,637,300 | **0** | real seed has **no Scope-3 factors** → 7 unresolved |
| Operational (S1+S2) | 565,050 | 566,360.8 | +1,310.8 (**+0.23%**, matches `tests/test_real_factors.py`) |
| Unresolved rows | 2 | **7** (`MATERIAL/WATER/WASTE/TRANSPORT`) | explicit, never fabricated |
| Data-quality score | 81.88 | 89.33 | fewer resolved-but-uncertain rows |

### Module G — Hotspots (what P4 consumes)

| Process | Mock (live engine) | Real (live engine) | Rank |
|---|---|---|---|
| Boiler | HIGH 76.36 | HIGH 76.41 | 1 |
| Dyeing | MODERATE 52.02 | MODERATE 52.22 | 2 |
| Drying | LOW 31.93 | LOW 32.06 | 3 |
| Finishing | LOW 26.66 | LOW 26.78 | 4 |
| Packaging | LOW 8.71 | LOW 8.76 | 5 |

**Rank order is identical; severity labels are identical; JSON shape is
field-for-field identical.** The frozen mock file shows Boiler `CRITICAL 88.5`
(a Phase 1 B3 decision: the mock is illustrative, not a reproduction target — see
`PHASE1_AUDIT.md` §1). No new drift introduced by Phase 2.

### Module K — Simulator

| Metric | Mock baseline | Real factors |
|---|---|---|
| Baseline kgCO2e | 7,202,350 | 566,360.8 |
| Projected kgCO2e | 7,141,874.5 | 553,296.8 |
| CO2 saving | 60,475.5 | 13,064 |
| Payback (y) | 5.29 | 10.7 |

The mock baseline includes Scope 3 (which the real seed cannot resolve), so the
absolute numbers differ — expected and documented. Shape (`ImpactAssessment`) is
identical, and `payback`/`unavailable` semantics are unchanged.

### Module L — Circularity

`total_score` = 0 for both (all-virgin inputs, landfill waste — a genuinely linear
SME), `is_internal_metric: true`, disclaimer present, `score_complete: true`.

---

## 5. Edge cases re-verified against real data

| Edge case | Expected | Observed (real) |
|---|---|---|
| Missing emission factor | explicit `unresolved`, no fabricated value | ✅ 7 rows, code `EMISSION_FACTOR_NOT_FOUND` |
| Scope 3 gaps in real factor table | not silently dropped; surfaced | ✅ `MATERIAL/WATER/WASTE/TRANSPORT` unresolved, `scope3 == 0`, `total == operational` |
| Factor provenance retained | every resolved calc carries id/code/version/source/year | ✅ asserted in `test_resolved_factors_keep_provenance` |
| On-site/export double-count | separate ledgers (Phase 1 F) | unchanged; covered by `tests/test_double_counting.py` (P2) + `tests/test_carbon.py` |
| Hotspot with missing benchmark | reweight, ranking never breaks | unchanged; rank order stable on real data |
| Payback when saving ≤ 0 | `UNAVAILABLE`, no number | unchanged (`PAYBACK_UNAVAILABLE`) |
| Circularity out of range / no data | clamp + incomplete label | unchanged |

---

## 6. Contract changes

**None.** `docs/phase2/contract_changes.md` gets an additive P3 note stating no
frozen shape changed. `validate_mocks.py` 9/9 and `validate_against_mock.py`
ALL PASS still hold.

---

## 7. Module H (stretch)

Module H was completed in Phase 1 (`engine/anomaly.py`, IsolationForest, guarded
by `min_samples_for_ml`, rules-only fallback, conservative confidence). Phase 2
did **not** extend it: P2's real seed exposes a single reporting period, so the
honest behavior remains **rules-only** (no ML certainty claim). It is flagged
STRETCH and is not a Phase 2 integration dependency. No change required.

---

## 8. How to run / rollback

```powershell
# Phase 1 mock behavior (default; no DB needed)
python -m pytest tests -q

# Full Phase 2 proof: baseline + real-data run + shape diff
python -m tools.phase2_p3_shape_diff

# Real engine against P2 tables (PostgreSQL)
$env:USE_MOCK_DATA="false"; $env:ECOLEAK_SQL_DSN="postgresql+psycopg://user:pass@host/ecoleak"
python -c "from engine.service import build_engine; e=build_engine(); print(type(e.data_source).__name__)"

# Rollback: unset the DSN or set ECOLEAK_USE_MOCK_DATA=true
```

---

## 9. Verification evidence

| Command | Result |
|---|---|
| `python -m pytest tests -q` | **140 passed** (127 pre-existing + 13 new) |
| `python validate_mocks.py` | 9/9 PASS |
| `python validate_against_mock.py` | ALL SHAPE CHECKS PASSED |
| `python -m tools.phase2_p3_shape_diff` | all sections `IDENTICAL`; edge cases PASS |
| new tests | `tests/test_data_source_flag.py` (7), `tests/test_phase2_real_source.py` (6) |

---

## 10. Known divergences / risks (values, not shape)

1. **Scope 3 unresolved on real factors** — P2's Phase-2 seed has no Scope-3
   factors. This is honest (no fabrication) but means inventory totals differ from
   the mock by an order of magnitude until P2 seeds materials/water/waste/transport
   factors. **Action for P2, not a P3 shape issue.**
2. **Factor-set divergence** — DEFRA NG/diesel shift operational totals +0.23%.
   Already a recorded Phase 1 B3 decision; carried forward.
3. **Hotspot severity vs frozen mock** — pre-existing Phase 1 decision (mock
   illustrative). P4 should key on rank/contribution/shape, not on the mock's
   numeric severity labels.
4. **SQLite vs PostgreSQL** — the integration image proves the read path and
   column mapping; P2's PG-backed CI remains the authoritative DB test (deferred
   in the Phase 1 audit to a PG CI service).
