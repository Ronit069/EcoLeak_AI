# Phase 3 — Final Audit Synthesis

**Purpose:** map every CRITICAL and HIGH finding across the Phase-1 audit lineage
and the four Phase-3 role audits to the original impact goals, record whether it
is **fixed**, **must fix before the next submission**, or a **known limitation**,
and rank the open work by what an evaluator will *directly see in a live demo*.

**Inputs read:** `PHASE1_AUDIT.md` (friend's Phase-1 report; `PHASE2_AUDIT.md` +
`docs/phase2/PHASE2_REMEDIATION.md` used as its remediation lineage),
`docs/phase3/p1_audit.md`, `docs/phase3/p2_audit.md` (+ `p2_audit_fasttrack.md`),
`docs/phase3/p3_audit.md`, `docs/phase3/p4_audit.md`, and the cross-cutting
`docs/phase3/general_audit.md`.

**Status basis:** `phase3-fixes` branch (PR #7) on top of `main` @ `e479c34`.
> **Merge caveat:** the fixes below are proven on PR #7 but **not yet merged to
> `main`**. Until #7 merges, every "FIXED" item is still open on `main` — the
> CRITICALs especially (P4-C1/GA-01) would still break any non-demo facility.

---

## 0. The four impact goals

| ID | Goal (problem statement) | What "good" looks like |
|---|---|---|
| **G1** | Emission sources **visible and actionable** for smaller businesses | Any facility's hotspots, scope split and leak points render and are drillable |
| **G2** | Drives adoption through **concrete, costed recommendations** | Ranked, budgetable interventions with CAPEX/saving/payback |
| **G3** | **Supports compliance with emerging carbon regulations** | Scope boundary correct and labelled, period locks, factor provenance, exportable report |
| **G4** | *(implicit)* **Auditability / trust in every number** | Every figure reproducible, sourced, and honestly labelled; no silent fakes |

---

## 1. Master mapping — every CRITICAL / HIGH finding

Status: **FIXED** = closed on PR #7 with executed evidence; **OPEN** = not yet fixed.

| ID | Sev | Source | One-line | Goal(s) | Status |
|---|---|---|---|---|---|
| **P4-C1 / GA-01** | CRITICAL | P4 / general | J2 recommendations + N1 dashboard 500 for **every non-demo facility** (mock demo facility/context hardcoded) | G1, G2, G3 | **FIXED** (live data source) |
| **P3-01 / GA-06** | CRITICAL | P3 / general | K1 simulator can't resolve 14/18 intervention ids on the **mock path** | G2 | **FIXED** (mock library = 19) |
| **P3-02** | HIGH | P3 | Factor validity window ignored vs reporting period | G3, G4 | OPEN |
| **P3-03** | HIGH | P3 | Region specificity ignored (wrong-country factor can apply) | G3, G4 | OPEN |
| **P3-04** | HIGH | P3 | Renewable/on-site electricity keyword-classified and excluded as if zero; captive fossil understated | G1, G3 | OPEN |
| **P3-05 / P2-06** | HIGH | P3 | Period `LOCKED`/`CLOSED` not enforced on F1 calculations | G3 | **FIXED** (409 PERIOD_LOCKED) |
| **P3-06** | HIGH | P3 | Weak/fallback factor matches don't lower confidence | G4 | OPEN |
| **P3-07** | HIGH | P3 | No persistence of calculations/hotspots; no `CALCULATION_RERUN` audit | G4 (G3) | OPEN |
| **P3-08** | HIGH | P3 | Cost/price data hardcoded/unsourced under "costed" recommendations | G2, G4 | OPEN (labelled `data_is_stub`) |
| **P4-H1** | HIGH | P4 | Negative-net recycling raised `ValidationError` → whole ranking crashed | G2 | **FIXED** (floor + signed note) |
| **P4-H2** | HIGH | P4 | Module P recommendations section still mock-derived + demo context | G3 | **FIXED** (live bridge) |
| **P2-01** | HIGH | P2 | Unauthenticated read access to KB endpoints (`/emission-factors`, `/interventions`) | G3, G4 | **FIXED in JWT**; stub residual (dev-only) |
| **P1-01** | HIGH | P1 | Dashboard "TOTAL EMISSIONS" is all-scope while header says Scope 1+2; hotspot share uses operational denominator | G3, G4, G1 | **FIXED** (labels + denominator) |
| **GA-02** | HIGH | general | Production could boot with `AUTH_MODE=stub` (header-spoofable) | G4 (G3) | **FIXED** (fail-closed) |
| **GA-03** | HIGH | general | Branch protection on `main` never applied | G4 (process) | OPEN (owner-admin) |
| **P1-AUDIT B1** | blocker | Phase-1 | No live G2/J2/N1/N2 endpoint served | G1, G2 | **FIXED** (merged API) |
| **P1-AUDIT B2** | blocker | Phase-1 | P3 had no SQL-backed data source | G1, G3 | **FIXED** (`sql_source`) |
| **P1-AUDIT B3** | blocker | Phase-1 | Factor-set divergence mock vs real shifts totals/severity | G4 | **Accepted decision (b)** — documented illustrative-mock; **known limitation** |
| **P1-AUDIT #5** | silent-risk | Phase-1 | Recycling-loop emissions not modelled (recycling ≠ zero) | G2, G4 | **FIXED** (C2; P4-H1 handles negative net) |
| **P1-AUDIT #6** | silent-risk | Phase-1 | Hotspot severity drift live vs frozen mock | G1, G4 | **Accepted decision (b)** — **known limitation** (documented) |

*(Phase-2 lineage, for completeness: K1 wrapper shape, scenario-slider 404, and
the PG-only runtime gap — all previously remediated and re-verified on real PG;
the K1 loose-assertion/env-baking false positives are guarded by the CI
`K1-adversarial` job.)*

---

## 2. Unresolved findings — goal threat + disposition

### Must fix before the next submission (real-data/compliance credibility)

| ID | Goal threatened | Why it must be fixed (not just logged) |
|---|---|---|
| **P3-07** | G4 (auditability — a *stated* goal) | "Every number auditable/reproducible" is not met while calculations/hotspots are never persisted and no `CALCULATION_RERUN` audit exists. A compliance claim cannot rest on "recompute and hope inputs are unchanged". |
| **P3-04** | G1, G3 | Any real facility with on-site generation gets Scope 1/2 *understated* (assumed zero) and captive-fossil mis-scoped. This is a **materially wrong number** for exactly the SMEs the product targets. |
| **P3-02** | G3, G4 | Applying an out-of-window factor to a current period is a wrong, unauditable number under a compliance lens. |
| **P3-03** | G3, G4 | A wrong-country factor applied silently breaks the "sourced/reproducible" promise. |
| **P3-06** | G4 | Confidence is a trust signal; not penalising weak fallback matches overstates confidence. |
| **GA-03** | G4 (process) | Unprotected `main` means the "proof a stranger can reproduce" guarantee (CI gating) is not enforced; admin-only. |

### Can be logged as a known limitation (for a demo-focused round) if labelled

| ID | Goal | Acceptable only if… |
|---|---|---|
| **P3-08** | G2, G4 | The **`data_is_stub=true`** label + "Fixture financial baselines" UI notice remain prominent (they do, F-8/P1). Evaluators must be told CAPEX/payback are fixture-priced. |
| **P2-01 residual** | G3, G4 | No deployment runs `AUTH_MODE=stub` (GA-02 now blocks stub outside development). Demo is dev-only. |
| **P1-AUDIT B3 / #6** | G4 | The live-vs-mock severity/factor differences stay documented (CONTRACTS_README decision (b)); evaluators don't compare against mocks. |

---

## 3. Fix list ranked by live-demo visibility

Order = *will a judge/evaluator see this on screen during the demo?* (descending).

**Tier A — directly visible on the demo screens**
1. **P3-08 (HIGH, G2/G4)** — CAPEX / annual saving / payback rendered on Recommendations + Dashboard + Scenarios. *Status: demonstrated with fixture prices, labelled `data_is_stub`.* → **Known limitation if the label stays; otherwise must-fix.** Highest visible impact because it is the "costed" promise.
2. **P3-04 (HIGH, G1/G3)** — Scope 1/2 totals and scope labels. *Not triggered by the current seed fixture* (no on-site activity rows), so invisible today; **must-fix before any real-data demo** (a solar/captive row flips the totals).
3. **P3-02 / P3-03 (HIGH, G3/G4)** — can change displayed totals/severity if data has expired or foreign factors. *Not triggered by the seed* (India grid factors, null validity windows) → invisible in the current demo; **must-fix before compliance-grade claims**.
4. **P3-06 (HIGH, G4)** — confidence/DQ figures shown on cards; a fallback match currently looks as confident as an exact one. Subtle on screen → **must-fix before claiming confidence accuracy**, low demo risk.

**Tier B — visible only in reports/exports, not the live screens**
5. **P3-07 (HIGH, G4)** — report "factor provenance" and audit trail; the report *renders* fine, but the underlying persistence/audit is absent. **Must-fix before any compliance submission**; invisible in the demo.
6. **GA-03 (HIGH, process)** — nothing on screen; **admin action**, log as known limitation.

**Tier C — not visible at all (ops/security)**
7. **P2-01 residual (HIGH, G3/G4)** — stub-mode anonymity; blocked in real deployments by GA-02. Known limitation.
8. **P1-AUDIT B3/#6 (accepted decisions)** — mock-vs-live differences; documentation-level. Known limitation.

> **All demo-visible CRITICAL/HIGH items are fixed on PR #7.** The current seed
> demo (Shakti Textiles) renders live, contract-accurate numbers with no mock
> fallback, no console errors, correct scope labels, a visible fixture-price
> notice, a Reports page, and a facility selector.

---

## 4. Goal-coverage verdict

| Goal | Open CRITICAL/HIGH threatening it | Net status after PR #7 (once merged) |
|---|---|---|
| **G1** Visible & actionable for SMEs | P3-04 (real-data only) | Demo-ready; real-data on-site gap remains |
| **G2** Concrete, costed recommendations | P3-08 (labelled) | Demo-ready with fixture-price disclosure |
| **G3** Regulatory compliance support | P3-02, P3-03, P3-04, P4-H2→fixed | Demo-ready; **not compliance-grade** until P3-02/03/04/07 close |
| **G4** Auditability / trust | P3-07, P3-06, GA-03, P1-AUDIT B3/#6 | Trustworthy on screen; not yet end-to-end auditable |

**Bottom line:** with PR #7 merged, there is **no open CRITICAL/HIGH that a
judge will see break or mislabel during the seed-facility demo**; the remaining
open HIGH items are either (a) labelled fixture-pricing (P3-08), (b) only
triggered by data the seed doesn't contain (P3-02/03/04), or (c) invisible to a
live demo but blocking for *compliance-grade* claims (P3-07, P3-06, GA-03).

**Before the next submission round:** merge PR #7 (clears all demo-visible
CRITICAL/HIGH) and apply branch protection (GA-03). **Before any compliance
claim:** close P3-07, P3-04, P3-02/P3-03, P3-06. Everything else is a documented
known limitation with an owner in `docs/phase3/backlog.md`.

---

## 5. Update — ranked fixes applied (branch `phase3-fixes`, commit `d341b17`)

**Now closed** (see `fix_report.md` §6, tests in `tests/test_phase3_engine_fixes.py`):
**P3-04** (on-site/captive ledger), **P3-02** (validity window), **P3-03** (region
specificity), **P3-06** (confidence penalties), **P3-08** (price provenance — now
sourced/versioned *and* still labelled `data_is_stub`).

**Still open, in ranked order:**
1. **P3-07** (HIGH, G4) — **the one must-fix-before-compliance item**: persist
   calculations/hotspots + `CALCULATION_RERUN` audit. Cross-team P3+P2 write path;
   not demo-visible; plan in `backlog.md`. Deliberately **not** implemented as a
   best-effort silent write.
2. **GA-03** (HIGH, process) — branch protection still unapplied (owner-admin).
3. **P2-01** residual (stub-only; blocked by GA-02).
4. **P3-09…P3-25 / P4-M4…M11 / LOWs** — methodology/feature backlog.

**Suites:** root `pytest` **175 passed**, backend on PostgreSQL **80 passed**,
mock + shape gates PASS. No unsolved *errors* remain; the open items are
unimplemented capability (P3-07) and process/admin (GA-03).
