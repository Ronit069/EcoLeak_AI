"""Swappable data access layer.

P3 builds against ``mocks/mock_dataset.json`` today; when P2's ingestion API is
live, only a new implementation of :class:`ActivityDataSource` is required. The
calculation, hotspot, simulator and circularity logic never imports the mock
file directly - it only talks to this interface, which is typed with the frozen
contract models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from contracts.schemas import (  # noqa: E402  (project root added by engine/__init__)
    ActivityData,
    CircularIntervention,
    EmissionFactor,
    Facility,
    Organization,
    Process,
    ReportingPeriod,
)

_DEFAULT_MOCK = Path(__file__).resolve().parent.parent / "mocks" / "mock_dataset.json"


@runtime_checkable
class ActivityDataSource(Protocol):
    """Read-only feed of facility activity data + emission factors.

    Implementations may be backed by the Phase 0 JSON mock or by P2's REST API.
    Every method returns frozen contract models, never ad-hoc dicts.
    """

    def get_organization(self) -> Organization | None: ...

    def get_facility(self, facility_id: str) -> Facility | None: ...

    def get_reporting_period(self, period_id: str) -> ReportingPeriod | None: ...

    def list_reporting_periods(self, facility_id: str) -> list[ReportingPeriod]: ...

    def get_processes(self, facility_id: str) -> list[Process]: ...

    def get_activity_data(
        self,
        facility_id: str,
        reporting_period_id: str,
        process_id: str | None = None,
    ) -> list[ActivityData]: ...

    def get_emission_factors(self, active_only: bool = True) -> list[EmissionFactor]: ...

    def get_interventions(self, active_only: bool = True) -> list[CircularIntervention]: ...

    def get_benchmarks(self, facility_id: str | None = None) -> list[dict]: ...

    def list_facilities(self) -> list[Facility]: ...


class InMemoryDataSource:
    """In-memory implementation - ideal for tests and for P2 to adapt to."""

    def __init__(
        self,
        *,
        organizations: list[Organization] | None = None,
        facilities: list[Facility] | None = None,
        reporting_periods: list[ReportingPeriod] | None = None,
        processes: list[Process] | None = None,
        activity_data: list[ActivityData] | None = None,
        emission_factors: list[EmissionFactor] | None = None,
        circular_interventions: list[CircularIntervention] | None = None,
        benchmarks: list[dict] | None = None,
    ) -> None:
        self._organizations = {str(o.id): o for o in (organizations or [])}
        self._facilities = {str(f.id): f for f in (facilities or [])}
        self._reporting_periods = {str(p.id): p for p in (reporting_periods or [])}
        self._processes = {str(p.id): p for p in (processes or [])}
        self._activity = list(activity_data or [])
        self._factors = list(emission_factors or [])
        self._interventions = list(circular_interventions or [])
        self._benchmarks = list(benchmarks or [])

    # -- mutation helpers (used to build/merge datasets) --------------------
    def extend(
        self,
        *,
        activity_data: list[ActivityData] | None = None,
        emission_factors: list[EmissionFactor] | None = None,
        circular_interventions: list[CircularIntervention] | None = None,
    ) -> None:
        self._activity.extend(activity_data or [])
        self._factors.extend(emission_factors or [])
        self._interventions.extend(circular_interventions or [])

    # -- protocol -----------------------------------------------------------
    def get_organization(self) -> Organization | None:
        return next(iter(self._organizations.values()), None)

    def get_facility(self, facility_id: str) -> Facility | None:
        return self._facilities.get(str(facility_id))

    def get_reporting_period(self, period_id: str) -> ReportingPeriod | None:
        return self._reporting_periods.get(str(period_id))

    def list_reporting_periods(self, facility_id: str) -> list[ReportingPeriod]:
        return [p for p in self._reporting_periods.values() if str(p.facility_id) == str(facility_id)]

    def get_processes(self, facility_id: str) -> list[Process]:
        return [p for p in self._processes.values() if str(p.facility_id) == str(facility_id)]

    def get_activity_data(
        self,
        facility_id: str,
        reporting_period_id: str,
        process_id: str | None = None,
    ) -> list[ActivityData]:
        rows = [
            a
            for a in self._activity
            if str(a.facility_id) == str(facility_id)
            and str(a.reporting_period_id) == str(reporting_period_id)
        ]
        if process_id is not None:
            rows = [a for a in rows if a.process_id is not None and str(a.process_id) == str(process_id)]
        return rows

    def get_emission_factors(self, active_only: bool = True) -> list[EmissionFactor]:
        return [f for f in self._factors if f.active or not active_only]

    def get_interventions(self, active_only: bool = True) -> list[CircularIntervention]:
        return [i for i in self._interventions if i.active or not active_only]

    def get_benchmarks(self, facility_id: str | None = None) -> list[dict]:
        return list(self._benchmarks)

    def list_facilities(self) -> list[Facility]:
        return list(self._facilities.values())


class MockDataSource(InMemoryDataSource):
    """Loads and validates ``mocks/mock_dataset.json`` through the contracts."""

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        path = Path(dataset_path) if dataset_path else _DEFAULT_MOCK
        raw = json.loads(path.read_text(encoding="utf-8"))
        super().__init__(
            organizations=[Organization.model_validate(raw["organization"])]
            if raw.get("organization")
            else [],
            facilities=[Facility.model_validate(x) for x in raw.get("facilities", [])],
            reporting_periods=[ReportingPeriod.model_validate(x) for x in raw.get("reporting_periods", [])],
            processes=[Process.model_validate(x) for x in raw.get("processes", [])],
            activity_data=[ActivityData.model_validate(x) for x in raw.get("activity_data", [])],
            emission_factors=[EmissionFactor.model_validate(x) for x in raw.get("emission_factors", [])],
            circular_interventions=[
                CircularIntervention.model_validate(x) for x in raw.get("circular_interventions", [])
            ],
            benchmarks=raw.get("industry_benchmarks", []),
        )


def load_mock_data_source(dataset_path: str | Path | None = None) -> MockDataSource:
    return MockDataSource(dataset_path)


def default_data_source():
    """Env-driven source selection (B2).

    ``ECOLEAK_SQL_DSN`` set  -> SQLActivityDataSource over P2's tables.
    Unset (Phase 1 default)  -> mock data source (fallback / test fixture).
    """
    import os

    dsn = os.environ.get("ECOLEAK_SQL_DSN")
    if dsn:
        from .sql_source import load_sql_data_source

        return load_sql_data_source(dsn)
    return load_mock_data_source()
