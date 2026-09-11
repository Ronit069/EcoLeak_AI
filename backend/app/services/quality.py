"""Module D - Carbon Data Quality Score.

Produces a 0-100 score per activity record and an aggregate facility/period
assessment (DB doc 8.1). Scores are deterministic and explainable; issues use the
frozen `ValidationIssue` shape (severity ERROR | WARNING | INFO |
CONFIRMATION_REQUIRED).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.errors import error_payload
from app.models.activity import ActivityData
from app.models.calculation import DataQualityAssessment
from app.models.core import Facility, ReportingPeriod
from app.models.factor import EmissionFactor
from app.services import factors as factor_service

SOURCE_QUALITY = {
    "SENSOR": Decimal("100"),
    "API": Decimal("100"),
    "CSV": Decimal("85"),
    "EXCEL": Decimal("85"),
    "MANUAL": Decimal("75"),
    "OCR": Decimal("50"),
}
_FACTOR_QUALITY = {"HIGH": Decimal("100"), "MEDIUM": Decimal("75"), "LOW": Decimal("50")}
_WEIGHTS = {
    "completeness": Decimal("0.30"),
    "source": Decimal("0.25"),
    "factor": Decimal("0.25"),
    "temporal": Decimal("0.10"),
    "unit": Decimal("0.10"),
}


def _issue(severity: str, code: str, message: str, field: str | None = None, details: dict | None = None) -> dict:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "field": field,
        "details": details or {},
    }


def match_factor(db: Session, activity: ActivityData) -> Optional[EmissionFactor]:
    return factor_service.lookup_factor(
        db,
        category=activity.activity_category,
        activity_subcategory=activity.activity_subcategory,
        normalized_unit=activity.normalized_unit,
        on_date=activity.created_at.date() if activity.created_at else None,
    )


def score_activity_record(
    activity: ActivityData,
    factor: Optional[EmissionFactor] = None,
    *,
    period_present: bool = True,
) -> Decimal:
    present = [
        activity.process_id,
        activity.source_name,
        activity.original_value,
        activity.normalized_value,
        activity.confidence_score,
    ]
    completeness = Decimal("100") * Decimal(sum(1 for p in present if p is not None)) / Decimal(len(present))

    source = SOURCE_QUALITY.get(activity.data_source_type, Decimal("60"))
    if activity.measured_or_estimated == "ESTIMATED":
        source = source * Decimal("0.7")

    factor_quality = (
        _FACTOR_QUALITY.get(factor.confidence_level or "", Decimal("50"))
        if factor is not None
        else Decimal("0")
    )

    temporal = Decimal("100") if period_present else Decimal("50")
    unit = Decimal("100") if activity.normalized_unit and activity.normalized_value is not None else Decimal("40")

    total = (
        completeness * _WEIGHTS["completeness"]
        + source * _WEIGHTS["source"]
        + factor_quality * _WEIGHTS["factor"]
        + temporal * _WEIGHTS["temporal"]
        + unit * _WEIGHTS["unit"]
    )
    return total.quantize(Decimal("0.01"))


def issues_for_activity(
    activity: ActivityData, factor: Optional[EmissionFactor]
) -> list[dict]:
    issues: list[dict] = []
    if factor is None:
        issues.append(
            _issue(
                "WARNING",
                "UNRESOLVED_EMISSION_FACTOR",
                "No compatible emission factor; record stays UNRESOLVED (no default fabricated).",
                field="normalized_unit",
                details={"category": activity.activity_category, "unit": activity.normalized_unit},
            )
        )
    if activity.original_value is not None and activity.normalized_value is not None:
        if activity.original_value == 0 and activity.normalized_value > 0:
            issues.append(_issue("WARNING", "MAGNITUDE_MISMATCH", "Normalized value changed from a zero original."))
    if activity.measured_or_estimated == "ESTIMATED":
        issues.append(
            _issue("INFO", "ESTIMATED_DATA", "Estimated value; lower confidence applied.")
        )
    return issues


def assess_period(
    db: Session,
    facility: Facility,
    period: ReportingPeriod,
    *,
    persist: bool = True,
) -> DataQualityAssessment:
    activities = list(
        db.scalars(
            select(ActivityData).where(
                ActivityData.facility_id == facility.id,
                ActivityData.reporting_period_id == period.id,
                ActivityData.deleted_at.is_(None),
            )
        )
    )
    issues: list[dict[str, Any]] = []
    factor_scores: list[Decimal] = []
    source_scores: list[Decimal] = []
    unit_scores: list[Decimal] = []
    record_scores: list[Decimal] = []

    for activity in activities:
        factor = match_factor(db, activity)
        record_scores.append(score_activity_record(activity, factor))
        factor_scores.append(_FACTOR_QUALITY.get(factor.confidence_level or "", Decimal("50")) if factor else Decimal("0"))
        source_scores.append(SOURCE_QUALITY.get(activity.data_source_type, Decimal("60")))
        unit_scores.append(Decimal("100") if activity.normalized_value is not None else Decimal("40"))
        issues.extend(issues_for_activity(activity, factor))

    def avg(values: list[Decimal], default: Decimal = Decimal("0")) -> Decimal:
        return (sum(values) / len(values)).quantize(Decimal("0.01")) if values else default

    completeness = Decimal("100") if activities else Decimal("0")
    source_quality = avg(source_scores)
    factor_quality = avg(factor_scores)
    temporal_quality = Decimal("100")
    unit_quality = avg(unit_scores)
    total = (
        completeness * _WEIGHTS["completeness"]
        + source_quality * _WEIGHTS["source"]
        + factor_quality * _WEIGHTS["factor"]
        + temporal_quality * _WEIGHTS["temporal"]
        + unit_quality * _WEIGHTS["unit"]
    ).quantize(Decimal("0.01"))

    if not activities:
        issues.append(_issue("WARNING", "NO_ACTIVITY_DATA", "No activity records in this period."))

    assessment = DataQualityAssessment(
        facility_id=facility.id,
        reporting_period_id=period.id,
        completeness_score=completeness,
        source_quality_score=source_quality,
        factor_quality_score=factor_quality,
        temporal_quality_score=temporal_quality,
        unit_quality_score=unit_quality,
        total_score=total,
        issues=issues,
        generated_at=utcnow(),
    )
    if persist:
        db.add(assessment)
        db.flush()
    return assessment


def assessment_to_dict(assessment: DataQualityAssessment) -> dict:
    return {
        "completeness_score": assessment.completeness_score,
        "source_quality_score": assessment.source_quality_score,
        "factor_quality_score": assessment.factor_quality_score,
        "temporal_quality_score": assessment.temporal_quality_score,
        "unit_quality_score": assessment.unit_quality_score,
        "total_score": assessment.total_score,
        "issues": assessment.issues or [],
    }
