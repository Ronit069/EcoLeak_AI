"""B1 acceptance: one served API surface (merged app).

Proves G2 / J2 / N1 / N2 (plus a P2 router + frozen error shape) are all
reachable behind ONE FastAPI app / base URL — the P1 `api.ts` swap targets.
Engine endpoints run on the default mock data source; P2 DB-backed routers are
exercised for health only (their full path needs PostgreSQL at Phase 2).
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

FID = "0a1b2c3d-0002-4002-8002-000000000002"
PID = "0a1b2c3d-0003-4003-8003-000000000003"

client = TestClient(app)


def test_health_behind_single_base_url() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_g2_hotspots_behind_single_base_url() -> None:
    r = client.get(f"/api/facilities/{FID}/reporting-periods/{PID}/hotspots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["facility_id"] == FID
    assert len(body["hotspots"]) == 5
    assert body["hotspots"][0]["severity"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert body["hotspots"][0]["contribution_percent"] > 0


def test_j2_recommendations_behind_single_base_url() -> None:
    r = client.get(
        f"/api/facilities/{FID}/reporting-periods/{PID}/recommendations?rank_max=3"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["recommendations"]) == 3
    item = body["recommendations"][0]
    assert item["intervention_code"]
    assert item["impact"]["estimated_capex"] >= 0
    assert item["final_score"] >= 0


def test_j1_generate_behind_single_base_url() -> None:
    r = client.post(
        f"/api/facilities/{FID}/reporting-periods/{PID}/recommendations/generate",
        json={"budget_limit": "3000000"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert isinstance(body["recommendations"], list)
    for rec in body["recommendations"]:
        assert rec["impact"]["estimated_capex"] <= 3_000_000


def test_m1_explanation_behind_single_base_url() -> None:
    recs = client.get(f"/api/facilities/{FID}/reporting-periods/{PID}/recommendations").json()
    first_id = recs["recommendations"][0]["id"]
    r = client.get(f"/api/recommendations/{first_id}/explanation")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recommendation_id"] == first_id
    assert set(body.keys()) == {
        "recommendation_id", "summary", "evidence", "assumptions", "confidence_score", "generated_by",
    }


def test_n1_dashboard_behind_single_base_url() -> None:
    r = client.get(f"/api/facilities/{FID}/reporting-periods/{PID}/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in (
        "total_kgco2e", "scope_breakdown", "carbon_intensity", "largest_hotspot",
        "circularity_score", "potential_reduction_kgco2e", "potential_annual_saving",
        "last_calculated_at", "empty_state",
    ):
        assert key in body, f"missing N1 key {key}"
    assert body["largest_hotspot"]["process_name"] == "Boiler"


def test_n2_leak_map_behind_single_base_url() -> None:
    r = client.get(f"/api/facilities/{FID}/reporting-periods/{PID}/leak-map")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["links"] == []
    assert len(body["nodes"]) == 5
    node_keys = {"process_id", "process_name", "emissions_kgco2e", "contribution_percent", "severity"}
    assert node_keys == set(body["nodes"][0].keys())


def test_engine_error_uses_frozen_shape_not_raw_http_exception() -> None:
    r = client.post(
        "/api/scenarios/11111111-1111-4111-8111-111111111111/simulate",
        json={"interventions": [{"intervention_code": "INT-DOES-NOT-EXIST"}]},
    )
    assert r.status_code == 404
    body = r.json()
    assert set(body.keys()) == {"error_code", "message", "severity", "details"}
    assert body["error_code"] == "NOT_FOUND"


def test_frozen_shape_validates_for_m1_explanation() -> None:
    recs = client.get(f"/api/facilities/{FID}/reporting-periods/{PID}/recommendations").json()
    first_id = recs["recommendations"][0]["id"]
    body = client.get(f"/api/recommendations/{first_id}/explanation").json()
    assert body["confidence_score"] == recs["recommendations"][0]["confidence_score"]