"""Module J scoring: deterministic, explainable multi-criteria rubric.

The final score is EXACTLY the requirements-doc formula (section 20):

    0.30 Carbon Saving + 0.25 Financial Return + 0.15 Feasibility
    + 0.15 Circularity + 0.10 Implementation Speed + 0.05 Confidence

Each component is a 0..100 score produced by the documented rubrics below.
No LLM, no randomness, no hidden state.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from p4.contracts import InterventionComplexity, RiskLevel
from p4.models import InterventionEntry, LoopType, ScoreBreakdown

WEIGHTS: dict[str, float] = {
    "carbon_saving": 0.30,
    "financial_return": 0.25,
    "feasibility": 0.15,
    "circularity": 0.15,
    "implementation_speed": 0.10,
    "confidence": 0.05,
}

CARBON_SAVING_REFERENCE_KG = 50_000.0
BEST_PAYBACK_YEARS = 1.0
WORST_PAYBACK_YEARS = 10.0

COMPLEXITY_BASE: dict[InterventionComplexity, float] = {
    InterventionComplexity.LOW: 90.0,
    InterventionComplexity.MEDIUM: 70.0,
    InterventionComplexity.HIGH: 45.0,
}
RISK_ADJUSTMENT: dict[RiskLevel, float] = {
    RiskLevel.LOW: 10.0,
    RiskLevel.MEDIUM: 0.0,
    RiskLevel.HIGH: -15.0,
}
COMPLEXITY_ORDER: dict[InterventionComplexity, int] = {
    InterventionComplexity.LOW: 0,
    InterventionComplexity.MEDIUM: 1,
    InterventionComplexity.HIGH: 2,
}
RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _f(value: Optional[Decimal]) -> Optional[float]:
    return None if value is None else float(value)


def carbon_saving_score(estimated_co2_saving_kg: Optional[Decimal]) -> float:
    """Absolute rubric: a saving >= 50 tCO2e/year scores 100."""

    if estimated_co2_saving_kg is None:
        return 0.0
    return clamp(100.0 * float(estimated_co2_saving_kg) / CARBON_SAVING_REFERENCE_KG)


def financial_return_score(payback_years: Optional[Decimal], annual_saving: Optional[Decimal]) -> float:
    """Payback rubric: 1 year -> 100, 10+ years -> 0. Zero CAPEX with positive
    saving is immediate payback -> 100; no/negative saving -> 0."""

    if annual_saving is not None and float(annual_saving) > 0 and payback_years == 0:
        return 100.0
    if payback_years is None:
        return 0.0
    payback = float(payback_years)
    if payback <= BEST_PAYBACK_YEARS:
        return 100.0
    if payback >= WORST_PAYBACK_YEARS:
        return 0.0
    return clamp(
        100.0 * (WORST_PAYBACK_YEARS - payback) / (WORST_PAYBACK_YEARS - BEST_PAYBACK_YEARS)
    )


def feasibility_score(
    entry: InterventionEntry,
    *,
    region_mismatch: bool = False,
    prerequisites_unmet: int = 0,
) -> tuple[float, list[str]]:
    """Complexity + risk + local availability + prerequisites."""

    score = COMPLEXITY_BASE.get(entry.complexity or InterventionComplexity.MEDIUM, 70.0)
    score += RISK_ADJUSTMENT.get(entry.risk_level or RiskLevel.MEDIUM, 0.0)
    notes: list[str] = []
    if region_mismatch:
        score -= 15.0
        notes.append("technology availability not confirmed for this region (-15 feasibility)")
    if prerequisites_unmet:
        penalty = min(20.0, 10.0 * prerequisites_unmet)
        score -= penalty
        notes.append(f"{prerequisites_unmet} prerequisite(s) not in the candidate set (-{penalty:g} feasibility)")
    return clamp(score), notes


def circularity_score(entry: InterventionEntry) -> float:
    """Resource-loop rubric: circular loops and waste/water diversion raise
    the score; pure energy-efficiency interventions score lower."""

    loops = set(entry.loop_types)
    score = 20.0
    circular_loops = {
        LoopType.MATERIAL,
        LoopType.WATER,
        LoopType.WASTE,
        LoopType.PACKAGING,
        LoopType.CHEMICAL,
    }
    if loops & circular_loops:
        score += 20.0
    if LoopType.HEAT_RECOVERY in loops:
        score += 10.0
    waste_mid = _mid_pct(entry.waste_reduction_min_pct, entry.waste_reduction_max_pct)
    if waste_mid:
        score += min(40.0, waste_mid * 0.4)
    water_mid = _mid_pct(entry.water_reduction_min_pct, entry.water_reduction_max_pct)
    if water_mid:
        score += min(15.0, water_mid * 0.3)
    return clamp(score)


def implementation_speed_score(entry: InterventionEntry) -> float:
    """1 month -> 100, 12 months -> ~12, floor 15."""

    months = _mid_pct(
        Decimal(entry.implementation_months_min) if entry.implementation_months_min is not None else None,
        Decimal(entry.implementation_months_max) if entry.implementation_months_max is not None else None,
    )
    if months is None:
        return 50.0
    return clamp(100.0 - max(0.0, (months - 1.0) * 8.0), low=15.0)


def confidence_score(
    data_quality_score: Optional[Decimal],
    entry: InterventionEntry,
    *,
    context_available: bool,
) -> float:
    """Input data quality (60%) + evidence quality (40%) - missing-context penalty."""

    data_quality = float(data_quality_score) if data_quality_score is not None else 70.0
    evidence = 80.0 if entry.evidence_source else 50.0
    score = 0.6 * data_quality + 0.4 * evidence
    if not context_available:
        score -= 10.0
    return clamp(score)


def _mid_pct(low: Optional[Decimal], high: Optional[Decimal]) -> Optional[float]:
    values = [float(value) for value in (low, high) if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def weighted_final_score(scores: ScoreBreakdown) -> float:
    """Exact requirements-doc formula. Weights must sum to 1.0."""

    total = (
        WEIGHTS["carbon_saving"] * scores.carbon_saving
        + WEIGHTS["financial_return"] * scores.financial_return
        + WEIGHTS["feasibility"] * scores.feasibility
        + WEIGHTS["circularity"] * scores.circularity
        + WEIGHTS["implementation_speed"] * scores.implementation_speed
        + WEIGHTS["confidence"] * scores.confidence
    )
    return round(total, 2)
