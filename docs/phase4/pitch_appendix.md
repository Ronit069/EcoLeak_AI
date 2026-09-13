# EcoLeak AI — Pitch Appendix: "Why this is defensible"

**Owner:** P4 · **Base revision:** `main` @ `d4a5ee8`
**Purpose:** the exact answers to the two hardest judge questions, using only claims already
documented in the merged Phase 3 audits. P3's Phase 4 `/docs/phase4/trust_summary.md` is the
canonical one-pager; this appendix mirrors the same facts and should be updated with a link when
P3's file lands. Nothing here is a new claim.

---

## 1. The two hardest questions

### Q1 — "How do I know the numbers are real?"

**Answer (30 seconds):**

> "Every number is a product of two inputs a judge can inspect: the activity value the factory
> reported, and an emission factor from a versioned knowledge base that carries its source, year
> and version. The accounting is ordinary decimal arithmetic — quantity × factor — with no AI in
> the loop. The report prints the factor code and source next to every calculation, and rows
> where no factor matches are excluded and flagged, never silently zeroed. We also hand-verified
> the arithmetic on the demo data, and the engine is covered by 175 tests locally and 80 more
> against PostgreSQL in CI."

**Receipts to point at:**

| Claim | Evidence |
|---|---|
| CO₂e = activity × factor, decimal arithmetic, no LLM | `engine/carbon.py`; `docs/phase3/p3_audit.md` item 1 (5 mock + 2 real products hand-recomputed exactly) |
| Factors are real and versioned | Seeded KB: CEA India grid 0.71 (v21.0, FY 2024-25), DEFRA 2023 fuels (NG 2.0384, diesel), IPCC AR5 refrigerants; report's **Factor provenance** list shows code/source/year/version per row |
| Hand-verified walkthrough | P3's `docs/phase4/calculation_walkthrough.md` (raw activity → factor → CO₂e → hotspot → simulator, arithmetic spelled out) |
| Honest gaps | Demo report shows **2 unresolved rows** (dyeing chemicals, wastewater) excluded from totals and flagged; the page says so on screen |
| Reproducibility | Deterministic engine, deterministic IDs, report content hash; recompute gives identical results for identical inputs (Phase 3 audit item 6) |
| Tests + CI | 175 root tests, 80 backend tests on PostgreSQL, CI workflow "EcoLeak CI" (4 jobs) gates `main` (branch protection enabled) |

**Disclose the fixture:** CAPEX/savings use a tariff fixture labelled `data_is_stub=true` on the
recommendation page and in the report. Saying it first makes the real/fixture boundary a trust
feature, not a discovery.

### Q2 — "How do I know the AI isn't hallucinating recommendations?"

**Answer (30 seconds):**

> "Because the AI doesn't make recommendations. Candidates come from a curated 19-intervention
> library; hard feasibility filters run before ranking; and the ranking is a deterministic
> weighted formula — carbon 30%, financial 25%, feasibility 15%, circularity 15%, speed 10%,
> confidence 5%. The language model is only allowed to write the explanation sentence, and it is
> fenced in: it can only cite intervention IDs that exist, any number that contradicts the stored
> calculation is rejected and regenerated, and prompt injection is isolated as data. In the demo
> you're seeing, the explanation is generated deterministically and no LLM is called at all."

**Receipts to point at:**

| Claim | Evidence (executed on real evidence, `docs/phase3/p4_audit.md` §3) |
|---|---|
| Ranking is deterministic | Exact weights in `p4/scoring.py`; hand-recomputed weighted sums for 5 real recommendations match the engine to 2 decimals; 12/12 component rubrics independently re-derived |
| Filters precede ranking | Budget ₹150k run: 16 over-budget codes filtered before output, none ranked even low; complexity, prerequisites and local-availability also pre-rank filters |
| LLM cannot touch numbers | Adversarial run injecting `final_score: 100` / `rank: 1` fields → rejected by schema (`extra="forbid"`), 18/18 fallback, ranking byte-identical |
| Contradictions rejected | Forced wrong values against **every** real evidence item: **18/18 rejected and regenerated** (sample: a fabricated "52.04 years" payback rejected, valid text re-generated) |
| Unknown citations rejected | Unknown code `INT-FREE-MONEY` and a **real code belonging to another recommendation** (`INT-LED-008`) both rejected |
| Prompt injection ignored | A real CSV upload carrying "IGNORE ALL PREVIOUS INSTRUCTIONS…" was stored as ordinary text; the evidence model has no notes field; forced into the untrusted narrative it still could not alter ranking |
| LLM optional | The demo runs `TemplateExplainer` (deterministic, no API key); the LLM path exists only as a validated enhancement |

**Bonus:** the "AI doesn't pick" property is why the recommendation list includes uncomfortable
answers — solar ranks #10 despite the best carbon score (payback 8 years), and the top picks are
cheap waste/steam fixes, not the most impressive-looking technology.

---

## 2. Trust summary (pulled from the Phase 3 audit synthesis)

Source: `docs/phase3/final_audit_summary.md` + `docs/phase3/fix_report.md` + `docs/phase3/p3_audit.md`.
(P3's `docs/phase4/trust_summary.md` will supersede this section when it lands.)

1. **Versioned factors, never overwritten.** Factors carry source, year and version; updates
   deactivate the old row and create a new version; every resolved calculation keeps the factor
   it used (DB doc §6.1 / §7.1). Report provenance lists them.
2. **Deterministic engine, Decimal arithmetic.** Activity × factor in Python `Decimal`; hotspot
   scores from documented weights; simulator payback = CAPEX ÷ saving with an explicit
   `UNAVAILABLE` state when saving ≤ 0; projected emissions floored at 0.
3. **No LLM in calculation.** The language model never computes, ranks or selects; it writes
   explanation text over stored evidence, and is validated for citations and numbers
   (reject-and-regenerate). The default demo uses no LLM at all.
4. **Honest unresolved states.** Missing factors produce an explicit unresolved row
   (`EMISSION_FACTOR_NOT_FOUND` / `NO_MATCHING_FACTOR`) excluded from totals — never fabricated.
5. **Auditable outputs.** Reports carry factor provenance, scope boundary, data-quality score and
   a content hash; exports are JSON/CSV. Platform writes are audited (`audit_logs`), and the
   remaining persistence/rerun-audit gap is a documented Phase-3 item with an owner (P3-07).
6. **Verified by execution.** 175 root tests + 80 PostgreSQL backend tests + CI gate (4 jobs) +
   adversarial K1 job; Phase 3 audits executed the hand-arithmetic, the guardrails, and the
   real-PostgreSQL paths; branch protection now enforces the CI gate on `main`.

---

## 3. Real vs fixture — say this before a judge asks

| Component | Status | How it is labelled |
|---|---|---|
| Activity data | Realistic synthetic textile SME (13 activity rows, FY 2025-26); real import pipeline (CSV/Excel + Pandera + Pint) | Import report; source names on data-input page |
| Emission factors | **Real published factors** (CEA India grid, DEFRA fuels, IPCC AR5 refrigerants) + 8 mock-labelled fixtures for Scope-3 categories | `(mock)` in source name; report provenance lists source/year/version |
| Tariffs / prices | **Fixture** (demo tariff set) | `impact.assumptions.data_is_stub=true`; amber "Fixture financial baselines" notice |
| Intervention library | Curated 19-entry P4 library; evidence sources are mock references | `Evidence source: … (mock)` inside each explanation |
| LLM narrative | **Not used by default** (deterministic template); optional validated path | Explanation text is evidence-bound; guardrails documented |
| Circularity score | Internal decision metric, 0 for this linear factory | "Module L — internal metric", not a certification |

---

## 4. Limitations we volunteer (and why they don't sink the demo)

| Limitation | Honest one-liner | Detail / owner |
|---|---|---|
| Fixture-priced financials | "Prices are a labelled fixture; the calculation is real." | P3-08, `data_is_stub` banner |
| 2 unresolved activity rows | "They're excluded and visible, not zeroed." | Dyeing chemicals, wastewater (no seeded factor) |
| Calculation persistence / rerun audit | "The model is exactly reproducible; persisting every run to the audit table is the next step." | P3-07, owner P3 |
| Single demo facility / period | "One facility here; the product supports separate facilities — the ranker resolves each facility's own data." | GA-01 fix verified |
| Scope-3 totals include mock-labelled factors | "Scope 3 exists to show the size of the blind spot; those fixtures are labelled." | P2-04 (LOW) |

---

## 5. Evidence index (for the deck's appendix slide)

- `docs/phase3/p3_audit.md` — hand-recomputed arithmetic, factor gaps, simulator edge cases.
- `docs/phase3/p4_audit.md` — LLM guardrails executed, feasibility-before-ranking, formula re-derivation.
- `docs/phase3/p2_audit.md` — live DB constraints, audit trails, unauth-read findings.
- `docs/phase3/final_audit_summary.md` — every CRITICAL/HIGH mapped to fixed/open with goal impact.
- `docs/phase3/READINESS.md` — CI red/green, JWT auth matrix, real-PostgreSQL runs.
- `docs/phase4/demo_script.md` — the live walkthrough + fallback video.
- `docs/phase4/bugs_found.md` — known display caveats the presenter should not be surprised by.
- `docs/phase4/calculation_walkthrough.md` (P3) — the number-by-number worked example.

## 6. One-breath cheat sheet

- "Quotes surface, engineering prices." → recommendations ranked by business return, not carbon theatre.
- "LLM writes words, never numbers." → deterministic ranker + validated narrative.
- "Unresolved stays unresolved." → missing factors are excluded and flagged, never faked.
- "Same inputs, same outputs." → deterministic engine, versioned factors, report hash.
- "Fixture prices are labelled." → `data_is_stub=true` on screen.
