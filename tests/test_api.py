from __future__ import annotations

from fastapi.testclient import TestClient

from engine.api import app

FACILITY = "0a1b2c3d-0002-4002-8002-000000000002"
PERIOD = "0a1b2c3d-0003-4003-8003-000000000003"
INTERVENTION = "0a1b2c3d-0011-4011-8011-000000000011"

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_inventory_summary():
    response = client.get(f"/api/facilities/{FACILITY}/reporting-periods/{PERIOD}/inventory-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["scope1_kgco2e"] == 224250
    assert body["scope2_kgco2e"] == 340800


def test_hotspot_detect_shape_and_top_actionable():
    response = client.post(
        f"/api/facilities/{FACILITY}/reporting-periods/{PERIOD}/hotspots/detect",
        json={"scope_boundary": ["SCOPE_1", "SCOPE_2"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hotspots"][0]["process_name"] == "Boiler"
    # G1/G2 return exactly the frozen HotspotDetectionResult envelope.
    assert "top_actionable_hotspot_id" not in body
    assert set(body.keys()) == {"facility_id", "reporting_period_id", "generated_at",
                                "scope_boundary", "total_emissions_kgco2e",
                                "data_quality_score", "hotspots"}
    assert body["total_emissions_kgco2e"] == 565050


def test_circularity_endpoint_labels_internal_metric():
    response = client.get(f"/api/facilities/{FACILITY}/reporting-periods/{PERIOD}/circularity-score")
    assert response.status_code == 200
    body = response.json()
    assert body["is_internal_metric"] is True
    assert body["disclaimer"]


def test_simulate_endpoint():
    response = client.post(
        "/api/scenarios/0a1b2c3d-0011-4011-8011-0000000000ff/simulate",
        json={
            "interventions": [
                {"intervention_id": INTERVENTION, "adoption_percentage": "100"}
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assessment"]["baseline_emissions_kg"] is not None
    assert body["assessment"]["projected_emissions_kg"] is not None
    assert body["payback_status"] in {"AVAILABLE", "UNAVAILABLE", "INCOMPLETE"}


def test_unknown_intervention_returns_404():
    response = client.post(
        "/api/scenarios/0a1b2c3d-0011-4011-8011-0000000000ff/simulate",
        json={"interventions": [{"intervention_id": "00000000-0000-4000-8000-000000000000"}]},
    )
    assert response.status_code == 404
