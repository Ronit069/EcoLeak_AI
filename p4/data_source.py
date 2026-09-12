"""Phase 2 mock-to-real hotspot source for P4 (Module J input gate).

Phase 1 ran the ranker on ``mocks/mock_hotspot_output.json``. Phase 2 swaps the
hotspot input to P3's live engine output while keeping the mock one flag away:

    USE_MOCK_DATA=true   -> frozen mock envelope (instant fallback, default-safe)
    USE_MOCK_DATA=false  -> live P3 Engine G output (P2 tables via SQL source)
    unset                -> legacy behavior: DSN present -> live, else mock

Precedence (mirrors ``engine.data_source.resolve_use_mock_data`` and P2's
``Settings.use_mock_data`` so all three components agree):

    1. explicit argument
    2. ``USE_MOCK_DATA`` env (P2 pydantic-settings name)
    3. ``ECOLEAK_USE_MOCK_DATA`` env (P3 engine name)
    4. ``None`` -> legacy rule

The mock path imports nothing beyond Pydantic + the frozen contracts, so the
Phase 1 demo keeps working with zero DB dependencies.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional
from uuid import UUID

from p4.contracts import (
    ActivityCategory,
    EmissionFactor,
    Facility,
    HotspotDetectionResult,
    Organization,
    Process,
)
from p4.models import FacilityContext, ProcessResourceBaseline, ResourceEmissionFactors, TariffSet

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_HOTSPOTS = REPO_ROOT / "mocks" / "mock_hotspot_output.json"

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def resolve_use_mock_data(use_mock_data: Optional[bool] = None) -> Optional[bool]:
    """Resolve the shared Phase 2 gate. ``None`` means "legacy: DSN decides"."""

    if use_mock_data is not None:
        return bool(use_mock_data)
    for name in ("USE_MOCK_DATA", "ECOLEAK_USE_MOCK_DATA"):
        raw = os.environ.get(name)
        if raw is None or not raw.strip():
            continue
        value = raw.strip().lower()
        if value in _TRUTHY:
            return True
        if value in _FALSY:
            return False
    return None


def active_dsn(dsn: Optional[str] = None) -> Optional[str]:
    return dsn or os.environ.get("ECOLEAK_SQL_DSN") or os.environ.get("ENGINE_DSN")


def load_mock_hotspots(path: Optional[str | Path] = None) -> HotspotDetectionResult:
    source = Path(path) if path is not None else MOCK_HOTSPOTS
    return HotspotDetectionResult.model_validate(json.loads(source.read_text(encoding="utf-8")))


@dataclass
class HotspotSource:
    """Hotspot envelope plus provenance for the integration log / diagnostics."""

    envelope: HotspotDetectionResult
    source: str  # "mock" | "live" | "mock_fallback"
    engine: object | None = None
    warnings: list[str] = field(default_factory=list)


def build_live_engine(dsn: Optional[str] = None, config=None):
    """Build a P3 engine on the flag-gated SQL source (real P2 tables)."""

    from engine.service import build_engine

    return build_engine(use_mock_data=False, dsn=active_dsn(dsn), config=config)


def load_hotspots(
    *,
    use_mock_data: Optional[bool] = None,
    facility_id: Optional[str] = None,
    period_id: Optional[str] = None,
    engine=None,
    dsn: Optional[str] = None,
    fallback_to_mock: bool = True,
    mock_path: Optional[str | Path] = None,
) -> HotspotSource:
    """Flag-gated hotspot envelope: mock JSON or P3's live G output.

    ``fallback_to_mock=True`` preserves the Phase 2 "main stays demo-able" rule:
    if the live path raises, the frozen mock envelope is returned with an
    explicit ``mock_fallback`` provenance and a warning.
    """

    flag = resolve_use_mock_data(use_mock_data)
    live = flag is False or (flag is None and bool(active_dsn(dsn)))
    if not live:
        return HotspotSource(load_mock_hotspots(mock_path), "mock")

    try:
        live_engine = engine or build_live_engine(dsn)
        context = live_engine.default_context()
        resolved_facility = str(facility_id or context["facility_id"])
        resolved_period = str(period_id or context["reporting_period_id"])
        envelope = live_engine.hotspot_result(resolved_facility, resolved_period)
        return HotspotSource(envelope, "live", engine=live_engine)
    except Exception as exc:  # noqa: BLE001 - degrade to the known-good mock
        if not fallback_to_mock:
            raise
        warning = (
            f"live hotspot source failed ({type(exc).__name__}: {exc}); "
            "fell back to mocks/mock_hotspot_output.json"
        )
        return HotspotSource(load_mock_hotspots(mock_path), "mock_fallback", warnings=[warning])


def load_facility_dataset(engine, facility_id: str) -> tuple[Organization | None, Facility, list[Process]]:
    """Organization/facility/processes for the live engine (real data shape)."""

    organization = engine.data_source.get_organization()
    facility = engine.data_source.get_facility(str(facility_id))
    if facility is None:
        raise ValueError(f"facility {facility_id} not found in the live data source")
    processes = engine.data_source.get_processes(str(facility_id))
    return organization, facility, processes


# ---------------------------------------------------------------------------
# Resource emission factors for the deterministic P4 estimator
# ---------------------------------------------------------------------------

_PACKAGING_KEYWORDS = ("ldpe", "packag", "film", "plastic")
_GAS_UNITS = {"m3", "m³"}
_LIQUID_UNITS = {"l", "litre", "liter"}


def _slot_of(factor: EmissionFactor) -> Optional[str]:
    """Map one factor row to the estimator slot it can fill (or None)."""

    category = factor.category.upper()
    unit = (factor.input_unit or "").lower()
    item = f"{factor.item_name} {factor.subcategory or ''}".lower()
    if "recycl" in item:
        return "recycling_processing_emission_factor"
    if category == ActivityCategory.ELECTRICITY.value and unit == "kwh":
        return "electricity_per_kwh"
    if category == ActivityCategory.FUEL.value and unit in _GAS_UNITS and "gas" in item:
        return "natural_gas_per_m3"
    if category == ActivityCategory.FUEL.value and unit in _LIQUID_UNITS and "diesel" in item:
        return "diesel_per_litre"
    if category == ActivityCategory.WATER.value and unit in _GAS_UNITS:
        return "water_per_m3"
    if category == ActivityCategory.WASTE.value and unit == "kg":
        return "waste_per_kg"
    if (
        category == ActivityCategory.MATERIAL.value
        and unit == "kg"
        and any(keyword in item for keyword in _PACKAGING_KEYWORDS)
    ):
        return "packaging_per_kg"
    return None


def _slot_candidates(factors: list[EmissionFactor]) -> dict[str, list[EmissionFactor]]:
    slots: dict[str, list[EmissionFactor]] = {}
    for factor in factors:
        if not factor.active:
            continue
        slot = _slot_of(factor)
        if slot is not None:
            slots.setdefault(slot, []).append(factor)
    return slots


def _factor_rank(factor: EmissionFactor, region_country: Optional[str]) -> tuple:
    region_match = 0
    if region_country and factor.region_country:
        region_match = 1 if factor.region_country.lower() == region_country.lower() else 0
    return (region_match, factor.source_year or 0, factor.version or "")


def _pick_factor(candidates: list[EmissionFactor], region_country: Optional[str]) -> EmissionFactor:
    """Deterministic priority: region > source_year > version > factor_code asc."""

    best_rank = max(_factor_rank(factor, region_country) for factor in candidates)
    tied = [factor for factor in candidates if _factor_rank(factor, region_country) == best_rank]
    return min(tied, key=lambda factor: factor.factor_code)


def factor_selection_notes(
    factors: list[EmissionFactor], region_country: Optional[str] = None
) -> dict[str, list[str]]:
    """Slots with more than one active candidate at the top priority.

    Recorded in the Phase 2 integration log: P4's estimator must not pick
    silently among competing factors (e.g. DEFRA diesel mineral vs biofuel
    blend). The deterministic tie-break is factor_code ascending, but P2 may
    want to mark a preferred factor in the KB.
    """

    notes: dict[str, list[str]] = {}
    for slot, candidates in sorted(_slot_candidates(factors).items()):
        if len(candidates) <= 1:
            continue
        best_rank = max(_factor_rank(factor, region_country) for factor in candidates)
        tied = sorted(
            factor.factor_code
            for factor in candidates
            if _factor_rank(factor, region_country) == best_rank
        )
        if len(tied) > 1:
            notes[slot] = tied
    return notes


def resource_factors_from_factors(
    factors: list[EmissionFactor], region_country: Optional[str] = None
) -> ResourceEmissionFactors:
    """Derive P4 estimator factors from the live versioned factor KB.

    Missing categories stay ``None`` (never fabricated): the estimator then
    falls back to the hotspot-share basis for the affected savings and records
    that in ``impact.assumptions``.
    """

    values = {
        slot: _pick_factor(candidates, region_country).total_co2e_factor
        for slot, candidates in _slot_candidates(factors).items()
    }
    return ResourceEmissionFactors.model_validate(values)


def resource_factors_from_dataset(
    dataset: dict, region_country: Optional[str] = None
) -> ResourceEmissionFactors:
    """Mock-dataset variant (same mapping as the Phase 1 ``_resource_factors``)."""

    factors = [EmissionFactor.model_validate(item) for item in dataset.get("emission_factors", [])]
    return resource_factors_from_factors(factors, region_country=region_country)


# ---------------------------------------------------------------------------
# Live FacilityContext (GA-01/P4-C1 fix)
# ---------------------------------------------------------------------------

_GAS_UNITS = {"m3", "m³", "scm", "nm3"}
_LIQUID_UNITS = {"l", "litre", "liter", "litres", "liters"}
_PACKAGING_HINTS = ("ldpe", "packag", "film", "plastic")


def _resource_slot(activity) -> Optional[str]:
    """Map one live activity row to the FacilityContext resource slot it fills."""
    category = (
        activity.activity_category.value
        if hasattr(activity.activity_category, "value")
        else str(activity.activity_category)
    )
    unit = (activity.normalized_unit or "").strip().lower()
    sub = (activity.activity_subcategory or "").lower()
    if category == ActivityCategory.ELECTRICITY.value and unit == "kwh":
        return "electricity_kwh_per_year"
    if category == ActivityCategory.FUEL.value and unit in _GAS_UNITS:
        return "natural_gas_m3_per_year"
    if category == ActivityCategory.FUEL.value and unit in _LIQUID_UNITS:
        return "diesel_litres_per_year"
    if category == ActivityCategory.WATER.value and (
        "effluent" in sub or "wastewater" in sub or "waste water" in sub
    ) and unit in _GAS_UNITS:
        return "wastewater_m3_per_year"
    if category == ActivityCategory.WATER.value and unit in _GAS_UNITS:
        return "water_m3_per_year"
    if category == ActivityCategory.WASTE.value and unit == "kg":
        return "waste_kg_per_year"
    if (
        category == ActivityCategory.MATERIAL.value
        and unit == "kg"
        and any(hint in sub for hint in _PACKAGING_HINTS)
    ):
        return "packaging_kg_per_year"
    return None


def default_tariffs() -> TariffSet:
    """The documented demo tariff fixture (prices). Quantities come from live
    activity data; only prices remain fixture, surfaced via ``data_is_stub``."""
    raw = json.loads((REPO_ROOT / "p4" / "demo" / "demo_context.json").read_text(encoding="utf-8"))
    return TariffSet.model_validate(raw["tariffs"])


def build_facility_context(engine, facility_id: str, period_id: str) -> FacilityContext:
    """Build a FacilityContext for the REQUESTED facility/period from the live
    data source.

    GA-01 / P4-C1 fix: ``p4/api.py`` previously ranked live hotspots against the
    hardcoded mock demo facility/context, so every non-demo facility failed
    ``p4/engine.py``'s facility-match guard with a 500. Resource baselines are
    now aggregated from real ``activity_data``; tariff prices remain the
    documented demo fixture (``is_fixture=True`` → ``assumptions.data_is_stub``).
    """
    facility = engine.data_source.get_facility(str(facility_id))
    if facility is None:
        raise ValueError(f"facility {facility_id} not found in the live data source")
    processes = engine.data_source.get_processes(str(facility_id))
    name_by_id = {str(process.id): process.name for process in processes}
    activities = engine.data_source.get_activity_data(str(facility_id), str(period_id))
    aggregated: dict[str, dict[str, Decimal]] = {}
    for activity in activities:
        slot = _resource_slot(activity)
        if slot is None or activity.normalized_value is None:
            continue
        key = name_by_id.get(str(activity.process_id), "Unassigned")
        bucket = aggregated.setdefault(key, {})
        bucket[slot] = bucket.get(slot, Decimal("0")) + Decimal(activity.normalized_value)
    baselines = [
        ProcessResourceBaseline(process_name=name, **values)
        for name, values in sorted(aggregated.items())
    ]
    return FacilityContext(
        facility_id=facility.id,
        reporting_period_id=UUID(str(period_id)),
        process_resources=baselines,
        tariffs=default_tariffs(),
        is_fixture=True,
    )
