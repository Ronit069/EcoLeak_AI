from __future__ import annotations

from decimal import Decimal

from engine import anomaly as anomaly_module
from engine.anomaly import AnomalyDetector, PeriodFeatures


def _features(normal_count: int, outlier: bool):
    rows = []
    for i in range(normal_count):
        rows.append(
            PeriodFeatures(
                period_id=f"2025-{i + 1:02d}",
                process_id="proc-1",
                energy_kwh=Decimal("100") + Decimal(i % 3),
                carbon_kg=Decimal("50") + Decimal(i % 2),
                waste_kg=Decimal("5"),
                production=Decimal("10"),
            )
        )
    if outlier:
        rows.append(
            PeriodFeatures(
                period_id="2025-13",
                process_id="proc-1",
                energy_kwh=Decimal("10000"),
                carbon_kg=Decimal("9000"),
                waste_kg=Decimal("800"),
                production=Decimal("10"),
            )
        )
    return rows


def test_insufficient_history_uses_rules_only():
    detector = AnomalyDetector()
    result = detector.detect(facility_id="f", reporting_period_id="p", history=_features(3, outlier=False))
    assert result.ml_used is False
    assert result.model_name == "rules-only"
    assert result.confidence_score is None
    assert any(i["code"] == "INSUFFICIENT_HISTORY" for i in result.issues)


def test_ml_used_with_enough_history_and_flags_outlier():
    detector = AnomalyDetector()
    result = detector.detect(facility_id="f", reporting_period_id="p", history=_features(20, outlier=True))
    assert result.ml_used is True
    assert any(a["is_anomaly"] for a in result.anomalies)
    assert result.confidence_score is not None


def test_confidence_never_high_with_small_history():
    detector = AnomalyDetector()
    result = detector.detect(facility_id="f", reporting_period_id="p", history=_features(10, outlier=False))
    assert result.ml_used is True
    assert result.confidence_score is not None
    assert result.confidence_score <= Decimal("90")


def test_sklearn_absent_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(anomaly_module, "HAS_SKLEARN", False)
    detector = AnomalyDetector()
    result = detector.detect(facility_id="f", reporting_period_id="p", history=_features(30, outlier=True))
    assert result.ml_used is False
    assert result.model_name == "rules-only"
