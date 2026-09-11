"""Module D - Unit Normalization Engine (Pint).

Rules implemented (DB doc section 4 / edge cases D):
- Normalize mass, volume, energy, distance, time and tonne-km to internal bases.
- Original value/unit are always preserved by callers; this engine only computes
  the normalized pair and the conversion factor/source.
- Never silently convert an ambiguous unit (e.g. litre <-> m3 without density, or
  mass <-> volume): raise ConfirmationRequiredError instead.
- Unknown units are rejected with InvalidUnitError (do not calculate until mapped).
- Case variations (kWh / KWH / kwh) are normalized safely.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

import pint

ureg = pint.UnitRegistry()
ureg.define("tonne_km = metric_ton * kilometer = tkm")

PINT_VERSION = pint.__version__
CONVERSION_SOURCE = f"Pint {PINT_VERSION} (SI / ISO 80000 unit definitions)"

# family -> (normalized output label, pint base expression)
_FAMILIES: dict[str, tuple[str, str]] = {
    "MASS": ("kg", "kilogram"),
    "ENERGY": ("kWh", "kilowatt_hour"),
    "VOLUME_LIQUID": ("L", "liter"),
    "VOLUME_GAS": ("m3", "meter**3"),
    "DISTANCE": ("km", "kilometer"),
    "TIME": ("h", "hour"),
    "TRANSPORT": ("tonne_km", "tonne_km"),
}

# alias (lower-case, no spaces) -> (family, pint expression)
_ALIASES: dict[str, tuple[str, str]] = {}


def _register(family: str, pint_expr: str, *aliases: str) -> None:
    for alias in aliases:
        _ALIASES[alias.lower()] = (family, pint_expr)


# MASS
_register("MASS", "kilogram", "kg", "kilogram", "kilograms", "kgs")
_register("MASS", "gram", "g", "gram", "grams")
_register("MASS", "milligram", "mg", "milligram", "milligrams")
_register("MASS", "metric_ton", "tonne", "tonnes", "ton", "tons", "t", "mt", "metricton")
# ENERGY
_register("ENERGY", "kilowatt_hour", "kwh", "kilowatt_hour", "kilowatthour")
_register("ENERGY", "megawatt_hour", "mwh", "megawatt_hour")
_register("ENERGY", "watt_hour", "wh", "watt_hour")
_register("ENERGY", "gigajoule", "gj", "gigajoule")
_register("ENERGY", "megajoule", "mj", "megajoule")
_register("ENERGY", "kilojoule", "kj", "kilojoule")
# VOLUME (liquid) - kept distinct from gas volumes on purpose
_register("VOLUME_LIQUID", "liter", "l", "liter", "litre", "liters", "litres")
_register("VOLUME_LIQUID", "milliliter", "ml", "milliliter", "millilitre")
# VOLUME (gas)
_register(
    "VOLUME_GAS",
    "meter**3",
    "m3",
    "m^3",
    "m\u00b3",
    "cubic_meter",
    "cubic_metre",
    "cubicmeter",
    "scm",
    "nm3",
)
# DISTANCE
_register("DISTANCE", "kilometer", "km", "kilometer", "kilometre")
_register("DISTANCE", "meter", "m", "meter", "metre")
_register("DISTANCE", "mile", "mi", "mile", "miles")
# TIME
_register("TIME", "hour", "h", "hr", "hour", "hours")
_register("TIME", "minute", "min", "minute", "minutes")
_register("TIME", "second", "s", "sec", "second", "seconds")
# TRANSPORT intensity
_register("TRANSPORT", "tonne_km", "tonne_km", "tkm", "t.km", "t-km", "ton_km")
_register("TRANSPORT", "kilogram * kilometer", "kg_km", "kg.km", "kg-km")

ALLOWED_UNITS = sorted(_ALIASES)


@dataclass
class NormalizationResult:
    original_value: Optional[Decimal]
    original_unit: str
    normalized_value: Optional[Decimal]
    normalized_unit: str
    conversion_factor: Optional[Decimal]
    conversion_source: str
    dimension: Optional[str] = None
    converted: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "original_value": self.original_value,
            "original_unit": self.original_unit,
            "normalized_value": self.normalized_value,
            "normalized_unit": self.normalized_unit,
            "conversion_factor": self.conversion_factor,
            "conversion_source": self.conversion_source,
        }


def canonical_family(unit: str) -> Optional[str]:
    entry = _ALIASES.get(unit.strip().lower())
    return entry[0] if entry else None


def is_allowed_unit(unit: str) -> bool:
    return unit.strip().lower() in _ALIASES


def dimension_of(unit: str) -> Optional[str]:
    """Physical dimension label used by the quality engine."""
    family = canonical_family(unit)
    if family is None:
        return None
    return "transport_intensity" if family == "TRANSPORT" else family.lower()


def normalize(
    value: Decimal | float | int,
    from_unit: str,
    to_unit: Optional[str] = None,
) -> NormalizationResult:
    """Normalize a value to its family base (or an explicit compatible `to_unit`)."""
    from app.errors import ConfirmationRequiredError, InvalidUnitError

    if from_unit is None or str(from_unit).strip() == "":
        raise InvalidUnitError("Missing original unit; record is unusable.")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise InvalidUnitError(f"Value '{value}' is not numeric.") from exc

    from_key = from_unit.strip().lower()
    if from_key not in _ALIASES:
        raise InvalidUnitError(
            f"Unrecognized unit '{from_unit}'. Map it before calculation.",
            details={"unit": from_unit, "allowed_units": ALLOWED_UNITS},
        )

    from_family, from_expr = _ALIASES[from_key]

    if to_unit is not None and str(to_unit).strip() != "":
        to_key = to_unit.strip().lower()
        if to_key not in _ALIASES:
            raise InvalidUnitError(
                f"Unrecognized target unit '{to_unit}'.",
                details={"unit": to_unit},
            )
        to_family, to_expr = _ALIASES[to_key]
        if to_family != from_family:
            raise ConfirmationRequiredError(
                "Ambiguous unit conversion requires a density/energy-content "
                "assumption and source. Refusing to convert silently.",
                details={
                    "from_unit": from_unit,
                    "to_unit": to_unit,
                    "from_dimension": from_family,
                    "to_dimension": to_family,
                },
            )
    else:
        to_family, to_expr = from_family, _FAMILIES[from_family][1]

    if decimal_value < 0:
        raise InvalidUnitError("Negative values are not allowed for normalization.")

    try:
        quantity = decimal_value * ureg.Unit(from_expr)
        converted = quantity.to(ureg.Unit(to_expr))
        normalized_value = Decimal(str(converted.magnitude))
    except Exception as exc:  # pint DimensionalityError / UndefinedUnitError
        from app.errors import ConfirmationRequiredError

        raise ConfirmationRequiredError(
            "Units are dimensionally incompatible; provide a verified conversion.",
            details={"from_unit": from_unit, "to_unit": to_unit},
        ) from exc

    factor = None
    if decimal_value != 0:
        factor = (normalized_value / decimal_value).quantize(Decimal("0.0000000001"))

    label = _FAMILIES[to_family][0]
    return NormalizationResult(
        original_value=decimal_value,
        original_unit=from_unit,
        normalized_value=normalized_value,
        normalized_unit=label,
        conversion_factor=factor,
        conversion_source=CONVERSION_SOURCE,
        dimension=dimension_of(from_unit),
        converted=from_key != to_expr.strip().lower(),
    )
