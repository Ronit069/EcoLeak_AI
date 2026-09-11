"""Module G - Emission Leak-Point / Hotspot Detector.

Composite score (requirements doc §20):

    Hotspot Score = w1(Carbon Contribution) + w2(Carbon Intensity)
                  + w3(Inefficiency) + w4(Waste Ratio) + w5(Improvement Potential)

All weights and thresholds are configurable (see :class:`engine.config.HotspotConfig`).
The engine never hardcodes them.

Graceful behaviour required by the Module G edge-case table:
- total emissions = 0        -> contribution percentage is not computed.
- missing production         -> carbon-intensity component is skipped.
- missing benchmark data     -> the composite renormalizes over the components
                                that are available; ranking never silently breaks.
- tied scores                -> deterministic tie-break (emissions, then name).
- estimated inputs           -> a confidence note is attached to the explanation.
- top actionable hotspot     -> exposed on the analysis wrapper (see
                                :attr:`HotspotAnalysis.top_actionable_hotspot_id`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from contracts.schemas import (
    ActivityCategory,
    HotspotDetectionResult,
    HotspotOutputItem,
    Scope,
)

from .carbon import CarbonInventory
from .config import HotspotConfig, HotspotWeights
from .ids import clamp, deterministic_id, q2, q4, q6, to_decimal

_DEFAULT_BOUNDARY = [Scope.SCOPE_1, Scope.SCOPE_2]


@dataclass
class _Group:
    key: str
    process_id: str | None
    process_name: str
    category_emissions: dict[str, Decimal] = field(default_factory=dict)
    emissions: Decimal = Decimal("0")
    raw_intensity: Decimal | None = None
    intensity_score: Decimal | None = None
    contribution: Decimal | None = None
    inefficiency: Decimal | None = None
    waste_ratio: Decimal | None = None
    improvement: Decimal | None = None
    score: Decimal | None = None
    severity: str = "LOW"
    explanation: str = ""
    component_sources: dict[str, str | None] = field(default_factory=dict)

    @property
    def category(self) -> str:
        if not self.category_emissions:
            return "OTHER"
        return max(self.category_emissions.items(), key=lambda kv: kv[1])[0]


@dataclass
class HotspotAnalysis:
    """Library-level wrapper around the frozen ``HotspotDetectionResult`` shape."""

    result: HotspotDetectionResult
    top_actionable_hotspot_id: str | None
    component_sources: dict[str, dict[str, str | None]] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)


class HotspotDetector:
    """Module G. Deterministic, benchmark-optional composite ranking."""

    def __init__(self, config: HotspotConfig | None = None) -> None:
        self.config = config or HotspotConfig()

    def detect(
        self,
        *,
        facility_id: str,
        reporting_period_id: str,
        inventory: CarbonInventory,
        processes: list,
        interventions: list | None = None,
        scope_boundary: list[Scope] | None = None,
        weights: HotspotWeights | dict | None = None,
        benchmarks: list[dict] | None = None,
        generated_at: datetime | None = None,
        top_n: int | None = None,
    ) -> HotspotAnalysis:
        now = generated_at or datetime.now(timezone.utc)
        boundary = list(scope_boundary or _DEFAULT_BOUNDARY)
        boundary_set = set(boundary)
        config = self.config
        if weights is not None:
            config = config.model_copy(
                update={"weights": weights if isinstance(weights, HotspotWeights) else HotspotWeights(**weights)}
            )

        process_by_id = {str(p.id): p for p in processes}
        interventions = interventions or []
        benchmarks = benchmarks or []

        groups = self._group(inventory, boundary_set, process_by_id)
        total = sum((g.emissions for g in groups.values()), Decimal("0"))

        # 1. raw carbon intensity (kgCO2e per production unit)
        for g in groups.values():
            if inventory.production is not None and inventory.production > 0:
                g.raw_intensity = g.emissions / inventory.production
            else:
                g.raw_intensity = None

        # 2. normalize intensity to 0..100 against the in-set maximum
        max_intensity = max((g.raw_intensity for g in groups.values() if g.raw_intensity is not None), default=None)
        min_intensity = min((g.raw_intensity for g in groups.values() if g.raw_intensity is not None), default=None)
        for g in groups.values():
            if g.raw_intensity is None or max_intensity is None or max_intensity <= 0:
                g.intensity_score = None
            else:
                g.intensity_score = clamp(g.raw_intensity / max_intensity * Decimal("100"))

        # 3. remaining components
        for g in groups.values():
            g.contribution = None if total <= 0 else q4(g.emissions / total * Decimal("100"))
            self._score_inefficiency(g, config, benchmarks, min_intensity, max_intensity)
            self._score_waste_ratio(g, inventory)
            self._score_improvement(g, interventions)
            self._build_explanation(g, boundary)

        # 4. composite + severity
        ranked = self._rank(groups.values(), config)
        ranked = ranked[:top_n] if top_n else ranked

        items: list[HotspotOutputItem] = []
        component_sources: dict[str, dict[str, str | None]] = {}
        for rank, g in enumerate(ranked, start=1):
            items.append(self._to_item(g, rank, facility_id, reporting_period_id, now, config))
            component_sources[g.key] = dict(g.component_sources)

        issues = self._issues(inventory, groups, total)
        top_actionable = next(
            (str(i.id) for i in items
             if i.improvement_potential_score is not None and i.improvement_potential_score > 0),
            str(items[0].id) if items else None,
        )

        result = HotspotDetectionResult(
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            generated_at=now,
            scope_boundary=boundary,
            total_emissions_kgco2e=q6(total),
            data_quality_score=inventory.data_quality_score,
            hotspots=items,
        )
        return HotspotAnalysis(
            result=result,
            top_actionable_hotspot_id=top_actionable,
            component_sources=component_sources,
            issues=issues,
        )

    # -- grouping -----------------------------------------------------------
    def _group(self, inventory: CarbonInventory, boundary: set[Scope], process_by_id: dict) -> dict[str, _Group]:
        groups: dict[str, _Group] = {}
        mode = self.config.group_by
        for record in inventory.records:
            if not record.resolved or record.co2e_kg is None or record.ledger != "SCOPE":
                continue
            if record.scope not in boundary:
                continue
            activity = record.activity
            pid = str(activity.process_id) if activity.process_id else None
            proc = process_by_id.get(pid) if pid else None
            name = proc.name if proc else "Unassigned"
            if mode == "PROCESS":
                key = f"PROCESS:{pid or 'UNASSIGNED'}"
            elif mode == "SOURCE":
                key = f"SOURCE:{activity.source_name or activity.activity_subcategory}"
            else:  # CATEGORY
                key = f"CATEGORY:{activity.activity_category.value}"
                pid, name = None, activity.activity_category.value
            g = groups.get(key)
            if g is None:
                g = _Group(key=key, process_id=pid, process_name=name)
                groups[key] = g
            g.emissions += record.co2e_kg
            cat = activity.activity_category.value
            g.category_emissions[cat] = g.category_emissions.get(cat, Decimal("0")) + record.co2e_kg
        return groups

    # -- component estimators ----------------------------------------------
    def _score_inefficiency(
        self,
        g: _Group,
        config: HotspotConfig,
        benchmarks: list[dict],
        min_intensity: Decimal | None,
        max_intensity: Decimal | None,
    ) -> None:
        strategy = config.inefficiency_strategy
        if strategy == "UNAVAILABLE":
            g.inefficiency = None
            g.component_sources["inefficiency"] = None
            return
        if strategy == "BENCHMARK":
            bench = self._find_benchmark(benchmarks, g)
            if bench is None:
                g.inefficiency = None
                g.component_sources["inefficiency"] = None
                return
            median = to_decimal(bench.get("median"))
            if median is None or median <= 0 or g.raw_intensity is None:
                g.inefficiency = None
                g.component_sources["inefficiency"] = None
                return
            ratio = g.raw_intensity / median
            g.inefficiency = clamp((ratio - Decimal("1")) * Decimal("50"))
            g.component_sources["inefficiency"] = "BENCHMARK"
            return
        # INTENSITY_PROXY: relative internal ranking proxy (no benchmark needed).
        if g.raw_intensity is None or min_intensity is None or max_intensity is None:
            g.inefficiency = None
            g.component_sources["inefficiency"] = None
            return
        span = max_intensity - min_intensity
        if span <= 0:
            g.inefficiency = None
            g.component_sources["inefficiency"] = None
            return
        g.inefficiency = clamp((g.raw_intensity - min_intensity) / span * Decimal("100"))
        g.component_sources["inefficiency"] = "INTENSITY_PROXY_NO_BENCHMARK"

    def _score_waste_ratio(self, g: _Group, inventory: CarbonInventory) -> None:
        if self.config.waste_ratio_strategy == "UNAVAILABLE" or g.process_id is None:
            g.waste_ratio = None
            g.component_sources["waste_ratio"] = None
            return
        waste = inventory.waste_emissions_by_process()
        all_scopes = inventory.process_emissions_all_scopes()
        w = waste.get(g.process_id)
        total_p = all_scopes.get(g.process_id)
        if not w or not total_p or total_p <= 0:
            g.waste_ratio = None
            g.component_sources["waste_ratio"] = None
            return
        g.waste_ratio = clamp(w / total_p * Decimal("100"))
        g.component_sources["waste_ratio"] = "WASTE_PATHWAY_EMISSIONS_RATIO"

    def _score_improvement(self, g: _Group, interventions: list) -> None:
        target = g.process_name.lower()
        category = g.category.lower()
        applicable = []
        for iv in interventions:
            pc = (iv.process_category or "").lower()
            if not pc:
                continue
            if pc in target or target in pc or pc == category:
                applicable.append(iv)
        if not applicable:
            g.improvement = None
            g.component_sources["improvement_potential"] = None
            return
        best_pct = max((to_decimal(iv.expected_co2_reduction_max_pct) or Decimal("0")) for iv in applicable)
        g.improvement = clamp(best_pct / Decimal(str(self.config.improvement_reference_pct)) * Decimal("100"))
        g.component_sources["improvement_potential"] = "APPLICABLE_INTERVENTION_MAX_CO2_PCT"

    @staticmethod
    def _find_benchmark(benchmarks: list[dict], g: _Group) -> dict | None:
        for b in benchmarks:
            pc = str(b.get("process_category") or "").lower()
            metric = str(b.get("metric_name") or "").lower()
            if (pc == g.process_name.lower() or pc == g.category.lower()) and (
                "co2" in metric or "kgco2" in metric or "intensity" in metric
            ):
                return b
        return None

    # -- ranking ------------------------------------------------------------
    def _rank(self, groups, config: HotspotConfig) -> list[_Group]:
        weights = config.weights.as_dict()
        for g in groups:
            components = {
                "carbon_contribution": g.contribution,
                "carbon_intensity": g.intensity_score,
                "inefficiency": g.inefficiency,
                "waste_ratio": g.waste_ratio,
                "improvement_potential": g.improvement,
            }
            available = {k: v for k, v in components.items() if v is not None}
            g.component_sources.update({k: ("COMPUTED" if v is not None else None) for k, v in components.items()
                                        if k not in g.component_sources})
            if not available or len(available) < config.min_components:
                g.score = None
                g.severity = "LOW"
                continue
            if not config.reweight_missing and len(available) < len(components):
                g.score = None
                g.severity = "LOW"
                continue
            total_w = sum(Decimal(str(weights[k])) for k in available)
            if total_w <= 0:
                g.score = None
                g.severity = "LOW"
                continue
            g.score = clamp(
                sum(Decimal(str(weights[k])) * v for k, v in available.items()) / total_w
            )
            g.severity = config.severity.classify(float(g.score))
        return sorted(
            groups,
            key=lambda x: (x.score if x.score is not None else Decimal("-1"), x.emissions, x.process_name),
            reverse=True,
        )

    # -- output -------------------------------------------------------------
    def _build_explanation(self, g: _Group, boundary: list[Scope]) -> None:
        if g.emissions <= 0:
            g.explanation = f"{g.process_name} has no resolved emissions within the scope boundary."
            return
        share = f"{g.contribution:.2f}%" if g.contribution is not None else "n/a"
        scopes = ", ".join(s.value for s in boundary)
        notes = []
        if str(g.component_sources.get("inefficiency") or "").startswith("INTENSITY_PROXY"):
            notes.append("inefficiency is an internal intensity proxy because no benchmark was supplied")
        if g.component_sources.get("improvement_potential"):
            notes.append("improvement potential derived from applicable interventions in the knowledge base")
        suffix = f" Notes: {'; '.join(notes)}." if notes else ""
        g.explanation = (
            f"{g.process_name} emits {g.emissions:,.0f} kgCO2e ({share} of the {scopes} total). "
            f"Dominant activity category: {g.category}. "
            f"Deterministic activity x factor calculation; no estimated value is substituted for a "
            f"missing factor.{suffix}"
        )

    def _to_item(
        self,
        g: _Group,
        rank: int,
        facility_id: str,
        reporting_period_id: str,
        now: datetime,
        config: HotspotConfig,
    ) -> HotspotOutputItem:
        category = g.category
        return HotspotOutputItem(
            id=deterministic_id("hotspot", facility_id, reporting_period_id, g.key),
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            process_id=g.process_id,
            asset_id=None,
            hotspot_type=config.group_by,
            emissions_kgco2e=q6(g.emissions),
            contribution_percent=g.contribution,
            carbon_intensity=q4(g.raw_intensity) if g.raw_intensity is not None else None,
            inefficiency_score=q2(g.inefficiency) if g.inefficiency is not None else None,
            waste_ratio_score=q2(g.waste_ratio) if g.waste_ratio is not None else None,
            improvement_potential_score=q2(g.improvement) if g.improvement is not None else None,
            hotspot_score=q2(g.score) if g.score is not None else None,
            severity=g.severity,
            explanation=g.explanation,
            created_at=now,
            rank=rank,
            process_name=g.process_name,
            activity_category=ActivityCategory(category) if category in ActivityCategory.__members__ else None,
        )

    def _issues(self, inventory: CarbonInventory, groups: dict[str, _Group], total: Decimal) -> list[dict]:
        issues: list[dict] = []
        if total <= 0:
            issues.append(
                {
                    "severity": "WARNING",
                    "code": "ZERO_TOTAL_EMISSIONS",
                    "message": "Total emissions within the scope boundary are zero; contribution percentages omitted.",
                }
            )
        if inventory.production is None or inventory.production <= 0:
            issues.append(
                {
                    "severity": "INFO",
                    "code": "INTENSITY_SKIPPED",
                    "message": "Production is zero or missing; carbon-intensity component skipped.",
                }
            )
        if any(str(g.component_sources.get("inefficiency") or "").startswith("INTENSITY_PROXY") for g in groups.values()):
            issues.append(
                {
                    "severity": "INFO",
                    "code": "BENCHMARK_UNAVAILABLE",
                    "message": "No industry benchmark supplied; inefficiency estimated from internal intensity ranking.",
                }
            )
        issues.extend(u.to_issue() for u in inventory.unresolved)
        return issues
