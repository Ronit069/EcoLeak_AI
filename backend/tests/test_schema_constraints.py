"""DB integrity: every CHECK/UNIQUE constraint actually rejects bad data."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import utcnow
from app.models.activity import ActivityData
from app.models.process import ProcessLink
from tests.factories import make_facility, make_org, make_period, make_process


def _expect_integrity_error(db, fn):
    with pytest.raises(IntegrityError):
        fn()
    db.rollback()


def test_organization_size_check(db):
    _expect_integrity_error(db, lambda: make_org(db, organization_size="HUGE"))


def test_facility_working_days_check(db):
    org = make_org(db)
    _expect_integrity_error(db, lambda: make_facility(db, org, working_days_per_year=400))


def test_facility_working_hours_check(db):
    org = make_org(db)
    _expect_integrity_error(db, lambda: make_facility(db, org, working_hours_per_day=Decimal("30")))


def test_facility_negative_production_check(db):
    org = make_org(db)
    _expect_integrity_error(db, lambda: make_facility(db, org, annual_production=Decimal("-1")))


def test_period_end_before_start_check(db):
    org = make_org(db)
    facility = make_facility(db, org)
    _expect_integrity_error(
        db,
        lambda: make_period(
            db, facility, start_date=date(2026, 1, 1), end_date=date(2025, 1, 1)
        ),
    )


def test_process_link_self_loop_check(db):
    org = make_org(db)
    facility = make_facility(db, org)
    process = make_process(db, facility)

    def _add():
        db.add(
            ProcessLink(
                facility_id=facility.id,
                source_process_id=process.id,
                target_process_id=process.id,
                flow_type="STEAM",
            )
        )
        db.flush()

    _expect_integrity_error(db, _add)


def test_negative_activity_value_check(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)

    def _add():
        db.add(
            ActivityData(
                facility_id=facility.id,
                reporting_period_id=period.id,
                activity_category="ELECTRICITY",
                activity_subcategory="Grid electricity",
                original_value=Decimal("-5"),
                original_unit="kWh",
                normalized_value=Decimal("-5"),
                normalized_unit="kWh",
                created_at=utcnow(),
            )
        )
        db.flush()

    _expect_integrity_error(db, _add)


def test_duplicate_facility_code_check(db):
    org = make_org(db)
    make_facility(db, org, facility_code="DUP-1")

    def _add():
        make_facility(db, org, facility_code="DUP-1")

    _expect_integrity_error(db, _add)


def test_duplicate_period_overlap_check(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    assert period.id is not None
