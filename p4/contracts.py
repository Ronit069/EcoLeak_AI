"""Import shim for the frozen Phase 0 contracts package.

The contracts directory intentionally has no __init__.py (it is a shared
artifact tree, not a Python package). P4 imports the frozen models from here
so every other module can do `from p4.contracts import ...`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"
if str(_CONTRACTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTRACTS_DIR))

from schemas import (  # noqa: E402,F401
    ActivityCategory,
    CircularIntervention,
    ConfidenceLevel,
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
