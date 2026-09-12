"""Phase-3 fix regression tests (backend surface).

Covers:
- GA-02: stub auth refused outside development (explicit opt-in required)
- P1-04: 5xx responses carry CORS + security + X-Request-Id headers
- P1-05: N1 dashboard exposes unresolved_count
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

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402

F = "0a1b2c3d-0002-4002-8002-000000000002"
P = "0a1b2c3d-0003-4003-8003-000000000003"


def test_ga02_stub_refused_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "stub")
    monkeypatch.setenv("JWT_SECRET", "a-real-32byte-secret-for-tests-0001")
    monkeypatch.delenv("ALLOW_STUB_AUTH", raising=False)
    with pytest.raises(Exception) as exc:
        Settings()
    assert "stub" in str(exc.value)


def test_ga02_stub_allowed_with_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_MODE", "stub")
    monkeypatch.setenv("JWT_SECRET", "a-real-32byte-secret-for-tests-0001")
    monkeypatch.setenv("ALLOW_STUB_AUTH", "true")
    settings = Settings()
    assert settings.auth_mode == "stub" and settings.allow_stub_auth is True


def test_p1_04_5xx_carries_cors_and_request_id():
    from app.main import create_app

    app = create_app()

    @app.get("/api/_audit_boom")
    def _boom():  # pragma: no cover - deliberate
        raise RuntimeError("deliberate 500 for header regression test")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/api/_audit_boom", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.headers.get("x-request-id")
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_p1_05_n1_exposes_unresolved_count(client):
    body = client.get(f"/api/facilities/{F}/reporting-periods/{P}/dashboard").json()
    assert "unresolved_count" in body
    assert isinstance(body["unresolved_count"], int)
    assert body["unresolved_count"] >= 0
