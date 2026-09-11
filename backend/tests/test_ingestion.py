"""Module C/D ingestion tests: validation, normalization, duplicates, warnings."""
from __future__ import annotations

from app.models.activity import ActivityData
from tests.factories import auth_headers, make_facility, make_org, make_period, make_process

CSV_HEADER = (
    "process_code,activity_category,activity_subcategory,original_value,original_unit,"
    "source_name,data_source_type,measured_or_estimated,confidence_score\n"
)
CSV_BODY = CSV_HEADER + (
    "PRC-X,FUEL,Diesel - generator,12000,L,Fuel register,CSV,MEASURED,90\n"
    "PRC-X,ELECTRICITY,Negative test,-5,kWh,Bad,CSV,MEASURED,80\n"
    "PRC-X,FUEL,Unknown unit,10,furlong,Bad,CSV,MEASURED,80\n"
    "PRC-X,ELECTRICITY,Implausible load,90000000,kWh,Main meter,CSV,MEASURED,88\n"
    "PRC-X,FUEL,Diesel - generator,12000,L,Fuel register,CSV,MEASURED,90\n"
    "PRC-X,WATER,Missing unit,10,,Meter,CSV,MEASURED,80\n"
)


def _setup(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    make_process(db, facility, name="Boiler", process_code="PRC-X")
    db.commit()
    return org, facility, period


def _post_import(client, headers, facility, period, body=CSV_BODY, dry_run=False):
    files = {"file": ("activity.csv", body.encode("utf-8"), "text/csv")}
    data = {"reporting_period_id": str(period.id)}
    if dry_run:
        data["dry_run"] = "true"
    return client.post(
        f"/api/facilities/{facility.id}/activity/import",
        files=files,
        data=data,
        headers=headers,
    )


def test_import_validates_and_normalizes(client, db):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    response = _post_import(client, headers, facility, period)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "PARTIAL", job
    codes = {issue["code"] for issue in job["row_issues"]}
    assert "NEGATIVE_VALUE" in codes
    assert "INVALID_UNIT" in codes
    assert "DUPLICATE_IN_FILE" in codes
    assert "MISSING_VALUE" in codes
    assert "IMPLAUSIBLE_MAGNITUDE" in codes

    activities = (
        client.get(f"/api/facilities/{facility.id}/activity", headers=headers).json()
    )
    assert len(activities) == 2
    diesel = next(a for a in activities if a["activity_subcategory"].startswith("Diesel"))
    assert diesel["original_unit"] == "L"
    assert diesel["original_value"] == "12000.000000"
    assert diesel["normalized_unit"] == "L"
    # Implausible magnitude is imported, not silently dropped.
    assert any(a["activity_category"] == "ELECTRICITY" for a in activities)


def test_duplicate_upload_is_rejected(client, db):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    assert _post_import(client, headers, facility, period).status_code == 202
    second = _post_import(client, headers, facility, period)
    assert second.status_code == 409
    assert second.json()["error_code"] == "DUPLICATE_IMPORT"


def test_dry_run_does_not_persist(client, db):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    body = CSV_HEADER + "PRC-X,FUEL,Only row,100,L,Reg,CSV,MEASURED,80\n"
    response = _post_import(client, headers, facility, period, body=body, dry_run=True)
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "DRY_RUN"
    activities = client.get(f"/api/facilities/{facility.id}/activity", headers=headers).json()
    assert activities == []


def test_missing_mandatory_columns_is_rejected(client, db):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    body = "foo,bar\n1,2\n"
    response = _post_import(client, headers, facility, period, body=body)
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "FAILED"
    assert any(i["code"] == "FILE_VALIDATION_ERROR" for i in job["row_issues"])


def test_ill_formed_file_is_rejected(client, db):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    files = {"file": ("bad.xlsx", b"not really an excel file", "application/octet-stream")}
    data = {"reporting_period_id": str(period.id)}
    response = client.post(
        f"/api/facilities/{facility.id}/activity/import",
        files=files,
        data=data,
        headers=headers,
    )
    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
