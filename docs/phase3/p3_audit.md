# P3 Phase 3 Audit — Carbon Accounting & Simulation Engine (F/G/K/L, stretch H)

**Owner:** P3
**Branch:** `Sakshi` (audit pass; no production code changed)
**Audited revision:** `main` @ `944ea10` (Phase 1 + Phase 2 + remediation + P2 Phase-3 audit merged)
**Reference doc:** `Industrial_Emission_Database_Security_Edge_Cases.md` (Module F/G/K/L/H tables, §7.1, §17, §23)
**Upstream read first:** `docs/phase3/p2_audit.md` + `docs/phase3/p2_audit_fasttrack.md`
**Evidence script:** `tools/phase3_p3_checks.py` (executes all six checklist items; logs reproduced below)
**Method:** hand re-derivation of raw `activity × factor` products (independent of the engine), executed API/library probes, real-factor SQL-source run, factor-version update simulation. No code under audit was modified (fixes are the follow-up pass).

> **Provisional status: CLEARED.** P2's audit found **no CRITICAL data-integrity issue**
> affecting calculation inputs (`p2_audit.md` §5: factor provenance trio complete for
> all 18 live factors; factor table intact; double-counting correct). P3 findings are
> therefore **not** downstream-provisional on P2. P2 cross-references P3-05 (period
> lock) and P3-07 (persistence) as P3-owned — retained here.

---

## 1. Checklist results (one row per required item)

| # | Checklist item | Result | Evidence | Severity of fail |
|---|---|---|---|---|
| 1 | Re-derive **3–5 real calculations** by hand from raw activity × factor and match the engine **exactly** | **PASS** | `tools/phase3_p3_checks.py` §1: 5 mock products (e.g. `210000 kWh × 0.71 = 149,100`; `95,000 m³ × 2.022 = 192,090`; `12,000 L × 2.68 = 32,160`; `1,100,000 kg × 5.9 = 6,490,000`; `320,000 t·km × 0.105 = 33,600`) and 2 real-factor products (`95,000 × 2.0384 = 193,648`; `12,000 × 2.6594 = 31,912.8`) all `engine == manual` to the Decimal. Factor code/version recorded per row. | — |
| 2 | Hotspot weighted formula uses the documented weights; missing benchmark degrades gracefully, **not silently zeroed** | **PARTIAL → HIGH/CRITICAL** | Formula verified: manual weighted recompute matches `hotspot_score` for all 5 hotspots using config weights `0.30/0.15/0.20/0.15/0.20` (Boiler 76.36, Dyeing 52.02, Drying 31.93, Finishing 26.66, Packaging 8.71). Missing components remain `None` and the score renormalizes (not zeroed); `inefficiency_strategy=UNAVAILABLE` still ranks. **But** reweighting *raises* a score relative to treating the missing component as no-actionability and **changes rank order** (Drying↔Finishing) — see **P3-12**. | **P3-12 CRITICAL (affects P4 ranking)** |
| 3 | Missing/unresolved factors under **real** data gaps return an explicit unresolved state; never fabricate | **PASS** | Real-factor SQL-source run: **7** unresolved, all code `EMISSION_FACTOR_NOT_FOUND`, categories `MATERIAL/WATER/WASTE/TRANSPORT`; `scope3 = 0`, `total == operational = 566,360.8`. Zero-factor source ⇒ all 13 activities unresolved, total 0. No default factor is substituted. | — |
| 4 | Simulator: payback "unavailable" when annual saving ≤ 0; combined interventions don't double-count under real P4 combinations | **PASS** | Real P4 combination (18 recs from `p4` output): combined saving **109,792.46** ≤ naive solo-sum **111,939.50** (overlapping Dyeing interventions interact); projected **7,092,557.54 ≥ 0**. Adoption 0 ⇒ `saving = 0`, `payback_years = None`, `payback_status = "UNAVAILABLE"`. | — |
| 5 | Circularity Score labelled explicitly as an internal metric in **every** API response | **PASS** | Library `to_dict()`: `is_internal_metric=true`, `not_a_certified_standard=true`, non-empty `disclaimer`. Live `GET …/circularity-score` (L1) returns 200 with the same three labels. | — |
| 6 | Reproducibility: simulate a factor version update and confirm the **OLD** calculation is unchanged (versioned, not live-overwritten) | **PASS (engine) / PARTIAL (system)** | v1 (2.022, `EF-NG-V1` v2006.2) → old calc `2022.000000 kg`, id stable on recompute; after v2 (2.0384, `EF-NG-V2` vDEFRA-2023) added and v1 deactivated: old calc object byte-stable, new calc uses v2, old factor row retained inactive. Caveat: engine is stateless, so the old result survives only if the caller stored it → **P3-07**. | **P3-07 HIGH (system-level)** |

Script exit: `CHECKLIST: 1 assertion(s) failed / flagged: ['missing-improvement policy does NOT change rank order']` — that flag **is** P3-12.

---

## 2. Detailed findings

### P3-01 — **CRITICAL** — K1 cannot resolve P4 library interventions on the default mock path
- **Location:** `engine/api.py` (`POST /api/scenarios/{scenario_id}/simulate`), `engine/data_source.py::get_interventions`, `mocks/mock_dataset.json` (5 interventions) vs `p4/interventions/intervention_library.json` (19).
- **What's wrong:** K1 resolves each intervention id against the engine data source. The default mock source holds 5; P4's live output references up to 19. In the Phase-3 check, a real P4 combination of **18** codes resolved only the **5** present in the mock dataset — the other **13 would 404**. (Remediation seeded SQLite/PG only; `p2_audit.md` §4 confirms this is not a P2 data defect and is owned by P3/P4.)
- **What the doc says:** shared Phase-2 rule "main can fall back to Phase 1's known-good mock behavior instantly"; `api_contract.md` K1 must simulate scenario interventions.
- **Downstream impact:** P1 scenario sliders fall back to local math in mock mode; any `USE_MOCK_DATA=true` demo.
- **Suggested fix:** seed all 19 library interventions into `mocks/mock_dataset.json`; and/or have `simulate` resolve unknown ids from the P4 library. Add a strict `computedVia == 'engine'` test on the **mock** leg.
- **Notify:** P1 (scenario UI) and P4 (id coverage).

### P3-12 — **CRITICAL** — Missing "improvement potential" can raise a hotspot and change the rank order P4 consumes
- **Location:** `engine/hotspots.py::_rank` (reweight over available components), `_score_improvement` (returns `None` when no applicable intervention).
- **What's wrong:** When `improvement_potential` is missing, its weight is dropped and the remaining weights are renormalized. That **raises** the composite relative to treating "no improvement potential" as low actionability, and it demonstrably **flips the rank order**: engine rank `Boiler, Dyeing, Drying, Finishing, Packaging` vs zero-fill rank `Boiler, Dyeing, Finishing, Drying, Packaging` (executed, §2 of the evidence script). Only `top_actionable_hotspot_id` excludes the no-improvement hotspot; the `hotspot_score`/`severity` still surface the inflated value to P4.
- **What the doc says:** Module G — "High emissions but no improvement potential → **lower** actionability score"; "hotspot ranking must adapt to missing benchmark or inefficiency information" (adapt, not inflate).
- **Downstream impact:** **P4 consumes `hotspot_score`/`severity`/`rank` for candidate targeting and scoring**; the ordering/severity of hotspots changes. This is why it is flagged **CRITICAL** per the audit rule.
- **Suggested fix:** when `improvement_potential` is absent, apply a configurable actionability penalty/cap instead of renormalizing it away; expose the applied policy in `assumptions`/issues.
- **Notify:** **P4 directly** (ranking input changed by this policy).

### P3-05 — HIGH — Reporting-period lock not enforced on F1 calculations
- **Location:** `engine/api.py` (`POST …/calculations`); `ReportingPeriod.status` never read.
- **What's wrong:** recalculation is allowed for `LOCKED`/`CLOSED` periods, with no version/unlock requirement. `p2_audit.md` §2 P2-06 confirms P2 correctly returns 409 `PERIOD_LOCKED` on writes; the gap is P3's F1.
- **What the doc says:** `api_contract.md` F1 "period not LOCKED/CLOSED unless versioned"; DB doc integrity rule #2.
- **Suggested fix:** read the period and reject (frozen error shape) when not `DRAFT` unless a versioned override is supplied; emit an audit event.

### P3-07 — HIGH — No persistence of calculations/hotspots and no calculation-rerun audit
- **Location:** `engine/` is stateless; `emission_calculations` / `emission_hotspots` / `audit_logs` are never written by the engine.
- **What's wrong:** item 6's "old calculation unchanged" holds only while the caller keeps the result; the reproducibility/audit goal requires stored rows + a `CALCULATION_RERUN` event. `p2_audit.md` §2 P2-05 cross-references this as P3-owned.
- **What the doc says:** §7.1 preserve activity value/factor id/version/formula/assumptions/timestamp; §17 lists "calculation rerun".
- **Suggested fix:** persist resolved `EmissionCalculation`/`EmissionHotspot` rows (ids are already deterministic ⇒ idempotent) and write the audit event; coordinate the tables with P2.

### P3-02 — HIGH — Factor validity window ignored
- `engine/carbon.py::select_factor` filters on category + `active` + unit only; `valid_from`/`valid_to` are never compared to the reporting period. Doc Module E: "Expired factor → avoid for new periods." A ranking input if an out-of-window factor is selected. Fix: window filter/penalty + `factor_validity` in assumptions.

### P3-03 — HIGH — Region specificity ignored
- No use of `factor.region_country`/`region_state`. A wrong-country factor can be selected via the single-candidate fallback. Doc Module E: "national fallback → indicate lower specificity." Fix: region priority + `factor_region_match` + confidence penalty.

### P3-04 — HIGH — Renewable/on-site electricity keyword-classified and excluded as zero
- `engine/carbon.py::_ledger_for` routes any electricity text containing `solar/on-site/self-consum/captive/renewable/biogas/wind` to `ONSITE` and excludes it from Scope 2 — mis-scoping purchased renewable (market-based) and excluding captive **fossil** generation. Doc Module F: "do not assume zero automatically." Fix: structured discriminator + recorded `accounting_methodology`.

### P3-06 — HIGH — Weak/fallback factor matches keep full confidence
- `select_factor` accepts a sole candidate with near-zero text overlap (`SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK`) and `confidence_score` is not reduced; only a basis string is recorded. Doc Module E: fallback must lower confidence. This can feed P4's confidence input. Fix: confidence penalty surfaced in the calculation/DQ.

### P3-08 — HIGH — Cost/price data hardcoded and unversioned
- `engine/config.py::CostModel` defaults drive `annual_saving`/`payback`/`cost_per_tonne_co2_avoided`; no `source`/`year`/`version`; P2's audit confirms there is **no tariff/cost table** (`p2_audit_fasttrack.md` §4). Problem goal "concrete and costed" rests on unsourced prices. Fix: add provenance fields + P2 source.

### Additional findings carried forward (from the provisional pass, unchanged severity unless noted)
| ID | Sev | Module | Summary |
|---|---|---|---|
| P3-09 | MEDIUM | F | Biogenic emissions not tracked separately (Module F) |
| P3-10 | MEDIUM | F | Fuel-as-feedstock not distinguished; combustion factor auto-applied |
| P3-11 | MEDIUM | F | Refrigerant GWP ambiguous when >1 refrigerant and gas unnamed |
| P3-13 | MEDIUM | G | No estimated-input confidence warning on hotspots |
| P3-14 | MEDIUM | K | Unmatched intervention process silently targets the whole facility |
| P3-15 | MEDIUM | K | CO2 % applied to energy quantities when energy % absent |
| P3-16 | MEDIUM | K | Intervention currency mismatch ignored |
| P3-17 | MEDIUM | K | K baseline defaults to all scopes while G uses S1+S2 |
| P3-18 | MEDIUM | L | Reweight-missing default lacks documented methodology permission |
| P3-19 | MEDIUM | L | No projected circularity score after interventions |
| P3-20 | MEDIUM | F | Unresolved issue severity always WARNING (doc §23 wants ERROR / CONFIRMATION_REQUIRED) |
| P3-21 | MEDIUM | H | H1 emits string scores; H2/H3 absent (accepted backlog) |
| P3-22 | MEDIUM | F | Data-quality score substitutes default 60 for missing confidence (potential P4 confidence input) |
| P3-23 | LOW | F | `co2e_kg` quantized at write time (doc: round for display only) |
| P3-24 | LOW | G | Single-process explanation / credits / non-CO2 benchmarks |
| P3-25 | LOW | L/H | Sector weighting absent; H model-registry/confidence gaps; unused symbols |

---

## 3. P4 ranking-impact assessment (CRITICAL gate)

| Finding | Reaches P4? | Mechanism | Verdict |
|---|---|---|---|
| **P3-12** | **Yes** | `hotspot_score`/`severity`/`rank` are the ranker's candidate priority/targeting input; executed rank order flips Drying↔Finishing | **CRITICAL — notify P4** |
| P3-01 | Indirect | Scenario simulation (`K1`) not the ranker; P4 recommendations feed K1 | **CRITICAL — notify P1/P4** |
| P3-02/03 | Potential | would change which factor/emissions feed contribution % and intensity if triggered | HIGH (not demonstrated on current seed) |
| P3-06 / P3-22 | Potential | flow into confidence/data-quality, which P4's confidence score may consume | HIGH/MEDIUM (confirm P4's input wiring) |

No other checklist item changes P4's inputs. G's response **shape** is unchanged (Phase-2 shape gate green), so only the ordering-policy issue above is a ranking concern.

---

## 4. Cross-check of prior findings (no re-litigation)

| Prior item | Source | P3 re-check @ `944ea10` |
|---|---|---|
| K1 scenario-slider 404 on library ids | `PHASE2_AUDIT.md` blocker #2 → P3-01 | Real combination 18 codes → only 5 resolvable on mock; **not closed** |
| Period lock on F1 | P2 `p2_audit.md` P2-06 | Confirmed P3-owned; unchanged |
| No calculation persistence / rerun audit | P2 `p2_audit.md` P2-05 | Confirmed P3-owned; unchanged |
| Hotspot severity ≠ frozen mock | `PHASE1_AUDIT.md` B3 decision (b) | Decision stands; live rank/contribution stable |
| Engine volume dimension merged | `PHASE1_AUDIT.md` silent-risk #4 | Resolved (liquid ≠ gas) |
| H2/H3 + anomaly persistence | `PHASE2_AUDIT.md` / `docs/phase3/backlog.md` | Accepted backlog, owner P3 |
| `/docs/audit/` absent | prior audits | Still absent; artifacts under `docs/phase3/` |

---

## 5. Notifications

- **P4 — CRITICAL.** `P3-12`: the hotspot composite's missing-improvement handling changes hotspot rank order/severity, which P4 consumes for candidate priority. Confirm whether your ranking reads `hotspot_score`/`severity`; if it does, expect order changes until the policy is fixed.
- **P1 — CRITICAL (downstream).** `P3-01`: on the default mock path, K1 cannot resolve 13 of P4's 18 recommendation ids → engine-verified simulation is unavailable and the UI falls back to local math.
- **P2 — none required.** No CRITICAL data-integrity input defect; P3-05/P3-07 are cross-referenced P3-owned items relying on P2-owned tables.

---

## 6. Verdict

**PASS on 4 of 6 checklist items; 2 items carry a defect.** Hand-derived arithmetic is exact (item 1); missing-factor handling is honest and never fabricates (item 3); the simulator correctly refuses a payback and does not double-count combined savings (item 4); circularity is consistently labelled internal (item 5); factor versioning keeps the old calculation stable at the engine level (item 6, with a system-level persistence caveat). The two open items are both **CRITICAL by the audit rule** and both strike P4's inputs:

1. **P3-12** — missing-improvement reweight inflates a hotspot and flips rank order (notify P4).
2. **P3-01** — K1 mock-path intervention coverage (notify P1/P4).

High follow-ups: P3-02/03/04/06 (factor selection correctness), P3-05 (period lock), P3-07 (audit persistence), P3-08 (cost provenance). No fix applied in this pass.
