"""Cross-cutting API tests: auth, tenant isolation, reports, locks, duplicates."""
from __future__ import annotations

from tests.factories import (
    auth_headers,
    make_facility,
    make_org,
    make_period,
    make_process,
)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_credentials_are_forbidden(client, db):
    org = make_org(db)
    facility = make_facility(db, org)
    db.commit()
    response = client.get(f"/api/facilities/{facility.id}")
    assert response.status_code == 403


def test_tenant_isolation(client, db):
    org_a = make_org(db)
    org_b = make_org(db)
    facility = make_facility(db, org_a)
    db.commit()
    headers_b = auth_headers(org_b.id, "ORGANIZATION_ADMIN")
    headers_a = auth_headers(org_a.id, "ORGANIZATION_ADMIN")

    forbidden = client.get(f"/api/facilities/{facility.id}", headers=headers_b)
    assert forbidden.status_code == 403

    organization = client.get(f"/api/organizations/{org_a.id}", headers=headers_b)
    assert organization.status_code == 403

    allowed = client.get(f"/api/facilities/{facility.id}", headers=headers_a)
    assert allowed.status_code == 200


def test_read_only_role_can_read_but_not_write(client, db):
    org = make_org(db)
    facility = make_facility(db, org)
    make_period(db, facility)
    make_process(db, facility)
    db.commit()
    headers = auth_headers(org.id, "VIEWER")

    assert client.get(f"/api/facilities/{facility.id}", headers=headers).status_code == 200
    create = client.post(
        "/api/facilities/{}/processes".format(facility.id),
        json={"name": "New"},
        headers=headers,
    )
    assert create.status_code == 403


def test_duplicate_activity_endpoint(client, db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    db.commit()
    headers = auth_headers(org.id)
    payload = {
        "reporting_period_id": str(period.id),
        "activity_category": "FUEL",
        "activity_subcategory": "Diesel - generator",
        "original_value": "100",
        "original_unit": "L",
    }
    first = client.post(f"/api/facilities/{facility.id}/activity", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/facilities/{facility.id}/activity", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["error_code"] == "DUPLICATE_ACTIVITY"


def test_locked_period_blocks_writes(client, db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility, status="LOCKED")
    db.commit()
    headers = auth_headers(org.id)
    response = client.post(
        f"/api/facilities/{facility.id}/activity",
        json={
            "reporting_period_id": str(period.id),
            "activity_category": "FUEL",
            "activity_subcategory": "Diesel",
            "original_value": "1",
            "original_unit": "L",
        },
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "PERIOD_LOCKED"


def test_data_quality_endpoint(client, db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    db.commit()
    headers = auth_headers(org.id)
    client.post(
        f"/api/facilities/{facility.id}/activity",
        json={
            "reporting_period_id": str(period.id),
            "activity_category": "ELECTRICITY",
            "activity_subcategory": "Purchased grid electricity",
            "original_value": "1000",
            "original_unit": "kWh",
        },
        headers=headers,
    )
    response = client.get(
        f"/api/facilities/{facility.id}/reporting-periods/{period.id}/data-quality",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= float(body["total_score"]) <= 100
    assert "issues" in body


def test_report_flow_and_pdf_stub(client, db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    db.commit()
    headers = auth_headers(org.id)

    created = client.post(
        f"/api/facilities/{facility.id}/reporting-periods/{period.id}/reports",
        json={"template_version": "v1", "include_scope3": True},
        headers=headers,
    )
    assert created.status_code == 202, created.text
    receipt = created.json()
    assert receipt["report_hash"]
    report_id = receipt["report_id"]

    fetched = client.get(f"/api/reports/{report_id}", headers=headers)
    assert fetched.status_code == 200
    payload = fetched.json()["payload"]
    assert set(
        ["report_meta", "profile", "boundary", "factor_provenance", "scope_summary", "hotspot_analysis"]
    ).issubset(payload.keys())

    pdf = client.get(f"/api/reports/{report_id}/export?format=pdf", headers=headers)
    assert pdf.status_code == 501
    assert pdf.json()["error_code"] == "PDF_EXPORT_NOT_IMPLEMENTED"

    csv_export = client.get(f"/api/reports/{report_id}/export?format=csv", headers=headers)
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]


def test_report_is_tenant_scoped(client, db):
    org_a = make_org(db)
    org_b = make_org(db)
    facility = make_facility(db, org_a)
    period = make_period(db, facility)
    db.commit()

    created = client.post(
        f"/api/facilities/{facility.id}/reporting-periods/{period.id}/reports",
        json={"template_version": "v1"},
        headers=auth_headers(org_a.id, "ORGANIZATION_ADMIN"),
    )
    report_id = created.json()["report_id"]
    other = client.get(
        f"/api/reports/{report_id}", headers=auth_headers(org_b.id, "ORGANIZATION_ADMIN")
    )
    assert other.status_code == 404
