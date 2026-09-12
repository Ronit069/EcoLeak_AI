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
    # STRICT (adversarial re-verification): success requires 200 + envelope +
    # no error payload. There is deliberately no OR-acceptance of any
    # fallback-shaped response, and payback_status uses ONE canonical
    # vocabulary (the engine's uppercase enum) — no dual-vocabulary union.
    assert r.status_code == 200, r.text
    body = r.json()
    assert "error_code" not in body, f"engine error leaked into K1: {body}"
    parsed = ScenarioSimulationEnvelope.model_validate(body)
    ImpactAssessment.model_validate(parsed.assessment)
    assert parsed.assessment.baseline_emissions_kg >= 0
    assert parsed.payback_status in {None, "AVAILABLE", "UNAVAILABLE"}
    assert parsed.payback_status != "available", "lowercase vocabulary leaking from a fallback path"  # noqa: E712 - deliberate strictness


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

def test_p104_five_hundred_carries_security_cors_request_id_headers() -> None:
    """P1-04 verification: a REAL 500 must still carry X-Content-Type-Options,
    X-Frame-Options, X-Request-Id and CORS allow-origin, so a browser can read
    the frozen error body instead of failing opaque-ERR_FAILED."""
    from starlette.responses import JSONResponse

    # Temporarily register a route that always bubbles an unhandled exception
    # (worst case for header attachment — goes through the 500 handler).
    @app.get("/__test_forced_500__")
    async def _boom():  # pragma: no cover - test route
        raise RuntimeError("forced P1-04 probe")

    try:
        # Allowed origin (the configured CORS list) — P1-04: a real 500 must
        # behave like any other response for a configured origin: CORS +
        # security + request-id headers, readable frozen body, never opaque.
        r = client.get(
            "/__test_forced_500__",
            headers={"Origin": "http://localhost:5173"},
        )
        assert r.status_code == 500, r.text
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("content-security-policy", "").startswith("default-src")
        assert r.headers.get("x-request-id"), "X-Request-Id must be present on 5xx"
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173", (
            "CORS header must be present on 5xx for a configured origin (audit P1-04)"
        )
        body = r.json()
        assert body.get("error_code") == "INTERNAL_ERROR"
        assert set(body.keys()) == {"error_code", "message", "severity", "details"}
    finally:
        app.routes[:] = [route for route in app.routes if getattr(route, "path", None) != "/__test_forced_500__"]
