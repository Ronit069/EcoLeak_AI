"""Phase-2 remediation contract tests.

Validates the LIVE merged-API responses (N1 dashboard, K1 simulate, Q
feedback) against the formally-added contract models from the Phase 2
addendum in ``contracts/schemas.py`` — closing the two shape deviations
flagged in PHASE2_AUDIT.md (A4).

Run:  python -m pytest tests/test_remediation.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from contracts.schemas import (  # noqa: E402
    DashboardResponse,
    ImpactAssessment,
    ScenarioSimulationEnvelope,
)

F = "0a1b2c3d-0002-4002-8002-000000000002"
P = "0a1b2c3d-0003-4003-8003-000000000003"
client = TestClient(app, raise_server_exceptions=False)


def test_n1_live_response_validates_against_formal_dashboard_model() -> None:
    r = client.get(f"/api/facilities/{F}/reporting-periods/{P}/dashboard")
    assert r.status_code == 200, r.text
    parsed = DashboardResponse.model_validate(r.json())
    assert parsed.production_unit  # formally accepted additive key
    assert parsed.total_kgco2e >= 0
    assert parsed.scope_breakdown.SCOPE_1 + parsed.scope_breakdown.SCOPE_2 + parsed.scope_breakdown.SCOPE_3 == parsed.total_kgco2e


def test_k1_live_response_validates_against_formal_envelope_model() -> None:
    r = client.post(
        f"/api/scenarios/00000000-0000-4000-8000-000000000000/simulate",
        json={
            "facility_id": F,
            "reporting_period_id": P,
            "interventions": [{"intervention_id": "0a1b2c3d-0011-4011-8011-000000000011", "adoption_percentage": 80}],
        },
    )
    assert r.status_code == 200, r.text
    parsed = ScenarioSimulationEnvelope.model_validate(r.json())
    ImpactAssessment.model_validate(parsed.assessment)
    assert parsed.assessment.baseline_emissions_kg >= 0
    assert parsed.payback_status in {None, "AVAILABLE", "UNAVAILABLE", "available", "unavailable"}


def test_q1_feedback_guard_uses_frozen_error_shape() -> None:
    rid = client.get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations").json()["recommendations"][0]["id"]
    r = client.post(f"/api/recommendations/{rid}/feedback", json={"feedback_type": "REJECTED"})
    assert r.status_code == 422
    assert set(r.json().keys()) == {"error_code", "message", "severity", "details"}
    assert r.json()["error_code"] == "FEEDBACK_VALIDATION"


def test_q2_feedback_history_shape() -> None:
    rid = client.get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations").json()["recommendations"][0]["id"]
    r = client.get(f"/api/recommendations/{rid}/feedback")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"recommendation_id", "latest_state", "history"}