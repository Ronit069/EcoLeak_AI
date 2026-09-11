# Surface brief — EcoLeak AI Phase 1 Frontend (Operate)

Scope: frontend/ SPA, six routes: / (Dashboard N + leak map), /recommendations (J/M cards), /processes (B mapper), /data (C input), /profiling (A SME/facility/period), /scenarios (O + K simulate prototype). Mode: Operate.

Audience/job/action: Plant/sustainability manager completes annual accounting task in one sitting; must see total, worst leak, best payback action within 30 seconds, then drill to evidence. Proof/content: frozen mocks (565050 total, 5 hotspots, 5 recs, budget 5000000) with provenance labels; constraints: frozen field names/enums, links:[], 501 PDF, no auth.

Chosen direction: AUDIT BENCH INSTRUMENT (grounded candidate 3 of 7 — boiler gauge wall + mill ledger). A daylight back-office bench: warm paper ground, gunmetal ink, hairline emission rails for severity, tabular instrument numerals for kgCO2e/INR, one safety-orange commit key per screen. Category-default SaaS card grid refused; opposite (dark neon carbon-glow) refused as unreadable in daylight audit scene.

Memorable moment: scenario adoption slider scrubs projected savings live like a bench knob with full keyboard parity.

Unresolved: scope_breakdown/circularity derivation until N1 live (show derived + empty_state note); PDF export hidden behind 501 notice; auth stubbed with fixed facility/period IDs.

## Direction contract

THESIS: An audit bench, not a SaaS dashboard — every number reads as a metered instrument with provenance, every rank as a rail tick. Refuses the hero-metric + equal-card grid where five interventions look interchangeable.

OWN-WORLD: Paper #FAF7F0 ground, ash panels #FFFFFF edged 1px #E3DDD0, gunmetal ink #1E2328, muted legend #6B675E, accent safety-orange #E4572E reserved for commit actions, severity carried by line-form + icon + word (CRITICAL doubled solid, HIGH solid, MODERATE dashed, LOW dotted) plus hue. One sans (system stack), tabular numerals for all measures, fixed scale 1.18, 1px hairlines, offset+blur shadows only.

STORY: Manager lands, reads total + worst leak + top payback without scrolling; believes it because factor source/year/version sits under each figure; acts by shortlisting a recommendation or scrubbing a scenario adoption %.

FIRST VIEWPORT: Top instrument strip (facility + period + total readout + data-quality + budget), left tick rail nav, main column: ranked hotspot rails (marker sized by contribution%, severity line-form left, process name + kgCO2e + intensity + score + explanation collapsed), right column: top-3 recommendation plates with CAPEX/payback/CO2 and orange Shortlist key. Primary action (Generate from mocks / Shortlist) sits at end of reading order, never floating.

FORM: Grounded candidate 3/7 (seed key 3c01c864). FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Raises (from challenger hand, seed 3c01c864): kept-line seven-segment — numerals set tabular with ghost-cell alignment in readouts; kept-line emission-rail — state is line-form/dash/doubling, never hue alone; kept-line bench-key — commit controls have tactile key travel (:active translate) and knob-detent slider motion 180ms.
