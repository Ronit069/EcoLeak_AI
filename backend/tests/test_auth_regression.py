"""T0-2 / T0-3 auth regression tests (permanent CI suite).

Red/green contract for the auth fixes:
- JWT mode: missing / malformed / expired Authorization header -> 401 in the
  frozen error shape; valid token -> success. NO fallthrough to stub headers.
- Stub mode: header-based auth still works as documented; wrong-org header is
  rejected by tenant guards.
- Engine/P4 surface: unauthenticated requests are 401; valid credentials
  succeed; wrong-tenant credentials are rejected (two-tenant test).
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import jwt as pyjwt  # noqa: E402
import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402

F = "0a1b2c3d-0002-4002-8002-000000000002"
P = "0a1b2c3d-0003-4003-8003-000000000003"
ORG = "0a1b2c3d-0001-4001-8001-000000000001"
FOREIGN_ORG = "11111111-2222-4333-8444-555555555555"
SECRET = "test-only-secret-not-for-production-0123456789"
FROZEN_KEYS = {"error_code", "message", "severity", "details"}


def _token_for(organization_id: str, role: str = "ORGANIZATION_ADMIN") -> str:
    return pyjwt.encode(
        {"sub": "00000000-0000-4000-8000-0000000000aa", "organization_id": organization_id, "role": role},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture()
def jwt_client(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    get_settings.cache_clear()
    yield client
    get_settings.cache_clear()


def test_jwt_mode_missing_header_is_401(jwt_client):
    r = jwt_client.post("/api/units/normalize", json={"value": 1, "from_unit": "kWh", "to_unit": "MWh"})
    assert r.status_code == 401
    assert set(r.json().keys()) == FROZEN_KEYS
    assert r.json()["error_code"] == "UNAUTHORIZED"


def test_jwt_mode_malformed_token_is_401(jwt_client):
    r = jwt_client.post(
        "/api/units/normalize",
        json={"value": 1, "from_unit": "kWh", "to_unit": "MWh"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401
    assert r.json()["error_code"] == "UNAUTHORIZED"


def test_jwt_mode_non_bearer_scheme_is_401(jwt_client):
    r = jwt_client.post(
        "/api/units/normalize",
        json={"value": 1, "from_unit": "kWh", "to_unit": "MWh"},
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert r.status_code == 401


def test_jwt_mode_expired_token_is_401(jwt_client):
    expired = pyjwt.encode(
        {
            "sub": "00000000-0000-4000-8000-0000000000aa",
            "organization_id": ORG,
            "role": "ORGANIZATION_ADMIN",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=30),
        },
        SECRET,
        algorithm="HS256",
    )
    r = jwt_client.post(
        "/api/units/normalize",
        json={"value": 1, "from_unit": "kWh", "to_unit": "MWh"},
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 401
    assert r.json()["error_code"] == "UNAUTHORIZED"


def test_jwt_mode_valid_token_succeeds(jwt_client):
    r = jwt_client.post(
        "/api/units/normalize",
        json={"value": 1, "from_unit": "kWh", "to_unit": "MWh"},
        headers={"Authorization": f"Bearer {_token_for(ORG, 'SUSTAINABILITY_ANALYST')}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["normalized_value"] == 1000.0
    assert body["normalized_unit"] == "kWh"


def test_jwt_mode_engine_surface_requires_token(jwt_client):
    r = jwt_client.get("/api/context")
    assert r.status_code == 401
    assert r.json()["error_code"] == "UNAUTHORIZED"
    r2 = jwt_client.get(f"/api/facilities/{F}/reporting-periods/{P}/hotspots")
    assert r2.status_code == 401


def test_stub_mode_headers_still_work(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "stub")
    get_settings.cache_clear()
    r = client.get(f"/api/facilities/{F}/reporting-periods/{P}/hotspots")
    assert r.status_code == 200, r.text


def test_two_tenant_isolation_jwt(client, monkeypatch):
    _token_for(ORG)
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    get_settings.cache_clear()
    other_org = str(uuid.uuid4())
    own = client.get(
        f"/api/facilities/{F}/reporting-periods/{P}/hotspots",
        headers={"Authorization": f"Bearer {_token_for(ORG)}"},
    )
    assert own.status_code == 200, own.text
    assert own.json()["facility_id"] == F
    foreign = client.get(
        f"/api/facilities/{F}/reporting-periods/{P}/hotspots",
        headers={"Authorization": f"Bearer {_token_for(other_org)}"},
    )
    assert foreign.status_code == 403
    assert foreign.json()["error_code"] == "FORBIDDEN"


def test_two_tenant_isolation_stub_headers(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "stub")
    get_settings.cache_clear()
    own = client.get(
        f"/api/facilities/{F}/reporting-periods/{P}/hotspots",
        headers={"X-Organization-Id": ORG, "X-Role": "SUSTAINABILITY_ANALYST"},
    )
    assert own.status_code == 200, own.text
    foreign = client.get(
        f"/api/facilities/{F}/reporting-periods/{P}/hotspots",
        headers={"X-Organization-Id": "11111111-2222-4333-8444-555555555555", "X-Role": "SUSTAINABILITY_ANALYST"},
    )
    assert foreign.status_code == 403
    assert foreign.json()["error_code"] == "FORBIDDEN"
