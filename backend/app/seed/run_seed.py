"""Idempotent seeder.

1. Loads `mocks/mock_dataset.json` verbatim (frozen UUIDs used by P1/P3/P4).
2. Loads `real_factors.json` (source-cited GHG Protocol / CEA / IPCC factors).
3. Seeds master reference rows and computes a Carbon Data Quality Score per
   seeded activity record.

Run:  python -m app.seed.run_seed
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
import app.models as m
from app.services import quality

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MOCK_DATASET = REPO_ROOT / "mocks" / "mock_dataset.json"
REAL_FACTORS = Path(__file__).resolve().parent / "real_factors.json"


def _convert(col_type: Any, value: Any) -> Any:
    if value is None:
        return None
    from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, Uuid

    if isinstance(col_type, Uuid):
        return value if isinstance(value, UUID) else UUID(str(value))
    if isinstance(col_type, DateTime):
        return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if isinstance(col_type, Date):
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    if isinstance(col_type, Numeric):
        return Decimal(str(value))
    if isinstance(col_type, Integer):
        return int(value)
    if isinstance(col_type, Boolean):
        return bool(value)
    return value


def _build(model: Any, payload: dict[str, Any]) -> Any:
    kwargs = {}
    for column in model.__table__.columns:
        if column.name in payload:
            kwargs[column.name] = _convert(column.type, payload[column.name])
    return model(**kwargs)


def _add_if_absent(db: Session, model: Any, payload: dict[str, Any]) -> Any | None:
    pk = payload.get("id")
    if pk is not None:
        existing = db.get(model, _convert(model.__table__.columns["id"].type, pk))
        if existing is not None:
            return None
    obj = _build(model, payload)
    db.add(obj)
    return obj


def seed_mock_dataset(db: Session) -> None:
    data = json.loads(MOCK_DATASET.read_text(encoding="utf-8"))
    # Flush level by level: SQLAlchemy's unit of work orders inserts by ORM
    # relationship, and we intentionally define no relationships, so explicit
    # flushes guarantee parent rows exist before child rows (FK safety).
    _add_if_absent(db, m.Organization, data["organization"])
    db.flush()
    for row in data["facilities"]:
        _add_if_absent(db, m.Facility, row)
    db.flush()
    for row in data["reporting_periods"]:
        _add_if_absent(db, m.ReportingPeriod, row)
    db.flush()
    for row in data["processes"]:
        _add_if_absent(db, m.Process, row)
    db.flush()
    for row in data["emission_factors"]:
        _add_if_absent(db, m.EmissionFactor, row)
    db.flush()
    # Phase 2 remediation (BLOCKER 1): seed P4's full 19-entry library so K1's
    # simulator can resolve every intervention_id that live J2 emits (the
    # mock dataset only carried 5).
    from seed_interventions import full_intervention_rows

    for row in full_intervention_rows(data["circular_interventions"]):
        _add_if_absent(db, m.CircularIntervention, row)
    db.flush()
    for row in data["activity_data"]:
        _add_if_absent(db, m.ActivityData, row)
    db.flush()


def seed_real_factors(db: Session) -> int:
    added = 0
    for row in json.loads(REAL_FACTORS.read_text(encoding="utf-8")):
        existing = db.scalar(
            select(m.EmissionFactor).where(m.EmissionFactor.factor_code == row["factor_code"])
        )
        if existing is None:
            _add_if_absent(db, m.EmissionFactor, row)
            added += 1
    db.flush()
    return added


def seed_master_reference(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(m.EnergySource)) == 0:
        for name, category, renewable, unit in [
            ("Grid Electricity (India)", "Electricity", False, "kWh"),
            ("Natural Gas", "Fossil", False, "m3"),
            ("Diesel", "Fossil", False, "L"),
            ("LPG", "Fossil", False, "L"),
            ("Rooftop Solar PV", "Renewable", True, "kWh"),
        ]:
            db.add(m.EnergySource(name=name, category=category, renewable=renewable, standard_unit=unit))
    if db.scalar(select(func.count()).select_from(m.Material)) == 0:
        for name, category, unit, recyclable in [
            ("Cotton woven fabric (virgin greige)", "Textiles", "kg", True),
            ("LDPE packaging film (virgin)", "Packaging", "kg", True),
            ("Dyeing chemicals and auxiliaries", "Chemicals", "kg", False),
        ]:
            db.add(m.Material(name=name, category=category, standard_unit=unit, recyclable=recyclable))
    if db.scalar(select(func.count()).select_from(m.WasteType)) == 0:
        for name, category, hazardous, recyclable, unit in [
            ("Textile offcuts and trimmings", "Textile", False, True, "kg"),
            ("Treated effluent to CETP", "Wastewater", False, False, "m3"),
        ]:
            db.add(
                m.WasteType(
                    name=name,
                    category=category,
                    hazardous=hazardous,
                    recyclable=recyclable,
                    standard_unit=unit,
                )
            )
    db.flush()


def compute_data_quality(db: Session) -> int:
    activities = list(
        db.scalars(select(m.ActivityData).where(m.ActivityData.deleted_at.is_(None)))
    )
    for activity in activities:
        factor = quality.match_factor(db, activity)
        activity.carbon_data_quality_score = quality.score_activity_record(activity, factor)
    db.flush()
    return len(activities)


def run() -> dict[str, int]:
    if not MOCK_DATASET.exists():
        raise SystemExit(f"Missing frozen mock dataset: {MOCK_DATASET}")
    db = SessionLocal()
    try:
        seed_mock_dataset(db)
        added_factors = seed_real_factors(db)
        seed_master_reference(db)
        scored = compute_data_quality(db)
        db.commit()
        counts = {
            "organizations": db.scalar(select(func.count()).select_from(m.Organization)) or 0,
            "facilities": db.scalar(select(func.count()).select_from(m.Facility)) or 0,
            "processes": db.scalar(select(func.count()).select_from(m.Process)) or 0,
            "activity_data": db.scalar(select(func.count()).select_from(m.ActivityData)) or 0,
            "emission_factors": db.scalar(select(func.count()).select_from(m.EmissionFactor)) or 0,
            "circular_interventions": db.scalar(select(func.count()).select_from(m.CircularIntervention)) or 0,
            "real_factors_added": added_factors,
            "records_scored": scored,
        }
        return counts
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    result = run()
    print("Seed complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
