"""B2 acceptance: P3 engine runs against a SQL-backed data source.

Seeds a portable SQLite image of P2's tables (same table/column names) from
``mocks/mock_dataset.json``, then runs the full engine (inventory, hotspots)
through :class:`SQLActivityDataSource` and proves the aggregations reconcile
exactly as in the mock-source suite, plus identical cross-check with
``test_aggregations_by_scope_process_source_category`` semantics.

Run:  python -m pytest tests/test_sql_source.py -q
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from engine.data_source import load_mock_data_source  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402
from engine.sql_source import SQLActivityDataSource, create_sql_schema  # noqa: E402

MOCKS = ROOT / "mocks" / "mock_dataset.json"


def _dt(value):
    """ISO-8601 (+05:30 / Z) -> datetime for SQLite DateTime columns."""
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _seed(engine, factors=None) -> None:
    """Seed a portable SQLite image of the P2 tables.

    ``factors`` defaults to the mock dataset factors; pass a list of factor dicts
    (e.g. P2's ``backend/app/seed/real_factors.json``) for a real-data run.
    """
    create_sql_schema(engine)
    data = json.loads(MOCKS.read_text(encoding="utf-8"))
    with engine.begin() as conn:
        org = data["organization"]
        fac = data["facilities"][0]
        period = data["reporting_periods"][0]
        conn.execute(
            "organizations".join([]) if False else
            __import__("engine.sql_source", fromlist=["organizations"]).organizations.insert(),
            [
                {
                    "id": UUID(org["id"]), "name": org["name"], "industry_sector": org["industry_sector"],
                    "industry_subtype": org["industry_subtype"], "country": org["country"],
                    "state": org["state"], "city": org["city"], "currency_code": org["currency_code"],
                    "organization_size": org["organization_size"],
                    "created_at": _dt(org["created_at"]), "updated_at": _dt(org["updated_at"]),
                }
            ],
        )
        conn.execute(
            __import__("engine.sql_source", fromlist=["facilities"]).facilities.insert(),
            [{
                "id": UUID(fac["id"]), "organization_id": UUID(fac["organization_id"]),
                "name": fac["name"], "facility_code": fac["facility_code"], "country": fac["country"],
                "state": fac["state"], "city": fac["city"], "latitude": fac["latitude"],
                "longitude": fac["longitude"], "annual_production": fac["annual_production"],
                "production_unit": fac["production_unit"],
                "working_days_per_year": fac["working_days_per_year"],
                "working_hours_per_day": fac["working_hours_per_day"],
                "active": fac["active"], "created_at": _dt(fac["created_at"]),
                "updated_at": _dt(fac["updated_at"]),
            }],
        )
        conn.execute(
            __import__("engine.sql_source", fromlist=["reporting_periods"]).reporting_periods.insert(),
            [{
                "id": UUID(period["id"]), "facility_id": UUID(period["facility_id"]),
                "period_type": period["period_type"], "start_date": period["start_date"],
                "end_date": period["end_date"], "status": period["status"],
                "created_at": _dt(period["created_at"]),
            }],
        )
        for p in data["processes"]:
            conn.execute(
                __import__("engine.sql_source", fromlist=["processes"]).processes.insert(),
                [{
                    "id": UUID(p["id"]), "facility_id": UUID(p["facility_id"]), "name": p["name"],
                    "process_code": p["process_code"], "sequence_no": p["sequence_no"],
                    "description": p["description"], "process_category": p["process_category"],
                    "active": p["active"], "created_at": _dt(p["created_at"]),
                }],
            )
        for a in data["activity_data"]:
            conn.execute(
                __import__("engine.sql_source", fromlist=["activity_data"]).activity_data.insert(),
                [{
                    "id": UUID(a["id"]), "facility_id": UUID(a["facility_id"]),
                    "process_id": UUID(a["process_id"]) if a["process_id"] else None,
                    "asset_id": UUID(a["asset_id"]) if a["asset_id"] else None,
                    "reporting_period_id": UUID(a["reporting_period_id"]),
                    "activity_category": a["activity_category"], "activity_subcategory": a["activity_subcategory"],
                    "source_name": a["source_name"], "original_value": a["original_value"],
                    "original_unit": a["original_unit"], "normalized_value": a["normalized_value"],
                    "normalized_unit": a["normalized_unit"], "data_source_type": a["data_source_type"],
                    "measured_or_estimated": a["measured_or_estimated"],
                    "confidence_score": a["confidence_score"], "notes": a["notes"],
                    "created_at": _dt(a["created_at"]),
                }],
            )
        for f in (factors if factors is not None else data["emission_factors"]):
            row = {
                k: (UUID(v) if k == "id" else _dt(v) if k == "created_at" else v)
                for k, v in f.items()
                if k not in ("supplier_id", "supplier_specific")
            }
            row.setdefault("created_at", _dt("2026-01-01T00:00:00+00:00"))
            conn.execute(
                __import__("engine.sql_source", fromlist=["emission_factors"]).emission_factors.insert(), [row],
            )
        for iv in data["circular_interventions"]:
            row = {k: (UUID(v) if k == "id" else v) for k, v in iv.items()}
            conn.execute(
                __import__("engine.sql_source", fromlist=["circular_interventions"]).circular_interventions.insert(),
                [row],
            )


FID = "0a1b2c3d-0002-4002-8002-000000000002"
PID = "0a1b2c3d-0003-4003-8003-000000000003"


def _make_engine(tmp_path) -> tuple[EcoLeakEngine, str]:
    db_path = tmp_path / "ecoleak_seed.db"
    sql_engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    _seed(sql_engine)
    dsn = f"sqlite+pysqlite:///{db_path}"
    return EcoLeakEngine(data_source=SQLActivityDataSource(sql_engine)), dsn


def test_sql_source_reproduces_fixture_totals(tmp_path) -> None:
    engine, _ = _make_engine(tmp_path)
    inv = engine.calculate_inventory(FID, PID)
    assert inv.scope1_kgco2e == Decimal("224250")
    assert inv.scope2_kgco2e == Decimal("340800")
    assert inv.operational_kgco2e == Decimal("565050")
    # Operational boundary (Scope 1+2) is 565,050; ALL scopes incl. Scope 3
    # materials/water/waste/transport total 7,202,350 — same as the mock run.
    assert inv.total_kgco2e == Decimal("7202350")
    assert len(inv.records) == 13
    # Same unresolved set as the mock run: dyeing chemicals (MATERIAL, no
    # matching factor) and wastewater (WATER, no matching factor). The engine
    # never fabricates values for either source.
    mock_inv = EcoLeakEngine(data_source=load_mock_data_source()).calculate_inventory(FID, PID)
    assert {u.activity_id for u in inv.unresolved} == {u.activity_id for u in mock_inv.unresolved}
    assert {u.code for u in inv.unresolved} == {u.code for u in mock_inv.unresolved}


def test_sql_source_aggregations_reconcile(tmp_path) -> None:
    engine, _ = _make_engine(tmp_path)
    inv = engine.calculate_inventory(FID, PID)
    # facility/scope/process/source/period sums all reconcile (B2 acceptance).
    by_process = inv.by_process()
    assert sum(by_process.values(), Decimal("0")) == inv.total_kgco2e
    by_source = inv.by_source()
    assert sum(by_source.values(), Decimal("0")) == inv.total_kgco2e
    assert inv.scope1_kgco2e + inv.scope2_kgco2e + inv.scope3_kgco2e == inv.total_kgco2e


def test_sql_source_matches_mock_source_results(tmp_path) -> None:
    sql_engine, _ = _make_engine(tmp_path)
    sql_inv = EcoLeakEngine(data_source=SQLActivityDataSource(sql_engine.data_source.engine)).calculate_inventory(FID, PID)
    mock_inv = EcoLeakEngine(data_source=load_mock_data_source()).calculate_inventory(FID, PID)
    assert sql_inv.total_kgco2e == mock_inv.total_kgco2e
    assert sql_inv.scope1_kgco2e == mock_inv.scope1_kgco2e
    assert sql_inv.scope2_kgco2e == mock_inv.scope2_kgco2e
    assert {h.id for h in _hotspots(sql_engine.data_source.engine).hotspots} == {h.id for h in _hotspots(None).hotspots}


def _hotspots(sql_engine):
    src = SQLActivityDataSource(sql_engine) if sql_engine is not None else load_mock_data_source()
    return EcoLeakEngine(data_source=src).hotspot_result(FID, PID)


def test_sql_source_hotspots_reconcile(tmp_path) -> None:
    result = _hotspots(_make_engine(tmp_path)[0].data_source.engine)
    contrib = sum(h.contribution_percent or Decimal("0") for h in result.hotspots)
    assert abs(contrib - Decimal("100")) < Decimal("0.01")
    assert result.hotspots[0].process_name == "Boiler"
    assert len(result.hotspots) == 5


def test_default_data_source_env_gated(tmp_path, monkeypatch) -> None:
    from engine.data_source import default_data_source

    monkeypatch.delenv("ECOLEAK_SQL_DSN", raising=False)
    assert type(default_data_source()).__name__ == "MockDataSource"

    db_path = tmp_path / "env.db"
    sql_engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    _seed(sql_engine)
    monkeypatch.setenv("ECOLEAK_SQL_DSN", f"sqlite+pysqlite:///{db_path}")
    assert type(default_data_source()).__name__ == "SQLActivityDataSource"