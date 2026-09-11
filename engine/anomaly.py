"""Module H (stretch) - Anomaly & Inefficiency Detector.

Uses ``sklearn.ensemble.IsolationForest`` over Energy / Carbon / Waste intensity
features. This is the ONLY module in the engine permitted to use ML (architecture
doc §36). If scikit-learn is unavailable, or there is too little history, the
detector returns **rules-only** results and never claims ML certainty
(edge case: "Too little historical data -> Disable ML anomaly claim; use rules
only"). No LLM is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from .carbon import CarbonInventory
from .config import AnomalyConfig
from .ids import clamp, deterministic_id, q2, q6, to_decimal, percentile

try:  # pragma: no cover - import guard
    from sklearn.ensemble import IsolationForest  # type: ignore

    HAS_SKLEARN = True
except Exception:  # noqa: BLE001
    HAS_SKLEARN = False
    IsolationForest = None  # type: ignore


@dataclass
class PeriodFeatures:
    period_id: str
    process_id: str | None
    energy_kwh: Decimal
    carbon_kg: Decimal
    waste_kg: Decimal
    production: Decimal | None
    activity_data_id: str | None = None


@dataclass
class AnomalyResult:
    facility_id: str
    reporting_period_id: str
    anomalies: list[dict]
    ml_used: bool
    confidence_score: Decimal | None
    model_name: str
    model_version: str
    generated_at: datetime
    issues: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "facility_id": self.facility_id,
            "reporting_period_id": self.reporting_period_id,
            "ml_used": self.ml_used,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "confidence_score": q2(self.confidence_score) if self.confidence_score is not None else None,
            "generated_at": self.generated_at.isoformat(),
            "anomalies": self.anomalies,
            "issues": self.issues,
        }


class AnomalyDetector:
    """Module H. ML when history permits, deterministic rules otherwise."""

    def __init__(self, config: AnomalyConfig | None = None) -> None:
        self.config = config or AnomalyConfig()

    def detect(
        self,
        *,
        facility_id: str,
        reporting_period_id: str,
        history: list[PeriodFeatures],
        generated_at: datetime | None = None,
    ) -> AnomalyResult:
        now = generated_at or datetime.now(timezone.utc)
        valid = [
            h for h in history
            if h.production is not None and h.production > 0 and h.carbon_kg >= 0
        ]
        issues: list[dict] = []
        if len(valid) < self.config.min_samples_for_ml or not HAS_SKLEARN:
            reason = (
                "scikit-learn is not installed" if not HAS_SKLEARN
                else f"only {len(valid)} historical samples (< {self.config.min_samples_for_ml})"
            )
            issues.append(
                {
                    "severity": "INFO",
                    "code": "INSUFFICIENT_HISTORY",
                    "message": f"ML anomaly detection disabled ({reason}); rules-only results returned.",
                }
            )
            anomalies = self._rules_only(facility_id, reporting_period_id, valid, now)
            return AnomalyResult(
                facility_id=facility_id,
                reporting_period_id=reporting_period_id,
                anomalies=anomalies,
                ml_used=False,
                confidence_score=None,
                model_name="rules-only",
                model_version="rules-1.0",
                generated_at=now,
                issues=issues,
            )

        matrix = [
            [float(h.energy_kwh / h.production), float(h.carbon_kg / h.production), float(h.waste_kg / h.production)]
            for h in valid  # type: ignore[operator]
        ]
        model = IsolationForest(
            n_estimators=100,
            contamination=self.config.contamination,
            random_state=self.config.random_state,
        )
        model.fit(matrix)
        raw_scores = [-s for s in model.score_samples(matrix)]
        lo, hi = min(raw_scores), max(raw_scores)
        span = (hi - lo) or 1.0
        predictions = model.predict(matrix)
        anomaly_scores = [clamp(Decimal(str((s - lo) / span * 100))) for s in raw_scores]
        threshold = to_decimal(percentile([to_decimal(s) for s in anomaly_scores], 100 * (1 - self.config.contamination)))
        if threshold is None:
            threshold = Decimal("50")
        confidence = self._confidence(len(valid))

        anomalies = []
        for h, score, pred in zip(valid, anomaly_scores, predictions):
            is_anomaly = bool(pred == -1)
            anomalies.append(
                {
                    "id": deterministic_id("anomaly", facility_id, h.period_id, h.process_id or "UNASSIGNED"),
                    "process_id": h.process_id,
                    "activity_data_id": h.activity_data_id,
                    "model_name": self.config.model_name,
                    "model_version": self.config.model_version,
                    "anomaly_score": str(q2(score)),
                    "threshold": str(q2(threshold)),
                    "is_anomaly": is_anomaly,
                    "explanation": (
                        "Energy/Carbon/Waste intensity combination is an IsolationForest outlier versus history."
                        if is_anomaly
                        else "Intensity combination is within the modelled normal range."
                    ),
                    "confidence_score": str(q2(confidence)),
                    "detected_at": now.isoformat(),
                }
            )
        return AnomalyResult(
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            anomalies=anomalies,
            ml_used=True,
            confidence_score=confidence,
            model_name=self.config.model_name,
            model_version=self.config.model_version,
            generated_at=now,
            issues=issues,
        )

    # -- rules fallback -----------------------------------------------------
    def _rules_only(
        self, facility_id: str, reporting_period_id: str, valid: list[PeriodFeatures], now: datetime
    ) -> list[dict]:
        if not valid:
            return []
        carbon_intensities = [h.carbon_kg / h.production for h in valid]  # type: ignore[operator]
        median = percentile(carbon_intensities, 50)
        out: list[dict] = []
        for h in valid:
            intensity = h.carbon_kg / h.production  # type: ignore[operator]
            extreme = median > 0 and intensity > median * Decimal("2")
            out.append(
                {
                    "id": deterministic_id("anomaly-rules", facility_id, h.period_id, h.process_id or "UNASSIGNED"),
                    "process_id": h.process_id,
                    "activity_data_id": h.activity_data_id,
                    "model_name": "rules-only",
                    "model_version": "rules-1.0",
                    "anomaly_score": None,
                    "threshold": None,
                    "is_anomaly": bool(extreme),
                    "explanation": (
                        "Carbon intensity exceeds 2x the available historical median (rules-only; "
                        "insufficient history for ML)." if extreme
                        else "Rules-only check: no threshold breach. ML not claimed with insufficient history."
                    ),
                    "confidence_score": None,
                    "detected_at": now.isoformat(),
                }
            )
        return out

    @staticmethod
    def _confidence(samples: int) -> Decimal:
        # Deliberately conservative: never HIGH with a small history.
        score = min(Decimal("90"), Decimal("40") + Decimal(samples) * Decimal("2"))
        return q2(clamp(score))

    # -- feature construction ----------------------------------------------
    @staticmethod
    def features_from_inventory(inventory: CarbonInventory) -> list[PeriodFeatures]:
        by_process: dict[str | None, PeriodFeatures] = {}
        for record in inventory.records:
            if not record.resolved or record.co2e_kg is None:
                continue
            pid = str(record.activity.process_id) if record.activity.process_id else None
            key = pid
            f = by_process.get(key)
            if f is None:
                f = PeriodFeatures(
                    period_id=inventory.reporting_period_id,
                    process_id=pid,
                    energy_kwh=Decimal("0"),
                    carbon_kg=Decimal("0"),
                    waste_kg=Decimal("0"),
                    production=inventory.production,
                )
                by_process[key] = f
            f.carbon_kg += record.co2e_kg
            qty = record.activity.normalized_value or Decimal("0")
            if record.activity.activity_category.value in {"ELECTRICITY", "FUEL", "STEAM"}:
                f.energy_kwh += qty
            elif record.activity.activity_category.value == "WASTE":
                f.waste_kg += qty
        return list(by_process.values())
