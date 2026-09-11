# Design

<!-- impeccable:design-schema 1 -->

## World

Audit Bench Instrument — daylight back-office meter wall + mill ledger. Paper ground #FAF7F0 with faint 32px rule lines, ash panels #FFFFFF edged 1px #E3DDD0, gunmetal ink #1E2328, legend #6B675E. Safety-orange #E4572E reserved for the single commit action per screen, with tactile key travel (:active translateY + shadow collapse). Severity is line-form + icon + word, never hue alone: CRITICAL doubled solid rail, HIGH solid, MODERATE dashed, LOW dotted, each with its own SVG pictogram and uppercase badge.

## Typography

One family: system sans stack (Inter → -apple-system → Segoe UI → Roboto). Fixed scale, h1 1.72rem / h2 1.18rem / h3 1rem, ratio ≈1.18, headings letter-spacing -0.015em, balanced. All measures set tabular (`font-variant-numeric: tabular-nums`); instrument readouts and codes also use ui-monospace stack. Body 15px/1.55, prose max 72ch; tables may run 120ch+.

## Color

Restrained strategy. Neutrals carry the page; orange carries commit; semantic severity hues (critical #B3261E, high #C2570B, moderate #8A6D00, low #3A7D44) always paired with line-form + label. Focus ring #1A5FB4 3px. Selection inverts ink/paper. Scrollbars tinted #CFC7B4 from the palette.

## Layout

App shell: 232px dark tick rail (gunmetal gradient, bone text) + fluid content max 1240px. Instrument strip: 4 gauges sticky under nav on desktop, wrapping on mobile. Split 1.55fr/0.9fr collapses to 1fr under 980px. Hotspot rows: 10px severity rail + rank cell + fluid body + expander. Recommendation plates: rank block + score grid (3→2 col) + impact strip (4→2 col). Leak map: vertical rail with sized dots. No kicker/eyebrow, no section numbers, no hero-metric template, no nested cards.

## Components

- HotspotRail: button rows, aria-expanded, contribution bar (block, gradient ink→orange), severity rail variants, explanation collapsible.
- SeverityBadge + ScoreMeter: icon + word badge; 6px meter with role=img label.
- RecommendationPlate: rank block (dark chip, mono), 6 score meters, impact strip (CAPEX/saving/CO₂/payback), Shortlist demo state machine (SUGGESTED→SHORTLISTED).
- Forms: uniform 8px radius, 1px line-strong borders, error text critical, inline hints; range inputs accent-orange 28px hit area.
- States: skeleton shimmer for loading, dashed notice for empty/locked/over-budget, disabled commit keys, visible focus everywhere.

## Motion

One authored moment: scenario adoption slider scrubs totals live (180ms, keyboard-complete). Key-travel press on primary buttons (80ms). Skeleton shimmer 1.2s. No page-load orchestration. `prefers-reduced-motion` disables all.

## Responsive

Structural only: rail becomes top bar, split → single column, score/impact grids halve, rank cell hides under 980px (rank survives in heading). Captures: desktop 1440 full-page, mobile 390 full-page, plus per-route desktop captures.

## Accessibility

WCAG 2.2 AA target: severity never color-only, table fallback under leak map, aria-live on scenario totals and adoption %, labels on every input, details/summary for audit table, tabular numerals, 4.5:1 body text (legend-ink #4A473F on paper).
