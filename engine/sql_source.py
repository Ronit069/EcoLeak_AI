"""SQL-backed :class:`ActivityDataSource` for the P3 engine (B2).

Reads the P2 platform tables (``organizations``, ``facilities``,
``reporting_periods``, ``processes``, ``activity_data``, ``emission_factors``,
``circular_interventions``) with the SAME table and column names as
``backend/app/models/*`` â€” in production it reads P2's seeded PostgreSQL
schema directly; in tests it runs over a portable SQLite image of the same
tables. JSONB columns are read as JSON; the portable types here are
read-compatible (``contracts.schemas`` remains the single source of truth).

Active when ``ECOLEAK_SQL_DSN`` is set (e.g.
``postgresql+psycopg://user:pass@host/ecoleak``); otherwise the engine keeps
the mock data source (B2: mock stays as fallback/test fixture).
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contracts.schemas import (
    ActivityCategory,
    ActivityData,
    CircularIntervention,
    ConfidenceLevel,
    DataSourceType,
    EmissionFactor,
    Facility,
    InterventionComplexity,
    MeasuredOrEstimated,
    Organization,
    OrganizationSize,
    PeriodType,
    Process,
    ReportingPeriod,
    ReportingPeriodStatus,
    RiskLevel,
    Scope,
)

from .data_source import ActivityDataSource

metadata = MetaData()


def _table(name: str, *columns: Column) -> Table:
    return Table(name, metadata, *columns, extend_existing=True)


organizations = _table(
    "organizations",
    Column("id", Uuid, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("industry_sector", String(100), nullable=False),
    Column("industry_subtype", String(100)),
    Column("country", String(100), nullable=False),
    Column("state", String(100)),
    Column("city", String(100)),
    Column("currency_code", String(3), nullable=False),
    Column("organization_size", String(30), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

facilities = _table(
    "facilities",
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, ForeignKey("organizations.id"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("facility_code", String(50)),
    Column("country", String(100), nullable=False),
    Column("state", String(100)),
    Column("city", String(100)),
    Column("latitude", Numeric(9, 6)),
    Column("longitude", Numeric(9, 6)),
    Column("annual_production", Numeric(18, 4)),
    Column("production_unit", String(30)),
    Column("working_days_per_year", String(10)),
    Column("working_hours_per_day", Numeric(5, 2)),
    Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

reporting_periods = _table(
    "reporting_periods",
    Column("id", Uuid, primary_key=True),
    Column("facility_id", Uuid, ForeignKey("facilities.id"), nullable=False),
    Column("period_type", String(20), nullable=False),
    Column("start_date", String(10), nullable=False),
    Column("end_date", String(10), nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

processes = _table(
    "processes",
    Column("id", Uuid, primary_key=True),
    Column("facility_id", Uuid, ForeignKey("facilities.id"), nullable=False),
    Column("name", String(150), nullable=False),
    Column("process_code", String(50)),
    Column("sequence_no", String(10)),
    Column("description", Text),
    Column("process_category", String(100)),
    Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

activity_data = _table(
    "activity_data",
    Column("id", Uuid, primary_key=True),
    Column("facility_id", Uuid, ForeignKey("facilities.id"), nullable=False),
    Column("process_id", Uuid, ForeignKey("processes.id")),
    Column("asset_id", Uuid),
    Column("reporting_period_id", Uuid, ForeignKey("reporting_periods.id"), nullable=False),
    Column("activity_category", String(40), nullable=False),
    Column("activity_subcategory", String(100), nullable=False),
    Column("source_name", String(150)),
    Column("original_value", Numeric(20, 6)),
    Column("original_unit", String(30), nullable=False),
    Column("normalized_value", Numeric(20, 6)),
    Column("normalized_unit", String(30), nullable=False),
    Column("data_source_type", String(30), nullable=False),
    Column("measured_or_estimated", String(20), nullable=False),
    Column("confidence_score", Numeric(5, 2)),
    Column("notes", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

emission_factors = _table(
    "emission_factors",
    Column("id", Uuid, primary_key=True),
    Column("factor_code", String(80), nullable=False),
    Column("category", String(50), nullable=False),
    Column("subcategory", String(100), nullable=False),
    Column("item_name", String(150), nullable=False),
    Column("region_country", String(100)),
    Column("region_state", String(100)),
    Column("scope", String(20), nullable=False),
    Column("input_unit", String(30), nullable=False),
    Column("output_unit", String(30), nullable=False),
    Column("co2_factor", Numeric(20, 8)),
    Column("ch4_factor", Numeric(20, 8)),
    Column("n2o_factor", Numeric(20, 8)),
    Column("total_co2e_factor", Numeric(20, 8), nullable=False),
    Column("source_name", String(255), nullable=False),
    Column("source_url", Text),
    Column("source_year", String(10), nullable=False),
    Column("valid_from", String(10)),
    Column("valid_to", String(10)),
    Column("methodology", Text),
    Column("confidence_level", String(20)),
    Column("version", String(30), nullable=False),
    Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

circular_interventions = _table(
    "circular_interventions",
    Column("id", Uuid, primary_key=True),
    Column("intervention_code", String(80), nullable=False),
    Column("title", String(200), nullable=False),
    Column("industry_sector", String(100)),
    Column("process_category", String(100)),
    Column("current_practice", Text),
    Column("alternative_practice", Text),
    Column("description", Text),
    Column("min_capex", Numeric(20, 2)),
    Column("max_capex", Numeric(20, 2)),
    Column("currency", String(3)),
    Column("expected_co2_reduction_min_pct", Numeric(8, 2)),
    Column("expected_co2_reduction_max_pct", Numeric(8, 2)),
    Column("energy_reduction_min_pct", Numeric(8, 2)),
    Column("energy_reduction_max_pct", Numeric(8, 2)),
    Column("waste_reduction_min_pct", Numeric(8, 2)),
    Column("waste_reduction_max_pct", Numeric(8, 2)),
    Column("implementation_months_min", String(10)),
    Column("implementation_months_max", String(10)),
    Column("complexity", String(20)),
    Column("risk_level", String(20)),
    Column("evidence_source", Text),
    Column("active", Boolean, nullable=False),
)


def create_sql_schema(target_engine: Engine) -> None:
    """Create the portable engine-read tables (tests / SQLite image)."""
    metadata.create_all(bind=target_engine)


class SQLActivityDataSource(ActivityDataSource):
    """Read-only feed over P2 tables (same names/columns as backend models)."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _session(self) -> Session:
        return Session(self.engine)

    @staticmethod
    def _u(value: str | UUID | None) -> Any:
        """Portable UUID bind (works for PG UUID and SQLite CHAR(32))."""
        return value if isinstance(value, UUID) else UUID(str(value))

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _as_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return value if isinstance(value, Decimal) else Decimal(str(value))

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if value is None or isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)

    # -- ActivityDataSource protocol ----------------------------------------
    def get_organization(self) -> Organization | None:
        with self._session() as db:
            row = db.execute(select(organizations).limit(1)).mappings().first()
        if row is None:
            return None
        return Organization(
            id=row["id"], name=row["name"], industry_sector=row["industry_sector"],
            industry_subtype=row["industry_subtype"], country=row["country"],
            state=row["state"], city=row["city"], currency_code=row["currency_code"],
            organization_size=OrganizationSize(row["organization_size"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def list_facilities(self) -> list[Facility]:
        with self._session() as db:
            rows = db.execute(select(facilities).order_by(facilities.c.name)).mappings().all()
        out: list[Facility] = []
        for r in rows:
            out.append(
                Facility(
                    id=r["id"], organization_id=r["organization_id"], name=r["name"],
                    facility_code=r["facility_code"], country=r["country"], state=r["state"],
                    city=r["city"], latitude=self._as_decimal(r["latitude"]),
                    longitude=self._as_decimal(r["longitude"]),
                    annual_production=self._as_decimal(r["annual_production"]),
                    production_unit=r["production_unit"],
                    working_days_per_year=self._as_int(r["working_days_per_year"]),
                    working_hours_per_day=self._as_decimal(r["working_hours_per_day"]),
                    active=bool(r["active"]), created_at=r["created_at"], updated_at=r["updated_at"],
                )
            )
        return out

    def get_facility(self, facility_id: str) -> Facility | None:
        for f in self.list_facilities():
            if str(f.id) == facility_id:
                return f
        return None

    def list_reporting_periods(self, facility_id: str) -> list[ReportingPeriod]:
        with self._session() as db:
            rows = db.execute(
                select(reporting_periods).where(reporting_periods.c.facility_id == self._u(facility_id))
                .order_by(reporting_periods.c.start_date)
            ).mappings().all()
        out: list[ReportingPeriod] = []
        for r in rows:
            out.append(
                ReportingPeriod(
                    id=r["id"], facility_id=r["facility_id"],
                    period_type=PeriodType(r["period_type"]),
                    start_date=self._as_date(r["start_date"]) or date.today(),
                    end_date=self._as_date(r["end_date"]) or date.today(),
                    status=ReportingPeriodStatus(r["status"]), created_at=r["created_at"],
                )
            )
        return out

    def get_reporting_period(self, period_id: str) -> ReportingPeriod | None:
        for period in self.list_reporting_periods(str(self._facility_id_of_period(period_id)) or ""):
            if str(period.id) == period_id:
                return period
        return None

    def _facility_id_of_period(self, period_id: str) -> Any:
        with self._session() as db:
            row = db.execute(
                select(reporting_periods.c.facility_id).where(reporting_periods.c.id == self._u(period_id))
            ).first()
        return row[0] if row else None

    def get_processes(self, facility_id: str) -> list[Process]:
        with self._session() as db:
            rows = db.execute(
                select(processes).where(processes.c.facility_id == self._u(facility_id))
                .order_by(processes.c.sequence_no)
            ).mappings().all()
        out: list[Process] = []
        for r in rows:
            out.append(
                Process(
                    id=r["id"], facility_id=r["facility_id"], name=r["name"],
                    process_code=r["process_code"], sequence_no=self._as_int(r["sequence_no"]),
                    description=r["description"], process_category=r["process_category"],
                    active=bool(r["active"]), created_at=r["created_at"],
                )
            )
        return out

    def get_activity_data(
        self,
        facility_id: str,
        reporting_period_id: str,
        process_id: str | None = None,
    ) -> list[ActivityData]:
        stmt = select(activity_data).where(
            activity_data.c.facility_id == self._u(facility_id),
            activity_data.c.reporting_period_id == self._u(reporting_period_id),
        )
        if process_id:
            stmt = stmt.where(activity_data.c.process_id == self._u(process_id))
        with self._session() as db:
            rows = db.execute(stmt.order_by(activity_data.c.created_at)).mappings().all()
        out: list[ActivityData] = []
        for r in rows:
            out.append(
                ActivityData(
                    id=r["id"], facility_id=r["facility_id"], process_id=r["process_id"],
                    asset_id=r["asset_id"], reporting_period_id=r["reporting_period_id"],
                    activity_category=ActivityCategory(r["activity_category"]),
                    activity_subcategory=r["activity_subcategory"], source_name=r["source_name"],
                    original_value=self._as_decimal(r["original_value"]),
                    original_unit=r["original_unit"],
                    normalized_value=self._as_decimal(r["normalized_value"]),
                    normalized_unit=r["normalized_unit"],
                    data_source_type=DataSourceType(r["data_source_type"]),
                    measured_or_estimated=MeasuredOrEstimated(r["measured_or_estimated"]),
                    confidence_score=self._as_decimal(r["confidence_score"]),
                    notes=r["notes"], created_at=r["created_at"],
                )
            )
        return out

    def get_emission_factors(self, active_only: bool = True) -> list[EmissionFactor]:
        stmt = select(emission_factors)
        if active_only:
            stmt = stmt.where(emission_factors.c.active.is_(True))
        with self._session() as db:
            rows = db.execute(stmt.order_by(emission_factors.c.source_year.desc())).mappings().all()
        out: list[EmissionFactor] = []
        for r in rows:
            out.append(
                EmissionFactor(
                    id=r["id"], factor_code=r["factor_code"], category=r["category"],
                    subcategory=r["subcategory"], item_name=r["item_name"],
                    region_country=r["region_country"], region_state=r["region_state"],
                    scope=Scope(r["scope"]), input_unit=r["input_unit"],
                    output_unit=r["output_unit"] or "kgCO2e",
                    co2_factor=self._as_decimal(r["co2_factor"]),
                    ch4_factor=self._as_decimal(r["ch4_factor"]),
                    n2o_factor=self._as_decimal(r["n2o_factor"]),
                    total_co2e_factor=self._as_decimal(r["total_co2e_factor"]) or Decimal("0"),
                    source_name=r["source_name"], source_url=r["source_url"],
                    source_year=self._as_int(r["source_year"]) or 0,
                    valid_from=self._as_date(r["valid_from"]),
                    valid_to=self._as_date(r["valid_to"]), methodology=r["methodology"],
                    confidence_level=ConfidenceLevel(r["confidence_level"]) if r["confidence_level"] else None,
                    version=r["version"], active=bool(r["active"]), created_at=r["created_at"],
                )
            )
        return out

    def get_interventions(self, active_only: bool = True) -> list[CircularIntervention]:
        stmt = select(circular_interventions)
        if active_only:
            stmt = stmt.where(circular_interventions.c.active.is_(True))
        with self._session() as db:
            rows = db.execute(stmt.order_by(circular_interventions.c.intervention_code)).mappings().all()
        out: list[CircularIntervention] = []
        for r in rows:
            out.append(
                CircularIntervention(
                    id=r["id"], intervention_code=r["intervention_code"], title=r["title"],
                    industry_sector=r["industry_sector"], process_category=r["process_category"],
                    current_practice=r["current_practice"], alternative_practice=r["alternative_practice"],
                    description=r["description"],
                    min_capex=self._as_decimal(r["min_capex"]), max_capex=self._as_decimal(r["max_capex"]),
                    currency=r["currency"],
                    expected_co2_reduction_min_pct=self._as_decimal(r["expected_co2_reduction_min_pct"]),
                    expected_co2_reduction_max_pct=self._as_decimal(r["expected_co2_reduction_max_pct"]),
                    energy_reduction_min_pct=self._as_decimal(r["energy_reduction_min_pct"]),
                    energy_reduction_max_pct=self._as_decimal(r["energy_reduction_max_pct"]),
                    waste_reduction_min_pct=self._as_decimal(r["waste_reduction_min_pct"]),
                    waste_reduction_max_pct=self._as_decimal(r["waste_reduction_max_pct"]),
                    implementation_months_min=self._as_int(r["implementation_months_min"]),
                    implementation_months_max=self._as_int(r["implementation_months_max"]),
                    complexity=InterventionComplexity(r["complexity"]) if r["complexity"] else None,
                    risk_level=RiskLevel(r["risk_level"]) if r["risk_level"] else None,
                    evidence_source=r["evidence_source"], active=bool(r["active"]),
                )
            )
        return out

    def get_benchmarks(self, facility_id: str | None = None) -> list[dict]:
        return []


def load_sql_data_source(dsn: str | None = None) -> SQLActivityDataSource:
    """Build the SQL-backed source from an explicit DSN or ECOLEAK_SQL_DSN."""
    dsn = dsn or os.environ.get("ECOLEAK_SQL_DSN")
    if not dsn:
        raise ValueError("load_sql_data_source requires a DSN (or ECOLEAK_SQL_DSN env)")
    # F-4/F-11: bounded connect so health/readiness checks fail fast on a dead DB.
    connect_args = {"connect_timeout": 3} if dsn.startswith("postgresql") else {}
    return SQLActivityDataSource(create_engine(dsn, future=True, connect_args=connect_args))