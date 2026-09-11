"""C2: recycling-loop emissions are modeled, not assumed zero.

The landfill-avoidance saving must be netted against the recycling pathway's
own processing emissions: a recycling intervention with a non-trivial
processing factor produces a LOWER net CO2 saving than a naive
landfill-avoidance-only calculation.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p4.financial import estimate_resource_co2  # noqa: E402
from p4.financial import ResourceSavings
from p4.models import ResourceEmissionFactors  # noqa: E402

WASTE_KG = Decimal("10000")  # e.g. 10 t of textile offcuts diverted per year


def _savings() -> ResourceSavings:
    return ResourceSavings(waste_kg=WASTE_KG)


def test_recycling_with_processing_factor_lowers_net_saving() -> None:
    landfill_only = ResourceEmissionFactors(waste_per_kg=Decimal("0.8"))
    netted = ResourceEmissionFactors(
        waste_per_kg=Decimal("0.8"),
        recycling_processing_emission_factor=Decimal("0.3"),
    )
    naive = estimate_resource_co2(_savings(), landfill_only)
    net = estimate_resource_co2(_savings(), netted)
    assert naive == Decimal("8000")  # 10,000 x 0.8 landfill avoided
    assert net == Decimal("5000")  # 10,000 x (0.8 - 0.3): processing netted out
    assert net < naive  # recycling is NOT zero-emission


def test_recycling_net_is_exactly_processing_netted_out() -> None:
    netted = ResourceEmissionFactors(
        waste_per_kg=Decimal("0.8"),
        recycling_processing_emission_factor=Decimal("0.3"),
    )
    net = estimate_resource_co2(_savings(), netted)
    assert net == WASTE_KG * Decimal("0.8") - WASTE_KG * Decimal("0.3")


def test_processing_factor_can_make_net_negative() -> None:
    # Energy-intensive recycling can emit MORE than the avoided landfill;
    # Module K reports additional emissions rather than a fabricated saving.
    worst = ResourceEmissionFactors(
        waste_per_kg=Decimal("0.8"),
        recycling_processing_emission_factor=Decimal("1.2"),
    )
    net = estimate_resource_co2(_savings(), worst)
    assert net == Decimal("-4000")
    assert net < 0


def test_no_waste_stream_ignores_processing_factor() -> None:
    factors = ResourceEmissionFactors(
        electricity_per_kwh=Decimal("0.71"),
        recycling_processing_emission_factor=Decimal("0.3"),
    )
    savings = ResourceSavings(electricity_kwh=Decimal("1000"))
    assert estimate_resource_co2(savings, factors) == Decimal("710")


def test_factor_model_accepts_new_field_with_default() -> None:
    f = ResourceEmissionFactors()
    assert f.recycling_processing_emission_factor is None
    assert f.recycling_processing_emission_factor is not None or True  # default None
    f2 = ResourceEmissionFactors(recycling_processing_emission_factor=Decimal("0.05"))
    assert f2.recycling_processing_emission_factor == Decimal("0.05")