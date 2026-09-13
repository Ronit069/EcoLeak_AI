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
        # P3-02: pass the period window so out-of-window factors are de-prioritised
        # and flagged (tolerate a missing period so ad-hoc calls still work).
        period = self.data_source.get_reporting_period(reporting_period_id)
        inventory = self.carbon.calculate(
            facility=facility,
            reporting_period_id=reporting_period_id,
            activity_data=activity,
            emission_factors=factors,
            generated_at=generated_at,
            period_start=getattr(period, "start_date", None),
            period_end=getattr(period, "end_date", None),
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
    # H2/H3 (history + acknowledge): session-scoped registry. The engine
    # detects anomalies on demand; this registry stores the most recent
    # detection per (facility, period) so H2 can serve history and H3 can
    # ACK/confirm before any downstream consumer may act on an anomaly.
    # NOTE (H3 trace): nothing in the current codebase auto-adjusts or
    # flags anomalies downstream; the acknowledge gate therefore protects
    # future consumers. Persistence is Phase-4 backlog (owner P3).
    _anomaly_registry: dict[tuple[str, str], tuple[AnomalyResult, datetime]] = {}
    _anomaly_ack: dict[str, dict] = {}  # anomaly_id -> {note, acknowledged_at}

    def anomalies(
        self,
        facility_id: str,
        reporting_period_id: str,
        *,
        history_inventories: list[CarbonInventory] | None = None,
        generated_at: datetime | None = None,
        store: bool = True,
    ) -> AnomalyResult:
        if history_inventories is None:
            history_inventories = [self.calculate_inventory(facility_id, reporting_period_id, generated_at=generated_at)]
        features: list[PeriodFeatures] = []
        for inv in history_inventories:
            features.extend(self.anomaly.features_from_inventory(inv))
        result = self.anomaly.detect(
            facility_id=facility_id,
            reporting_period_id=reporting_period_id,
            history=features,
            generated_at=generated_at,
        )
        if store:
            now = result.generated_at
            self._anomaly_registry[(facility_id, reporting_period_id)] = (result, now)
        return result

    def list_anomalies(self, facility_id: str, reporting_period_id: str) -> dict:
        """H2: latest stored detection for a facility/period, ACK state merged."""
        entry = self._anomaly_registry.get((facility_id, reporting_period_id))
        if entry is None:
            raise EntityNotFoundError(
                "No anomaly detection stored for this facility/period; run detect first",
                {"facility_id": facility_id, "reporting_period_id": reporting_period_id},
            )
        result, _ = entry
        payload = result.to_dict()
        merged: list[dict] = []
        for a in payload.get("anomalies", []):
            aid = str(a.get("id") or a.get("anomaly_id") or "/")
            ack = self._anomaly_ack.get(aid)
            row = dict(a)
            row["acknowledged"] = bool(ack)
            if ack:
                row["acknowledged_note"] = ack.get("note")
                row["acknowledged_at"] = ack.get("acknowledged_at")
            merged.append(row)
        return {**payload, "anomalies": merged}

    def acknowledge_anomaly(self, anomaly_id: str, *, note: str | None = None) -> dict:
        """H3: mark an anomaly acknowledged (=='confirmed/seen') before any
        downstream consumer may act on it. Requires the anomaly to exist in
        the registry; tenant ownership is enforced by the route layer via the
        facility resolution guard."""
        for (facility_id, period_id), (result, _) in self._anomaly_registry.items():
            for a in result.anomalies:
                aid = str(a.get("id") or a.get("anomaly_id"))
                if aid == anomaly_id:
                    from datetime import datetime as _dt, timezone as _tz
                    self._anomaly_ack[anomaly_id] = {
                        "note": note,
                        "acknowledged_at": _dt.now(_tz.utc).isoformat(),
                        "facility_id": facility_id,
                        "reporting_period_id": period_id,
                    }
                    return self._anomaly_ack[anomaly_id]
        raise EntityNotFoundError("Unknown anomaly id", {"anomaly_id": anomaly_id})

    def resolve_anomaly_facility(self, anomaly_id: str) -> str:
        """Tenant-resolution step for H3: return the owning facility WITHOUT
        writing any state (so a cross-tenant PATCH cannot mutate as a side
        effect of failing auth)."""
        for (facility_id, _period_id), (result, _) in self._anomaly_registry.items():
            for a in result.anomalies:
                aid = str(a.get("id") or a.get("anomaly_id"))
                if aid == anomaly_id:
                    return facility_id
        raise EntityNotFoundError("Unknown anomaly id", {"anomaly_id": anomaly_id})


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
