"""Deterministic identifier + numeric helpers.

Identifiers are UUIDv5 derived from stable business keys so that re-running the
engine over the same inputs produces byte-identical IDs. This is what makes the
Phase 0 mock and the live engine interchangeable.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid5

# Fixed namespace for all EcoLeak deterministic IDs (do not change - it would
# invalidate previously persisted, reproducible IDs).
ECOL_NAMESPACE = UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

_D6 = Decimal("0.000001")
_D4 = Decimal("0.0001")
_D2 = Decimal("0.01")


def deterministic_id(*parts: Any) -> str:
    """Return a stable UUIDv5 string derived from ``parts``."""
    return str(uuid5(ECOL_NAMESPACE, "|".join(str(p) for p in parts)))


def to_decimal(value: Any) -> Decimal | None:
    """Best-effort lossless-ish Decimal conversion (never via float math)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q6(value: Any) -> Decimal:
    """Quantize to 6 decimal places (matches contract decimal_places=6)."""
    return to_decimal(value).quantize(_D6, rounding=ROUND_HALF_UP)  # type: ignore[union-attr]


def q4(value: Any) -> Decimal:
    return to_decimal(value).quantize(_D4, rounding=ROUND_HALF_UP)  # type: ignore[union-attr]


def q2(value: Any) -> Decimal:
    return to_decimal(value).quantize(_D2, rounding=ROUND_HALF_UP)  # type: ignore[union-attr]


def clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("100")) -> Decimal:
    if value < low:
        return low
    if value > high:
        return high
    return value


def percentile(values: list[Decimal], pct: float) -> Decimal:
    """Simple deterministic linear-interpolation percentile (pct in 0..100)."""
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = Decimal(str(rank - low))
    return ordered[low] + (ordered[high] - ordered[low]) * frac
