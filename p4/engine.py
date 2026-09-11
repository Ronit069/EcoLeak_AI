"""Module J - deterministic circular recommendation engine.

Pipeline (hard feasibility filters BEFORE ranking, LLM never touches numbers):

    library -> applicability match -> hard filters (budget, complexity, region,
    exclusions, scale, currency, prerequisites) -> dedupe -> deterministic
    multi-criteria ranking (exact requirements-doc formula) -> explanations (M)

Output is a `RecommendationGenerationResult` whose JSON shape matches
mocks/mock_recommendation_output.json exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from p4.contracts import (
    Facility,
    HotspotDetectionResult,
    HotspotOutputItem,
    Organization,
    Process,
    RecommendationAssessment,
    RecommendationGenerationResult,
    RecommendationOutputItem,
    RecommendationStatus,
)
from p4.explainability import Explainer, TemplateExplainer
from p4.financial import (
    ResourceSavings,
    aggregate_baselines,
    compute_payback,
    estimate_resource_co2,
    estimate_resource_savings,
    midpoint,
)
from p4.library import InterventionLibrary, default_library
from p4.models import (
    EngineDiagnostics,
    ExplanationEvidence,
    FacilityContext,
    FilterRecord,
    InterventionEntry,
    LoopType,
    RecommendationConstraints,
    ResourceEmissionFactors,
    ScoredCandidateDiagnostics,
    ScoreBreakdown,
)
from p4.scoring import (
    COMPLEXITY_ORDER,
    carbon_saving_score,
    circularity_score,
    confidence_score,
    feasibility_score,
    financial_return_score,
    implementation_speed_score,
    weighted_final_score,
)

ZERO = Decimal("0")
Clock = Callable[[], datetime]

FILTER_REASONS = {
    "INACTIVE": "intervention is not active",
    "INDUSTRY_NOT_APPLICABLE": "industry sector does not match",
    "BELOW_MIN_SCALE": "facility production is below the intervention minimum scale",
    "CURRENCY_MISMATCH": "intervention currency differs from the requested currency",
    "EXCLUDED_BY_USER": "excluded by user constraints",
    "LOCALLY_UNAVAILABLE": "marked locally unavailable by user constraints",
    "COMPLEXITY_LIMIT": "complexity exceeds the user's technical limit",
    "NO_APPLICABLE_HOTSPOT": "no hotspot matches the intervention applicability",
    "PREREQUISITES_UNMET": "required prerequisite intervention is not in the candidate set",
    "BUDGET_EXCEEDED": "estimated CAPEX exceeds the budget ceiling",
    "MAX_PAYBACK_EXCEEDED": "payback exceeds the user's maximum payback constraint",
}


@dataclass
class _Candidate:
    entry: InterventionEntry
    hotspot: HotspotOutputItem
    baseline_available: bool
    savings: ResourceSavings
    co2_saving_kg: Optional[Decimal]
    co2_basis: str
    estimated_capex: Optional[Decimal]
    annual_saving: Optional[Decimal]
    payback: Optional[Decimal]
    payback_note: Optional[str]
    scores: ScoreBreakdown
    final_score: float
    prerequisites_unmet: list[str] = field(default_factory=list)
    feasibility_notes: list[str] = field(default_factory=list)
    region_mismatch: bool = False


@dataclass
class EngineRun:
    result: RecommendationGenerationResult
    diagnostics: EngineDiagnostics


def _dec(value, places: int = 2) -> Optional[Decimal]:
    if value is None:
        return None
    quant = Decimal("1").scaleb(-places)
    return Decimal(str(value)).quantize(quant)


def _rec_uuid(*parts) -> UUID:
    return uuid5(NAMESPACE_URL, "ecoleak/recommendation/" + "/".join(str(part) for part in parts))


def generate_recommendations(
    hotspots: HotspotDetectionResult,
    facility: Facility,
    *,
    organization: Optional[Organization] = None,
    processes: Optional[list[Process]] = None,
    context: Optional[FacilityContext] = None,
    emission_factors: Optional[ResourceEmissionFactors] = None,
    constraints: Optional[RecommendationConstraints] = None,
    library: Optional[InterventionLibrary] = None,
    explainer: Optional[Explainer] = None,
    clock: Optional[Clock] = None,
) -> RecommendationGenerationResult:
    """Contract-shaped output. Use `generate_with_diagnostics` for telemetry."""

    return generate_with_diagnostics(
        hotspots,
        facility,
        organization=organization,
        processes=processes,
        context=context,
        emission_factors=emission_factors,
        constraints=constraints,
        library=library,
        explainer=explainer,
        clock=clock,
    ).result


def generate_with_diagnostics(
    hotspots: HotspotDetectionResult,
    facility: Facility,
    *,
    organization: Optional[Organization] = None,
    processes: Optional[list[Process]] = None,
    context: Optional[FacilityContext] = None,
    emission_factors: Optional[ResourceEmissionFactors] = None,
    constraints: Optional[RecommendationConstraints] = None,
    library: Optional[InterventionLibrary] = None,
    explainer: Optional[Explainer] = None,
    clock: Optional[Clock] = None,
) -> EngineRun:
    if hotspots.facility_id != facility.id:
        raise ValueError("hotspot envelope facility_id does not match facility.id")
    constraints = constraints or RecommendationConstraints()
    library = library or default_library()
    explainer = explainer or TemplateExplainer()
    now = (clock or (lambda: datetime.now(timezone.utc)))()

    diagnostics = EngineDiagnostics(considered=len(library.all()))
    process_categories = {
        process.name: process.process_category for process in (processes or [])
    }

    baselines = {}
    if context is not None:
        if context.facility_id != facility.id:
            raise ValueError("context.facility_id does not match facility.id")
        baselines = {item.process_name: item for item in context.process_resources}
        facility_baseline = aggregate_baselines(context.process_resources)
    else:
        facility_baseline = None

    candidates: list[_Candidate] = []

    for entry in sorted(library.all(), key=lambda item: item.intervention_code):
        reason = _pre_candidate_filter(entry, facility, organization, constraints)
        if reason is not None:
            diagnostics.filtered.append(
                FilterRecord(
                    intervention_code=entry.intervention_code,
                    reason=reason,
                    detail=FILTER_REASONS[reason],
                )
            )
            continue

        matched = _build_candidates(
            entry,
            hotspots,
            baselines,
            facility_baseline,
            context,
            emission_factors,
            constraints,
            process_categories,
        )
        if not matched:
            diagnostics.filtered.append(
                FilterRecord(
                    intervention_code=entry.intervention_code,
                    reason="NO_APPLICABLE_HOTSPOT",
                    detail=FILTER_REASONS["NO_APPLICABLE_HOTSPOT"],
                )
            )
            continue

        candidates.extend(matched)

    # Deduplicate: one recommendation per intervention, attached to the
    # hotspot where it saves the most CO2e.
    candidates.sort(
        key=lambda item: (
            -(float(item.co2_saving_kg) if item.co2_saving_kg is not None else -1.0),
            item.entry.intervention_code,
        )
    )
    deduped: dict[str, _Candidate] = {}
    duplicate_counts: dict[str, int] = {}
    for candidate in candidates:
        code = candidate.entry.intervention_code
        if code in deduped:
            duplicate_counts[code] = duplicate_counts.get(code, 1) + 1
            continue
        deduped[code] = candidate
    for code, count in sorted(duplicate_counts.items()):
        diagnostics.duplicates_removed.append(f"{code} (x{count} hotspots, kept best CO2e saving)")

    surviving = list(deduped.values())
    candidate_codes = {candidate.entry.intervention_code for candidate in surviving}

    # Prerequisite handling (Module I/J edge cases).
    for candidate in surviving:
        unmet = [code for code in candidate.entry.prerequisite_codes if code not in candidate_codes]
        if not unmet:
            continue
        if constraints.require_prerequisites_met:
            diagnostics.filtered.append(
                FilterRecord(
                    intervention_code=candidate.entry.intervention_code,
                    reason="PREREQUISITES_UNMET",
                    detail=f"requires {unmet}",
                )
            )
        else:
            candidate.prerequisites_unmet = unmet
            feasibility, notes = feasibility_score(
                candidate.entry, region_mismatch=candidate.region_mismatch, prerequisites_unmet=len(unmet)
            )
            candidate.scores = candidate.scores.model_copy(update={"feasibility": feasibility})
            candidate.final_score = weighted_final_score(candidate.scores)
            candidate.feasibility_notes.extend(notes)

    if constraints.require_prerequisites_met:
        blocked = {
            record.intervention_code
            for record in diagnostics.filtered
            if record.reason == "PREREQUISITES_UNMET"
        }
        surviving = [candidate for candidate in surviving if candidate.entry.intervention_code not in blocked]

    # Budget and max-payback hard filters (after prerequisites, so the
    # candidate set used for prerequisite satisfaction is complete).
    survivors: list[_Candidate] = []
    for candidate in surviving:
        if (
            constraints.budget_limit is not None
            and constraints.strict_budget_filter
            and candidate.estimated_capex is not None
            and candidate.estimated_capex > constraints.budget_limit
        ):
            diagnostics.filtered.append(
                FilterRecord(
                    intervention_code=candidate.entry.intervention_code,
                    reason="BUDGET_EXCEEDED",
                    detail=f"estimated CAPEX {candidate.estimated_capex} > budget {constraints.budget_limit}",
                )
            )
            continue
        if (
            constraints.max_payback_years is not None
            and candidate.payback is not None
            and candidate.payback > constraints.max_payback_years
        ):
            diagnostics.filtered.append(
                FilterRecord(
                    intervention_code=candidate.entry.intervention_code,
                    reason="MAX_PAYBACK_EXCEEDED",
                    detail=f"payback {candidate.payback} > {constraints.max_payback_years}",
                )
            )
            continue
        if constraints.max_payback_years is not None and candidate.payback is None:
            diagnostics.warnings.append(
                f"{candidate.entry.intervention_code}: payback unavailable, max-payback constraint not evaluable"
            )
        survivors.append(candidate)

    # Deterministic ranking: final score desc, then CO2 saving desc, then code.
    survivors.sort(
        key=lambda item: (
            -item.final_score,
            -(float(item.co2_saving_kg) if item.co2_saving_kg is not None else -1.0),
            item.entry.intervention_code,
        )
    )
    if constraints.max_recommendations is not None:
        survivors = survivors[: constraints.max_recommendations]

    final_codes = {candidate.entry.intervention_code for candidate in survivors}
    for candidate in survivors:
        for other in sorted(candidate.entry.conflicts_with_codes):
            if other in final_codes:
                pair = sorted([candidate.entry.intervention_code, other])
                if pair not in diagnostics.conflicts:
                    diagnostics.conflicts.append(pair)

    recommendations: list[RecommendationOutputItem] = []
    for rank, candidate in enumerate(survivors, start=1):
        conf = _dec(candidate.scores.confidence, 2)
        co2_saving = _dec(candidate.co2_saving_kg, 6)
        capex = _dec(candidate.estimated_capex, 2)
        annual_saving = _dec(candidate.annual_saving, 2)
        payback = _dec(candidate.payback, 2)
        energy_saving = (
            _dec(candidate.savings.energy_kwh_equivalent, 2) if context is not None else None
        )
        waste_reduction = (
            _dec(candidate.savings.waste_kg + candidate.savings.packaging_kg, 2)
            if context is not None
            else None
        )
        cost_per_tonne = None
        if capex is not None and co2_saving is not None and co2_saving > ZERO:
            cost_per_tonne = _dec(capex / (co2_saving / Decimal("1000")), 2)

        conflicts = [
            other
            for other in sorted(candidate.entry.conflicts_with_codes)
            if other in final_codes
        ]
        rec_id = _rec_uuid(
            "rec",
            facility.id,
            hotspots.reporting_period_id,
            candidate.hotspot.id,
            candidate.entry.id,
        )
        assessment_id = _rec_uuid("assessment", rec_id)

        assumptions = dict(candidate.savings.assumptions)
        assumptions.update(
            {
                "co2_saving_basis": candidate.co2_basis
                + " (deterministic P4 estimator until P3 baselines are live)",
                "cost_per_tonne_co2_avoided_basis": "estimated CAPEX / first-year tCO2e avoided",
                "context_available": context is not None,
            }
        )
        if candidate.payback_note:
            assumptions["payback_note"] = candidate.payback_note

        assessment = RecommendationAssessment(
            id=assessment_id,
            recommendation_id=rec_id,
            estimated_capex=capex,
            estimated_annual_opex_change=(
                _dec(candidate.savings.opex_change_currency, 2) if context is not None else None
            ),
            estimated_annual_saving=annual_saving,
            estimated_co2_saving_kg=co2_saving,
            estimated_energy_saving=energy_saving,
            estimated_waste_reduction=waste_reduction,
            payback_years=payback,
            cost_per_tonne_co2_avoided=cost_per_tonne,
            assumptions=assumptions,
            confidence_score=conf,
        )

        evidence = ExplanationEvidence(
            recommendation_id=rec_id,
            intervention_code=candidate.entry.intervention_code,
            intervention_title=candidate.entry.title,
            rank=rank,
            final_score=candidate.final_score,
            scores=candidate.scores,
            hotspot_rank=candidate.hotspot.rank,
            hotspot_process_name=candidate.hotspot.process_name,
            hotspot_severity=candidate.hotspot.severity.value,
            hotspot_contribution_percent=candidate.hotspot.contribution_percent,
            hotspot_emissions_kgco2e=candidate.hotspot.emissions_kgco2e,
            hotspot_carbon_intensity=candidate.hotspot.carbon_intensity,
            hotspot_inefficiency_score=candidate.hotspot.inefficiency_score,
            hotspot_waste_ratio_score=candidate.hotspot.waste_ratio_score,
            hotspot_improvement_potential_score=candidate.hotspot.improvement_potential_score,
            hotspot_explanation=candidate.hotspot.explanation,
            co2_reduction_min_pct=candidate.entry.expected_co2_reduction_min_pct,
            co2_reduction_max_pct=candidate.entry.expected_co2_reduction_max_pct,
            energy_reduction_min_pct=candidate.entry.energy_reduction_min_pct,
            energy_reduction_max_pct=candidate.entry.energy_reduction_max_pct,
            waste_reduction_min_pct=candidate.entry.waste_reduction_min_pct,
            waste_reduction_max_pct=candidate.entry.waste_reduction_max_pct,
            water_reduction_min_pct=candidate.entry.water_reduction_min_pct,
            water_reduction_max_pct=candidate.entry.water_reduction_max_pct,
            capex_min=candidate.entry.min_capex,
            capex_max=candidate.entry.max_capex,
            estimated_capex=capex,
            estimated_annual_saving=annual_saving,
            estimated_annual_opex_change=(
                _dec(candidate.savings.opex_change_currency, 2) if context is not None else None
            ),
            estimated_co2_saving_kg=co2_saving,
            co2_saving_basis=candidate.co2_basis,
            estimated_energy_saving_kwh=energy_saving,
            estimated_waste_reduction_kg=waste_reduction,
            estimated_water_reduction_m3=(
                _dec(candidate.savings.water_m3, 2) if context is not None else None
            ),
            payback_years=payback,
            cost_per_tonne_co2_avoided=cost_per_tonne,
            currency=constraints.currency,
            implementation_months_min=candidate.entry.implementation_months_min,
            implementation_months_max=candidate.entry.implementation_months_max,
            evidence_source=candidate.entry.evidence_source,
            confidence_score=candidate.scores.confidence,
            data_quality_score=hotspots.data_quality_score,
            context_available=context is not None,
            assumptions=assumptions,
            prerequisites=list(candidate.entry.prerequisite_codes),
            prerequisites_unmet=list(candidate.prerequisites_unmet),
            conflicts_with=conflicts,
            feasibility_notes=list(candidate.feasibility_notes),
        )

        outcome = explainer.explain(evidence)
        diagnostics.explanation_sources[outcome.source] = (
            diagnostics.explanation_sources.get(outcome.source, 0) + 1
        )

        recommendations.append(
            RecommendationOutputItem(
                id=rec_id,
                facility_id=facility.id,
                reporting_period_id=hotspots.reporting_period_id,
                hotspot_id=candidate.hotspot.id,
                intervention_id=candidate.entry.id,
                rank=rank,
                carbon_saving_score=_dec(candidate.scores.carbon_saving, 2),
                financial_return_score=_dec(candidate.scores.financial_return, 2),
                feasibility_score=_dec(candidate.scores.feasibility, 2),
                circularity_score=_dec(candidate.scores.circularity, 2),
                implementation_speed_score=_dec(candidate.scores.implementation_speed, 2),
                confidence_score=conf,
                final_score=_dec(candidate.final_score, 2),
                status=RecommendationStatus.SUGGESTED,
                generated_at=now,
                intervention_code=candidate.entry.intervention_code,
                intervention_title=candidate.entry.title,
                explanation=outcome.text,
                impact=assessment,
            )
        )

        diagnostics.scored.append(
            ScoredCandidateDiagnostics(
                intervention_code=candidate.entry.intervention_code,
                hotspot_id=candidate.hotspot.id,
                process_name=candidate.hotspot.process_name,
                scores=candidate.scores,
                final_score=candidate.final_score,
                estimated_co2_saving_kg=co2_saving,
                estimated_capex=capex,
                estimated_annual_saving=annual_saving,
                payback_years=payback,
                prerequisites_unmet=list(candidate.prerequisites_unmet),
                feasibility_notes=list(candidate.feasibility_notes),
            )
        )

    diagnostics.applicable = len(survivors)
    result = RecommendationGenerationResult(
        facility_id=facility.id,
        reporting_period_id=hotspots.reporting_period_id,
        generated_at=now,
        budget_limit=constraints.budget_limit,
        recommendations=recommendations,
    )
    return EngineRun(result=result, diagnostics=diagnostics)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pre_candidate_filter(
    entry: InterventionEntry,
    facility: Facility,
    organization: Optional[Organization],
    constraints: RecommendationConstraints,
) -> Optional[str]:
    if not entry.active:
        return "INACTIVE"
    sector = organization.industry_sector if organization is not None else None
    if sector and entry.industry_sector not in (None, "All", sector):
        return "INDUSTRY_NOT_APPLICABLE"
    if entry.min_annual_production_tonnes is not None:
        production_unit = (facility.production_unit or "").lower()
        if production_unit.startswith("tonne") or production_unit in {"t", ""}:
            production = facility.annual_production or ZERO
            if production < entry.min_annual_production_tonnes:
                return "BELOW_MIN_SCALE"
    if entry.currency and entry.currency != constraints.currency:
        return "CURRENCY_MISMATCH"
    if entry.intervention_code in constraints.excluded_intervention_codes:
        return "EXCLUDED_BY_USER"
    if entry.intervention_code in constraints.locally_unavailable_codes:
        return "LOCALLY_UNAVAILABLE"
    if (
        constraints.max_complexity is not None
        and entry.complexity is not None
        and COMPLEXITY_ORDER[entry.complexity] > COMPLEXITY_ORDER[constraints.max_complexity]
    ):
        return "COMPLEXITY_LIMIT"
    return None


def _process_matches(
    entry: InterventionEntry,
    hotspot: HotspotOutputItem,
    process_categories: dict[str, Optional[str]],
) -> bool:
    categories = entry.applicable_process_categories
    if not categories or "*" in categories:
        return True
    if hotspot.process_name and hotspot.process_name in categories:
        return True
    category = process_categories.get(hotspot.process_name or "")
    return bool(category and category in categories)


def _resource_signal(entry: InterventionEntry, baseline) -> bool:
    if baseline is None:
        return False
    loops = set(entry.loop_types)
    if LoopType.WASTE in loops and (baseline.waste_kg_per_year or ZERO) > ZERO:
        return True
    if LoopType.WATER in loops and (
        (baseline.water_m3_per_year or ZERO) > ZERO or (baseline.wastewater_m3_per_year or ZERO) > ZERO
    ):
        return True
    if LoopType.PACKAGING in loops and (baseline.packaging_kg_per_year or ZERO) > ZERO:
        return True
    if LoopType.MATERIAL in loops and (baseline.waste_kg_per_year or ZERO) > ZERO:
        return True
    return False


def _region_mismatch(entry: InterventionEntry, constraints: RecommendationConstraints) -> bool:
    if not entry.applicable_regions:
        return False
    known = {
        value
        for value in (constraints.region_country, constraints.region_state)
        if value
    }
    if not known:
        return False
    return not (set(entry.applicable_regions) & known)


def _build_candidates(
    entry: InterventionEntry,
    hotspots: HotspotDetectionResult,
    baselines: dict,
    facility_baseline,
    context: Optional[FacilityContext],
    emission_factors: Optional[ResourceEmissionFactors],
    constraints: RecommendationConstraints,
    process_categories: dict[str, Optional[str]],
) -> list[_Candidate]:
    facility_wide = not entry.applicable_process_categories or "*" in entry.applicable_process_categories
    matches: list[_Candidate] = []
    data_quality = hotspots.data_quality_score

    for hotspot in hotspots.hotspots:
        if not _process_matches(entry, hotspot, process_categories):
            continue
        baseline = facility_baseline if facility_wide else baselines.get(hotspot.process_name or "")
        activity_ok = (
            hotspot.activity_category in entry.applicable_activity_categories
            if entry.applicable_activity_categories
            else True
        )
        if not activity_ok and not _resource_signal(entry, baseline):
            continue

        if context is not None and baseline is not None:
            savings = estimate_resource_savings(entry, baseline, context.tariffs, context.conversions)
            baseline_available = True
        else:
            savings = ResourceSavings()
            baseline_available = False

        co2_mid = midpoint(entry.expected_co2_reduction_min_pct, entry.expected_co2_reduction_max_pct)
        hotspot_share_co2 = (
            min(hotspot.emissions_kgco2e, hotspot.emissions_kgco2e * co2_mid / Decimal("100"))
            if co2_mid is not None
            else None
        )
        physical_co2 = (
            estimate_resource_co2(savings, emission_factors)
            if baseline_available and emission_factors is not None
            else None
        )
        if physical_co2 is not None:
            co2_saving = physical_co2
            co2_basis = "resource-based: quantity saved x versioned emission factor"
        else:
            co2_saving = hotspot_share_co2
            co2_basis = (
                "midpoint of expected CO2 reduction range applied to targeted hotspot emissions"
            )

        estimated_capex = midpoint(entry.min_capex, entry.max_capex)
        annual_saving = savings.annual_saving_currency if baseline_available else None
        payback, payback_note = compute_payback(estimated_capex, annual_saving)
        region_mismatch = _region_mismatch(entry, constraints)

        feasibility, notes = feasibility_score(entry, region_mismatch=region_mismatch)
        scores = ScoreBreakdown(
            carbon_saving=carbon_saving_score(co2_saving),
            financial_return=financial_return_score(payback, annual_saving),
            feasibility=feasibility,
            circularity=circularity_score(entry),
            implementation_speed=implementation_speed_score(entry),
            confidence=confidence_score(data_quality, entry, context_available=context is not None),
        )
        matches.append(
            _Candidate(
                entry=entry,
                hotspot=hotspot,
                baseline_available=baseline_available,
                savings=savings,
                co2_saving_kg=co2_saving,
                co2_basis=co2_basis,
                estimated_capex=estimated_capex,
                annual_saving=annual_saving,
                payback=payback,
                payback_note=payback_note,
                scores=scores,
                final_score=weighted_final_score(scores),
                feasibility_notes=notes,
                region_mismatch=region_mismatch,
            )
        )
    return matches
