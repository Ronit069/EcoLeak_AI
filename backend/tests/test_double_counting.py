"""Phase 2 edge-case re-verification: on-site generation / export are not
double counted against purchased grid electricity under real ingested data."""
from __future__ import annotations

from decimal import Decimal

from app.config import get_settings
from app.db import utcnow
from app.models.factor import EmissionFactor
from app.services import engine_bridge
from tests.factories import auth_headers, make_facility, make_org, make_period, make_process


def _setup(db):
    org = make_org(db)
    facility = make_facility(db, org)
    period = make_period(db, facility)
    make_process(db, facility, name="Boiler", process_code="PRC-X")
    db.add(
        EmissionFactor(
            factor_code="EF-ELEC-DC-TEST",
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


def _add(client, headers, facility, period, subcategory, value):
    response = client.post(
        f"/api/facilities/{facility.id}/activity",
        json={
            "reporting_period_id": str(period.id),
            "activity_category": "ELECTRICITY",
            "activity_subcategory": subcategory,
            "original_value": str(value),
            "original_unit": "kWh",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_onsite_and_export_kept_out_of_scope_totals(client, db, monkeypatch):
    org, facility, period = _setup(db)
    headers = auth_headers(org.id)
    _add(client, headers, facility, period, "Purchased grid electricity", 1000)
    _add(client, headers, facility, period, "Rooftop solar PV self-consumption", 400)
    _add(client, headers, facility, period, "Electricity exported to grid (surplus)", 200)

    monkeypatch.setenv("USE_MOCK_DATA", "false")
    get_settings.cache_clear()
    engine = engine_bridge.build_engine()
    inventory = engine.calculate_inventory(str(facility.id), str(period.id))

    # Purchased grid only in Scope 2.
    assert inventory.scope2_kgco2e == Decimal("500.000000")
    # On-site self-consumption and exported surplus are separate ledgers.
    assert inventory.onsite_generation_kgco2e == Decimal("200.000000")
    assert inventory.exported_electricity_kgco2e == Decimal("100.000000")
    # Total excludes the separate ledgers: no double counting.
    assert inventory.total_kgco2e == inventory.scope1_kgco2e + inventory.scope2_kgco2e
    assert inventory.total_kgco2e == Decimal("500.000000")
