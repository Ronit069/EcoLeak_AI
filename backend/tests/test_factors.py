"""Module E tests: lookup priority, versioning, explicit unresolved state."""
from __future__ import annotations

from decimal import Decimal

from app.db import utcnow
from app.models.factor import EmissionFactor
from app.services import factors as factor_service
from tests.factories import auth_headers, make_org


def _factor(**overrides) -> EmissionFactor:
    base = dict(
        factor_code=f"EF-{utcnow().timestamp()}",
        category="FUEL",
        subcategory="Diesel",
        item_name="Diesel",
        region_country="India",
        region_state=None,
        scope="SCOPE_1",
        input_unit="L",
        output_unit="kgCO2e",
        total_co2e_factor=Decimal("2.68"),
        source_name="IPCC 2006",
        source_year=2006,
        version="2006.1",
        active=True,
        confidence_level="HIGH",
        created_at=utcnow(),
    )
    base.update(overrides)
    return EmissionFactor(**base)


def test_missing_factor_is_explicit_none(db):
    result = factor_service.lookup_factor(
        db,
        category="FUEL",
        activity_subcategory="Diesel",
        normalized_unit="L",
    )
    assert result is None


def test_state_factor_beats_country_factor(db):
    db.add(_factor(factor_code="EF-COUNTRY", region_country="India", region_state=None))
    db.add(
        _factor(
            factor_code="EF-STATE",
            region_country="India",
            region_state="Gujarat",
            total_co2e_factor=Decimal("2.70"),
        )
    )
    db.flush()
    best = factor_service.lookup_factor(
        db,
        category="FUEL",
        activity_subcategory="Diesel",
        normalized_unit="L",
        region_country="India",
        region_state="Gujarat",
    )
    assert best is not None and best.factor_code == "EF-STATE"


def test_supplier_specific_overrides_generic(db):
    db.add(_factor(factor_code="EF-GENERIC", source_year=2006))
    db.add(
        _factor(
            factor_code="EF-SUPPLIER",
            supplier_specific=True,
            supplier_id="SUP-1",
            total_co2e_factor=Decimal("1.90"),
        )
    )
    db.flush()
    best = factor_service.lookup_factor(
        db,
        category="FUEL",
        activity_subcategory="Diesel",
        normalized_unit="L",
        supplier_id="SUP-1",
    )
    assert best is not None and best.factor_code == "EF-SUPPLIER"


def test_new_version_deactivates_old(client, db):
    org = make_org(db)
    db.commit()
    headers = auth_headers(org.id)
    body = {
        "factor_code": "EF-VER",
        "category": "FUEL",
        "subcategory": "Diesel",
        "item_name": "Diesel",
        "scope": "SCOPE_1",
        "input_unit": "L",
        "total_co2e_factor": "2.68",
        "source_name": "IPCC",
        "source_year": 2006,
        "version": "2006.1",
    }
    created = client.post("/api/emission-factors", json=body, headers=headers)
    assert created.status_code == 201, created.text
    factor_id = created.json()["id"]

    body["version"] = "2023.1"
    body["total_co2e_factor"] = "2.50"
    versioned = client.post(
        f"/api/emission-factors/{factor_id}/new-version", json=body, headers=headers
    )
    assert versioned.status_code == 201, versioned.text
    assert versioned.json()["active"] is True

    old = client.get(f"/api/emission-factors/{factor_id}", headers=headers).json()
    assert old["active"] is False
    assert old["factor_code"] == "EF-VER"  # never overwritten/deleted


def test_create_factor_requires_admin_role(client, db):
    org = make_org(db)
    db.commit()
    body = {
        "factor_code": "EF-ROLE",
        "category": "FUEL",
        "subcategory": "Diesel",
        "item_name": "Diesel",
        "scope": "SCOPE_1",
        "input_unit": "L",
        "total_co2e_factor": "2.68",
        "source_name": "IPCC",
        "source_year": 2006,
        "version": "1",
    }
    forbidden = client.post(
        "/api/emission-factors", json=body, headers=auth_headers(org.id, "SUSTAINABILITY_ANALYST")
    )
    assert forbidden.status_code == 403


def test_lookup_endpoint_returns_unresolved_error(client, db):
    org = make_org(db)
    db.commit()
    response = client.get(
        "/api/emission-factors/lookup",
        params={"category": "REFRIGERANT", "activity_subcategory": "X", "normalized_unit": "kg"},
        headers=auth_headers(org.id),
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "EMISSION_FACTOR_NOT_FOUND"
