"""Import shim for the frozen Phase 0 contracts package.

P4, P2 and P3 must share the *same* frozen model classes, so this shim imports
via ``contracts.schemas`` (the way ``engine/*`` and ``backend/*`` do) instead
of loading a second ``schemas`` module. Dual module identity would make
``isinstance``/``model_validate`` behave inconsistently when P3 objects flow
into the P4 ranker.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.schemas import (  # noqa: E402,F401
    ActivityCategory,
    CircularIntervention,
    ConfidenceLevel,
    EmissionFactor,
    Facility,
    FeedbackType,
    HotspotDetectionResult,
    HotspotOutputItem,
    HotspotSeverity,
    InterventionComplexity,
    Organization,
    Process,
    Recommendation,
    RecommendationAssessment,
    RecommendationFeedback,
    RecommendationGenerationResult,
    RecommendationOutputItem,
    RecommendationStatus,
    RiskLevel,
    Scenario,
    ScenarioIntervention,
    Scope,
    StrictBaseModel,
    ValidationSeverity,
)
