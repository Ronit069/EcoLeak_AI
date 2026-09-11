"""EcoLeak AI - P4: AI Recommendation, Explainability & Demo (Phase 1).

Public surface:
- InterventionLibrary / default_library   (Module I knowledge base)
- generate_recommendations / generate_with_diagnostics (Module J engine)
- TemplateExplainer / LLMExplainer / find_numeric_contradictions (Module M)
- InMemoryFeedbackStore / FeedbackEvent   (Module Q)
"""

from p4.engine import EngineRun, generate_recommendations, generate_with_diagnostics
from p4.explainability import (
    Explainer,
    LLMExplainer,
    TemplateExplainer,
    build_prompt,
    find_numeric_contradictions,
)
from p4.feedback import FeedbackError, FeedbackEvent, InMemoryFeedbackStore
from p4.financial import apply_adoption, compute_payback, project_emissions
from p4.library import InterventionLibrary, default_library
from p4.models import (
    EngineDiagnostics,
    ExplanationEvidence,
    ExplanationOutcome,
    FacilityContext,
    InterventionEntry,
    LoopType,
    OpexImpact,
    ProcessResourceBaseline,
    RecommendationConstraints,
    RejectionReasonCode,
    ResourceEmissionFactors,
    ScoreBreakdown,
    TariffSet,
)
from p4.scoring import WEIGHTS, weighted_final_score
from p4.serialization import to_api_dict

__all__ = [
    "EngineDiagnostics",
    "EngineRun",
    "Explainer",
    "ExplanationEvidence",
    "ExplanationOutcome",
    "FacilityContext",
    "FeedbackError",
    "FeedbackEvent",
    "InMemoryFeedbackStore",
    "InterventionEntry",
    "InterventionLibrary",
    "LLMExplainer",
    "LoopType",
    "OpexImpact",
    "ProcessResourceBaseline",
    "RecommendationConstraints",
    "RejectionReasonCode",
    "ResourceEmissionFactors",
    "ScoreBreakdown",
    "TariffSet",
    "TemplateExplainer",
    "WEIGHTS",
    "apply_adoption",
    "build_prompt",
    "compute_payback",
    "default_library",
    "find_numeric_contradictions",
    "generate_recommendations",
    "generate_with_diagnostics",
    "project_emissions",
    "to_api_dict",
    "weighted_final_score",
]
