"""Test data factories (explicit flushes satisfy FK ordering)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.core import Facility, Organization, ReportingPeriod
from app.models.process import Process


def auth_headers(organization_id, role: str = "SYSTEM_ADMIN") -> dict:
    return {"X-Organization-Id": str(organization_id), "X-Role": role}


def make_org(db: Session, **overrides) -> Organization:
    data = dict(
        name=f"Org {uuid.uuid4().hex[:6]}",
        industry_sector="Textile",
        country="India",
        state="Gujarat",
        city="Surat",
        currency_code="INR",
        organization_size="MEDIUM",
    )
    data.update(overrides)
    org = Organization(**data)
    db.add(org)
    db.flush()
    return org


def make_facility(db: Session, org: Organization, **overrides) -> Facility:
    data = dict(
        organization_id=org.id,
        name=f"Facility {uuid.uuid4().hex[:6]}",
        facility_code=f"FAC-{uuid.uuid4().hex[:6]}",
        country="India",
        state="Gujarat",
        annual_production=Decimal("1000"),
        production_unit="tonne",
        working_days_per_year=300,
        working_hours_per_day=Decimal("16"),
    )
    data.update(overrides)
    facility = Facility(**data)
    db.add(facility)
    db.flush()
    return facility


def make_period(db: Session, facility: Facility, **overrides) -> ReportingPeriod:
    data = dict(
        facility_id=facility.id,
        period_type="ANNUAL",
        start_date=date(2025, 4, 1),
        end_date=date(2026, 3, 31),
        status="DRAFT",
        created_at=utcnow(),
    )
    data.update(overrides)
    period = ReportingPeriod(**data)
    db.add(period)
    db.flush()
    return period


def make_process(db: Session, facility: Facility, **overrides) -> Process:
    data = dict(
        facility_id=facility.id,
        name=f"Process {uuid.uuid4().hex[:6]}",
        process_code=f"PRC-{uuid.uuid4().hex[:6]}",
        sequence_no=1,
        process_category="Utilities",
        created_at=utcnow(),
    )
    data.update(overrides)
    process = Process(**data)
    db.add(process)
    db.flush()
    return process
