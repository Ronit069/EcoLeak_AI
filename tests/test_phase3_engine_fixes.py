"""Phase-3 engine fix regression tests (audit-ranked items).

- P3-04: on-site vs captive electricity ledger classification
- P3-02: factor validity window preference + flag
- P3-03: region match preference + flag
- P3-06: fallback match lowers effective confidence
- P3-08: cost price provenance in simulation assumptions
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

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

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)
FID = uuid.uuid4()
PID = uuid.uuid4()


def _facility(country: str = "India", state: str | None = "Gujarat") -> Facility:
    return Facility(
        id=FID, organization_id=uuid.uuid4(), name="Test", country=country, state=state,
        active=True, created_at=NOW, updated_at=NOW,
    )


def _activity(subcategory: str, unit: str = "kWh", category: ActivityCategory = ActivityCategory.ELECTRICITY,
              confidence: Decimal | None = Decimal("90")) -> ActivityData:
    return ActivityData(
        id=uuid.uuid4(), facility_id=FID, reporting_period_id=PID,
        activity_category=category, activity_subcategory=subcategory,
        original_value=Decimal("1000"), original_unit=unit,
        normalized_value=Decimal("1000"), normalized_unit=unit,
        confidence_score=confidence, created_at=NOW,
    )


def _factor(code: str, item: str, *, country: str | None = None, state: str | None = None,
            valid_from: date | None = None, valid_to: date | None = None,
            factor: Decimal = Decimal("0.5"), version: str = "v1") -> EmissionFactor:
    return EmissionFactor(
        id=uuid.uuid4(), factor_code=code, category="ELECTRICITY", subcategory=item,
        item_name=item, region_country=country, region_state=state, scope=Scope.SCOPE_2,
        input_unit="kWh", total_co2e_factor=factor, source_name="test", source_year=2025,
        version=version, active=True, valid_from=valid_from, valid_to=valid_to, created_at=NOW,
    )


def test_p3_04_captive_fossil_is_counted_not_excluded():
    inv = CarbonAccountingEngine().calculate(
        facility=_facility(), reporting_period_id=str(PID),
        activity_data=[_activity("Captive diesel generation")],
        emission_factors=[_factor("EF-CAP", "Captive diesel generation")],
    )
    assert inv.onsite_generation_kgco2e == Decimal("0")
    assert inv.scope2_kgco2e == Decimal("500.000000")  # 1000 kWh * 0.5, counted
    assert inv.records[0].calculation.assumptions["ledger"] == "SCOPE"


def test_p3_04_on_site_self_consumption_and_export_kept_separate():
    inv = CarbonAccountingEngine().calculate(
        facility=_facility(), reporting_period_id=str(PID),
        activity_data=[
            _activity("Solar on-site self-consumption"),
            _activity("Exported electricity to grid"),
        ],
        emission_factors=[
            _factor("EF-ON", "Solar on-site self-consumption"),
            _factor("EF-EX", "Exported electricity to grid"),
        ],
    )
    assert inv.onsite_generation_kgco2e == Decimal("500.000000")
    assert inv.exported_electricity_kgco2e == Decimal("500.000000")
    assert inv.scope2_kgco2e == Decimal("0")


def test_p3_02_prefers_in_window_factor_and_flags_out_of_window():
    in_window = _factor("EF-IN", "Grid electricity", valid_from=date(2025, 1, 1), valid_to=date(2026, 12, 31))
    expired = _factor("EF-OLD", "Grid electricity", valid_from=date(2019, 1, 1), valid_to=date(2020, 12, 31))
    eng = CarbonAccountingEngine()
    inv = eng.calculate(
        facility=_facility(), reporting_period_id=str(PID),
        activity_data=[_activity("Grid electricity")],
        emission_factors=[expired, in_window],
        period_start=date(2025, 4, 1), period_end=date(2026, 3, 31),
    )
    assert inv.records[0].factor.factor_code == "EF-IN"
    assert inv.records[0].calculation.assumptions["factor_validity"] == "IN_WINDOW"


def test_p3_02_out_of_window_only_factor_is_penalised():
    expired = _factor("EF-OLD", "Grid electricity", valid_from=date(2019, 1, 1), valid_to=date(2020, 12, 31))
    eng = CarbonAccountingEngine()
    inv = eng.calculate(
        facility=_facility(), reporting_period_id=str(PID),
        activity_data=[_activity("Grid electricity", confidence=Decimal("90"))],
        emission_factors=[expired],
        period_start=date(2025, 4, 1), period_end=date(2026, 3, 31),
    )
    a = inv.records[0].calculation.assumptions
    assert a["factor_validity"] == "OUT_OF_WINDOW"
    assert a["confidence_penalty"] == 10.0
    assert a["effective_confidence"] == "80.0"


def test_p3_03_prefers_region_match_and_flags_mismatch():
    india = _factor("EF-IN", "Grid electricity", country="India")
    uk = _factor("EF-UK", "Grid electricity", country="United Kingdom")
    eng = CarbonAccountingEngine()
    inv = eng.calculate(
        facility=_facility("India"), reporting_period_id=str(PID),
        activity_data=[_activity("Grid electricity")],
        emission_factors=[uk, india],
    )
    assert inv.records[0].factor.factor_code == "EF-IN"
    assert inv.records[0].calculation.assumptions["factor_region_match"] == "MATCH"

    mismatch_only = eng.calculate(
        facility=_facility("India"), reporting_period_id=str(PID),
        activity_data=[_activity("Grid electricity")],
        emission_factors=[uk],
    )
    a = mismatch_only.records[0].calculation.assumptions
    assert a["factor_region_match"] == "MISMATCH"
    assert a["confidence_penalty"] >= 10.0


def test_p3_06_single_candidate_fallback_lowers_confidence():
    vague = _factor("EF-VAGUE", "Nuclear steam cycle")  # no text overlap with the activity
    eng = CarbonAccountingEngine()
    inv = eng.calculate(
        facility=_facility(), reporting_period_id=str(PID),
        activity_data=[_activity("Grid electricity", confidence=Decimal("90"))],
        emission_factors=[vague],
    )
    a = inv.records[0].calculation.assumptions
    assert a["factor_match_basis"] == "SINGLE_CANDIDATE_CATEGORY_UNIT_FALLBACK"
    assert a["confidence_penalty"] == 15.0
    assert a["effective_confidence"] == "75.0"


def test_p3_08_price_provenance_in_simulation():
    from engine.data_source import load_mock_data_source
    from engine.service import EcoLeakEngine

    eng = EcoLeakEngine(data_source=load_mock_data_source())
    ctx = eng.default_context()
    selections = []
    from engine.simulator import InterventionSelection

    interventions = eng.data_source.get_interventions()[:1]
    selections = [InterventionSelection(intervention=interventions[0], adoption_percentage=Decimal("100"))]
    result = eng.simulate(ctx["facility_id"], ctx["reporting_period_id"], selections, scenario_id="s")
    assumptions = result.interventions[0].assumptions
    assert assumptions["price_source"]
    assert assumptions["price_version"]
    assert assumptions["price_valid_year"]
