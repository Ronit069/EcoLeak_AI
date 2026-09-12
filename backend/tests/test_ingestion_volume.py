"""Phase 2 volume check: ingestion + normalization severities at scale."""
from __future__ import annotations

from collections import Counter

from app.seed.messy_dataset import build_messy_csv
from tests.factories import auth_headers, make_facility, make_org, make_period, make_process


def _setup(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    make_process(db, facility, name="Boiler", process_code="PRC-X")
    db.commit()
    return org, facility, period


def _post_import(client, headers, facility, period, body):
    files = {"file": ("messy.csv", body.encode("utf-8"), "text/csv")}
    data = {"reporting_period_id": str(period.id)}
    return client.post(
        f"/api/facilities/{facility.id}/activity/import",
        files=files,
        data=data,
        headers=headers,
    )


def test_messy_volume_severity_mix(client, db):
    org, facility, period = _setup(db)
    body, expected, wrong_period = build_messy_csv(scale=12)
    response = _post_import(client, auth_headers(org.id), facility, period, body)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "PARTIAL", job

    severities = Counter(i["severity"] for i in job["row_issues"])
    codes = Counter(i["code"] for i in job["row_issues"])

    assert severities["ERROR"] == expected["rejected"]
    assert severities["WARNING"] == expected["warning_rows"]
    assert severities["INFO"] == expected["info_issues"]
    assert severities.get("CONFIRMATION_REQUIRED", 0) == 0
    assert codes["NEGATIVE_VALUE"] == 12
    assert codes["MISSING_VALUE"] == 12
    assert codes["INVALID_UNIT"] == 12
    assert codes["DUPLICATE_IN_FILE"] == 12
    assert codes["PERIOD_MISMATCH"] == 12
    assert codes["IMPLAUSIBLE_MAGNITUDE"] == 12
    assert codes["UNIT_CONVERTED"] == 24

    activities = client.get(
        f"/api/facilities/{facility.id}/activity", headers=auth_headers(org.id)
    ).json()
    # accepted = valid diesel + tonne material + MWh electricity + implausible load
    assert len(activities) == expected["accepted"]
    # malformed rows never persisted; WARNING rows are (never silently dropped)
    assert all(float(a["original_value"]) >= 0 for a in activities)
    assert all(a["original_unit"] != "furlong" for a in activities)
    assert all(a["normalized_unit"] for a in activities)
    # unit normalization actually changed values for conversion rows
    assert any(a["original_unit"] == "tonne" and a["normalized_unit"] == "kg" for a in activities)
    assert any(a["original_unit"] == "MWh" and a["normalized_unit"] == "kWh" for a in activities)


def test_confirmation_required_is_explicit(client, db):
    org = make_org(db)
    db.commit()
    headers = auth_headers(org.id)
    for _ in range(5):
        response = client.post(
            "/api/units/normalize",
            json={"value": "1", "from_unit": "L", "to_unit": "kg"},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "CONFIRMATION_REQUIRED"
        assert response.json()["severity"] == "CONFIRMATION_REQUIRED"

    ok = client.post(
        "/api/units/normalize",
        json={"value": "1000", "from_unit": "kg", "to_unit": "tonne"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["normalized_value"] == "1.000"


def test_factor_endpoints_resolve_or_flag_unresolved(client, db):
    org = make_org(db)
    db.commit()
    headers = auth_headers(org.id)
    listing = client.get("/api/emission-factors", headers=headers)
    assert listing.status_code == 200

    flagged = client.get(
        "/api/emission-factors/lookup",
        params={"category": "UNICORN", "activity_subcategory": "x", "normalized_unit": "kg"},
        headers=headers,
    )
    assert flagged.status_code == 422
    assert flagged.json()["error_code"] == "EMISSION_FACTOR_NOT_FOUND"
