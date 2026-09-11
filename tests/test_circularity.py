from __future__ import annotations

from decimal import Decimal

from contracts.schemas import Facility, PeriodType, ReportingPeriod
from engine.data_source import InMemoryDataSource
from engine.service import EcoLeakEngine


def test_mock_circularity_is_internal_and_in_range(mock_engine):
    engine, facility_id, period_id = mock_engine
    result = engine.circularity_score(facility_id, period_id)
    payload = result.to_dict()
    assert payload["is_internal_metric"] is True
    assert payload["not_a_certified_standard"] is True
    assert payload["disclaimer"]
    assert Decimal("0") <= result.total_score <= Decimal("100")
    for key in (
        "recycled_input_score",
        "waste_recovery_score",
        "energy_recovery_score",
        "water_reuse_score",
        "reuse_score",
        "total_score",
        "methodology_version",
        "calculated_at",
    ):
        assert key in payload


def test_virgin_landfill_fixture_is_low_circularity(mock_engine):
    engine, facility_id, period_id = mock_engine
    result = engine.circularity_score(facility_id, period_id)
    # All inputs are virgin and waste is landfilled; the internal score must be low.
    assert result.total_score is not None
    assert result.total_score < Decimal("25")


def test_no_baseline_data_marks_score_incomplete():
    from datetime import datetime, timezone

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    facility = Facility(
        id="22222222-2222-4222-8222-222222222222",
        organization_id="44444444-4444-4444-8444-444444444444",
        name="Empty",
        country="India",
        created_at=now,
        updated_at=now,
    )
    period = ReportingPeriod(
        id="33333333-3333-4333-8333-333333333333",
        facility_id=facility.id,
        period_type=PeriodType.ANNUAL,
        start_date=now.date(),
        end_date=now.date(),
        created_at=now,
    )
    ds = InMemoryDataSource(facilities=[facility], reporting_periods=[period], activity_data=[])
    engine = EcoLeakEngine(data_source=ds)
    result = engine.circularity_score(str(facility.id), str(period.id))
    assert result.total_score is None
    assert result.score_complete is False
    assert any(i["code"] == "CIRCULARITY_INCOMPLETE" for i in result.issues)
