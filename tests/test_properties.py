"""C3: Hypothesis property-based tests for the carbon engine.

Properties pinned (per Phase-1 completion criteria):
1. Negative activity values are ALWAYS rejected (never a number is emitted).
2. Zero / missing production NEVER divides without an explicit guard
   (carbon_intensity stays None).
3. A missing factor ALWAYS yields an explicit unresolved state — never a
   fabricated value.
4. Unit conversions NEVER silently cross incompatible dimensions.

Run:  python -m pytest tests/test_properties.py
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

from hypothesis import given, settings
from hypothesis import strategies as st

from contracts.schemas import (  # noqa: E402
    ActivityCategory,
    ActivityData,
    EmissionFactor,
    Facility,
    Scope,
)
from engine.carbon import CarbonAccountingEngine  # noqa: E402
from engine.errors import InvalidUnitError  # noqa: E402
from engine.units import convert  # noqa: E402


def _facility(production: Decimal | None = None) -> Facility:
    return Facility(
        id=uuid4(), organization_id=uuid4(), name="P", country="IN",
        annual_production=production, production_unit="tonne",
        active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _activity(value: Decimal, validate: bool = True) -> ActivityData:
    """Build an activity row. ``validate=False`` uses ``model_construct`` so the
    property tests can exercise the ENGINE's own negative-value defense (the
    contract layer would reject negatives before they ever reach the engine)."""
    fields = dict(
        id=uuid4(), facility_id=uuid4(), reporting_period_id=uuid4(),
        activity_category=ActivityCategory.FUEL,
        activity_subcategory="Natural gas - stationary combustion",
        original_value=value, original_unit="m3",
        normalized_value=value, normalized_unit="m3",
        created_at=datetime.now(timezone.utc),
    )
    return ActivityData.model_validate(fields) if validate else ActivityData.model_construct(**fields)


def _ng_factor() -> EmissionFactor:
    return EmissionFactor(
        id=uuid4(), factor_code="EF-NG", category="FUEL", subcategory="Natural gas",
        item_name="Natural gas - stationary combustion",
        scope=Scope.SCOPE_1, input_unit="m3", total_co2e_factor=Decimal("2.0384"),
        source_name="DEFRA 2023", source_year=2023, version="D", active=True,
        created_at=datetime.now(timezone.utc),
    )


# -- Property 1: negative activity is always rejected ------------------------

@given(st.decimals(min_value=-10**12, max_value=-Decimal("0.000001"), places=6))
@settings(max_examples=60, deadline=None)
def test_negative_activity_always_rejected(value) -> None:
    engine = CarbonAccountingEngine()
    inv = engine.calculate(
        facility=_facility(Decimal("1000")), reporting_period_id="0" * 32,
        activity_data=[_activity(value, validate=False)],
        emission_factors=[_ng_factor()],
    )
    assert inv.unresolved, f"negative {value} must be unresolved"
    assert inv.unresolved[0].code == "NEGATIVE_ACTIVITY"
    assert inv.total_kgco2e == Decimal("0")


# -- Property 2: zero/missing production never divides ------------------------

@given(st.decimals(min_value=0, max_value=10**9, places=6))
@settings(max_examples=60, deadline=None)
def test_zero_production_never_divides(value) -> None:
    engine = CarbonAccountingEngine()
    inv = engine.calculate(
        facility=_facility(production=Decimal("0")), reporting_period_id="0" * 32,
        activity_data=[_activity(Decimal("10"))],
        emission_factors=[_ng_factor()],
    )
    assert inv.carbon_intensity is None
    assert inv._resolved_in_scope()  # emissions still calculated
    assert inv.total_kgco2e > 0

    inv_none = engine.calculate(
        facility=_facility(production=None), reporting_period_id="0" * 32,
        activity_data=[_activity(Decimal("10"))],
        emission_factors=[_ng_factor()],
    )
    assert inv_none.carbon_intensity is None


# -- Property 3: missing factor always unresolved, never fabricated -----------

@given(st.decimals(min_value=Decimal("0.000001"), max_value=10**12, places=6))
@settings(max_examples=60, deadline=None)
def test_missing_factor_always_unresolved(value) -> None:
    engine = CarbonAccountingEngine()
    inv = engine.calculate(
        facility=_facility(Decimal("1000")), reporting_period_id="0" * 32,
        activity_data=[_activity(value)],
        emission_factors=[],  # factor table empty
    )
    assert inv.unresolved
    assert inv.unresolved[0].code == "EMISSION_FACTOR_NOT_FOUND"
    assert inv.total_kgco2e == Decimal("0")


# -- Property 4: cross-dimension conversion never silent ----------------------

_DIMS = (
    # same-dimension pairs that MUST convert
    ("kg", "tonne", True),
    ("kwh", "mwh", True),
    ("l", "kl", True),
    # cross-dimension pairs that MUST raise
    ("kg", "kwh", False),
    ("l", "kg", False),
    ("m3", "l", False),
    ("km", "hour", False),
)


@given(
    st.sampled_from([(a, b, ok) for a, b, ok in _DIMS]),
    st.decimals(min_value=Decimal("0.000001"), max_value=10**9, places=6),
)
@settings(max_examples=120, deadline=None)
def test_conversion_dimension_rules(pair, value) -> None:
    from_a, to_b, should_work = pair
    if should_work:
        result = convert(value, from_a, to_b)
        assert result > 0
    else:
        try:
            convert(value, from_a, to_b)
        except InvalidUnitError:
            return
        raise AssertionError(f"silent cross-dimension conversion {from_a}->{to_b}")


# -- Property 5: arbitrary decimals never crash the engine --------------------

@given(st.decimals(min_value=-10**12, max_value=10**12, places=6))
@settings(max_examples=80, deadline=None)
def test_engine_never_raises_on_arbitrary_values(value) -> None:
    engine = CarbonAccountingEngine()
    try:
        inv = engine.calculate(
            facility=_facility(Decimal("1000")), reporting_period_id="0" * 32,
            activity_data=[_activity(value, validate=False)],
            emission_factors=[_ng_factor()],
        )
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"engine raised on {value}: {exc}") from exc
    assert inv.total_kgco2e >= 0