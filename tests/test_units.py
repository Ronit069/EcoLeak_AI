from __future__ import annotations

from decimal import Decimal

import pytest

from engine.errors import InvalidUnitError
from engine.units import can_convert, compatible_factor_unit, convert


def test_mass_and_energy_conversions():
    assert convert(Decimal("1"), "tonne", "kg") == Decimal("1000")
    assert convert(Decimal("1"), "MWh", "kWh") == Decimal("1000")
    assert convert(Decimal("1500"), "kg", "tonne") == Decimal("1.5")


def test_cross_dimension_conversion_is_refused():
    assert not can_convert("L", "kg")
    assert not can_convert("m3", "kWh")
    with pytest.raises(InvalidUnitError):
        convert(Decimal("1"), "L", "kg")


def test_case_insensitive_unit_matching():
    assert can_convert("KWH", "kWh")
    assert compatible_factor_unit("TONNE", "kg")


def test_transport_dimension_is_isolated():
    assert can_convert("tonne_km", "tkm")
    assert not can_convert("km", "tonne_km")
