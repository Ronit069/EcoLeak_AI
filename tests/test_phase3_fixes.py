"""Phase-3 fix regression tests (engine surface).

Covers:
- GA-04/P3-05: F1 POST calculations refuses a LOCKED period (409 frozen shape)
- GA-06/P3-01: the default mock dataset carries the full 19-entry library
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import engine.api as engine_api  # noqa: E402
from contracts.schemas import (  # noqa: E402
    Facility,
    PeriodType,
    ReportingPeriod,
    ReportingPeriodStatus,
)
from engine.data_source import InMemoryDataSource, load_mock_data_source  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402

client = TestClient(engine_api.app, raise_server_exceptions=False)


def _fixture(status: ReportingPeriodStatus):
    facility_id = uuid.uuid4()
    period_id = uuid.uuid4()
    facility = Facility(
        id=facility_id, organization_id=uuid.uuid4(), name="Ad-hoc",
        country="India", active=True,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    period = ReportingPeriod(
        id=period_id, facility_id=facility_id, period_type=PeriodType.ANNUAL,
        start_date=date(2025, 4, 1), end_date=date(2026, 3, 31),
        status=status, created_at=datetime.now(timezone.utc),
    )
    source = InMemoryDataSource(facilities=[facility], reporting_periods=[period])
    return EcoLeakEngine(data_source=source), facility_id, period_id


def test_ga04_locked_period_refuses_calculation(monkeypatch):
    engine, facility_id, period_id = _fixture(ReportingPeriodStatus.LOCKED)
    monkeypatch.setattr(engine_api, "_engine", engine)
    r = client.post(f"/api/facilities/{facility_id}/reporting-periods/{period_id}/calculations")
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["error_code"] == "PERIOD_LOCKED"
    assert set(body.keys()) == {"error_code", "message", "severity", "details"}


def test_ga04_draft_period_still_calculates(monkeypatch):
    engine, facility_id, period_id = _fixture(ReportingPeriodStatus.DRAFT)
    monkeypatch.setattr(engine_api, "_engine", engine)
    r = client.post(f"/api/facilities/{facility_id}/reporting-periods/{period_id}/calculations")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_ga06_mock_dataset_carries_full_library():
    data = json.loads((ROOT / "mocks" / "mock_dataset.json").read_text(encoding="utf-8"))
    assert len(data["circular_interventions"]) == 19
    assert len(load_mock_data_source().get_interventions()) == 19
