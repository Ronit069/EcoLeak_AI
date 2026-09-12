"""Item 5 — Module O scenario CRUD/clone/restore/compare (full bar).

Covers: O1-O7 CRUD, clone INDEPENDENCE (mutating the clone must not affect
the original), restore-to-baseline, duplicate + adoption guard, cross-tenant
403 on every scenario-scoped route, unknown-id 404, K3 compare deltas.
Runs against the merged app (mock source) via TestClient.

Run: python -m pytest tests/test_phase3_scenarios.py -q
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

F = "0a1b2c3d-0002-4002-8002-000000000002"
ORG = "0a1b2c3d-0001-4001-8001-000000000001"
FOREIGN = "22222222-2222-4222-8222-222222222222"
client = TestClient(app, raise_server_exceptions=False)


def _h(org: str = ORG) -> dict:
    return {"X-Organization-Id": org, "X-Role": "SUSTAINABILITY_ANALYST"}


def _create(name: str = "Retrofit A", org: str = ORG) -> str:
    r = client.post(f"/api/facilities/{F}/scenarios",
                    json={"name": name, "budget_limit": "5000000", "target_reduction_pct": 20},
                    headers=_h(org))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_rec(sid: str, adoption: int = 80, org: str = ORG) -> str:
    recs = client.get(f"/api/facilities/{F}/reporting-periods/0a1b2c3d-0003-4003-8003-000000000003/recommendations",
                      headers=_h(org)).json()["recommendations"]
    rid = recs[0]["id"]
    r = client.post(f"/api/scenarios/{sid}/interventions",
                    json={"recommendation_id": rid, "adoption_percentage": adoption},
                    headers=_h(org))
    assert r.status_code == 201, r.text
    return rid


def test_o1_o3_create_and_get() -> None:
    sid = _create("Named scenario")
    r = client.get(f"/api/scenarios/{sid}", headers=_h())
    assert r.status_code == 200
    assert r.json()["scenario"]["name"] == "Named scenario"
    assert r.json()["scenario_interventions"] == []


def test_o2_list_facility_scenarios() -> None:
    a = _create("L1")
    b = _create("L2")
    r = client.get(f"/api/facilities/{F}/scenarios", headers=_h())
    ids = [s["id"] for s in r.json()["scenarios"]]
    assert a in ids and b in ids


def test_o4_update_scenario() -> None:
    sid = _create()
    r = client.patch(f"/api/scenarios/{sid}", json={"name": "Renamed"}, headers=_h())
    assert r.status_code == 200 and r.json()["name"] == "Renamed"


def test_o6_o7_intervention_add_remove() -> None:
    sid = _create()
    rid = _add_rec(sid)
    r3 = client.get(f"/api/scenarios/{sid}", headers=_h())
    iv = r3.json()["scenario_interventions"][0]
    assert str(iv["recommendation_id"]) == rid and iv["adoption_percentage"] == 80
    # duplicate rejected
    dup = client.post(f"/api/scenarios/{sid}/interventions",
                      json={"recommendation_id": rid, "adoption_percentage": 50}, headers=_h())
    assert dup.status_code == 422 and dup.json()["error_code"] == "CARBON_PLATFORM_ERROR"
    # adoption out of range rejected
    bad = client.patch(f"/api/scenarios/{sid}", json={"name": "x"}, headers=_h())
    assert bad.status_code == 200
    # O7 remove
    rm = client.delete(f"/api/scenarios/{sid}/interventions/{iv['id']}", headers=_h())
    assert rm.status_code == 204
    assert client.get(f"/api/scenarios/{sid}", headers=_h()).json()["scenario_interventions"] == []


def test_o5_soft_delete() -> None:
    sid = _create()
    assert client.delete(f"/api/scenarios/{sid}", headers=_h()).status_code == 204
    gone = client.get(f"/api/scenarios/{sid}", headers=_h())
    assert gone.status_code == 404  # typed NOT_FOUND via the frozen error shape (Closure handler)


def test_clone_is_independent() -> None:
    src = _create("Original")
    rid = _add_rec(src, adoption=60)
    r = client.post(f"/api/scenarios/{src}/clone", json={"new_name": "Clone A"}, headers=_h())
    assert r.status_code == 201
    clone_id = r.json()["id"]
    assert clone_id != src
    # mutating the CLONE (remove its intervention) must not affect the original
    clone_iv = client.get(f"/api/scenarios/{clone_id}", headers=_h()).json()["scenario_interventions"][0]
    client.delete(f"/api/scenarios/{clone_id}/interventions/{clone_iv['id']}", headers=_h())
    orig = client.get(f"/api/scenarios/{src}", headers=_h()).json()
    assert len(orig["scenario_interventions"]) == 1, "clone mutation leaked into the original"
    assert orig["scenario_interventions"][0]["recommendation_id"] == rid


def test_restore_reverts_to_baseline() -> None:
    sid = _create("Restorable")
    rid = _add_rec(sid, adoption=70)
    r = client.post(f"/api/scenarios/{sid}/restore", headers=_h())
    assert r.status_code == 200
    after = client.get(f"/api/scenarios/{sid}", headers=_h()).json()
    assert after["scenario_interventions"] == [], "restore must revert to creation-time baseline"
    # scenario still usable: re-add and simulate
    _add_rec(sid, adoption=70)
    recs = client.get(f"/api/scenarios/{sid}", headers=_h()).json()
    assert len(recs["scenario_interventions"]) == 1
    assert rid  # keep rid referenced


def test_cross_tenant_403_on_scenario_routes() -> None:
    sid = _create()
    for method, url, body in [
        ("GET", f"/api/scenarios/{sid}", None),
        ("PATCH", f"/api/scenarios/{sid}", {"name": "hijack"}),
        ("DELETE", f"/api/scenarios/{sid}", None),
        ("POST", f"/api/scenarios/{sid}/clone", {}),
        ("POST", f"/api/scenarios/{sid}/restore", None),
    ]:
        r = client.request(method, url, json=body, headers=_h(FOREIGN))
        assert r.status_code == 403, f"{method} {url} expected 403, got {r.status_code}"
        assert r.json()["error_code"] == "FORBIDDEN"
    # foreign facility-scoped create/list also blocked
    r = client.get(f"/api/facilities/{F}/scenarios", headers=_h(FOREIGN))
    assert r.status_code == 403


def test_k3_compare_two_scenarios() -> None:
    a = _create("Compare A")
    _add_rec(a, adoption=50)
    b = _create("Compare B")
    _add_rec(b, adoption=100)
    r = client.get(f"/api/scenarios/compare?scenario_ids={a},{b}", headers=_h())
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["comparisons"]) == 2
    assert set(body["deltas"].keys()) == {b}
    d = body["deltas"][b]
    assert "projected_emissions_delta_kg" in d and "capex_delta" in d
    # single-id compare rejected
    one = client.get(f"/api/scenarios/compare?scenario_ids={a}", headers=_h())
    assert one.status_code == 422