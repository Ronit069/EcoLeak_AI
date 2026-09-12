"""High-level engine facade.

Wraps the swappable :class:`~engine.data_source.ActivityDataSource` and the four
modules into one callable object. This is the object P2 can call server-side and
that the optional FastAPI layer exposes.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from contracts.schemas import HotspotDetectionResult, Scope

from .anomaly import AnomalyDetector, AnomalyResult, PeriodFeatures
from .carbon import CarbonAccountingEngine, CarbonInventory
from .circularity import CircularityEngine, CircularityScoreResult
from .config import EngineConfig, HotspotWeights
from .data_source import ActivityDataSource, load_mock_data_source
from .errors import EntityNotFoundError
from .hotspots import HotspotAnalysis, HotspotDetector
from .simulator import ImpactSimulator, InterventionSelection, SimulationResult


class EcoLeakEngine:
    """Facade over Modules F, G, K, L (and H)."""

    def __init__(self, data_source: ActivityDataSource | None = None, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self.data_source = data_source or load_mock_data_source()
        self.carbon = CarbonAccountingEngine(self.config)
        self.hotspots = HotspotDetector(self.config.hotspot)
        self.simulator = ImpactSimulator(self.config.simulator)
        self.circularity = CircularityEngine(self.config.circularity)
        self.anomaly = AnomalyDetector(self.config.anomaly)
        self._inventory_cache: dict[tuple[str, str], CarbonInventory] = {}

    # -- context ------------------------------------------------------------
    def facility(self, facility_id: str):
        facility = self.data_source.get_facility(facility_id)
        if facility is None:
            raise EntityNotFoundError("Facility not found.", {"facility_id": facility_id})
        return facility

    def reporting_period(self, period_id: str):
        period = self.data_source.get_reporting_period(period_id)
        if period is None:
            raise EntityNotFoundError("Reporting period not found.", {"reporting_period_id": period_id})
        return period

    def default_context(self) -> dict:
        facilities = self.data_source.list_facilities()
        if not facilities:
            raise EntityNotFoundError("No facilities available in the data source.")
        facility = facilities[0]
        periods = self.data_source.list_reporting_periods(str(facility.id))
        period_id = str(periods[0].id) if periods else None
        return {"facility_id": str(facility.id), "reporting_period_id": period_id}

    # -- Module F -----------------------------------------------------------
    def calculate_inventory(
        self,
        facility_id: str,
        reporting_period_id: str,
        *,
        generated_at: datetime | None = None,
        use_cache: bool = False,
    ) -> CarbonInventory:
        if use_cache and (facility_id, reporting_period_id) in self._inventory_cache:
            return self._inventory_cache[(facility_id, reporting_period_id)]
        facility = self.facility(facility_id)
        activity = self.data_source.get_activity_data(facility_id, reporting_period_id)
        factors = self.data_source.get_emission_factors()
        inventory = self.carbon.calculate(
            facility=facility,
            reporting_period_id=reporting_period_id,
            activity_data=activity,
            emission_factors=factors,
            generated_at=generated_at,
        )
        self._inventory_cache[(facility_id, reporting_period_id)] = inventory
        return inventory

    def inventory_summary(self, facility_id: str, reporting_period_id: str, **kwargs) -> dict:
        return self.calculate_inventory(facility_id, reporting_period_id, **kwargs).inventory_summary()

    # -- Module G -----------------------------------------------------------
    def detect_hotspots(
        self,
        facility_id: str,
        reporting_period_id: str,
        *,
        scope_boundary: list[Scope] | None = None,
        weights: HotspotWeights | dict | None = None,
        top_n: int | None = None,
        generated_at: datetime | None = None,
        inventory: CarbonInventory | None = None,
    ) -> HotspotAnalysis:
        inventory = inventory or self.calculate_inventory(facility_id, reporting_period_id, generated_at=generated_at)
        processes = self.data_source.get_processes(facility_id)
        interventions = self.data_source.get_interventions()
        benchmarks = self.data_source.get_benchmarks(facility_id)
        return self.hotspots.detect(
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            inventory=inventory,
            processes=processes,
            interventions=interventions,
            scope_boundary=scope_boundary,
            weights=weights,
            benchmarks=benchmarks,
            generated_at=generated_at,
            top_n=top_n,
        )

    def hotspot_result(self, facility_id: str, reporting_period_id: str, **kwargs) -> HotspotDetectionResult:
        return self.detect_hotspots(facility_id, reporting_period_id, **kwargs).result

    # -- Module K -----------------------------------------------------------
    def simulate(
        self,
        facility_id: str,
        reporting_period_id: str,
        selections: list[InterventionSelection],
        *,
        scenario_id: str | None = None,
        budget_limit: Decimal | None = None,
        target_reduction_pct: Decimal | None = None,
        scope_boundary: set[Scope] | None = None,
        generated_at: datetime | None = None,
        inventory: CarbonInventory | None = None,
    ) -> SimulationResult:
        inventory = inventory or self.calculate_inventory(facility_id, reporting_period_id, generated_at=generated_at)
        processes = self.data_source.get_processes(facility_id)
        return self.simulator.simulate(
            inventory=inventory,
            selections=selections,
            scenario_id=scenario_id,
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            budget_limit=budget_limit,
            target_reduction_pct=target_reduction_pct,
            scope_boundary=scope_boundary,
            processes=processes,
            generated_at=generated_at,
        )

    # -- Module L -----------------------------------------------------------
    def circularity_score(
        self,
        facility_id: str,
        reporting_period_id: str,
        *,
        generated_at: datetime | None = None,
        inventory: CarbonInventory | None = None,
    ) -> CircularityScoreResult:
        inventory = inventory or self.calculate_inventory(facility_id, reporting_period_id, generated_at=generated_at)
        activity = self.data_source.get_activity_data(facility_id, reporting_period_id)
        return self.circularity.calculate(inventory=inventory, activity_data=activity, generated_at=generated_at)

    # -- Module H -----------------------------------------------------------
    def anomalies(
        self,
        facility_id: str,
        reporting_period_id: str,
        *,
        history_inventories: list[CarbonInventory] | None = None,
        generated_at: datetime | None = None,
    ) -> AnomalyResult:
        if history_inventories is None:
            history_inventories = [self.calculate_inventory(facility_id, reporting_period_id, generated_at=generated_at)]
        features: list[PeriodFeatures] = []
        for inv in history_inventories:
            features.extend(self.anomaly.features_from_inventory(inv))
        return self.anomaly.detect(
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            history=features,
            generated_at=generated_at,
        )


def build_engine(
    *,
    use_mock_data: bool | None = None,
    dsn: str | None = None,
    config: EngineConfig | None = None,
) -> EcoLeakEngine:
    """Phase 2 bootstrap: build an engine behind the ``USE_MOCK_DATA`` gate.

    - ``use_mock_data`` defaults to the ``ECOLEAK_USE_MOCK_DATA`` env var, then to
      the legacy DSN-presence rule (see :func:`engine.data_source.default_data_source`).
    - Passing ``dsn`` explicitly selects the SQL source unless the flag forces mock.
    - Default (nothing set) stays on the Phase 1 mock fixture so ``main`` remains
      demo-able without a database.
    """
    from .data_source import default_data_source, load_mock_data_source, resolve_use_mock_data

    if dsn is not None:
        if resolve_use_mock_data(use_mock_data) is True:
            source = load_mock_data_source()
        else:
            from .sql_source import load_sql_data_source

            source = load_sql_data_source(dsn)
    else:
        source = default_data_source(use_mock_data)
    return EcoLeakEngine(data_source=source, config=config)
