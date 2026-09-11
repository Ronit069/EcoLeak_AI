"""Module L - Circularity Score.

An **internal** 0-100 indicator built from recycled input, waste recovery, energy
recovery, water reuse and reuse practices. It is explicitly labelled as an
internal decision metric, never a statutory/certified rating (edge case: "User
interprets score as official certification -> Display disclaimer").

Edge cases handled:
- no baseline data for a component     -> component is ``None``; the total
  renormalizes over available components only if the methodology permits it
  (``reweight_missing``); otherwise the score is marked incomplete.
- score > 100 / < 0                    -> clamped/capped (defect guard).
- same waste counted in reuse+recycling -> the two components are measured on
  disjoint activity sets (recycled *input* vs recovered *waste*), never summed.
- methodology updates                  -> ``methodology_version`` is versioned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from contracts.schemas import ActivityData

from .carbon import CarbonInventory
from .config import CircularityConfig
from .ids import clamp, q2, to_decimal

_RECYCLED_KEYWORDS = ("recycl", "reclaim", "regenerat", "secondary material", "post-consumer")
_VIRGIN_KEYWORDS = ("virgin", "primary", "fresh")
_RECOVERY_KEYWORDS = ("recycl", "reuse", "recover", "compost", "repair", "upcycl")
_LANDFILL_KEYWORDS = ("landfill", "open disposal", "disposal", "incinerat", "dump")
_WATER_REUSE_KEYWORDS = ("reuse", "recycl", "reclaim", "recirculat", "water loop")
_ENERGY_RECOVERY_KEYWORDS = ("waste heat", "heat recovery", "recover", "onsite solar", "on-site solar", "captive")


@dataclass
class CircularityScoreResult:
    recycled_input_score: Decimal | None
    waste_recovery_score: Decimal | None
    energy_recovery_score: Decimal | None
    water_reuse_score: Decimal | None
    reuse_score: Decimal | None
    total_score: Decimal | None
    methodology_version: str
    calculated_at: datetime
    is_internal_metric: bool = True
    score_complete: bool = True
    disclaimer: str = ""
    component_sources: dict[str, str | None] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """L1 response shape plus the mandatory internal-metric labelling."""
        return {
            # ---- frozen L1 contract keys ----
            "recycled_input_score": self.recycled_input_score,
            "waste_recovery_score": self.waste_recovery_score,
            "energy_recovery_score": self.energy_recovery_score,
            "water_reuse_score": self.water_reuse_score,
            "reuse_score": self.reuse_score,
            "total_score": self.total_score,
            "methodology_version": self.methodology_version,
            "calculated_at": self.calculated_at,
            # ---- required labelling / diagnostics ----
            "is_internal_metric": True,
            "not_a_certified_standard": True,
            "disclaimer": self.disclaimer,
            "score_complete": self.score_complete,
            "component_sources": self.component_sources,
            "issues": self.issues,
        }


def _text(activity: ActivityData) -> str:
    return f"{activity.activity_subcategory} {activity.source_name or ''} {activity.notes or ''}".lower()


def _quantity(activity: ActivityData) -> Decimal | None:
    value = activity.normalized_value if activity.normalized_value is not None else activity.original_value
    return to_decimal(value)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


class CircularityEngine:
    """Module L. Deterministic internal score."""

    def __init__(self, config: CircularityConfig | None = None) -> None:
        self.config = config or CircularityConfig()

    def calculate(
        self,
        *,
        inventory: CarbonInventory,
        activity_data: list[ActivityData],
        generated_at: datetime | None = None,
    ) -> CircularityScoreResult:
        now = generated_at or datetime.now(timezone.utc)
        components: dict[str, Decimal | None] = {
            "recycled_input": self._recycled_input(activity_data),
            "waste_recovery": self._waste_recovery(inventory, activity_data),
            "energy_recovery": self._energy_recovery(activity_data),
            "water_reuse": self._water_reuse(activity_data),
            "reuse": self._reuse(activity_data),
        }
        sources = {
            key: ("COMPUTED" if value is not None else "NO_BASELINE_DATA")
            for key, value in components.items()
        }
        available = {k: v for k, v in components.items() if v is not None}
        issues: list[dict] = []
        complete = True

        if not available:
            total = None
            complete = False
            issues.append(
                {
                    "severity": "WARNING",
                    "code": "CIRCULARITY_INCOMPLETE",
                    "message": "No baseline data available for any circularity component; score incomplete.",
                }
            )
        else:
            weights = self.config.weights.as_dict()
            missing = [k for k in components if k not in available]
            if missing and not self.config.reweight_missing:
                total = None
                complete = False
                issues.append(
                    {
                        "severity": "WARNING",
                        "code": "CIRCULARITY_INCOMPLETE",
                        "message": f"Missing components {missing}; methodology does not permit reweighting.",
                    }
                )
            else:
                total_w = sum(Decimal(str(weights[k])) for k in available)
                total = clamp(
                    sum(Decimal(str(weights[k])) * v for k, v in available.items()) / total_w
                )
                if missing:
                    complete = False
                    issues.append(
                        {
                            "severity": "INFO",
                            "code": "CIRCULARITY_PARTIAL",
                            "message": (
                                f"Components {missing} have no baseline data; remaining weights renormalized. "
                                "Reported as incomplete."
                            ),
                        }
                    )

        if total is not None and (total < 0 or total > 100):
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "CIRCULARITY_OUT_OF_RANGE",
                    "message": "Computed score fell outside 0..100 and was clamped (calculation defect guard).",
                }
            )
            total = clamp(total)

        return CircularityScoreResult(
            recycled_input_score=q2(available.get("recycled_input")) if "recycled_input" in available else None,
            waste_recovery_score=q2(available.get("waste_recovery")) if "waste_recovery" in available else None,
            energy_recovery_score=q2(available.get("energy_recovery")) if "energy_recovery" in available else None,
            water_reuse_score=q2(available.get("water_reuse")) if "water_reuse" in available else None,
            reuse_score=q2(available.get("reuse")) if "reuse" in available else None,
            total_score=q2(total) if total is not None else None,
            methodology_version=self.config.methodology_version,
            calculated_at=now,
            is_internal_metric=True,
            score_complete=complete,
            disclaimer=self.config.disclaimer,
            component_sources=sources,
            issues=issues,
        )

    # -- components ---------------------------------------------------------
    @staticmethod
    def _recycled_input(activity_data: list[ActivityData]) -> Decimal | None:
        rows = [a for a in activity_data if a.activity_category.value == "MATERIAL"]
        if not rows:
            return None
        total = Decimal("0")
        recycled = Decimal("0")
        for a in rows:
            qty = _quantity(a)
            if qty is None:
                continue
            total += qty
            if _contains_any(_text(a), _RECYCLED_KEYWORDS):
                recycled += qty
        if total <= 0:
            return None
        return clamp(recycled / total * Decimal("100"))

    @staticmethod
    def _waste_recovery(inventory: CarbonInventory, activity_data: list[ActivityData]) -> Decimal | None:
        rows = [a for a in activity_data if a.activity_category.value == "WASTE"]
        if not rows:
            return None
        # Prefer emission-weighted recovery (unit-safe); fall back to quantity.
        weights: dict[str, Decimal] = {}
        for r in inventory.records:
            if r.co2e_kg is None or r.activity.activity_category.value != "WASTE":
                continue
            weights[str(r.activity.id)] = r.co2e_kg
        total = Decimal("0")
        recovered = Decimal("0")
        for a in rows:
            w = weights.get(str(a.id))
            if w is not None and w > 0:
                total += w
                if _contains_any(_text(a), _RECOVERY_KEYWORDS) and not _contains_any(_text(a), _LANDFILL_KEYWORDS):
                    recovered += w
                continue
            qty = _quantity(a)
            if qty is None:
                continue
            total += qty
            if _contains_any(_text(a), _RECOVERY_KEYWORDS) and not _contains_any(_text(a), _LANDFILL_KEYWORDS):
                recovered += qty
        if total <= 0:
            return None
        return clamp(recovered / total * Decimal("100"))

    @staticmethod
    def _energy_recovery(activity_data: list[ActivityData]) -> Decimal | None:
        rows = [a for a in activity_data if a.activity_category.value in {"ELECTRICITY", "FUEL", "STEAM"}]
        if not rows:
            return None
        total = Decimal("0")
        recovered = Decimal("0")
        for a in rows:
            qty = _quantity(a)
            if qty is None:
                continue
            total += qty
            if _contains_any(_text(a), _ENERGY_RECOVERY_KEYWORDS):
                recovered += qty
        if total <= 0:
            return None
        return clamp(recovered / total * Decimal("100"))

    @staticmethod
    def _water_reuse(activity_data: list[ActivityData]) -> Decimal | None:
        rows = [a for a in activity_data if a.activity_category.value == "WATER"]
        if not rows:
            return None
        total = Decimal("0")
        reused = Decimal("0")
        for a in rows:
            qty = _quantity(a)
            if qty is None:
                continue
            total += qty
            if _contains_any(_text(a), _WATER_REUSE_KEYWORDS):
                reused += qty
        if total <= 0:
            return None
        return clamp(reused / total * Decimal("100"))

    @staticmethod
    def _reuse(activity_data: list[ActivityData]) -> Decimal | None:
        rows = [a for a in activity_data if a.activity_category.value in {"MATERIAL", "WASTE", "WATER", "STEAM"}]
        if not rows:
            return None
        total = Decimal("0")
        reused = Decimal("0")
        for a in rows:
            qty = _quantity(a)
            if qty is None:
                continue
            total += qty
            if _contains_any(_text(a), ("reuse", "reused", "repair", "refill", "returnable", "recirculat")):
                reused += qty
        if total <= 0:
            return None
        return clamp(reused / total * Decimal("100"))
