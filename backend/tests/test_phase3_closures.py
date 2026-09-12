"""Phase-3 readiness closure tests (permanent CI suite).

Covers the silent-correctness findings closed before Phase 3:
- F-4 health probes dependencies
- F-6 M1 unknown recommendation uses the frozen error shape
- F-7 F2 GET calculations served; J3 PATCH status transitions
- F-8 machine-readable degraded-mode label (data_is_stub)
- F-13 malformed input -> 422 frozen shape (not 500)
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

F = "0a1b2c3d-0002-4002-8002-000000000002"
P = "0a1b2c3d-0003-4003-8003-000000000003"
FROZEN_KEYS = {"error_code", "message", "severity", "details"}


def test_f4_health_reports_dependencies(client):
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["components"].keys()) == {"database", "engine"}
    assert body["components"]["database"] == "ok"
    assert body["components"]["engine"] == "ok"


def test_f4_health_returns_request_id(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Request-Id")


def test_f6_unknown_recommendation_frozen_404(client):
    r = client.get("/api/recommendations/00000000-0000-4000-8000-ffffffffffff/explanation")
    assert r.status_code == 404
    assert set(r.json().keys()) == FROZEN_KEYS
    assert r.json()["error_code"] == "NOT_FOUND"


def test_f7_f2_get_calculations_matches_f1_post(client):
    post = client.post(f"/api/facilities/{F}/reporting-periods/{P}/calculations", json={})
    get = client.get(f"/api/facilities/{F}/reporting-periods/{P}/calculations")
    assert post.status_code == 200, post.text
    assert get.status_code == 200, get.text
    assert len(get.json()) > 0
    first = get.json()[0]
    assert {"activity_data_id", "emission_factor_id", "scope", "co2e_kg"} <= set(first.keys())

    # Deterministic values must be identical; only per-call timestamps differ.
    stable = ("id", "activity_data_id", "emission_factor_id", "scope", "co2e_kg", "calculation_version")
    def projection(rows):
        return [{key: row.get(key) for key in stable} for row in rows]

    assert projection(get.json()) == projection(post.json())


def test_f7_j3_status_transitions_and_negatives(client):
    recs = client.get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations").json()
    rid = recs["recommendations"][0]["id"]

    # unknown id -> 404 frozen
    r = client.patch(
        "/api/recommendations/00000000-0000-4000-8000-ffffffffffff",
        json={"status": "SHORTLISTED"},
    )
    assert r.status_code == 404
    assert set(r.json().keys()) == FROZEN_KEYS

    # invalid status value -> 422 frozen
    r = client.patch(f"/api/recommendations/{rid}", json={"status": "NOT_A_STATUS"})
    assert r.status_code == 422
    assert set(r.json().keys()) == FROZEN_KEYS

    # valid transitions: SUGGESTED -> PLANNED -> IMPLEMENTED
    r = client.patch(f"/api/recommendations/{rid}", json={"status": "PLANNED"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PLANNED"
    r = client.patch(f"/api/recommendations/{rid}", json={"status": "IMPLEMENTED"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "IMPLEMENTED"

    # invalid transition from a terminal state -> 409 frozen
    r = client.patch(f"/api/recommendations/{rid}", json={"status": "SHORTLISTED"})
    assert r.status_code == 409
    assert set(r.json().keys()) == FROZEN_KEYS
    assert r.json()["error_code"] == "CONFLICT"


def test_f8_data_is_stub_label_present(client):
    body = client.get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations").json()
    assert body["recommendations"], "expected recommendations"
    for rec in body["recommendations"]:
        assumptions = (rec.get("impact") or {}).get("assumptions") or {}
        assert assumptions.get("data_is_stub") is True


def test_f13_malformed_uuid_is_422_frozen(client):
    r = client.get("/api/emission-factors/x%27%20UNION%20SELECT%20null--")
    assert r.status_code == 422
    assert set(r.json().keys()) == FROZEN_KEYS
    assert r.json()["error_code"] == "VALIDATION_ERROR"


def test_f13_invalid_reason_code_is_422_frozen(client):
    recs = client.get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations").json()
    rid = recs["recommendations"][0]["id"]
    r = client.post(
        f"/api/recommendations/{rid}/feedback",
        json={"feedback_type": "REJECTED", "reason_code": "NOT_A_REAL_CODE"},
    )
    assert r.status_code == 422
    assert set(r.json().keys()) == FROZEN_KEYS
    assert r.json()["error_code"] == "VALIDATION_ERROR"


def test_f13_non_numeric_feedback_field_is_422_frozen(client):
    recs = client.get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations").json()
    rid = recs["recommendations"][0]["id"]
    r = client.post(
        f"/api/recommendations/{rid}/feedback",
        json={"feedback_type": "USEFUL", "actual_capex": "not-a-number"},
    )
    assert r.status_code == 422
    assert set(r.json().keys()) == FROZEN_KEYS
