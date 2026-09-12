# P2 Phase 3 — Step 0 Fast-Track: P4-C1 / P4-H2

**Owner:** P2 (Backend Platform & Data Engine)
**Branch:** `phase3-p2-audit`
**Base:** `main` @ `10c2b9f`
**Mode:** Step 0 only; full checklist in `p2_audit.md`.

> **Artifact caveat.** The referenced `docs/phase3/p4_audit.md` and branch
> `phase3-p4-audit` do **not** exist in this repository: not in the working tree,
> not in `git log --all --name-only`, and not on any remote (`origin/main`,
> `origin/aryan`, `origin/Sakshi`, `origin/Ronit`, `origin/phase2-*`,
> `origin/k1-adversarial-verification`, `origin/Mahima`). I therefore
> reconstructed P4-C1/P4-H2 from the prompt and re-ran the proof myself against
> the live code at `10c2b9f`. All claims below are from executed evidence, not
> from the missing file.

---

## 1. Verdict

**Root cause: P4 hardcoded fallback (`p4/api.py`). Not a P2 data gap.**
A second, **P2-owned** instance of the same anti-pattern exists in
`backend/app/services/engine_bridge.py` (P4-H2) but it degrades gracefully and is
**not** the demo-breaking path.

**Proposed fix owner: P4** for the 500s (`p4/api.py`). **P2** queues the
`engine_bridge.py` remediation as a normal Phase-3 fix (not the emergency
exception).

---

## 2. Executed proof (reproduced)

Created a genuinely non-demo facility (new organization, facility, period,
process, one 1000 kWh grid activity) in the live `ecoleak` schema, then ran the
merged ASGI app with `USE_MOCK_DATA=false` / `ECOLEAK_USE_MOCK_DATA=false` and
`ECOLEAK_SQL_DSN` set (live engine), and hit all four endpoints:

| Caller | Endpoint | Status |
|---|---|---|
| demo facility `0a1b2c3d-0002-…0002` | `GET …/hotspots` | 200 |
| demo facility | `GET …/leak-map` | 200 |
| demo facility | `GET …/recommendations` | 200 |
| demo facility | `GET …/dashboard` | 200 |
| **non-demo** `691d3071-58e3-…5b2c` | `GET …/hotspots` | **200** |
| **non-demo** | `GET …/leak-map` | **200** |
| **non-demo** | `GET …/recommendations` | **500 `INTERNAL_ERROR`** |
| **non-demo** | `GET …/dashboard` | **500 `INTERNAL_ERROR`** |

Direct call traceback (bypassing the generic 500 handler):

```
File "p4/api.py", line 80, in _run_ranker
    run = generate_with_diagnostics(
File "p4/engine.py", line 162, in generate_with_diagnostics
    raise ValueError("hotspot envelope facility_id does not match facility.id")
ValueError: hotspot envelope facility_id does not match facility.id
```

`p4/engine.py` validates that the hotspot envelope belongs to the facility being
ranked. `_run_ranker` passes **live hotspots for the requested facility** together
with the **mock demo facility** returned by `_facility_and_org()` — so the guard
fires for every non-demo facility. Leak-map stays 200 because it never calls
`_run_ranker`.

---

## 3. Call-path ownership (traced end to end)

Request `GET /api/facilities/{id}/reporting-periods/{pid}/recommendations`
(J2) and `…/dashboard` (N1):

| Step | Code | Data used | Owner |
|---|---|---|---|
| Hotspots | `p4/api.py::_run_ranker` → `engine.api.get_engine().hotspot_result()` | **real** (SQL source) | P3/P4 |
| Facility | `p4/api.py::_facility_and_org()` → `mocks/mock_dataset.json` | **mock demo** | **P4** |
| Organization | same | **mock demo** | **P4** |
| Processes | same (`mock_dataset.json.processes`) | **mock demo** | **P4** |
| Facility context | `p4/api.py::_context()` → `p4/demo/demo_context.json` (fixed `facility_id`) | **demo hardcoded** | **P4** |
| Resource factors | `p4/api.py::_run_ranker` → `p4.demo.run_demo._resource_factors(mock_dataset)` | **mock-derived** | **P4** |
| Ranker | `p4.engine.generate_with_diagnostics` | validates facility match | P4 |

So for the **dashboard/leak-map/JSon endpoints the hardcoding is entirely in
`p4/api.py`.** P4 already shipped the correct helpers in `p4/data_source.py`
(`load_facility_dataset()` and `resource_factors_from_factors()`) but does not
call them from `p4/api.py`.

`backend/app/services/engine_bridge.py` (P2-owned, used only by **Module P
reports**, not by J2/N1/N2):

```
File "engine_bridge.py", line 97-99   real org/facility/processes   ← correct
engine_bridge.py line 93-96           mock_dataset factors         ← P2 defect
engine_bridge.py line 94-96           p4/demo/demo_context.json    ← P2 defect
```

Empirically, `engine_bridge.real_recommendations(non-demo)` returns
`UNAVAILABLE: ValueError: context.facility_id does not match facility.id`
(caught, so Module P never 500s — it silently loses the recommendations section
for non-demo facilities). This is **split** between the two files, but the
demo-breaking 500 is P4's.

---

## 4. Data-availability check on P2 side (the "is it a data gap?" question)

| Input | In P2 live schema? | Evidence |
|---|---|---|
| Emission factors | **YES** — global `emission_factors`, 17 active across 7 categories | non-demo facility resolved `EF-ELEC-GRID-IN-CEA21-FY2024-25` (CEA v21, 0.710): `scope2 = 710 kgCO2e` for 1000 kWh, 0 unresolved |
| Facilities / org / processes / activity | **YES** — P2 tables, readable via the engine SQL source | non-demo `…/hotspots` returned 200 |
| Tariff / price / cost | **NO table** (`information_schema` has no `%tariff%`/`%cost%`/`%price%` table) | tariffs exist only in `p4/demo/demo_context.json` (`TariffSet`) and engine `CostModel` defaults |
| Per-process resource baselines | Not a table; derivable from P2 `activity_data` | `FacilityContext.process_resources` is currently demo JSON |

**Conclusion:** the 500 is **not** caused by missing emission factors or missing
P2 data. Non-demo facilities have valid, source-cited factors and full activity
data. The only genuinely absent P2 artifact is a tariff/cost source — but the
frozen `contracts/api_contract.md` defines **no tariff entity or endpoint**, and
the engine's own `CostModel` documents prices as *assumptions* ("can be replaced
by P2 cost data"). So tariff absence is a Phase-3/Phase-4 enhancement, **not**
the regression's root cause. P4's hardcoding was a workaround; the bug is the
mismatch it creates.

---

## 5. Actions taken

- **No change to `p4/api.py`** — it is P4's code and the root cause is their
  hardcoded fallback; handing back per Step 0.5.
- **No emergency P2 patch** — the Step 0.5 exception applies only to a confirmed
  P2-side *data gap*, which this is not.
- **P2 remediation queued (not applied here):** `engine_bridge.real_recommendations`
  must (a) stop using `mocks/mock_dataset.json` resource factors, using
  `p4.data_source.resource_factors_from_factors(engine.data_source.get_emission_factors())`
  instead, and (b) stop using the fixed demo `FacilityContext`, deriving/aligning
  context to the requested `facility_id` (or passing `None` so the engine uses its
  documented fallback). This restores the Module P recommendations section for
  non-demo facilities.
- Audit facility used for the proof was **deleted** afterwards to restore
  `default_context()` (facilities=1, organizations=1).
- No schema/contract change; no migration.

## 6. Handoff / notification

- **P4 (owner of the 500):** in `p4/api.py::_run_ranker` and
  `_facility_and_org`/`_context`, use the live data source exactly as
  `p4/data_source.py` already provides: `load_facility_dataset(engine, facility_id)`
  + a `FacilityContext` keyed to `facility_id` + `resource_factors_from_factors`.
  The guard `p4/engine.py:162` is correct and should stay — the caller must pass
  matching facility data.
- **P1 (dashboard consumer):** J2/N1 are currently safe only for the seeded demo
  UUID. Track P4's fix; the mock fallback (`USE_MOCK_DATA=true`) keeps the demo
  green meanwhile.
- **P3:** no calculation-input defect found in this item; nothing to action.
  Full factor-provenance / double-counting checks continue in `p2_audit.md`.

**Verdict: root cause = P4 hardcoded fallback (`p4/api.py`); split with a
secondary, gracefully-degrading P2 instance in `engine_bridge.py`; no P2
emission-factor data gap. Fix owner: P4 (primary), P2 (secondary).**
