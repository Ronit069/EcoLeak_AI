# ECOLEAK AI — MASTER UI DESIGN PROMPT v2

## Industrial Carbon Leak Detector — "Engineering Audit Instrument" Edition

**Version:** 2.1 — FROZEN | **Date:** 2026-09-12 | **Audience:** UI/UX designer, design engineer, or AI UI-generation agent
**Companion docs:** `UI_REDESIGN_REQUIREMENTS.md` (integration/contract truth — wins on all field/enum/endpoint/error matters), Hackathon Requirements (modules A–Q), Security & Edge-Case doc, Library/Use-case doc.
**Change in v2.1 (final):** added §2.7 anti-overcorrection rules (modernity without SaaS aesthetics; density-is-not-the-aesthetic) after reviewer feedback. Spec is now frozen — do not expand or restyle. **Change from v1:** all functionality, contracts, pages, edge cases, and acceptance criteria are preserved unchanged. **Only the visual/UX execution direction has been hardened.** The product requirements were always strong; this version prevents the UI from drifting into a generic "AI SaaS dashboard" look.

---

## 0. HOW TO USE THIS PROMPT

This is the single master instruction for designing the EcoLeak AI frontend. It defines the problem, users, screens, behaviors, and the **exact visual identity** the interface must carry. Where this prompt and `UI_REDESIGN_REQUIREMENTS.md` / `contracts/` disagree on data shapes, the contracts win. Where a previous tendency toward generic SaaS styling appears, this prompt overrides it.

> **Golden rule:** The UI must feel like a **serious plant-analysis instrument an engineer trusts and an SME owner isn't afraid of** — not a landing page, not a chatbot wrapper. A factory operator should read the screen the way they read an energy audit report or a control-room panel: dense, factual, sourced, calm.

---

## 1. PROBLEM STATEMENT (unchanged — design for THIS problem)

Small and medium industrial enterprises have **no visibility into where their carbon footprint originates** and **no guidance on which circular-economy alternatives are technically and financially practical** for their specific processes.

**User pain:** totals without process attribution; generic advice detached from budget and payback; expensive consultants; messy data (mixed units, Excel, estimates, missing factors) that tools either reject silently or render with false precision.

**Product job-to-be-done:** ingest raw factory data → normalize units with honest quality grading → deterministic carbon accounting (Activity × Emission Factor, versioned, reproducible) → **Carbon Leak Map** of process hotspots → feasibility-filtered circular interventions with CAPEX / savings / payback / CO₂ impact → what-if scenario comparison → evidence-based explanations → auditable report.

**Must NOT become:** a form + pie chart calculator; an LLM chatbot inventing numbers; a recommendation list without cost/payback/feasibility; a system hiding factor sources or confidence.

---

## 2. VISUAL IDENTITY — THE CORE DIRECTION (NEW, overrides v1 §6)

### 2.1 Concept

> **Industrial control-room / engineering audit instrument.**
> Think: factory SCADA/HMI panel, engineering workstation, energy-audit report, industrial instrumentation, financial analysis terminal — NOT Linear, Notion, Vercel, glassmorphism SaaS, or "AI startup" aesthetics.

The product's identity is built from the things the prompt already requires — **evidence, provenance, confidence, calculation timestamps, data quality, severity ranks**. Those data-integrity elements become the visual language. There is no decorative layer.

### 2.2 Hard anti-patterns (reject on sight)

| ❌ Reject | ✅ Use instead |
| --- | --- |
| Many rounded floating cards | Sections separated by hairline rules and dividers; fixed panels |
| Huge hero KPIs with gradients | Dense, labeled operational metric blocks |
| Soft shadows / elevation candy | 1px borders + typographic hierarchy only |
| Large border-radius (12–24px) | Mostly 0–6px; square, instrument-like edges |
| Gradient backgrounds / glassmorphism | Flat matte surfaces; one dark or one light theme, no blends |
| Decorative illustrations / empty-state art | Technical diagrams, schematic process glyphs, tabular data |
| Generic "AI sparkles" icons | Industrial/status iconography (valve, gauge, flow, warning triangle, ledger) |
| Copy: "AI recommendation" | "Intervention assessment", "assessed action", "ranked by engine" |
| Floating card grids | Fixed instrument layout: header bar / left index / main panel / detail strip |
| Big empty whitespace | Controlled, deliberate information density |
| Colorful candy charts | Restrained technical palette; ink-first, color only for semantics |
| AI-generated prose first | **Evidence first, explanation second** — numbers and provenance above narrative |

### 2.3 The palette (restrained, technical)

- **Base surfaces:** one near-white warm gray (light mode) or graphite `#16181d` (dark mode). Pick ONE primary mode (recommend dark for control-room feel); the other is a clean inversion, not a redesign.
- **Ink hierarchy:** primary text near-black/high-contrast, secondary muted, tertiary faint — hierarchy via weight and size, never via colored body text.
- **Semantic severity (the ONLY saturated colors, always icon + label + color):**
- `LOW` — desaturated teal/green
- `MODERATE` — amber
- `HIGH` — orange
- `CRITICAL` — red
Severity color appears in small badges, map nodes, and issue rows — never as page backgrounds or big fills.
- **Scope coding (consistent across every chart):** Scope 1 warm-neutral, Scope 2 cool-neutral, Scope 3 gray. Bar/line charts in near-monochrome with scope accents.
- **Accent:** a single industrial accent (e.g., safety-orange or signal-cyan) reserved for primary actions and the LIVE indicator only.

### 2.4 Typography & numbers

- One grotesque/technical sans (e.g., Inter, IBM Plex Sans); a **monospaced or tabular-numeric face** (e.g., IBM Plex Mono / JetBrains Mono) for ALL emissions, money, factors, scores, timestamps, and IDs — the "instrument readout" look.
- Numbers right-aligned in tables; decimal-aligned where compared; full precision in state, rounded at render; thousands separators; `null` renders as `—` (tooltip: "Not available") — **never 0**.
- Units always attached ("480,000 kWh", "565,050 kgCO₂e", "₹4.2 lakh"); large values scale to tCO₂e with explicit labeling.

### 2.5 Layout grammar

- **Chrome:** thin top bar — `ECOLEAK` wordmark · facility name · reporting period · data-mode badge (`LIVE ●` / `DEMO ○` / `MIXED ◐`) · health dot · role/org chip. Fixed, never scrolling.
- **Body:** three-column instrument layout — narrow left index rail (processes / modules), wide main panel, bottom or right detail strip for the selected object. Panels divided by 1px rules, headers in small caps mono labels.
- **Density:** engineering-terminal density. If a screen feels like a Notion page, it is wrong. If it feels like a Bloomberg terminal crossed with an audit worksheet, it is right.
- **Motion:** functional only — value ticks, progress rails for `202` polling, skeleton lines shaped like the content. No bounces, no parallax.

### 2.6 Iconography & copy voice

- Icons: thin-stroke industrial set (gauge, pipe/valve, bolt, flame, droplet, gear, ledger/book, shield, lock, warning triangle). No sparkle/wand/brain "AI" icons anywhere in the product UI.
- Voice: terse, factual, audit-grade. "Intervention assessment", "Factor provenance", "Calculation version", "Data quality", "Assumptions", "Evidence". Numbers precede adjectives. Uncertainty is stated, not softened.

### 2.7 Anti-overcorrection rules (critical — read before executing §2)

There is a real danger of overcorrecting: pushed too hard toward "control room / Bloomberg terminal," an agent will produce a **1990s legacy ERP**. That is exactly as wrong as AI SaaS. The target is **modern industrial engineering software**: borrow the *information hierarchy and operational seriousness* of control rooms and audit worksheets — **not** their outdated visual treatment.

**Rule 1 — Modernity without SaaS aesthetics.** The interface must be contemporary, highly legible, and visually refined while remaining industrial and information-dense. Do not imitate legacy ERP, literal SCADA screens, or Bloomberg terminals. No beveled edges, no dithered textures, no cramped 11px grid walls, no 2003-era gray toolbars. Modern typography, generous-enough line height, precise alignment, and excellent micro-interactions are mandatory.

**Rule 2 — Density is not the aesthetic.** Do not make "dense" a style goal in itself. Every visible element must have an operational purpose; prefer fewer, stronger elements over filling space merely to appear "industrial." A screen with three decisive instruments beats a screen with forty decorative readouts. Whitespace is permitted — it must be *deliberate*, not the accidental emptiness of a marketing page.

**The final visual target, stated once:** ❌ AI SaaS · ❌ startup dashboard · ❌ glassmorphism · ❌ futuristic cyberpunk · ❌ legacy ERP · ❌ literal SCADA clone → ✅ precision instrument · ✅ engineering workstation · ✅ audit-grade · ✅ data-dense where useful · ✅ extremely clear hierarchy · ✅ restrained · ✅ evidence-driven · ✅ modern typography · ✅ excellent micro-interactions · ✅ credible enough to be used by a real factory.

---

## 3. USERS & ROLES (unchanged)

| Role | Need from the UI |
| --- | --- |
| `FACTORY_OPERATOR` | Fast data entry, import, anomaly flags, "fix this first" clarity |
| `SUSTAINABILITY_ANALYST` (default) | Full drill-down, factors, quality scores, scenarios, reports |
| `ORGANIZATION_ADMIN` | Setup, org/facility management, budgets |
| `VIEWER` | Read-only dashboard, leak map, report summaries |
| `REGULATOR_READ_ONLY` | Provenance, audit trail, read access across orgs |
| `SYSTEM_ADMIN` | Global reference data (factors, interventions) |

Role-aware chrome (write actions hidden/disabled for viewers; audit emphasis for regulators; simplified operator paths). Distinct designed states for `401` (not authenticated) and `403` (wrong tenant / insufficient role). Persona is an SME owner, not a data scientist: plain-language summary first, expert detail on demand, India-first defaults (INR, kWh/tonne) on region-agnostic architecture.

---

## 4. INFORMATION ARCHITECTURE (unchanged, 8 destinations + chrome)

Left index rail: **Dashboard · Carbon Leak Map · Data & Activities · Process Map · Recommendations · Scenario Simulator · Reports · Settings.**
Global chrome: facility + reporting-period selectors (drive all scoped calls); mandatory data-mode badge with per-group fallback list; org/role identity chip; health indicator from `/api/health`.

---

## 5. PAGE SPECS — FUNCTIONALITY UNCHANGED, EXECUTION RE-DIRECTED

### 5.1 Onboarding / Factory Profile (Modules A, B)

Stepped wizard (Organization → Facility → Reporting Period → Process Map). All validations as before (production > 0 for intensity; overlapping periods → inline `409`; locked period → read-only + persistent lock banner). Execution: form rows with rule separators, mono validation readouts, no card stacks.

### 5.2 Dashboard (Module N) — REWORKED LAYOUT

**An engineering workstation, not a hero page.** Reference structure:

```text
┌──────────────────────────────────────────────────────────────────┐
│ ECOLEAK / FACILITY 01          FY2026 (ANNUAL)     LIVE ●  OPS   │
├──────────────┬───────────────────────────────────────────────────┤
│ PROCESS      │ CARBON AUDIT — FY2026                           │
│ INDEX        │                                                   │
│              │ TOTAL        565,050 kgCO₂e     DENSITY tCO₂/...  │
│ 01 Dyeing    │ SCOPE 1      312,400   ██████████░░░░  55%        │
│ 02 Drying    │ SCOPE 2      214,300   ██████░░░░░░░░  38%        │
│ 03 Boiler ►  │ SCOPE 3       38,350   █░░░░░░░░░░░░░   7%        │
│ 04 Finishing │                                                   │
│ 05 Packaging │ DATA QUALITY   78.4 / 100   [▓▓▓▓▓░░] + issues  │
│ 06 Transport │ LAST CALCULATED 2026-09-12 14:32 UTC             │
│              │                                                   │
│              ├───────────────────────────────────────────────────┤
│              │ PROCESS CARBON LEAK MAP                           │
│              │   DYEING ●───────────● DRYING                     │
│              │        21% MODERATE      12% MODERATE             │
│              │                                                   │
│              │   BOILER ●████████████ CRITICAL · 42.1%           │
│              │                                                   │
├──────────────┴───────────────────────────────────────────────────┤
│ SELECTED: BOILER (P-03)                                          │
│ CONTRIBUTION 42.1%   SEVERITY CRITICAL   237,xxx kgCO₂e         │
│ ROOT CAUSE   FUEL CONSUMPTION / OPERATING HOURS / NO HEAT REC.  │
│ ASSESSMENT   WASTE-HEAT RECOVERY — rank 1 · score 0.87           │
│ CAPEX ₹X     SAVING ₹Y/yr        PAYBACK 2.1 yr   CO₂ −Z t/yr   │
│ [VIEW EVIDENCE]                              [RUN SCENARIO ▶]    │
└──────────────────────────────────────────────────────────────────┘
```

Notice what is **absent**: no giant "AI-powered" hero, no gradients, no floating glass cards, no chatbot. The bottom strip is the audit readout for the selected leak.

- KPIs are a compact metric block (mono numerals, scope bars), not oversized stat cards.
- Charts: scope distribution as labeled bars (donut only when ≥2 non-zero scopes), process Pareto with cumulative line, leak-map preview. Advanced charts (Sankey, marginal abatement cost, waterfall) behind tabs, monochrome-first.
- Every computed widget carries `LAST CALCULATED {timestamp}`. Empty/zero/stale states designed as instrument readouts ("NO DATA — RUN CALCULATION"), not illustrations.

### 5.3 Carbon Leak Map (Module G) — HERO SCREEN, INSTRUMENT EXECUTION

- Left index rail lists processes in sequence with contribution % and severity badge; center panel is the map (node size ∝ contribution, multi-channel severity encoding: icon + label + color); bottom or right strip is the audit readout for the selection (contribution, intensity, inefficiency/waste/improvement scores, hotspot_score, severity, plain-language `explanation`, estimated-input confidence warning).
- Edge states as before: single process (100% + limitation note), zero total (no %, explicit note), dominant outlier (dual flag: hotspot AND suspected data anomaly + "confirm this value"), ties (deterministic order, footnoted).
- Data from `GET …/leak-map` → `{nodes, links: []}` — layout must accommodate links later without rework.

### 5.4 Data & Activities (Modules C, D) — LEDGER EXECUTION

- Activity table reads like a **ledger**: original value/unit | normalized value/unit (server-side only — UI never mutates normalized), provenance, confidence, source type. Row rules, mono numerals.
- Manual entry: inline validated fields mirroring Pydantic rules; `422 CONFIRMATION_REQUIRED` cross-dimension conversions prompt for density/assumption — never silent conversion.
- Import: drag-and-drop (.csv/.xlsx), sheet picker, **dry-run default ON** → results ledger with per-row `row_issues` at all four severities (`ERROR/WARNING/INFO/CONFIRMATION_REQUIRED`), row numbers, raw rows; `409 DUPLICATE_IMPORT` handled; job tracker for `RECEIVED→PROCESSING→COMPLETED/PARTIAL/FAILED/DRY_RUN`.
- Data-quality panel: five component scores + total as instrument gauges; warning gate before recommendations when quality is low.

### 5.5 Recommendations (Modules J, M, Q) — ASSESSMENT REGISTER

- A ranked **register/table-first** layout (not chatty cards): rank · intervention code+title · linked hotspot · status · final_score with component score bars (carbon/financial/feasibility/circularity/speed/confidence) · impact columns (CAPEX, annual saving, CO₂ saving, payback, ₹/tCO₂).
- **Payback rules (mandatory):** null when annual saving ≤ 0 → "NO FINANCIAL PAYBACK ESTIMATED"; negative saving → "NET COST ₹X/yr"; zero CAPEX + positive saving → "IMMEDIATE". Never invented.
- Budget constraint visible as a filter readout ("2 interventions excluded by budget ₹25,00,000").
- Explanation panel: **evidence block first** (hotspot contribution, scores, impact, assumptions, confidence, `generated_by`), AI narrative second and visually tagged ("AI-generated explanation — derived from engine evidence"). Plain and expert reading levels.
- Feedback: USEFUL / NOT_APPLICABLE / CONSIDER_LATER / IMPLEMENTED / REJECTED; REJECTED requires structured `reason_code`; IMPLEMENTED invites actual outcome capture; history timeline.
- Honest states: "NO SUITABLE INTERVENTION WITHIN CONSTRAINTS" as a designed register row; "COST ESTIMATE UNAVAILABLE" never fabricated.

### 5.6 Scenario Simulator (Modules K, O) — COMPARISON WORKSHEET

- Builder: named scenario, selected interventions with adoption % sliders (0–100 enforced), budget limit, target reduction %.
- Results as a **baseline vs projected worksheet**: emissions, Δ, total saving, reduction %, CAPEX, annual saving, payback, projected circularity — plus a monochrome waterfall.
- `ScenarioSimulationEnvelope` unwrapped: `{scenario_id, assessment{...}, interventions[], payback_status?, payback_reason?, over_budget, issues[]}` — `over_budget` banner prominent; `payback_status/reason` rendered; `issues[]` listed.
- Live vs local labeled ("ENGINE-COMPUTED" vs "LOCAL ESTIMATE"). Edge states: 0% adoption = baseline; savings > source emissions = capped + flagged; negative projection = floored + explained; incompatible interventions = blocked with reason.

### 5.7 Reports (Module P) — AUDIT DOCUMENT

- Generation: template_version + include_scope3 → `202` receipt → polling rail → render.
- Sections in fixed audit order: profile · boundary · **factor provenance table** (source/year/version/methodology; `UNRESOLVED` flagged rows) · scope summary (with on-site generation and exported electricity as **separate ledger rows, never in totals**) · data quality · hotspot analysis · circularity (disclaimer + `not_a_certified_standard`) · recommendations · financial assessment · roadmap (rank/code/title/payback) · assumptions · disclaimer.
- **String-number coercion guard:** payload numerics arrive as strings (JSONB `default=str`) — coerce + validate; malformed → "REPORT DATA MALFORMED" state, never NaN.
- Section status stamps `STUB / REAL / UNAVAILABLE`; `report_meta.data_is_stub` triggers a "DEMO DATA" watermark.
- Export: JSON/CSV downloads; PDF button shows designed "PDF EXPORT NOT AVAILABLE IN THIS PHASE (501)" state.
- Version history via `GET /api/reports` (each regeneration increments `version`).

### 5.8 Settings & Global States

Org/facility/period management; **data-mode switch AUTO/LIVE/DEMO** backed by `localStorage` key `ecoleak.useMockData` (precedence: localStorage → `VITE_USE_MOCK_DATA` → `VITE_USE_MOCKS` → `auto`); active mode + fallback groups always visible; auth panel with distinct 401/403 screens.

---

## 6. CROSS-CUTTING BEHAVIORAL REQUIREMENTS (unchanged, non-negotiable)

1. **Error contract:** frozen shape `{error_code, message, severity, details}`; designed states for 400/422 (per-field/per-row `details.issues[]`), 401, 403, 404 (masks cross-tenant leaks), 409 (locked/duplicate/overlap + recovery), 429 (retry hint), 500 (generic + `X-Request-Id`), 501 (PDF). All four severities rendered, `CONFIRMATION_REQUIRED` as a decision point. Surface — never swallow — unresolved factors, quality issues, stub sections, mock fallbacks.
2. **Auth/tenancy:** stub headers (`X-Organization-Id`, `X-Role`, `X-Actor-Id`) or Bearer token on every call; token from env only; active org always visible. Known gap: `/api/emission-factors` and `/api/interventions` are unauthenticated — never use them as session probes.
3. **Bootstrap:** `GET /api/context` → org/facility/period IDs (demo-ID fallback in mock mode); **no `processes` key** — fetch separately.
4. **Mock transparency:** `auto` = live-first with **per-group** fallback (`dataset, processes, activities, hotspots, dashboard, leak-map, recommendations, explanation, scenario-simulate`); persistent badge + group list; `live` mode = errors, no silent fallback; `200` + `text/html` = failed live call, not JSON.
5. **Async:** all `202` flows get progress/polling UX with cancel/retry; import job tracker.
6. **Scale/perf:** ~100 processes (filter/search), 20k import rows (virtualized), unit scaling, responsive desktop → tablet → mobile-degraded (forms and ranked lists survive; complex viz falls back to tables).
7. **Accessibility:** WCAG AA; severity never color-only; keyboard-navigable map with list fallback; chart data as tables; reduced-motion respected.
8. **Security-conscious UI:** escaped rendering; DOMPurify if any HTML rendering (prefer structured fields); no secrets in storage; no tokens in URLs; sanitized export filenames.

---

## 7. KEY FLOWS & DEMO SCENARIO (unchanged)

Design end-to-end: first-run wizard → demo textile factory; CSV dry-run import → PARTIAL → fix rows → re-import; calculation → leak map → CRITICAL boiler → top intervention (waste-heat recovery, payback 2.1 yr) → shortlist; scenario (80% + 50% adoption, ₹25L budget) → reduction 18% → save & compare; report v1 (2 UNRESOLVED factors) → fix → v2. Demo scenario magnitudes: 1,000 t/yr production, 480,000 kWh, 95,000 m³ gas, 12,000 L diesel, 80 t textile waste; processes Dyeing/Drying/Boiler/Finishing/Packaging/Transport.

---

## 8. DEFINITION OF DONE (unchanged checklist — all v1 items retained)

- [ ] All 8 destinations with every state (loading/empty/error/success/locked/demo) in the instrument visual language.
- [ ] Bootstrap from `/api/context` + demo-ID fallback; no `processes` assumption.
- [ ] Auth headers; distinct 401/403; org context always visible.
- [ ] AUTO/MOCK/LIVE + localStorage override + visible badge + per-group fallback list.
- [ ] Four severities rendered; 409/422/429/404/501 designed states.
- [ ] Dry-run import with per-row issues (row numbers + raw rows).
- [ ] Scope 1/2/3 + total; on-site/export as separate ledgers.
- [ ] Leak map: rank/contribution/severity/process/drill-down; zero-total & single-process states.
- [ ] Recommendations: component scores, final_score, impact, payback null/negative/zero-CAPEX rules, evidence-first explanation, structured rejection feedback.
- [ ] Scenario simulator: envelope unwrapped, `over_budget`+`issues[]`, live-vs-local labels, adoption 0–100.
- [ ] Reports: 202→poll→render; string coercion validated; STUB/REAL/UNAVAILABLE stamps; unresolved factors flagged; version history; JSON/CSV; PDF 501 state.
- [ ] Circularity labeled internal metric, not certified.
- [ ] `null` → `—`, never 0; full precision in state.
- [ ] No secrets in storage; LLM text escaped; no tokens in URLs.
- [ ] Responsive + WCAG AA + color-blind-safe severity.
- [ ] `npm run build` (tsc + vite) zero errors.
- [ ] **Visual audit:** passes §2.7 — no gradient backgrounds, no floating rounded cards, no glassmorphism, no "AI sparkle" iconography, no hero-KPI worship, no decorative illustrations, no chatbot-first layout. The interface reads as an engineering audit instrument at first glance. Neither overcorrected: no legacy-ERP/SCADA imitation (bevels, cramped 90s grids, gray toolbars), and no decorative density (no purposeless readouts filling space). The Carbon Leak Map → evidence → intervention → ROI → scenario flow is visibly the centerpiece.
- [ ] **Modernity check (§2.7):** contemporary typography/spacing/micro-interactions; looks like modern industrial engineering software, not 90s enterprise software.
- [ ] **Purpose check (§2.7):** every visible element has an operational reason; no density-for-density's-sake.

---

## 9. ONE-PARAGRAPH SUMMARY

Build EcoLeak AI as an **industrial carbon leak detector with the visual grammar of a control-room audit instrument** — flat matte surfaces, hairline rules, fixed panels, tabular/mono numerals, restrained semantic color, evidence-before-narrative ordering — on a React + Vite + TypeScript frontend (Zod-validated contracts, React Hook Form) against FastAPI at `/api`. A factory owner profiles the plant, maps processes, ingests messy data via forms and dry-run CSV/Excel import, and reads a severity-coded **Carbon Leak Map** with honest data-quality gauges; each leak links to a feasibility-filtered **intervention assessment register** with CAPEX, savings, CO₂ impact and null-safe payback, explained by evidence first and AI narrative second (always labeled); a scenario worksheet compares baseline vs projected under budgets and adoption sliders; and a versioned audit report exports JSON/CSV with full factor provenance. Every screen honors the frozen error contract, four validation severities, AUTO/MOCK/LIVE transparency with per-group fallback, locked periods, unresolved factors, `null`-never-zero rendering, and the hero experience answering: **where is the leak, why, what fix, what does it save in CO₂ and money.**