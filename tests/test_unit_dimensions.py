"""C1: engine unit dimensions — VOLUME_LIQUID and VOLUME_GAS are separate.

Regression: natural-gas m3 must NEVER resolve against a litre-based diesel
factor (the pre-fix engine treated both as one "volume" dimension). The
single-candidate fallback must only fire on genuinely unambiguous,
same-dimension matches.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.schemas import (  # noqa: E402
    ActivityCategory,
    ActivityData,
    EmissionFactor,
    Facility,
    Scope,
)
from engine.carbon import CarbonAccountingEngine  # noqa: E402
from engine.units import can_convert, compatible_factor_unit, convert  # noqa: E402
from engine.errors import InvalidUnitError  # noqa: E402


def _facility() -> Facility:
    return Facility(
        id=uuid4(), organization_id=uuid4(), name="Test", country="India",
        annual_production=Decimal("1000"), production_unit="tonne",
        active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _ng_activity(value: Decimal = Decimal("95")) -> ActivityData:
    return ActivityData(
        id=uuid4(), facility_id=uuid4(), reporting_period_id=uuid4(),
        activity_category=ActivityCategory.FUEL,
        activity_subcategory="Natural gas - stationary combustion",
        original_value=value, original_unit="m3",
        normalized_value=value, normalized_unit="m3",
        created_at=datetime.now(timezone.utc),
    )


def _diesel_factor_liter() -> EmissionFactor:
    return EmissionFactor(
        id=uuid4(), factor_code="EF-DIESEL-L", category="FUEL", subcategory="Diesel",
        item_name="Diesel - combustion", region_country="United Kingdom",
        scope=Scope.SCOPE_1, input_unit="L", total_co2e_factor=Decimal("2.6594"),
        source_name="DEFRA 2023", source_year=2023, version="DEFRA-2023", active=True,
        created_at=datetime.now(timezone.utc),
    )


def _ng_factor_m3() -> EmissionFactor:
    return EmissionFactor(
        id=uuid4(), factor_code="EF-NG-M3", category="FUEL", subcategory="Natural gas",
        item_name="Natural gas - stationary combustion", region_country="United Kingdom",
        scope=Scope.SCOPE_1, input_unit="m3", total_co2e_factor=Decimal("2.0384"),
        source_name="DEFRA 2023", source_year=2023, version="DEFRA-2023", active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_m3_and_litre_are_different_dimensions() -> None:
    assert can_convert("m3", "L") is False
    assert can_convert("L", "m3") is False
    assert compatible_factor_unit("m3", "L") is False
    assert compatible_factor_unit("L", "m3") is False


def test_cross_dimension_conversion_is_blocked_not_silent() -> None:
    try:
        convert(Decimal("1"), "m3", "L")
    except InvalidUnitError:
        pass
    else:
        raise AssertionError("m3->L must raise InvalidUnitError")


def test_same_dimension_conversion_still_works() -> None:
    assert convert(Decimal("2"), "kl", "l") == Decimal("2000")
    assert convert(Decimal("10"), "m3", "scm") == Decimal("10")


def test_ng_m3_activity_never_resolves_to_litre_diesel_factor() -> None:
    engine = CarbonAccountingEngine()
    inv = engine.calculate(
        facility=_facility(), reporting_period_id="0" * 32,
        activity_data=[_ng_activity()],
        emission_factors=[_diesel_factor_liter()],  # ONLY a litre factor exists
    )
    assert inv.unresolved, "must be unresolved, never resolved via cross-dimension"
    assert inv.unresolved[0].code == "EMISSION_FACTOR_NOT_FOUND"
    assert inv.total_kgco2e == Decimal("0")


def test_single_candidate_fallback_fires_only_within_same_dimension() -> None:
    engine = CarbonAccountingEngine()
    inv = engine.calculate(
        facility=_facility(), reporting_period_id="0" * 32,
        activity_data=[_ng_activity()],
        emission_factors=[_ng_factor_m3()],  # single m3 candidate: unambiguous
    )
    assert len(inv.records) == 1 and inv.records[0].resolved
    assert inv.records[0].co2e_kg == Decimal("193.648")  # 95 x 2.0384
    assert inv.unresolved == []