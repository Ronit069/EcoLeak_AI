"""Pytest fixtures: isolated PostgreSQL test database (ecoleak_test)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV = BACKEND_DIR / ".env"


def _read_env(key: str) -> str | None:
    if not _ENV.exists():
        return None
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


# Must happen before importing app modules (engine is created at import time).
_test_url = _read_env("TEST_DATABASE_URL")
if _test_url:
    os.environ["DATABASE_URL"] = _test_url
os.environ.setdefault("AUTH_MODE", "stub")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000000")
os.environ.setdefault("UPLOAD_RATE_LIMIT_PER_MINUTE", "1000000")
os.environ.setdefault("MAX_UPLOAD_BYTES", "10485760")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    assert engine.url.database == "ecoleak_test", (
        f"Tests must run against ecoleak_test, got {engine.url.database}"
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    from app.services.ratelimit import reset_rate_limits

    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    reset_rate_limits()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def auth_headers(organization_id, role: str = "SYSTEM_ADMIN") -> dict:
    return {"X-Organization-Id": str(organization_id), "X-Role": role}
