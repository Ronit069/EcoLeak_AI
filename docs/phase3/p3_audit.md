# P3 — Phase 3 Hardening Audit (Calculation Engine: Modules F / G / K / L, stretch H)

> **STATUS: PROVISIONAL — PENDING UPSTREAM P2 AUDIT.**
> Phase 3 requires the audit order P2 → P3 → P4 → P1, and P3 may only start
> after P2 posts `docs/phase3/p2_audit.md`. As of this writing **no
> `/docs/phase3/` and no `/docs/audit/` folder exists**, so the upstream P2
> audit has not landed. Every finding below is therefore **provisional**: an
> upstream P2 finding (data integrity, factor table, unit normalization,
> period-lock enforcement at the API boundary) may change a P3 finding's
> severity or invalidate it. Do not action these fixes until the P2 log exists
> and this file is re-checked against it.

| Field | Value |
|---|---|
| **Role** | P3 — Carbon Accounting & Simulation Engine (Modules F, G, K, L; stretch H) |
| **Base commit** | `10c2b9f` (`main`, Phase 2 merged + remediation; `engine/` unchanged since `a0a6aa9`) |
| **Date** | 2026-09-12 |
| **Method** | Code inspection with `file:line` evidence; execution of the full suite (`python -m pytest tests -q` → **164 passed**), `validate_mocks.py` (9/9), `validate_against_mock.py` (ALL PASS), `tools/phase2_p3_shape_diff.py` (all sections IDENTICAL). No code changed. |
| **Sources audited against** | `Industrial_Emission_Database_Security_Edge_Cases.md` §6/§7/§9/§11–14/§17/§23 and the Module F/G/K/L edge-case tables; the original problem statement's four impact goals; `PHASE1_AUDIT.md`; `PHASE2_AUDIT.md`; `docs/phase2/PHASE2_REMEDIATION.md`; `docs/phase2/process_notes.md`; `contracts/schemas.py`; `contracts/api_contract.md`. |

Legend: **CRITICAL** breaks a downstream teammate or produces materially wrong/compliance-relevant output · **HIGH** correctness or contract gap with real-data exposure · **MEDIUM** edge-case/robustness gap · **LOW** cosmetic/documentation.

---

## 0. Summary of findings

| ID | Sev | Module | One-line |
|---|---|---|---|
| P3-01 | **CRITICAL** | K | K1 cannot resolve 14 of P4's 19 library intervention ids on the **default mock path** → 404 → P1 falls back to local math (remediation closed SQL/PG only) |
| P3-02 | HIGH | F | Factor validity window (`valid_from`/`valid_to`) never checked against the reporting period |
| P3-03 | HIGH | F | Region specificity ignored; wrong-country factor can be applied silently (esp. via single-candidate fallback) |
| P3-04 | HIGH | F | Renewable/on-site electricity is keyword-classified and **excluded from Scope 2**, assuming zero — not an approved methodology |
| P3-05 | HIGH | F | Reporting-period `LOCKED`/`CLOSED` state not enforced on F1 calculations |
| P3-06 | HIGH | F | Weak/fallback factor matches do **not** lower `confidence_score` (Module E rule) |
| P3-07 | HIGH | F/P | No persistence of `emission_calculations`/`emission_hotspots` and no `CALCULATION_RERUN` audit event → auditability goal not met |
| P3-08 | HIGH | K | Cost/price data is hardcoded in `CostModel`; "concrete and costed" recommendations rest on unsourced prices |
| P3-09 | MEDIUM | F | Biogenic emissions not tracked separately |
| P3-10 | MEDIUM | F | Fuel-as-feedstock not distinguished; combustion factor auto-applied |
| P3-11 | MEDIUM | F | Refrigerant GWP ambiguous when >1 refrigerant factor and the gas is unnamed |
| P3-12 | MEDIUM | G | "High emissions but no improvement potential" can *raise* the composite by reweighting instead of lowering actionability |
| P3-13 | MEDIUM | G | No estimated-inputs confidence warning on hotspots; explanation is generic |
| P3-14 | MEDIUM | K | Unmatched intervention process silently targets the **entire facility** |
| P3-15 | MEDIUM | K | When energy-reduction % is absent, CO2-reduction % is applied to energy quantities (physically invalid proxy) |
| P3-16 | MEDIUM | K | Currency mismatch between interventions is ignored (blind summation) |
| P3-17 | MEDIUM | K | K1 baseline defaults to **all scopes** while G uses Scope 1+2; inconsistent cross-module baseline |
| P3-18 | MEDIUM | L | Missing-component reweight is the default without a documented methodology permission |
| P3-19 | MEDIUM | L | Projected circularity score after selected interventions is not produced (Module L functional req #2) |
| P3-20 | MEDIUM | F | Unresolved issue severity is always `WARNING`, contradicting DB doc §23 (`NEGATIVE_VALUE` = ERROR; ambiguous = CONFIRMATION_REQUIRED) |
| P3-21 | MEDIUM | H | H1 response emits `anomaly_score`/`threshold`/`confidence_score` as **strings**; H2/H3 still absent (accepted backlog) |
| P3-22 | MEDIUM | F | Data-quality score substitutes a default 60 for missing confidence instead of flagging unknown |
| P3-23 | LOW | F | Stored `co2e_kg` is quantized at write time (doc says store full precision, round for display) |
| P3-24 | LOW | G | Single-process / credits / benchmark-metric gaps and unused symbols |
| P3-25 | LOW | L/H | Sector-specific circularity weighting absent; H model registry/confidence unbounded |

---

## 1. Cross-check of prior audit findings (do not re-litigate)

| Prior finding | Source | P3 re-check at `10c2b9f` | Status |
|---|---|---|---|
| Hotspot severity differs from frozen mock (Boiler HIGH 76.4 vs CRITICAL 88.5) | `PHASE1_AUDIT.md` §1/B3, decision (b) | Live output still Boiler HIGH 76.41 with identical rank order/contribution; decision documented in `CONTRACTS_README` + `engine/config.py` comment | ✅ **Accepted decision, resolved** |
| Engine unit "volume" merged m³ == litre | `PHASE1_AUDIT.md` §3, silent-risk #4 | **Fixed**: `engine/units.py:40-54` separates `volume_liquid` and `volume_gas`; `tests/test_unit_dimensions.py` passes | ✅ **Resolved** |
| No SQL-backed data source | `PHASE1_AUDIT.md` §3/§8 | `engine/sql_source.py` + `USE_MOCK_DATA` gate present | ✅ **Resolved** |
| K1 response wrapper undocumented | `PHASE2_AUDIT.md` A4 / remediation C2 | `ScenarioSimulationEnvelope` formalized in `contracts/schemas.py:494-506`, K1 row updated (`api_contract.md:182`) | ✅ **Resolved (SQL/PG)** — but see **P3-01** for the mock path |
| Scenario-slider live path (K1 404 on library ids) | `PHASE2_AUDIT.md` blocker #2 / remediation B1 | Seeded 19 interventions into **SQLite/PG**; `mocks/mock_dataset.json` still holds **5** (`get_interventions()` → 5 on mock, 19 in P4 library, id overlap = 5) | ❌ **NOT fully closed** → promoted to **P3-01 CRITICAL** |
| No lower confidence on fallback factor (silent-correctness #4) | `PHASE1_AUDIT.md` §8 | Still no confidence downgrade; only `factor_match_basis` recorded | ❌ **Open** → **P3-06** |
| H2/H3 endpoints, Q persistence | `PHASE2_AUDIT.md` remaining #10 | H2/H3 explicitly assigned to P3 Phase-3 backlog | 📝 **Accepted backlog** (see §5) |
| `/docs/audit/` absent (naming drift) | `PHASE2_AUDIT.md` finding #7 | Still absent; this file follows the Phase-3 path `docs/phase3/` | 📝 **Recorded** |

No finding below duplicates a prior logged item except where explicitly cross-referenced.

---

## 2. Detailed findings

### P3-01 — **CRITICAL** — K1 cannot simulate P4 library interventions on the default mock path
- **Location:** `engine/api.py:106-155` (`simulate`), `engine/data_source.py:135-138` (`get_interventions` on `MockDataSource`), `mocks/mock_dataset.json` (`circular_interventions`: 5), `p4/interventions/intervention_library.json` (19).
- **What's wrong:** K1 resolves each `intervention_id` against `engine.data_source.get_interventions()`. On the default (mock) source only **5** interventions exist, but P4's live J2 emits **18–19** recommendations. The 5 mock ids are a subset of the library, so **14 of 18 ids → 404 `NOT_FOUND`**. The remediation seeded the 19 into SQLite/PG only; the mock fallback path (the one the team must be able to demo with, per the shared rule) still fails. P1's scenario page then silently uses local Module-K math.
- **What the doc says:** `api_contract.md` K1 expected to simulate scenario interventions; shared Phase-2 rule: "main can fall back to Phase 1's known-good mock behavior instantly." `PHASE2_AUDIT.md` blocker #2 (owner P2/P3/P4) was declared CLOSED but only for the real path.
- **Downstream impact:** P1 (scenario sliders show non-engine numbers in mock mode); any P4/live demo that runs `USE_MOCK_DATA=true`.
- **Suggested fix:** seed all 19 library interventions into `mocks/mock_dataset.json` (mirror of the SQL seed); and/or have `simulate` fall back to the P4 library by id/code when the data source lacks it. Add a strict test asserting `computedVia == 'engine'` for the **mock** source with all 18 live ids (extend the K1 adversarial check to the mock leg).
- **Notify:** P1 and P4 directly (data-source id coverage), per the CRITICAL rule.

### P3-02 — HIGH — Factor validity window ignored
- **Location:** `engine/carbon.py:234-272` (`select_factor`); candidates filtered only by category + `active` + unit (`:244-250`).
- **What's wrong:** `EmissionFactor.valid_from`/`valid_to` are never compared to the reporting period. A superseded/expired factor that is still `active` (or an out-of-window factor) can be applied to a current period. `get_emission_factors(active_only=True)` only checks the `active` flag.
- **What the doc says:** DB doc edge case Module E — "Expired factor → Keep for historical calculations; avoid for new periods."
- **Suggested fix:** filter/penalise candidates by window vs `reporting_period.start_date/end_date`; prefer in-window; if only out-of-window exists, emit `WARNING` and record `factor_validity: OUT_OF_WINDOW` in `EmissionCalculation.assumptions`.

### P3-03 — HIGH — Region specificity ignored
- **Location:** `engine/carbon.py:244-272`; no use of `factor.region_country`/`region_state` anywhere in the engine.
- **What's wrong:** A facility in India can be matched to a UK factor (e.g. DEFRA) if it is the sole active candidate (single-candidate fallback, `:266-271`), with no indication of lower specificity. The Phase-2 real run "works" only because the seed happens to include an India grid factor.
- **What the doc says:** Module E — "Region-specific grid factor missing → Use national factor and indicate lower specificity."
- **Suggested fix:** add region to factor scoring/priority; record a `factor_region_match: MATCH|NATIONAL_FALLBACK|MISMATCH` and lower confidence on fallback/mismatch.

### P3-04 — HIGH — Renewable/on-site electricity is keyword-classified and excluded, assuming zero
- **Location:** `engine/carbon.py:402-412` (`_ledger_for`); ledgers excluded from scope totals (`:113-117`).
- **What's wrong:** Any electricity activity whose free text contains `solar/on-site/self-consum/captive/rooftop pv/renewable/biogas/wind` is routed to `ONSITE` and **excluded from Scope 2** (treated as zero), and `export/feed-in/surplus` to `EXPORT`. Two problems: (a) **purchased renewable electricity** (market-based contracts) is mis-scoped away; (b) captive **fossil** generation (e.g. diesel genset described as "captive") is also excluded, understating what is really Scope 1. No methodology field records the accounting choice.
- **What the doc says:** Module F — "Renewable electricity → Apply approved accounting methodology; do not assume zero automatically"; "On-site solar self-consumption → Separate from grid purchase"; cross-module "Never mix Scope 1/2/3 without labels."
- **Suggested fix:** require a structured discriminator (subcategory enum / explicit `onsite` / `export` flag) instead of substring matching; for on-site fossil generation count Scope 1; store `accounting_methodology` (location-based vs market-based, on-site treatment) with each ledger entry.

### P3-05 — HIGH — Reporting-period lock not enforced on calculations
- **Location:** `engine/api.py:72-75` (`POST .../calculations`); `ReportingPeriod.status` never read by the engine.
- **What's wrong:** F1 recalculates for any period, including `LOCKED`/`CLOSED`. No version/unlock requirement, no audit event.
- **What the doc says:** `api_contract.md` F1 security/business rule: "period not LOCKED/CLOSED unless versioned"; DB doc integrity rule #2.
- **Suggested fix:** look up the period, reject (frozen error shape) when `status != DRAFT` unless a `calculation_version`ed override is explicitly supplied; log the event.

### P3-06 — HIGH — Weak/fallback factor matches do not lower confidence
- **Location:** `engine/carbon.py:266-271` (fallback), `:336-354` (assumptions), `:364` (`confidence_score=activity.confidence_score`), `:414-440` (`_data_quality`).
- **What's wrong:** A match accepted purely because it is the only candidate (`SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK`, possibly zero text overlap) keeps the activity's original confidence and only records a basis string. The result is indistinguishable in confidence from an exact description match.
- **What the doc says:** Module E — "No exact factor available → Use approved fallback factor and **lower confidence**."
- **Suggested fix:** apply a configurable confidence penalty for fallback/region-mismatch/out-of-window; surface in `EmissionCalculation.confidence_score` and the hotspot `data_quality_score`.

### P3-07 — HIGH — No persistence of calculations/hotspots and no calculation-rerun audit trail
- **Location:** `engine/carbon.py` / `engine/hotspots.py` are pure and stateless; `engine/service.py` caches in-memory only; no write path to `emission_calculations`/`emission_hotspots`/`audit_logs`.
- **What's wrong:** Every F/G call recomputes; the DB tables in the design doc are never populated by the engine. Reproducibility holds only while inputs and factor rows are unchanged, and there is no `CALCULATION_RERUN` audit record (DB doc §17 lists it as a required event), nor a stored `data_quality_assessment`.
- **What the doc says:** DB doc §7.1 "must preserve activity value, factor ID, factor version, formula, assumptions, timestamp"; §17 audit events; §26 separation principle; problem statement goal "every number must be auditable/reproducible."
- **Downstream impact:** Module P report "factor provenance" and any regulator-facing audit; F2/G2 return recomputed data rather than stored results.
- **Suggested fix (owner P3 + P2):** persist resolved `EmissionCalculation` rows (deterministic ids already exist, so duplicates are idempotent) and `EmissionHotspot` rows on each run; write one `audit_logs` `CALCULATION_RERUN` entry. P2 owns the tables — coordinate.

### P3-08 — HIGH — Cost/price data is hardcoded, not sourced or versioned
- **Location:** `engine/config.py:112-142` (`CostModel` defaults `electricity:kwh: 8.0`, `fuel:m3: 45.0`, …); used at `engine/simulator.py:345-359`.
- **What's wrong:** `annual_saving`, `payback_years`, `cost_per_tonne_co2_avoided` — the headline "costed" outputs — rest on unsourced static prices with no `source`/`year`/`version` per price, and no P2 cost feed.
- **What the doc says:** Problem statement impact goal "recommendations must be concrete and costed"; DB doc §26 requires provenance; library doc money rules (Decimal) are met but source is not.
- **Suggested fix:** add `source`, `currency`, `valid_year`, `version` to each price; source them from P2 config/master table; expose per-intervention provenance in `assumptions`.

### P3-09 — MEDIUM — Biogenic emissions not tracked separately
- **Location:** `engine/carbon.py` (no biogenic channel).
- **What the doc says:** Module F — "Biogenic emissions → Track according to selected methodology."
- **Suggested fix:** add a biogenic ledger/flag on activity/factor and report outside scopes.

### P3-10 — MEDIUM — Fuel-as-feedstock not distinguished
- **Location:** `engine/carbon.py:244-272` matches any `FUEL` factor by category/unit/text.
- **What the doc says:** Module F — "Fuel used as feedstock, not combustion → Do not apply combustion factor automatically."
- **Suggested fix:** an `end_use`/`feedstock` discriminator that suppresses the combustion factor.

### P3-11 — MEDIUM — Refrigerant GWP selection can be ambiguous
- **Location:** `engine/carbon.py:254-272`; real seed has R-134a (1430) and R-410A (2088), both `kg`/`REFRIGERANT`.
- **What's wrong:** An activity like "refrigerant top-up" without the gas name can match either factor; the single-candidate fallback does not apply (2 candidates), but a weak token overlap can still pick the wrong GWP.
- **Suggested fix:** require an explicit refrigerant identifier (dedicated subcategory/`item_name` match threshold) and flag ambiguity.

### P3-12 — MEDIUM — "No improvement potential" can inflate the hotspot score
- **Location:** `engine/hotspots.py:287-321` (`_rank`, reweight of available components), `:257-273` (`_score_improvement` → `None` when no applicable intervention).
- **What's wrong:** When `improvement_potential` is `None`, its weight is removed and the remaining weights renormalised; the composite can therefore **rise** for a hotspot with no actionable improvement, which is the opposite of the Module G intent. Only `top_actionable_hotspot_id` (`:148-152`) excludes it.
- **What the doc says:** Module G — "High emissions but no improvement potential → Lower actionability score."
- **Suggested fix:** when `improvement_potential` is missing, do not renormalise it away; apply a configurable actionability cap/penalty and surface the reason.

### P3-13 — MEDIUM — No per-hotspot estimated-input warning
- **Location:** `engine/hotspots.py:324-341` (`_build_explanation`) — static text.
- **What the doc says:** Module G — "Hotspot based on estimated inputs → Display confidence warning"; recommendation based on estimated data must say so.
- **Suggested fix:** aggregate `measured_or_estimated`/`confidence_score` of contributing activities into the explanation and a per-item confidence field.

### P3-14 — MEDIUM — Unmatched intervention targets the whole facility
- **Location:** `engine/simulator.py:362-385` (`_targets`); when `matched_pids` is empty, `candidates = list(states)` (`:373`) and the fallback selects all energy/waste states (`:384`).
- **What's wrong:** An intervention whose `process_category` does not match any process silently reduces **facility-wide** quantities, overstating savings and hiding a mapping error.
- **What the doc says:** Module I/K — intervention applicability before simulation; "Two interventions affect same baseline → interaction model"; `InterventionNotApplicableError` exists but is unused here.
- **Suggested fix:** raise/flag `INTERVENTION_NOT_APPLICABLE` (or skip with a WARNING) instead of a facility-wide fallback.

### P3-15 — MEDIUM — CO2 % applied to energy quantities when energy % is absent
- **Location:** `engine/simulator.py:397-408` (`_fractions`): `e_pct` falls back to `expected_co2_reduction_*`.
- **What's wrong:** A CO2-intensity reduction is not an energy-quantity reduction; using it as a quantity multiplier is physically invalid and can over/under-state energy and cost savings.
- **Suggested fix:** when only a CO2 % is available, model an emission-factor/emissions reduction path explicitly and label the basis; do not reduce quantities.

### P3-16 — MEDIUM — Currency mismatch ignored
- **Location:** `engine/simulator.py:525-538` (`_capex_point`) and `:226` (sum of capex); `CostModel.currency` single-valued (`config.py:119`).
- **What the doc says:** Module K — "Currency mismatch → Convert explicitly or keep separate."
- **Suggested fix:** validate each intervention `currency` against the cost model, or return separate per-currency totals and `INCOMPLETE` when mixed.

### P3-17 — MEDIUM — K baseline scope inconsistent with G
- **Location:** `engine/api.py:141-154`: `scope_boundary` only set when the request body supplies it; otherwise `simulate` uses `None` = **all scopes** (`engine/simulator.py:156`, `:337-343`). G defaults to `[SCOPE_1, SCOPE_2]` (`hotspots.py:39`).
- **What's wrong:** The scenario baseline (e.g. 7,202,350 kgCO₂e incl. Scope 3) is a different boundary from the hotspot total (565,050), which can confuse P1/P4 comparisons and risks treating Scope 3 reductions as Scope 1+2.
- **Suggested fix:** default K1 to the same boundary as G (or echo the boundary in the envelope) and make the boundary explicit in `assumptions`.

### P3-18 — MEDIUM — Circularity reweight default lacks documented permission
- **Location:** `engine/config.py:186` (`reweight_missing=True` default); `engine/circularity.py:128-157`.
- **What the doc says:** Module L — "Missing one score component → Reweight only if methodology explicitly permits."
- **Suggested fix:** set `reweight_missing=False` by default or record the permission explicitly in `methodology_version` + issues; keep the current behaviour only when a documented methodology flag is set.

### P3-19 — MEDIUM — No projected circularity score
- **Location:** `engine/circularity.py` returns current only; `engine/simulator.py` never adjusts circularity components.
- **What the doc says:** Module L functional requirement — "Show current score and **projected score after selected interventions**."
- **Suggested fix:** compute a projected circularity (recycled/recovery/water deltas from selected interventions) and include it in the scenario envelope.

### P3-20 — MEDIUM — Validation severity misclassification for unresolved F issues
- **Location:** `engine/carbon.py:81-91` (`UnresolvedActivity.to_issue` always `severity="WARNING"`).
- **What the doc says:** DB doc §23 — ERROR examples include "negative electricity consumption", "unsupported factor/unit conversion"; CONFIRMATION_REQUIRED for ambiguous/duplicate.
- **What's wrong:** `NEGATIVE_ACTIVITY` and genuine unit-conversion failure are emitted as `WARNING`, so an upstream consumer will not treat them as blocking. (Note: the contract model forbids negative values, so negative can only arrive via a bypassed validator — still, the severity contract is wrong.)
- **Suggested fix:** map `NEGATIVE_ACTIVITY`/`INVALID_UNIT`→`ERROR`, ambiguous unit→`CONFIRMATION_REQUIRED`, missing factor→`WARNING` (per doc examples).

### P3-21 — MEDIUM — H1 emits string numbers; H2/H3 absent
- **Location:** `engine/anomaly.py:142-152, 185-194` (`str(q2(...))`); `engine/api.py:158-165` (H1 only).
- **What's wrong:** `anomaly_score`, `threshold`, `confidence_score` are stringified inside the item dicts, so `to_jsonable` cannot restore numeric types; the H1 contract describes numeric scores. H2/H3 remain unimplemented (accepted backlog) so anomaly results are not persisted or acknowledgable.
- **What the doc says:** `api_contract.md` Module H; DB doc §10.
- **Suggested fix:** emit `Decimal`/numbers and let `to_jsonable` encode; H2/H3 pending persistence.

### P3-22 — MEDIUM — Data-quality score invents a default 60 for missing confidence
- **Location:** `engine/carbon.py:434-439`.
- **What's wrong:** Missing activity/factor confidence becomes `60`, which can mask genuinely unknown quality as "medium-ish".
- **What the doc says:** Module D/§23 require provenance and lower confidence for estimated/unknown data; "Do not claim certainty."
- **Suggested fix:** return `None`/`UNKNOWN` component or a conservative floor with an explicit issue when confidence is absent.

### P3-23 — LOW — Quantization at store time
- **Location:** `engine/carbon.py:333` (`q6(...)`).
- **What the doc says:** Module F — "Store full precision; round only for display."
- **Suggested fix:** keep full Decimal in the calculation record; quantize only at serialization. (Contract allows 6 dp; low impact.)

### P3-24 — LOW — G robustness/cosmetic gaps
- Single-process case has no explicit "may be 100% by construction" explanation (Module G edge case).
- Credit/removal (negative) emissions have no separate channel before percentage ranking.
- `_find_benchmark` only accepts CO₂/intensity metrics, so kWh/tonne or waste kg/tonne benchmarks never feed inefficiency/waste (`hotspots.py:275-284`).

### P3-25 — LOW — L/H cosmetic gaps
- Circularity has no sector-specific weighting for e.g. water reuse (`circularity.py`); fine while documented.
- Anomaly confidence is a linear function capped at 90 with no model registry/feature-pipeline version (`anomaly.py:199-203`).
- Unused symbols: `engine/anomaly.py:19` imports `q6`; `engine/circularity.py:31` defines `_VIRGIN_KEYWORDS` unused.

---

## 3. Impact-goal assessment (problem statement)

| Impact goal | Verdict | Evidence / gap |
|---|---|---|
| 1. Emission sources visible and actionable | ✅ mostly | G ranks process hotspots with contribution %, severity, `top_actionable_hotspot_id`; provenance in explanations. Gaps: P3-12 (actionability inversion), P3-13 (no estimated-input warning), P3-24. |
| 2. Recommendations concrete and costed | ⚠️ partial (P3 side) | K returns CAPEX, annual saving, payback, cost/tCO₂e, with `UNAVAILABLE` rules. Gaps: P3-08 (unsourced prices), P3-14/P3-15/P3-16 (targeting/currency/proxy). P4 owns ranking. |
| 3. Support regulatory compliance | ⚠️ partial | Scope labels + factor provenance retained per calc (`carbon.py:336-354`) and `is_internal_metric` disclaimer for L. Gaps: P3-02/P3-03 (wrong/expired/out-of-region factor), P3-04 (boundary methodology unrecorded), P3-05 (period lock), P3-07 (no persisted audit trail). |
| 4. Every number auditable/reproducible | ⚠️ partial | Deterministic UUIDs, Decimal arithmetic, full assumptions dict (`carbon.py:336-354`), unit tests + property tests + shape gate. Gaps: P3-07 (nothing persisted; no rerun audit), P3-22 (invented DQ default), P3-23 (store-time rounding). |

---

## 4. Module coverage / edge-case trace (F, G, K, L, H)

| Module | Edge-case rows verified implemented | Rows with gaps (IDs) |
|---|---|---|
| F | missing factor → unresolved; activity 0 → 0; negative → rejected; on-site/export separate ledgers; duplicate via deterministic id; rounding recorded; aggregation by scope/process/source | P3-02, P3-03, P3-04, P3-05, P3-06, P3-09, P3-10, P3-11, P3-20, P3-22, P3-23 |
| G | total=0 → no %; missing production → skip intensity; missing benchmark → reweight; tied → deterministic; estimated note (partial) | P3-12, P3-13, P3-24 |
| K | saving≤0 → UNAVAILABLE; adoption 0/ >100; CAPEX 0 → immediate; projected floored; saving>baseline capped; sequential no-double-count; static-price assumption shown | P3-08, P3-14, P3-15, P3-16, P3-17, P3-19 |
| L | 0..100 clamp; no data → incomplete; internal-metric disclaimer; methodology version; disjoint recycled-input vs waste sets | P3-18, P3-19, P3-25 |
| H | insufficient history → rules-only, no ML claim; conservative confidence; sklearn-only ML; no LLM | P3-21, P3-25 |

---

## 5. Explicitly accepted backlog (already owned, not new findings)

- **H2/H3** (GET anomalies, acknowledge) + anomaly persistence — Phase-3 backlog, owner **P3** (recorded in `docs/phase2/process_notes.md` §4).
- **Q persistence** — owner **P2**.
- **PostgreSQL CI** — remediation added `.github/workflows/phase2-ci.yml`; PG runtime re-verified by P2 (54/54) but not in this local environment.
- **Direct-to-main hygiene** — recorded in `process_notes.md`; GitHub branch protection is an owner-admin action.

---

## 6. Method & evidence (executed)

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `10c2b9f` |
| `python -m pytest tests -q` | **164 passed** (5 warnings) |
| `python validate_mocks.py` | 9/9 PASS |
| `python validate_against_mock.py` | ALL SHAPE CHECKS PASSED |
| `python -m tools.phase2_p3_shape_diff` | meta/F/G/K/L shape IDENTICAL; real-data unresolved = 7 (`EMISSION_FACTOR_NOT_FOUND`) |
| `python -c "… mock vs p4 library ids …"` | mock ids 5, library ids 19, overlap 5 (basis for P3-01) |
| `git diff --stat a0a6aa9..HEAD -- engine` | **empty** — no engine change since Phase 2, so this audit covers the shipped code |

Files read (full): `contracts/schemas.py`, `contracts/api_contract.md`, `engine/carbon.py`, `engine/hotspots.py`, `engine/simulator.py`, `engine/circularity.py`, `engine/anomaly.py`, `engine/config.py`, `engine/units.py`, `engine/errors.py`, `engine/api.py`, `engine/data_source.py`, `engine/sql_source.py`, `engine/service.py`, `engine/serialization.py`, `PHASE1_AUDIT.md`, `PHASE2_AUDIT.md`, `docs/phase2/PHASE2_REMEDIATION.md`, `docs/phase2/process_notes.md`, `docs/phase2/p2_integration_log.md`, `docs/phase2/contract_changes.md`.

---

## 7. Re-check checklist once P2's Phase-3 audit lands

1. Does P2 enforce `ReportingPeriod.status` at the API boundary? If yes, P3-05 downgrades to LOW (engine-level defence-in-depth).
2. Does P2's factor table carry region/validity and a lookup that already filters them? If yes, P3-02/P3-03 become P3-side hardening only.
3. Does P2 persist engine `EmissionCalculation`/`EmissionHotspot` rows or audit events? If yes, P3-07 is P2/interface coordination only.
4. Are cost/price masters seeded by P2? If yes, P3-08 reduces to a wiring task.
5. Confirm module ownership for P3-20 (validation severity) — this crosses P2's ingestion issue codes.

**No fixes were applied. This is an audit record only.**
