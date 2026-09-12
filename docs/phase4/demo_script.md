# EcoLeak AI — Judge Demo Script (4–6 min)

**Owner:** P4 (Demo Script & Pitch Narrative) · **Base revision:** `main` @ `d4a5ee8`
**Target runtime:** **5:30** (hard stop 6:00) · **Presenter:** one voice, one clicker
**Live URL:** _P2 to paste here from `docs/phase4/deployment.md` once deployed_ — until then, use the
local fallback in §3 (verified local stack) or the fully-mocked offline mode.
**Scenario:** Shakti Textiles Pvt. Ltd. (fictional), Surat, Gujarat — 1,000 t fabric/year,
FY 2025-26, processes Dyeing → Drying → Boiler → Finishing → Packaging → Transportation.

> **Before judging, verify the demo is in LIVE mode.** Open the app; if the amber
> "Using demo data" banner is visible, click **Force live** (or fix the API) so the walkthrough
> shows engine numbers. If the banner lists only a specific group (e.g. `activities`), that is
> the honest per-group mock fallback — say so and continue (§4).

---

## 0. Pre-flight (T-10 minutes)

1. Open the live URL in Chrome/Edge; **zoom to 110%** so gauge text is readable from the back.
2. Confirm **no amber banner**. Left rail must show: Dashboard · Recommendations · Processes ·
   Data input · Profiling · Scenarios · Reports.
3. Visit **Dashboard** once and check: TOTAL EMISSIONS ≈ 7,203.7 t · LARGEST LEAK `#1 Boiler` ·
   LEAK POINTS list shows 5 rows · no red error notice.
4. Visit **Reports** and delete nothing; leave the list as-is (we generate a fresh report live).
5. Close other tabs/notifications. Put the pitch deck on a second desktop (Appendix content in
   `docs/phase4/pitch_appendix.md`).
6. Keep `docs/phase4/demo_script.md` (this file) open on your phone as a cue card.

**If anything looks wrong, switch to §3 fallback immediately.** Never debug in front of judges.

---

## 1. Run sheet

### S0 — Opening (0:00 → 0:25) · Screen: **Dashboard**

| Do | Say (verbatim) |
|---|---|
| Land on Dashboard, cursor still. | "This is Shakti Textiles, a small dyeing and finishing unit in Surat — 1,000 tonnes of fabric a year. In one screen we show where its carbon actually leaks, and what to do about it." |
| Gesture across the six gauges. | "Seven thousand two hundred tonnes all-scope — most of that is embedded carbon in the cotton they buy. The Scope 1 and 2 operational footprint we control is **566 tonnes**, and the single biggest leak is the **Boiler at 39.8%**." |

**Proof on screen:** TOTAL EMISSIONS (ALL SCOPES) 7,203.7 t · gauge sub-line `Scope 1+2 566,360.8 kg` · LARGEST LEAK `#1 Boiler · 39.83%`.

### S1 — The leak map, drilled to a machine (0:25 → 1:15) · Screen: **Dashboard**

| Do | Say (verbatim) |
|---|---|
| Point at **Leak points, ranked** rail. | "Notice we don't show a pie chart of a total. We rank the leaks: Boiler, Dyeing, Drying, Finishing, Packaging — each with severity and share." |
| Under **Carbon leak map (D3 drill-down)**, click the dark facility card. | "Facility → process." |
| Hover the tall orange **Boiler** bar (tooltip shows `Boiler · HIGH · 225,560.8 kg`), then click it. | "Boiler emits 225.6 tonnes — 39.8% of operations, severity HIGH." |
| The activity view lists **Natural gas** (95,000 m3) and **Diesel** (12,000 L); click **Processes**, then **Facility** to reset. | "And here is the root cause — gas and diesel going into that boiler. That's the leak point, not a generic 'energy' category." |

**Proof on screen:** five ranked bars → Boiler bar → activity rows with values/units · *Pareto* below shows the 80/20 concentration · *Scope breakdown* donut.

### S2 — Largest is not automatically the best target (1:15 → 1:35)

| Do | Say (verbatim) |
|---|---|
| Point at the accent notice above the gauges: **"Best intervention target: Boiler (rank 1)…"** | "The biggest emitter isn't automatically the smartest action. Our hotspot score weighs contribution, intensity, inefficiency, waste ratio and improvement potential — here Boiler scores highest on both, but on a factory where a smaller process has more headroom, this target flips. That's why we rank actionability, not size." |
| Point at **Circularity** gauge `0`. | "Circularity is zero — a genuinely linear factory. That is the baseline we improve." |

### S3 — Concrete, costed recommendations (1:35 → 2:40) · Screen: **Recommendations**

| Do | Say (verbatim) |
|---|---|
| Click **Recommendations** in the rail. | "Nineteen interventions in our curated library; the ranker returns the eighteen that apply here." |
| Point at the amber **Fixture financial baselines** notice. | "Full transparency: CAPEX and savings use a tariff fixture that is labelled `data_is_stub`. The calculation plumbing is real; plugging in the factory's own tariffs is a config swap." |
| Point at card **#1 INT-SCRAP-004**. | "Rank one: **textile offcut collection and recycled yarn recovery**. It cuts **32 tonnes of CO2e a year** for **₹5 lakh** of CAPEX, returns **₹2.45 lakh a year**, payback **2.04 years**." |
| Read the six component meters. | "Score 77.4 out of 100: carbon 64, financial 88, feasibility 100, circularity 60, speed 80, confidence 81 — an explicit weighted formula, not a black box." |
| Scroll to **#10 INT-SOLAR-002**. | "Solar has the best carbon score in the list — 51 tonnes — but ranks tenth because payback is eight years and it costs ₹42.5 lakh. A carbon-only tool would lead with it; a business tool won't." |
| Point at the closing note under the list. | "And the explanation text is evidence-bound: the LLM writes words, never numbers. If it contradicts a calculated value, we reject and regenerate it." |

**Proof on screen:** 18 ranked plates with component meters, CAPEX / annual saving / CO₂ saving / payback / ₹ per tCO₂e · fixture banner (`data_is_stub=true`) · explanations containing the exact same numbers as the cards.

### S4 — What-if the factory invests (2:40 → 4:05) · Screen: **Scenarios**

| Do | Say (verbatim) |
|---|---|
| Click **Scenarios**. Show the 18 sliders at 100% and the red **Over budget** notice. | "Everything at 100% costs ₹1.94 crore — well over the ₹50 lakh budget, and the app says so instead of hiding it." |
| Drag these seven sliders to **0%** (in rank order): `#10 INT-SOLAR-002`, `#12 INT-SOLAR-THERMAL-018`, `#14 INT-VFD-007`, `#15 INT-DYEBATH-003`, `#16 INT-STENTER-HR-010`, `#17 INT-RAIN-013`, `#18 INT-RO-014`. | "Let's keep the quick operational wins and park the big-ticket capital projects." |
| Wait for the green notice **Engine-verified simulation (K1)**. | "The engine recomputes every slider move — no server round-trip guessing." |
| Point at the numbers. | "Eleven interventions, **₹45.4 lakh CAPEX**, **₹30.5 lakh saved per year**, payback **1.49 years**, and **205.9 tonnes of CO2e avoided** in year one." |
| Point at BASELINE vs PROJECTED. | "Baseline 7,203.7 tonnes; project just under 7,000 tonnes. The simulator applies interventions sequentially so overlapping savings are not double-counted." |

**Alternative if sliders are slow:** skip the reset and drag only `#10`, `#12`, `#18` to 0 → still over budget; then say "budget forces prioritisation" and click **Clear all**, then drag any four green cards up. **Prefer the seven-slider version above; rehearse it twice.**

**Proof on screen:** over-budget notice at 100% (₹19,390,000 vs ₹5,000,000) · green `Engine-verified simulation (K1)` · PROJECTED 6,997.7 t vs Baseline 7,203.7 t · reduction 2.9% · CAPEX ₹45.4L · Annual saving ₹30.5L · Payback 1.49 years.

### S5 — The compliance-grade report (4:05 → 5:05) · Screen: **Reports**

| Do | Say (verbatim) |
|---|---|
| Click **Reports**, then **Generate report**. | "Everything on screen is exportable as an auditable report." |
| Click **View** on the new row. Point at **Scope summary**. | "Scope 1: 225.6 tonnes; Scope 2: 340.8; Scope 3: 6,637.3 embedded in purchased materials; total 7,203.7." |
| Point at **Factor provenance**. | "Every factor used is listed with its code, source, year and version — for example the CEA India grid factor v21.0 at 0.71 kg per kWh. Nothing is hard-coded or hidden." |
| Point at the **2 unresolved** notice. | "Two rows — dyeing chemicals and wastewater — had no matching factor, so they are **excluded from totals and flagged**, never silently zeroed. That honesty is the point." |
| Point at **Data quality** score (89.8/100) and the report hash. | "A data-quality score and a content hash ship with every report." |
| Click **JSON** (or CSV) to show the machine-readable export. | "Same numbers, machine-readable, ready for a regulator or a consultant." |

**Proof on screen:** 202/200 generate+view · scope table · provenance list · unresolved notice · DQ 89.8 · hash · JSON/CSV buttons.

### S6 — Close and hand off to Q&A (5:05 → 5:30)

| Do | Say (verbatim) |
|---|---|
| Back to **Dashboard**. | "EcoLeak AI turns raw factory data into a ranked, costed, auditable decarbonisation plan — it finds the leak, proves the number, and prices the fix." |
| Point at the footer/mode pill. | "If the live API has any hiccup, the app falls back to frozen payloads with a visible banner — the demo never dies. We'd love your hardest question." |

Then take questions using `docs/phase4/pitch_appendix.md` (two hardest questions pre-answered).

---

## 2. Exact demo data sheet (verify against screen before presenting)

| Thing | Value |
|---|---|
| Facility | Shakti Textiles — Surat Unit 1 (mock), 1,000 t/year, FY 2025-26 |
| Total emissions (all scopes) | 7,203,660.8 kgCO₂e |
| Scope 1 / 2 / 3 | 225,560.8 / 340,800 / 6,637,300 kgCO₂e |
| Operational (Scope 1+2) boundary | 566,360.8 kgCO₂e |
| Largest hotspot | Boiler — 225,560.8 kg, 39.83%, HIGH |
| Other hotspots | Dyeing 149,100 (26.33%, MODERATE) · Drying 106,500 (18.80%, LOW) · Finishing 56,800 (10.03%, LOW) · Packaging 28,400 (5.01%, LOW) |
| Hotspot data quality | 81.5 / 100 |
| Circularity | 0 (internal metric, not a certification) |
| Potential reduction / saving | 317,736 kgCO₂e · ₹6,699,475 (sum of standalone estimates) |
| Top recommendation | INT-SCRAP-004 score **77.4** · 32,000 kgCO₂e/yr · CAPEX ₹500,000 · saving ₹244,800/yr · payback 2.04 y |
| #2 / #3 | INT-WASTESEG-015 77.0 · INT-STEAMTRAP-006 71.7 |
| Solar contrast | INT-SOLAR-002 rank **#10**, score 61.8, carbon score 100 but payback 8.01 y, CAPEX ₹4,250,000 |
| Scenario all-18 @100% | CAPEX ₹19,390,000 → over ₹5,000,000 · projected 6,919.0 t · reduction 3.95% · payback 4.61 y |
| Scenario quick-11 (7 big-ticket at 0%) | CAPEX ₹4,540,000 · saving ₹3,051,271/yr · projected 6,997.7 t · reduction 2.86% · payback 1.49 y |
| Report | DQ 89.8/100 · 10 provenance entries · 2 unresolved · recommendations status REAL, 18 items |
| Unresolved rows | Dyeing chemicals (MATERIAL) · Wastewater (WASTE) — excluded and flagged |

**Two semantics to explain if asked:**
1. The **dashboard potential saving (₹67.0L)** sums the standalone estimates of all 18 recommendations; the **simulator (₹42.1L for 18, ₹30.5L for 11)** applies them sequentially so overlaps are not double-counted. Both are honest; the simulator is the conservative number.
2. The **scenario baseline is all-scope (7,203.7 t)** because the simulator works on the full inventory; the leak map is operational Scope 1+2 (566.4 t). Scope 3 is embedded cotton.

---

## 3. If the live URL is down (fallback)

**Level 1 — banner fallback (10 seconds).** If the amber banner appears, click **Auto** and let the
per-group fallback serve frozen payloads; say: "The live API is unreachable, so the app switched to
frozen Phase 1 payloads — same contract shape, visibly labelled." Continue the run sheet; numbers
will match the frozen mock (Boiler CRITICAL 39.69%, top rec INT-SCRAP-004, etc. — the scripted
values above are live values; in mock mode quote shares instead of exact savings if unsure).

**Level 2 — local one-command fallback (P2, `docs/phase4/deployment.md`).** If P2's Docker Compose
is available: `docker compose up --build` and open the printed URL; seed runs automatically.
**Level 3 — offline video** (Appendix A). Play the 2-minute recording; narrate the two hardest
questions after it.

*Locally verified by P4 during Phase 4 (clean seed): Postgres 18 + `python -m uvicorn app.main:app --port 8000`
from `backend/` with `USE_MOCK_DATA=false`, `DATABASE_URL` seeded via `python -m app.seed.run_seed`;
frontend per `frontend/README.md` (`npm install && npm run dev`, `VITE_USE_MOCK_DATA=auto`,
`VITE_API_URL=http://localhost:8000`).*

---

## 4. Judge interruptions — ready answers

| Interruption | One-line answer | Detail |
|---|---|---|
| "Is this real data?" | "It's a realistic synthetic SME with real published emission factors — CEA India grid, DEFRA fuels, IPCC refrigerants. Plugging in a real factory is an import away." | `pitch_appendix.md` Q1 |
| "Where do the CAPEX numbers come from?" | "From our intervention library, fixture-priced and labelled `data_is_stub=true` — the label is on screen." | S3 banner |
| "What if the AI lies?" | "The AI never touches numbers — the ranker is a deterministic weighted formula; the LLM only writes the explanation and is validated for numbers and citations." | `pitch_appendix.md` Q2 |
| "Why is scope 3 so huge?" | "Because it's embedded carbon in 1,100 tonnes of purchased cotton — exactly the blind spot SMEs have." | S0/S5 |
| "Can it handle my other facility?" | "Yes — facilities are separate records; the ranker resolves each facility's own activity data and factors." | GA-01 fix |
| "Is this certified/compliant?" | "No — it's an auditable decision tool, explicitly **not** a compliance certification; the report says so." | Report disclaimer |

---

## Appendix A — 2-minute backup video outline

Record once, 1080p, no cursor shake, use the live URL if stable else mock mode. Narration in
quotes is a full script (~260 words → ~2:00 at a calm pace).

| Time | Shot | Narration |
|---|---|---|
| 0:00–0:12 | Dashboard top, slow scroll to gauges | "Seven thousand two hundred tonnes all-scope; five hundred sixty-six operational; the Boiler leaks 39.8% of it." |
| 0:12–0:30 | Click facility card → hover Boiler → click → activity view | "Facility, process, machine. This is where the carbon actually leaves the building: gas and diesel into the boiler." |
| 0:30–0:55 | Recommendations top cards, zoom on #1 | "Rank one is textile offcut recycling: thirty-two tonnes of CO₂e saved a year, five lakh CAPEX, payback two years. Ranked by a transparent weighted formula, not by carbon alone." |
| 0:55–1:15 | Scroll to solar #10 | "Solar has the best carbon score but eighth-year payback, so it ranks tenth — a business tool, not a greenwashing tool." |
| 1:15–1:40 | Scenarios: show over-budget, drag seven sliders, green notice | "With a fifty-lakh budget, the engine drops the big-ticket items and returns an in-budget plan: forty-five lakh CAPEX, thirty lakh a year saved, payback one-point-five years." |
| 1:40–1:58 | Reports: generate, scope table, provenance | "The report carries every factor's source, year and version, flags two unresolved rows instead of faking them, and exports machine-readable." |
| 1:58–2:00 | Title card "EcoLeak AI" | "Find the leak. Price the fix. Prove the number." |

**Backup-of-backup:** if video playback fails, walk the frozen mock payloads in
`mocks/*.json` on a code editor and narrate — the shapes are the contract.

---

## Appendix B — Explanation adversarial pass (demo dataset)

All 18 explanation texts served by the live J2 endpoint were read end-to-end on the clean seed
(2026-09-12). Findings:

- **No contradictions** between explanation text and card/assessment numbers (payback, CAPEX,
  savings, shares, scores all match; the numeric checker plus manual read).
- **Two wording defects fixed** in this branch (copy-only, template explainer): the stale
  "until the P3 engine supplies verified baselines" assumption (all 18) and "payback 0.00 years"
  for zero-CAPEX items (now "payback immediate (zero CAPEX)"). Evidence:
  `p4/demo/output/demo_explanations.live.md`, `var/p4_j2_explanations.txt`.
- **Honest labels retained**: `(mock)` on library evidence sources, `data_is_stub=true` in
  assumptions, "waste ratio not estimated", "not available (no positive annual saving)". The
  script never reads these aloud as weaknesses — the appendix turns them into trust points.
- Known display caveats are listed in `docs/phase4/bugs_found.md` (report unresolved labels in
  live mode; J2-vs-K1 per-item saving basis). The script avoids showing both per-item saving
  figures side by side.
