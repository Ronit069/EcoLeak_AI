"""Contract parity: serializers must emit exactly the frozen field names."""
from __future__ import annotations

from app.contracts_compat import schemas as C
from app.db import utcnow
from app.schemas.serialize import (
    activity_to_dict,
    facility_to_dict,
    intervention_to_dict,
    organization_to_dict,
    period_to_dict,
    process_to_dict,
)
from app.services.factors import factor_to_dict
from tests.factories import make_facility, make_org, make_period, make_process


def _check(serialized: dict, model) -> None:
    assert set(serialized.keys()) == set(model.model_fields.keys())


def test_organization_parity(db):
    org = make_org(db)
    _check(organization_to_dict(org), C.Organization)


def test_facility_parity(db):
    org = make_org(db)
    _check(facility_to_dict(make_facility(db, org)), C.Facility)


def test_reporting_period_parity(db):
    org = make_org(db)
    facility = make_facility(db, org)
    _check(period_to_dict(make_period(db, facility)), C.ReportingPeriod)


def test_process_parity(db):
    org = make_org(db)
    facility = make_facility(db, org)
    _check(process_to_dict(make_process(db, facility)), C.Process)


def test_activity_parity(db):
    from app.models.activity import ActivityData

    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    activity = ActivityData(
        facility_id=facility.id,
        reporting_period_id=period.id,
        activity_category="ELECTRICITY",
        activity_subcategory="Purchased grid electricity",
        original_value=1,
        original_unit="kWh",
        normalized_value=1,
        normalized_unit="kWh",
        created_at=utcnow(),
    )
    db.add(activity)
    db.flush()
    _check(activity_to_dict(activity), C.ActivityData)


def test_intervention_parity(db):
    from app.models.intervention import CircularIntervention

    intervention = CircularIntervention(
        intervention_code="INT-TEST-1", title="Test intervention"
    )
    db.add(intervention)
    db.flush()
    _check(intervention_to_dict(intervention), C.CircularIntervention)


def test_emission_factor_parity(db):
    from app.models.factor import EmissionFactor

    factor = EmissionFactor(
        factor_code="EF-TEST-1",
        category="FUEL",
        subcategory="Diesel",
        item_name="Diesel",
        scope="SCOPE_1",
        input_unit="L",
        total_co2e_factor=2.68,
        source_name="Test",
        source_year=2023,
        version="1",
    )
    db.add(factor)
    db.flush()
    _check(factor_to_dict(factor), C.EmissionFactor)
