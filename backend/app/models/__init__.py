"""Import every model so Base.metadata is complete for Alembic and seeding."""
from app.models.activity import ActivityData
from app.models.analytics import AnomalyResult, CircularityScore, EmissionHotspot
from app.models.audit import AuditLog
from app.models.calculation import (
    CarbonInventorySummary,
    DataQualityAssessment,
    EmissionCalculation,
)
from app.models.core import Facility, Organization, ReportingPeriod
from app.models.factor import EmissionFactor
from app.models.ingestion import IngestionBatch, IngestionError
from app.models.intervention import CircularIntervention, InterventionApplicability
from app.models.master import EnergySource, IndustryBenchmark, Material, WasteType
from app.models.process import Process, ProcessAsset, ProcessLink
from app.models.recommendation import (
    Recommendation,
    RecommendationAssessment,
    RecommendationFeedback,
)
from app.models.report import Report
from app.models.scenario import Scenario, ScenarioIntervention, ScenarioResult

__all__ = [
    "ActivityData",
    "AnomalyResult",
    "AuditLog",
    "CarbonInventorySummary",
    "CircularIntervention",
    "CircularityScore",
    "DataQualityAssessment",
    "EmissionCalculation",
    "EmissionFactor",
    "EmissionHotspot",
    "EnergySource",
    "Facility",
    "IndustryBenchmark",
    "IngestionBatch",
    "IngestionError",
    "InterventionApplicability",
    "Material",
    "Organization",
    "Process",
    "ProcessAsset",
    "ProcessLink",
    "Recommendation",
    "RecommendationAssessment",
    "RecommendationFeedback",
    "Report",
    "ReportingPeriod",
    "Scenario",
    "ScenarioIntervention",
    "ScenarioResult",
    "WasteType",
]
