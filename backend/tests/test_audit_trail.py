"""Phase 2 audit check: real ingested data writes AuditLog rows."""
from __future__ import annotations

from app.models.audit import AuditLog
from app.seed.messy_dataset import build_messy_csv
from tests.factories import auth_headers, make_facility, make_org, make_period, make_process


def _setup(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    make_process(db, facility, name="Boiler", process_code="PRC-X")
    db.commit()
    return org, facility, period


def test_import_writes_batch_and_per_activity_audit(client, db):
    org, facility, period = _setup(db)
    body, expected, _ = build_messy_csv(scale=3)
    response = client.post(
        f"/api/facilities/{facility.id}/activity/import",
        files={"file": ("messy.csv", body.encode("utf-8"), "text/csv")},
        data={"reporting_period_id": str(period.id)},
        headers=auth_headers(org.id),
    )
    assert response.status_code == 202, response.text

    db.expire_all()
    batch_events = (
        db.query(AuditLog).filter(AuditLog.event_type == "FILE_IMPORT").all()
    )
    assert len(batch_events) == 1
    assert batch_events[0].organization_id == org.id
    assert batch_events[0].entity_type == "ingestion_batch"
    assert batch_events[0].new_value["accepted_rows"] == expected["accepted"]

    imported = (
        db.query(AuditLog).filter(AuditLog.event_type == "ACTIVITY_IMPORTED").all()
    )
    assert len(imported) == expected["accepted"]
    assert all(row.organization_id == org.id for row in imported)
    assert all(row.entity_type == "activity_data" for row in imported)
    assert all(row.entity_id is not None for row in imported)


def test_manual_activity_writes_audit(client, db):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    response = client.post(
        f"/api/facilities/{facility.id}/activity",
        json={
            "reporting_period_id": str(period.id),
            "activity_category": "FUEL",
            "activity_subcategory": "Diesel - generator",
            "original_value": "100",
            "original_unit": "L",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    activity_id = response.json()["id"]

    db.expire_all()
    created = (
        db.query(AuditLog).filter(AuditLog.event_type == "ACTIVITY_CREATED").all()
    )
    assert len(created) == 1
    assert str(created[0].entity_id) == activity_id
    assert created[0].organization_id == org.id
