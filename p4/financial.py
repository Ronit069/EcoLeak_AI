"""Deterministic financial/impact estimation for Module J/K recommendations.

Module K edge cases handled here (security doc section 21, Module K):
- annual saving = 0            -> payback is unavailable (None), reason returned
- annual saving < 0            -> reported as additional annual cost, no payback
- CAPEX = 0                    -> immediate payback (0 years) when saving > 0
- adoption = 0%                -> no change
- adoption > 100%              -> rejected by the contract (0..100 constraint)
- saving exceeds source       -> capped at source emissions and flagged
- negative projected emissions -> floored at 0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from p4.models import (
    EnergyConversions,
    InterventionEntry,
    ProcessResourceBaseline,
    ResourceEmissionFactors,
    TariffSet,
)
from p4.contracts import ActivityCategory

ZERO = Decimal("0")


def _d(value: Optional[Decimal]) -> Decimal:
    return value if value is not None else ZERO


def midpoint(low: Optional[Decimal], high: Optional[Decimal]) -> Optional[Decimal]:
    if low is None and high is None:
        return None
    if low is None:
        return high
    if high is None:
        return low
    return (low + high) / Decimal("2")


@dataclass
class ResourceSavings:
    """Annual resource savings and their cash value (all deterministic)."""

    electricity_kwh: Decimal = ZERO
    natural_gas_m3: Decimal = ZERO
    diesel_litres: Decimal = ZERO
    water_m3: Decimal = ZERO
    wastewater_m3: Decimal = ZERO
    waste_kg: Decimal = ZERO
    packaging_kg: Decimal = ZERO
    energy_kwh_equivalent: Decimal = ZERO
    resource_saving_currency: Decimal = ZERO
    affected_baseline_cost_currency: Decimal = ZERO
    opex_change_currency: Optional[Decimal] = None
    annual_saving_currency: Optional[Decimal] = None
    assumptions: dict = field(default_factory=dict)


def aggregate_baselines(
    baselines: list[ProcessResourceBaseline],
) -> ProcessResourceBaseline:
    """Facility-total baseline (used by facility-wide interventions)."""

    def total(attr: str) -> Optional[Decimal]:
        values = [getattr(item, attr) for item in baselines if getattr(item, attr) is not None]
        if not values:
            return None
        return sum(values, ZERO)

    return ProcessResourceBaseline(
        process_name="*",
        electricity_kwh_per_year=total("electricity_kwh_per_year"),
        natural_gas_m3_per_year=total("natural_gas_m3_per_year"),
        diesel_litres_per_year=total("diesel_litres_per_year"),
        water_m3_per_year=total("water_m3_per_year"),
        wastewater_m3_per_year=total("wastewater_m3_per_year"),
        waste_kg_per_year=total("waste_kg_per_year"),
        packaging_kg_per_year=total("packaging_kg_per_year"),
    )


def estimate_resource_savings(
    entry: InterventionEntry,
    baseline: ProcessResourceBaseline,
    tariffs: TariffSet,
    conversions: EnergyConversions,
) -> ResourceSavings:
    """Apply the intervention's percentage ranges to the process baseline."""

    categories = set(entry.applicable_activity_categories)
    energy_pct = midpoint(entry.energy_reduction_min_pct, entry.energy_reduction_max_pct)
    water_pct = midpoint(entry.water_reduction_min_pct, entry.water_reduction_max_pct)
    waste_pct = midpoint(entry.waste_reduction_min_pct, entry.waste_reduction_max_pct)
    opex_pct = midpoint(entry.opex_change_pct_min, entry.opex_change_pct_max)

    savings = ResourceSavings()

    if energy_pct is not None and ActivityCategory.ELECTRICITY in categories:
        savings.electricity_kwh = _d(baseline.electricity_kwh_per_year) * energy_pct / 100
    if energy_pct is not None and ActivityCategory.FUEL in categories:
        savings.natural_gas_m3 = _d(baseline.natural_gas_m3_per_year) * energy_pct / 100
        savings.diesel_litres = _d(baseline.diesel_litres_per_year) * energy_pct / 100
    if water_pct is not None and ActivityCategory.WATER in categories:
        savings.water_m3 = _d(baseline.water_m3_per_year) * water_pct / 100
        savings.wastewater_m3 = _d(baseline.wastewater_m3_per_year) * water_pct / 100
    if waste_pct is not None and ActivityCategory.WASTE in categories:
        savings.waste_kg = _d(baseline.waste_kg_per_year) * waste_pct / 100
    if waste_pct is not None and ActivityCategory.MATERIAL in categories:
        savings.packaging_kg = _d(baseline.packaging_kg_per_year) * waste_pct / 100

    savings.energy_kwh_equivalent = (
        savings.electricity_kwh
        + savings.natural_gas_m3 * conversions.natural_gas_kwh_per_m3
        + savings.diesel_litres * conversions.diesel_kwh_per_litre
    )

    savings.resource_saving_currency = (
        savings.electricity_kwh * tariffs.electricity_per_kwh
        + savings.natural_gas_m3 * tariffs.natural_gas_per_m3
        + savings.diesel_litres * tariffs.diesel_per_litre
        + savings.water_m3 * tariffs.water_per_m3
        + savings.wastewater_m3 * tariffs.wastewater_per_m3
        + savings.waste_kg * tariffs.waste_disposal_per_kg
        + savings.packaging_kg * tariffs.packaging_per_kg
    )

    affected_cost = ZERO
    if ActivityCategory.ELECTRICITY in categories:
        affected_cost += _d(baseline.electricity_kwh_per_year) * tariffs.electricity_per_kwh
    if ActivityCategory.FUEL in categories:
        affected_cost += _d(baseline.natural_gas_m3_per_year) * tariffs.natural_gas_per_m3
        affected_cost += _d(baseline.diesel_litres_per_year) * tariffs.diesel_per_litre
    if ActivityCategory.WATER in categories:
        affected_cost += _d(baseline.water_m3_per_year) * tariffs.water_per_m3
        affected_cost += _d(baseline.wastewater_m3_per_year) * tariffs.wastewater_per_m3
    if ActivityCategory.WASTE in categories:
        affected_cost += _d(baseline.waste_kg_per_year) * tariffs.waste_disposal_per_kg
    if ActivityCategory.MATERIAL in categories:
        affected_cost += _d(baseline.packaging_kg_per_year) * tariffs.packaging_per_kg

    savings.affected_baseline_cost_currency = affected_cost
    if opex_pct is not None:
        # Cash delta: negative = cost reduction, positive = extra annual cost.
        savings.opex_change_currency = affected_cost * opex_pct / 100
        savings.annual_saving_currency = (
            savings.resource_saving_currency - savings.opex_change_currency
        )
    else:
        savings.opex_change_currency = None
        savings.annual_saving_currency = (
            savings.resource_saving_currency if savings.resource_saving_currency > ZERO else None
        )

    savings.assumptions = {
        "energy_saving_unit": "kWh (thermal equivalent)",
        "waste_reduction_unit": "kg/year",
        "water_reduction_unit": "m3/year",
        "electricity_kwh_saved_per_year": str(savings.electricity_kwh.quantize(Decimal("0.01"))),
        "natural_gas_m3_saved_per_year": str(savings.natural_gas_m3.quantize(Decimal("0.01"))),
        "diesel_litres_saved_per_year": str(savings.diesel_litres.quantize(Decimal("0.01"))),
        "water_m3_saved_per_year": str(savings.water_m3.quantize(Decimal("0.01"))),
        "wastewater_m3_avoided_per_year": str(savings.wastewater_m3.quantize(Decimal("0.01"))),
        "waste_kg_diverted_per_year": str(savings.waste_kg.quantize(Decimal("0.01"))),
        "packaging_kg_saved_per_year": str(savings.packaging_kg.quantize(Decimal("0.01"))),
        "static_energy_prices": True,
        "tariff_source": "P4 demo tariff fixture (mock)",
        "opex_change_pct_mid": str(opex_pct) if opex_pct is not None else None,
    }
    return savings


def estimate_resource_co2(
    savings: ResourceSavings, factors: "ResourceEmissionFactors"
) -> Optional[Decimal]:
    """Physical-basis CO2 saving from saved resources x emission factors."""

    total = ZERO
    used = False
    pairs = (
        (savings.electricity_kwh, factors.electricity_per_kwh),
        (savings.natural_gas_m3, factors.natural_gas_per_m3),
        (savings.diesel_litres, factors.diesel_per_litre),
        (savings.water_m3, factors.water_per_m3),
        (savings.wastewater_m3, factors.wastewater_per_m3),
        (savings.waste_kg, factors.waste_per_kg),
        (savings.packaging_kg, factors.packaging_per_kg),
    )
    for quantity, factor in pairs:
        if quantity and quantity > ZERO and factor is not None:
            total += quantity * factor
            used = True
    if not used:
        return None
    return total


def compute_payback(
    capex: Optional[Decimal], annual_saving: Optional[Decimal]
) -> tuple[Optional[Decimal], Optional[str]]:
    """Module K-safe payback. Returns (payback_years or None, reason or None)."""

    if capex is None or annual_saving is None:
        return None, "financial inputs incomplete; payback not estimated"
    if annual_saving < ZERO:
        return None, "annual saving is negative (additional annual cost); no financial payback estimated"
    if annual_saving == ZERO:
        return None, "annual saving is zero; payback unavailable"
    if capex == ZERO:
        return ZERO, "immediate payback (zero CAPEX)"
    return (capex / annual_saving).quantize(Decimal("0.01")), None


def apply_adoption(annual_value: Optional[Decimal], adoption_percentage: Decimal) -> Optional[Decimal]:
    """Scale an annual value by adoption percentage. Contract enforces 0..100."""

    if annual_value is None:
        return None
    return annual_value * adoption_percentage / Decimal("100")


def project_emissions(
    baseline_kg: Decimal,
    savings_by_recommendation: list[Decimal],
) -> tuple[Decimal, Decimal, list[str]]:
    """Sequential (non-double-counting) emission projection.

    Returns (projected_kg, total_saving_kg, notes). Each saving is applied to
    the *remaining* baseline, so combined interventions cannot double-count.
    Projected emissions are floored at 0 and each saving is capped at the
    remaining baseline (Module K: no negative projected emissions; saving
    cannot exceed the source).
    """

    notes: list[str] = []
    remaining = baseline_kg
    for index, saving in enumerate(savings_by_recommendation):
        if saving is None or saving < ZERO:
            continue
        if saving > remaining:
            notes.append(
                f"saving #{index + 1} ({saving} kg) exceeded the remaining baseline "
                f"({remaining} kg); capped at the source"
            )
            saving = remaining
        remaining -= saving
    projected = remaining
    if projected < ZERO:
        notes.append("projected emissions floored at 0 (physically valid value)")
        projected = ZERO
    total_saving = baseline_kg - projected
    return projected, total_saving, notes
