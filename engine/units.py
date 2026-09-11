"""Deterministic unit handling for Module F factor matching.

This is intentionally small and conservative. P2 owns full unit normalization
(Module D / Pint); Module F only needs to know whether an activity's normalized
unit can be matched to a factor's input unit, and to perform *safe* magnitude
conversions when it can.

Rules taken from the requirements / library doc:
- Never silently convert across dimensions (litre diesel -> kg, m3 gas -> kWh).
- Unit case variations are normalized (``KWH`` -> ``kWh``).
- If a conversion is ambiguous, the factor is treated as not matching (the
  activity becomes an explicit ``unresolved`` result; we never fabricate).
"""

from __future__ import annotations

from decimal import Decimal

from .errors import InvalidUnitError
from .ids import to_decimal

# Canonical unit per dimension. factor = how many canonical units in 1 of unit.
_CONVERSIONS: dict[str, dict[str, Decimal]] = {
    "mass": {
        "kg": Decimal("1"),
        "g": Decimal("0.001"),
        "mg": Decimal("0.000001"),
        "tonne": Decimal("1000"),
        "tonnes": Decimal("1000"),
        "t": Decimal("1000"),
        "metric_ton": Decimal("1000"),
        "metric_tonne": Decimal("1000"),
    },
    "energy": {
        "kwh": Decimal("1"),
        "mwh": Decimal("1000"),
        "gwh": Decimal("1000000"),
        "wh": Decimal("0.001"),
    },
    "volume_liquid": {
        "l": Decimal("1"),
        "litre": Decimal("1"),
        "liter": Decimal("1"),
        "ml": Decimal("0.001"),
        "kl": Decimal("1000"),
    },
    # Gas volume is its OWN dimension: m3 must never silently convert to litres
    # (C1: aligns with backend Pint families VOLUME_GAS != VOLUME_LIQUID).
    "volume_gas": {
        "m3": Decimal("1"),
        "cubic_meter": Decimal("1"),
        "scm": Decimal("1"),
        "nm3": Decimal("1"),
    },
    "distance": {
        "km": Decimal("1000"),
        "m": Decimal("1"),
    },
    "transport": {
        # tonne_km is its own dimension; a km or tonne alone is NOT compatible.
        "tonne_km": Decimal("1"),
        "tkm": Decimal("1"),
        "t_km": Decimal("1"),
    },
    "time": {
        "hour": Decimal("1"),
        "h": Decimal("1"),
        "hr": Decimal("1"),
    },
}

_UNIT_TO_DIMENSION: dict[str, str] = {
    unit: dim for dim, units in _CONVERSIONS.items() for unit in units
}


def normalize_unit_token(unit: str) -> str:
    return (unit or "").strip().lower().replace(" ", "_").replace("³", "3")


def dimension_of(unit: str) -> str | None:
    return _UNIT_TO_DIMENSION.get(normalize_unit_token(unit))


def can_convert(from_unit: str, to_unit: str) -> bool:
    """True when both units belong to the same known dimension."""
    return dimension_of(from_unit) is not None and dimension_of(from_unit) == dimension_of(to_unit)


def convert(value: Decimal | float | str, from_unit: str, to_unit: str) -> Decimal:
    """Convert ``value`` between compatible units.

    Raises :class:`InvalidUnitError` for unknown or cross-dimension conversions
    so callers cannot accidentally fabricate a number.
    """
    src = normalize_unit_token(from_unit)
    dst = normalize_unit_token(to_unit)
    if src == dst:
        return to_decimal(value)  # type: ignore[return-value]
    src_dim = _UNIT_TO_DIMENSION.get(src)
    dst_dim = _UNIT_TO_DIMENSION.get(dst)
    if src_dim is None or dst_dim is None or src_dim != dst_dim:
        raise InvalidUnitError(
            f"Cannot convert '{from_unit}' to '{to_unit}' without an approved, "
            "sourced conversion factor.",
            {"from_unit": from_unit, "to_unit": to_unit},
        )
    canonical = to_decimal(value) * _CONVERSIONS[src_dim][src]
    return canonical / _CONVERSIONS[dst_dim][dst]


def compatible_factor_unit(activity_unit: str, factor_unit: str) -> bool:
    """Unit match test used before a factor is allowed to be selected."""
    a = normalize_unit_token(activity_unit)
    f = normalize_unit_token(factor_unit)
    if a == f:
        return True
    return can_convert(a, f)
