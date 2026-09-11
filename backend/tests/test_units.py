"""Module D unit engine tests (Pint)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.errors import ConfirmationRequiredError, InvalidUnitError
from app.services import units


def test_tonne_to_kg():
    result = units.normalize(Decimal("1.5"), "tonne")
    assert result.normalized_value == Decimal("1500.0")
    assert result.normalized_unit == "kg"


def test_mwh_to_kwh():
    result = units.normalize(1, "MWh")
    assert result.normalized_value == Decimal("1000.0")
    assert result.normalized_unit == "kWh"


def test_case_insensitive_unit():
    result = units.normalize(500, "KWH")
    assert result.normalized_unit == "kWh"
    assert result.normalized_value == Decimal("500")


def test_litre_stays_litre():
    result = units.normalize(12000, "L")
    assert result.normalized_unit == "L"
    assert result.normalized_value == Decimal("12000")


def test_transport_tonne_km():
    result = units.normalize(320000, "tonne_km")
    assert result.normalized_unit == "tonne_km"


def test_ambiguous_mass_volume_is_refused():
    with pytest.raises(ConfirmationRequiredError):
        units.normalize(1, "L", "kg")


def test_litre_to_m3_is_refused():
    with pytest.raises(ConfirmationRequiredError):
        units.normalize(1, "L", "m3")


def test_unknown_unit_is_rejected():
    with pytest.raises(InvalidUnitError):
        units.normalize(1, "furlong")


def test_missing_unit_is_rejected():
    with pytest.raises(InvalidUnitError):
        units.normalize(1, "")


def test_negative_value_is_rejected():
    with pytest.raises(InvalidUnitError):
        units.normalize(-1, "kg")
