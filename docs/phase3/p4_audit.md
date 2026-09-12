# P4 Phase 3 Audit — Recommendation, Explainability & Feedback (I/J/M/Q + merged P4 router)

**Owner:** P4 · **Branch:** `phase3-p4-audit` · **Audited revision:** `main` @ `4b2eb9e`
**Date:** 2026-09-12
**Reference doc:** `Industrial_Emission_Database_Security_Edge_Cases.md` (Modules G/I/J/K/M/Q tables, §§ 19, 21, 23, 24 + Level-4 AI/ML checklist)
**Upstream read first:** `docs/phase3/p3_audit.md` (cleared provisional), `docs/phase3/p2_audit.md` + `docs/phase3/p2_audit_fasttrack.md`
**Evidence script:** `tools/phase3_p4_checks.py` (37 executed checks; full output reproduced in §3)
**Environment:** PostgreSQL 18.1 (local audit instance, port 55432; alembic head + `app.seed.run_seed` = 1 org / 13 activities / 18 factors / 19 interventions), merged ASGI app with `USE_MOCK_DATA=false`, P3 live Engine G (SQL source), real-factor estimator inputs
**Method:** executed probes + independent hand re-derivation; no production code modified (fixes are the follow-up pass)

> **Provisional status: CLEARED.** P2's audit found **no CRITICAL data-integrity defect** in
> calculation inputs (factor provenance trio complete for all 18 live factors; factor table
> intact; double-counting correct), and P3's audit was posted and read before this pass.
> P3-12 (hotspot reweight policy) is answered with executed evidence in §4 — it does **not**
> reach P4's numeric ranking. This audit's findings are therefore not downstream-provisional.
>
> **Artifact-availability note:** P2's fast-track (§Artifact caveat) could not find the earlier
> P4 first-pass audit because it was never committed/pushed. This file supersedes it and is the
> authoritative P4 audit on `phase3-p4-audit`.

> **CRITICAL NOTIFICATION — P1 (dashboard consumer), direct:**
> **P4-C1 is still open on `main` @ `4b2eb9e`.** `GET …/recommendations` (J2) and
> `GET …/dashboard` (N1) return **500 INTERNAL_ERROR for every facility except the seeded
> demo UUID** when the live engine is active (reproduced in this pass; root cause traced in
> `p2_audit_fasttrack.md` §3). The dashboard's displayed recommendations are affected →
> CRITICAL per the audit rule. Owner: **P4** (`p4/api.py::_run_ranker`). The mock fallback
> (`USE_MOCK_DATA=true`) keeps the demo green meanwhile.

---

## 1. Checklist results

| # | Checklist item | Result | Evidence | Severity of fail |
|---|---|---|---|---|
| 1 | Hard constraints (budget, technical, location) applied **before** ranking; no above-budget item appears even ranked low | **PASS** | Budget ₹150k: only `INT-NOCAPEX-019`, `INT-WASTESEG-015`; 16 codes filtered `BUDGET_EXCEEDED`; `diagnostics.scored == output` (filter precedes rank); boundary ₹200k admits `INT-CAIR-011` (midpoint == budget, not `>`); `max_complexity=MEDIUM` filters `INT-RO-014` `COMPLEXITY_LIMIT`; `locally_unavailable_codes` filters `INT-WHR-001`; location policy = −15 feasibility, item retained (doc says "lower feasibility", not filter). | — |
| 2 | Ranking formula re-derived by hand for 3–5 real recommendations | **PASS** | 5 real recs: manual weighted sum == engine `final_score` exactly (77.37 / 77.02 / 71.67 / 69.95 / 67.38). Full component re-derivation for `INT-WHR-001` and `INT-SCRAP-004`: **12/12 components exact** (carbon/financial/feasibility/circularity/speed/confidence). | — |
| 3 | LLM guardrails under **real** evidence | **PASS** | (a) valid LLM narrative: 18/18 used, IDs/ranks/scores byte-identical to template; LLM attempting to inject `final_score`/`rank` extra fields → `extra="forbid"` rejection, 18/18 fallback, ranking unchanged. (b) contradiction: forced on every real evidence item → first attempt rejected, second used (`attempts=2`), sample observed `52.04 years` → rejected. (c) unknown code `INT-FREE-MONEY` and **real-but-foreign** library code `INT-LED-008` both rejected. (d) real CSV upload with injection in `notes` accepted (202) and stored verbatim as data; P4's evidence model has **no notes field**; injection forced into the untrusted narrative still rejected and ranking unchanged. | — |
| 4 | Feedback state history preserved, not overwritten, under real interaction | **PASS*** | Via real HTTP: `USEFUL` → `NOT_APPLICABLE(reason_code)` → `IMPLEMENTED(actuals)` all 201; history `[1,2,3]`, latest `IMPLEMENTED`, `previous_feedback_type` chain intact; missing reason / bad reason_code / bad numeric → 422 frozen. *Exception:* invalid `feedback_type` → **500** (P4-M1). | **P4-M1 MEDIUM** |
| 5 | Demo end-to-end on current main: hotspot → recommendation → simulation → report coherent | **PASS** | Live G: total 566,360.8 kgCO₂e (S1+S2), top **Boiler HIGH**; J2: 18 recs, all bound to real hotspot ids, `data_is_stub=true` flagged 18/18 (F-8); K1 with **all 18 ids → 200**, baseline 7,203,660.8 == inventory total, projected 6,919,020.54, saving 284,640.26 ≥ 0; Module P report 202/200, all 11 sections, `recommendations.status=REAL`, 18/18 items + roadmap, factor provenance 11 items, per-item fixture flag carried. Story is coherent (Boiler-led, waste/steam wins first, financials flagged provisional). | — |

**Runner summary:** **33/37 checks PASS**; the 4 failures are findings P4-C1, P4-H1, P4-M1, and the P3-owned P3-01 cross-check (see §2/§4). Root suite: exit 0 (164 tests); `validate_mocks.py` 9/9; `validate_against_mock.py` ALL PASS.

---

## 2. Detailed findings (v1 findings re-verified on current main)

### P4-C1 — **CRITICAL** — J2/N1 still rank with the mock demo facility/context
**Status: OPEN (confirmed by executed re-probe; root cause also traced by P2; owner P4).**
- **Location:** `p4/api.py:75-81` (`_facility_and_org` → `mocks/mock_dataset.json`), `p4/api.py:97-117` (`_run_ranker` overrides the requested facility, uses `_resource_factors(_dataset())` + `_context()`), `p4/api.py:260-265` (M1 default context); guard at `p4/engine.py:162`.
- **What's wrong:** live hotspots are fetched for the requested facility, but ranking inputs are the mock demo organization/facility/processes, mock-derived factors and the fixed demo tariff context. Any non-demo facility → `ValueError("hotspot envelope facility_id does not match facility.id")` → 500. Executed on current main with a second real facility inserted into PG:
  `J2=500 N1=500` (demo facility = 200; N2 works because it never calls `_run_ranker`).
- **What the doc says:** Module A ("More than one facility → keep separate facility records"), DB §19 rule 10 (tenant filtering), `api_contract.md` J2/N1/M1 ("tenant ownership"), problem goal "emission sources visible and actionable".
- **Impact:** the dashboard's displayed recommendations (J2) and dashboard KPIs (N1) are broken for every facility created through the product; Module P loses its recommendations section for them (P2 fasttrack §3).
- **Suggested fix (exact):** in `_run_ranker`, use `p4.data_source.load_facility_dataset(engine, facility_id)` and `resource_factors_from_factors(engine.data_source.get_emission_factors(), region_country=facility.country)`; derive/align `FacilityContext` to the requested facility (or pass `None` to trigger the documented incomplete-financials path). Keep the engine guard. Add a non-demo-facility regression test.
- **Notify:** P1 (dashboard consumer) and P2 (`engine_bridge` secondary instance, already queued).

### P4-H1 — **HIGH** — negative-net recycling CO₂ still crashes the ranker
**Status: OPEN.**
- **Location:** `p4/financial.py::estimate_resource_co2` (netting can be negative) → `p4/engine.py` → `contracts/schemas.py:400` (`RecommendationAssessment.estimated_co2_saving_kg: Field(ge=0)`).
- **What's wrong:** the Phase-1 C2 decision explicitly allows a recycling pathway to emit more than the landfill it avoids. The engine forwards the signed value into a contract field that forbids negatives, so the whole run raises. Executed: synthetic waste-loop entry, `waste_per_kg=0.8`, `recycling_processing_emission_factor=1.2` → `ValidationError … estimated_co2_saving_kg Input should be greater than or equal to 0 (input=-16000)`. The existing `tests/test_recycling_emissions.py` only exercises the financial helper, so CI stays green.
- **What the doc says:** Module K ("CO₂ saving exceeds source emissions → cap or flag invalid", "negative projected emissions → floor at physically valid value"); Module J must not crash on real data; the C2 remediation states negative nets are "reported as additional emissions".
- **Suggested fix:** choose and log in `contract_changes.md`: (a) signed `estimated_co2_saving_kg` + explicit "additional emissions" flag, or (b) floor at 0 and record the signed delta in `assumptions`. Add an engine-level test for the negative-net path.

### P4-H2 — **HIGH** — Module P recommendations still use mock factors + demo context
**Status: OPEN / P2-owned remediation queued (cross-ref, not re-litigated).**
- **Location:** `backend/app/services/engine_bridge.py:87-109`.
- **What's wrong:** in real mode the bridge derives estimator factors from `mocks/mock_dataset.json` and uses the demo `FacilityContext`, while inventory/hotspots are live. P2's fast-track confirmed empirically: `real_recommendations(non-demo)` returns `UNAVAILABLE: ValueError: context.facility_id does not match facility.id` (caught, so the report silently loses the section).
- **What the doc says:** Module P "calculation provenance and factor-year/version"; impact goal "every number auditable/reproducible".
- **Suggested fix:** P2's queued remediation — use `p4.data_source.resource_factors_from_factors(engine.data_source.get_emission_factors())` and a facility-aligned context (or `None`). P4 helper already shipped.
- **Notify:** P2 (owner), P1 (report reviewers).

### P4-M1 — **MEDIUM** — invalid `feedback_type` returns 500, not the frozen 422
**Status: PARTIAL of F-13 — observed on current main.**
- **Location:** `p4/api.py:345-371` (`feedback_type` passed raw into the store; `FeedbackEvent` pydantic validation raises uncaught); contrast `reason_code`/`actual_*`, which are now validated (422 frozen).
- **Executed:** `POST …/feedback {"feedback_type": "BOGUS"}` → `500 {"error_code":"INTERNAL_ERROR", …}`; missing reason → 422; bad reason_code → 422; bad numeric → 422.
- **What the doc says:** §23 severity `ERROR` for invalid values; Level-1 API security "proper HTTP status codes", "safe error response".
- **Suggested fix:** validate `FeedbackType(feedback_type)` at the boundary and raise `PlatformValidationError` (same pattern as `reason_code`); add a test.

### P4-M2 — MEDIUM — Q1/Q2 response shapes deviate from `api_contract.md` (undocumented)
`FeedbackEvent` superset on Q1 (`reason_code`, `sequence_no`, `previous_feedback_type`, `is_self_reported_outcome`, `validation_notes`) and `{recommendation_id, latest_state, history}` on Q2 vs `RecommendationFeedback[]`. Fix: formal addendum or align; update P1 TS types.

### P4-M3 — MEDIUM — feedback accepted for non-existent recommendation ids
`recommendation_tenant_guard` now scopes the tenant (T0-3) but never verifies the recommendation exists; arbitrary UUIDs are stored and returned as history. Fix: resolve against the ranker/P2 store before accepting, 404 otherwise.

### P4-M4 — MEDIUM — "no feasible intervention" surfaces no reason
J1/J2 return `recommendations: []` with the diagnostics (budget/applicability/prereq reasons) discarded. Module J edge wants an honest "no suitable recommendation". Fix: envelope addendum with `status`/`reason_codes` or an opt-in diagnostics field.

### P4-M5 — MEDIUM — conflicts/prerequisites dropped at the K1 seed boundary
`seed_interventions.py::load_library_contracts` maps the 19 library entries onto the frozen `CircularIntervention` schema only, so `conflicts_with_codes`/`prerequisite_codes` never reach the simulator; Module O cannot block conflicting combinations (solar vs solar-thermal, RO prerequisites). Fix: contract addendum or simulator reads the P4 library metadata. Related to P3-01.

### P4-M6 — MEDIUM — operating hours missing from explanations
Module M explicitly requires "operating hours" among supporting evidence; neither the hotspot envelope nor P4 evidence carries them. Fix: P3 includes per-process hours (structured) or P4 joins `ProcessAsset.operating_hours`.

### P4-M7 — MEDIUM — tariff currency never validated against constraint currency; assessment carries no currency
`context.tariffs.currency` is ignored; money values would be presented under `constraints.currency` regardless. Fix: validate/convert explicitly, record currency in `assumptions` (and ideally the assessment via addendum).

### P4-M8 — MEDIUM — P4 CO₂ savings lack factor provenance
`resource_factors_from_factors` returns only values; `impact.assumptions` records quantities/tariffs but not the selected factor `code/version/source_year`. Fix: return and persist per-slot provenance (Module E/F "every result should retain factor version and source").

### P4-M9 — MEDIUM — no structured low-data-quality warning before generation
P4 never emits `ValidationIssue`; the only signal is a post-hoc template sentence. Module D edge: "Data quality < threshold → Show warning **before** recommendation generation". Fix: threshold + `WARNING` issue in diagnostics/envelope.

### P4-M10 — MEDIUM — recycled-material factors misclassified as recycling-processing
`p4/data_source.py:150-157`: any factor with "recycl" in its text becomes the single `recycling_processing_emission_factor` slot before material classification; recycled-input factors (e.g. recycled LDPE/cotton) can never fill packaging/material slots, and one processing factor is applied to all waste streams. Fix: explicit pathway marker + material/waste-type scoping.

### P4-M11 — MEDIUM — stub mode serves P4 endpoints anonymously (by design; production JWT enforced)
**Cross-ref P2-01/P2-02 (P2-owned surface) and readiness ledger item 3.** Executed on current main:
`GET …/recommendations` and `GET …/recommendations/{id}/feedback` → **200 with no credentials** under `AUTH_MODE=stub`; the router-level `get_current_principal` dependency runs but stub semantics treat an absent org header as the default demo tenant (`backend/app/guards.py`). JWT mode is strictly enforced (readiness: 401/403 matrix, 28/28). Doc §24 requires Authentication on every endpoint. Fix/decision: keep stub only for dev/demo, and record the explicit "stub = anonymous dev tenant" exception in the contract or close it with a required stub header before any shared deployment.

### LOW findings (carried forward, unchanged)
| ID | Summary |
|---|---|
| P4-L1 | Sub-score rubric derivations not exposed in output/assumptions (auditability polish) |
| P4-L2 | Missing CO₂ estimate conflated with zero carbon score |
| P4-L3 | No "top drivers"/simplified-vs-expert views; no causal-language guard (F-12 backlog, owner P4) |
| P4-L4 | No "actual saving physically implausible" feedback flag |
| P4-L5 | M1 `generated_by` hardcoded TemplateExplainer; no LLM model/version logging |
| P4-L6 | J2 `status`/`rank_max` query params unvalidated (invalid status → empty 200) |
| P4-L7 | Broad `except Exception` mock fallback in `p4/data_source.load_hotspots` can mask programming errors |
| P4-L8 | No Hypothesis property tests for P4 (PHASE1_AUDIT C3) |
| P4-L9 | No prompt-size guard on untrusted hotspot narrative |

---

## 3. Executed evidence digest (`tools/phase3_p4_checks.py`)

```
=== Item 1 ===  8/8 PASS
budget=150k: ranked=['INT-NOCAPEX-019','INT-WASTESEG-015']; above-budget present=[]
budget=150k: 16 codes filtered BUDGET_EXCEEDED, none ranked
budget=200k boundary: CAIR (mid==budget) admitted
max_complexity=MEDIUM: INT-RO-014 filtered COMPLEXITY_LIMIT
locally_unavailable_codes: INT-WHR-001 filtered LOCALLY_UNAVAILABLE
region mismatch: feasibility delta=15.0, item retained

=== Item 2 ===  2/2 PASS
1 INT-SCRAP-004   manual=77.37 engine=77.37   ... 5 INT-PKG-005 manual=67.38 engine=67.38
INT-WHR-001: 6/6 components exact; INT-SCRAP-004: 6/6 components exact

=== Item 3 ===  8/8 PASS
validated LLM: sources={'llm': 18}, ranking/IDs identical
score injection: sources={'template_fallback': 18}, ranking identical
contradiction: 18/18 attempts=2; observed '52.04 years' rejected
unknown code / real-but-foreign code: rejected with 'unsupported intervention citation'
real CSV upload: 202; injection stored verbatim in activity_data.notes
evidence fields=48, 'notes' absent; injection forced into narrative: rejected, ranking identical

=== Item 4 ===  4/5 PASS
USEFUL/NOT_APPLICABLE(r)/IMPLEMENTED 201,201,201; history=[1,2,3]; latest IMPLEMENTED
missing reason 422; bad reason_code 422; bad numeric 422
FAIL: invalid feedback_type -> 500

=== Item 5 ===  8/8 PASS
hotspots: total=566360.800000, top=Boiler HIGH
J2: 18 recs, all bound to real hotspot ids; data_is_stub 18/18
K1 with all 18 ids: 200; baseline=7203660.8 == inventory; projected=6919020.543; saving=284640.257
report: 202/200; recommendations=REAL 18/18; provenance=11; scope total==inventory

=== R - regressions / cross-checks ===  1/4 PASS
P3-12: flipping severity/hotspot_score/rank leaves P4 ranking identical  -> PASS
P4-C1: J2=500 N1=500 for a real non-demo facility                     -> FAIL (owned P4)
P4-H1: negative recycling net raises ValidationError                  -> FAIL (owned P4)
P3-01: mock-path K1 404 for a library-only id                          -> FAIL (owned P3)

SUMMARY: 33/37 passed
```

---

## 4. Upstream cross-checks (no re-litigation)

| Item | Source | This pass |
|---|---|---|
| **P3-12** missing-improvement reweight changes hotspot order/severity — "confirm whether P4 ranking reads `hotspot_score`/`severity`" | `p3_audit.md` §3, notification | **Answered: P4 does not read them numerically.** Executed: flipping every hotspot's `severity`, `hotspot_score` and `rank` leaves recommendation IDs/ranks/final scores byte-identical. P4 consumes `emissions_kgco2e`, `process_name`, `activity_category`, `contribution_percent` (explanation only) and envelope `data_quality_score` (confidence). P3-12 therefore affects explanation text, not the ranking. |
| **P3-01** K1 mock path cannot resolve 13 of 18 ids | `p3_audit.md` §2 | **Confirmed on current main:** mock K1 for `INT-STEAMTRAP-006` → 404. SQL/PG path resolves all 18 (item 5 PASS). P4-side mitigation available: `simulate` may resolve unknown ids via `p4.library.default_library()`. Owner P3 (per P3 audit), P4 helper offered. |
| **P3-06 / P3-22** weak fallback factor match / DQ default 60 feed confidence | `p3_audit.md` §3 | P4 confidence consumes envelope `data_quality_score` (weight 0.6); an inflated DQ propagates into P4 confidence until P3 fixes land. Cross-referenced, P3-owned. |
| **P2-01 / P2-02** unauth reads / auth-not-first | `p2_audit.md` | P4 router now carries router-level principal + tenant guards (T0-3/readiness); remaining stub-mode anonymity recorded as P4-M11 (cross-ref, consistent with P2's framing). |
| **P2-04** 8 mock factors seeded alongside 10 real ones | `p2_audit.md` item 4 (LOW) | Not re-litigated. Consequence noted for item 5: in the PG seed, Scope-3 mock factors resolve, so the K1 baseline includes Scope 3 (7,203,660.8) while hotspots stay S1+S2 (566,360.8); coherent, and P2 already logged the fixtures. |
| **P4-H3** no auth on P4 endpoints | prior P4 first-pass audit | **Closed with caveat:** router-level AuthN + tenant guards added (readiness item 3: JWT 401/403 matrix 28/28; two-tenant tests). Stub mode remains anonymous by documented design → now tracked as P4-M11. |
| F-6/F-8/F-13/T0-2/T0-3 closures | readiness ledger §§2-3 | Cross-checked: M1 404 frozen shape, `data_is_stub` labelling (18/18 in item 5), reason_code/numeric 422s all verified by execution; `feedback_type` remains the one F-13 gap (P4-M1). |
| Q persistence / J3 store | `docs/phase3/backlog.md` (P2) | In-memory append-only semantics verified; persistence deferred with owner. |

---

## 5. Notifications

- **P1 — CRITICAL (dashboard):** P4-C1. J2 recommendations and N1 dashboard are 500 for any
  non-demo facility while the live engine is active; the dashboard cannot be relied on for
  newly created facilities until `p4/api.py::_run_ranker` uses the live facility dataset/context.
  The mock fallback keeps the demo green. Track with P2's fast-track handoff.
- **P2 — HIGH (cross-ref, already queued):** P4-H2 bridge remediation; also note P4-M11
  (stub-mode anonymity) as the shared decision with P2-01/P2-02.
- **P3 — info + confirmations:** P3-12 does not affect P4 numerics (executed answer above);
  P3-01 confirmed open on the mock path (P4 library resolver offered).
- **Audit owner (P4 follow-up pass):** P4-C1 → P4-H1 → P4-M1 first; P4-M5/P4-M9/P4-M7 next.

## 6. Verdict

**PASS on all five checklist items, with four defects surfaced by the checks.** Feasibility
filters demonstrably precede ranking (budget/complexity/local-availability, with the documented
location-penalty policy); the scoring formula reproduces exactly by hand for 5 real
recommendations including independent component re-derivation; the LLM guardrails hold under
real evidence (ranking immunity incl. score-field injection, 18/18 contradiction
reject/regenerate, unknown and foreign citations rejected, real-upload injection stored inert
and unable to alter numbers); feedback history is append-only across real API states; and the
full demo pipeline — hotspot → recommendation → simulation → report — is coherent on real PG
data with hardcoded demo UUIDs. The four failures are: **P4-C1 (CRITICAL, dashboard-breaking,
owner P4)**, **P4-H1 (HIGH, data-dependent crash, owner P4)**, **P4-M1 (MEDIUM, error shape,
owner P4)**, and **P3-01 (upstream, owner P3, confirmed open)**. No production code was
changed in this pass.
