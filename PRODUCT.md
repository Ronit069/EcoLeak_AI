# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: Vite + React 18 + TypeScript + Zod + React Router (single-page Operate dashboard, static deploy, mock-JSON now, REST swap later). No SSR needed for Phase 1 SME internal tool. [Inferred — no answer mechanism in this harness; user said "start phase 1" without stack preference.]

## Users

Primary: SME sustainability / plant manager at a small-medium textile factory (e.g. Shakti Textiles mock) doing annual carbon accounting in a back-office with intermittent connectivity. Job: profile factory, map 6 processes, enter 13 activity records, find leak points, pick circular interventions within budget. [Inferred from mock_dataset.json + CONTRACTS_README.md P1 scope.]

Secondary: Hackathon parallel teams P2/P3/P4 who consume frozen contracts; P1 must not break field names/shapes.

## Product Purpose

EcoLeak AI finds emission leak-points (hotspots) per process and recommends circular interventions with financial + CO2 evidence, so an SME can act within budget. Phase 1 success = all six surfaces render from frozen mocks with zero contract drift, then swap to live G2/J2/N1 without component rewrites.

## Positioning

Only tool in this hackathon that binds deterministic carbon math (CO2e = normalized_value × factor, 565,050 kgCO2e fixture total) to ranked circular-economy actions with CAPEX/payback/confidence provenance — LLM explains only, never invents numbers (Module M rule).

## Operating Context

Annual reporting period (FY25-26 mock: 2025-04-01..2026-03-31 DRAFT); workflows A→B→C→F→G→J→O→N; factory floor data arrives as manual entry + CSV/XLSX import (Pandera) + Pint unit normalization; period LOCKED/CLOSED blocks mutation; audit_logs on every mutation. Desktop-first back-office, 1440px primary, 390px fallback for walk-through checks.

## Capabilities and Constraints

Confirmed: Modules A (org/facility/period CRUD), B (process CRUD, sequence_no>0, soft-delete), C-frontend (activity CRUD + import + normalize + data-quality), N (dashboard + leak-map nodes, links:[] Phase 1), O-frontend (scenario CRUD + adoption% + simulate + compare), recommendation cards (rank, 6 scores, impact). Frozen: field names, enums, endpoint paths, mock shapes until Phase 2 (contract_version bump + full-team sync for any change).
Undecided: auth/tenant resolution UI (no auth in Phase 0), PDF export (501 in Phase 1), process_links Sankey editor (Phase 2), anomaly ML UI (Module H).

Terminology: hotspot = ranked EmissionHotspot + rank/process_name/activity_category; recommendation = Recommendation + intervention_code/title/explanation/impact(RecommendationAssessment); scenario = Scenario + ScenarioInterventions with adoption_percentage.

## Brand Commitments

Name: EcoLeak AI. No logo, palette, or voice committed. Industrial-utilitarian tone from DB/security docs; no marketing claims allowed. Currency INR in mocks.

## Evidence on Hand

Real: contracts/schemas.py (510 lines, Pydantic v2 source of truth); contracts/api_contract.md (219 lines, A–Q endpoints); mocks/mock_dataset.json (700 lines: 1 org, 1 facility, 1 period, 6 processes, 13 activities, 8 factors, 5 interventions); mocks/mock_hotspot_output.json (5 hotspots, total 565050); mocks/mock_recommendation_output.json (5 recs, budget 5000000); validate_mocks.py (9/9 PASS). Absences future work must not fabricate: scope_breakdown, circularity_score methodology, factor provenance beyond mock source_name/version, real imagery.

## Product Principles

1. Contract fidelity over convenience — Zod mirrors Pydantic ranges/enums exactly, StrictBaseModel extra=forbid means no extra fields.
2. Evidence before advice — every CO2/₹ number shows source/year/version/confidence; LLM text labeled separately.
3. Operate clarity — rank, severity, payback readable in seconds; color never the only signal.
4. Mock-to-live swap without rewrite — components consume hooks, never raw mock paths.
5. No dead ends — every empty/locked/incomplete state names the recovery (add activity, unlock period, add factor).

## Accessibility & Inclusion

WCAG 2.2 AA target: keyboard-complete forms/sliders, visible focus, 4.5:1 body text, severity with icon+text, table fallback for every chart, INR + kgCO2e tabular numerals.
