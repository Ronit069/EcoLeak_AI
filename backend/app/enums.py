"""Enums re-exported from the frozen contract so there is exactly one definition."""
from __future__ import annotations

from app.contracts_compat import schemas as _s

ActivityCategory = _s.ActivityCategory
ConfidenceLevel = _s.ConfidenceLevel
DataSourceType = _s.DataSourceType
FeedbackType = _s.FeedbackType
HotspotSeverity = _s.HotspotSeverity
InterventionComplexity = _s.InterventionComplexity
MeasuredOrEstimated = _s.MeasuredOrEstimated
OrganizationSize = _s.OrganizationSize
PeriodType = _s.PeriodType
RecommendationStatus = _s.RecommendationStatus
ReportingPeriodStatus = _s.ReportingPeriodStatus
RiskLevel = _s.RiskLevel
Scope = _s.Scope
ValidationSeverity = _s.ValidationSeverity

ACTIVITY_CATEGORIES = [e.value for e in ActivityCategory]
DATA_SOURCE_TYPES = [e.value for e in DataSourceType]
MEASURED_OR_ESTIMATED = [e.value for e in MeasuredOrEstimated]
SCOPES = [e.value for e in Scope]
PERIOD_TYPES = [e.value for e in PeriodType]
PERIOD_STATUSES = [e.value for e in ReportingPeriodStatus]
ORG_SIZES = [e.value for e in OrganizationSize]
CONFIDENCE_LEVELS = [e.value for e in ConfidenceLevel]
HOTSPOT_SEVERITIES = [e.value for e in HotspotSeverity]
RECOMMENDATION_STATUSES = [e.value for e in RecommendationStatus]
FEEDBACK_TYPES = [e.value for e in FeedbackType]

# Roles (DB doc section 20, Level 2).
ROLES = [
    "SYSTEM_ADMIN",
    "ORGANIZATION_ADMIN",
    "SUSTAINABILITY_ANALYST",
    "FACTORY_OPERATOR",
    "VIEWER",
    "REGULATOR_READ_ONLY",
]
