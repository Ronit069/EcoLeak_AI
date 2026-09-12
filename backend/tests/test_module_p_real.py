"""Phase 2 Module P: report pulls live F/G/J/L output when the flag is off."""
from __future__ import annotations

from decimal import Decimal

from app.config import get_settings
from app.db import utcnow
from app.models.factor import EmissionFactor
from tests.factories import auth_headers, make_facility, make_org, make_period, make_process


def _setup(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    make_process(db, facility, name="Boiler", process_code="PRC-X")
    db.add(
        EmissionFactor(
            factor_code="EF-ELEC-P-TEST",
            category="ELECTRICITY",
            subcategory="Purchased electricity",
            item_name="Grid electricity",
            region_country="India",
            scope="SCOPE_2",
            input_unit="kWh",
            output_unit="kgCO2e",
            total_co2e_factor=Decimal("0.5"),
            source_name="verification fixture",
            source_year=2024,
            version="1",
            active=True,
            confidence_level="HIGH",
            created_at=utcnow(),
        )
    )
    db.commit()
    return org, facility, period


def test_report_real_mode_uses_engine_output(client, db, monkeypatch):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    created_activity = client.post(
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
    assert created_activity.status_code == 201

    # Mock behaviour first (regression guard).
    mock_report = client.post(
        f"/api/facilities/{facility.id}/reporting-periods/{period.id}/reports",
        json={"template_version": "v1", "include_scope3": True},
        headers=headers,
    )
    assert mock_report.status_code == 202
    mock_payload = client.get(
        f"/api/reports/{mock_report.json()['report_id']}", headers=headers
    ).json()["payload"]
    assert mock_payload["report_meta"]["use_mock_data"] is True
    assert mock_payload["hotspot_analysis"]["status"] == "STUB"

    # Real behaviour behind the flag.
    monkeypatch.setenv("USE_MOCK_DATA", "false")
    get_settings.cache_clear()
    real_report = client.post(
        f"/api/facilities/{facility.id}/reporting-periods/{period.id}/reports",
        json={"template_version": "v1", "include_scope3": True},
        headers=headers,
    )
    assert real_report.status_code == 202, real_report.text
    payload = client.get(
        f"/api/reports/{real_report.json()['report_id']}", headers=headers
    ).json()["payload"]

    meta = payload["report_meta"]
    assert meta["use_mock_data"] is False
    assert meta["data_is_stub"] is False

    scope = payload["scope_summary"]
    assert scope["scope2_kgco2e"] is not None
    assert payload["factor_provenance"], "factor provenance must be present"
    assert payload["hotspot_analysis"]["status"] == "REAL"
    assert payload["circularity_assessment"]["status"] in {"REAL", "UNAVAILABLE"}
    assert payload["recommendations"]["status"] in {"REAL", "UNAVAILABLE"}
    assert payload["data_quality_score"]["total_score"] is not None


def test_health_exposes_mock_flag(client):
    body = client.get("/api/health").json()
    assert "use_mock_data" in body
