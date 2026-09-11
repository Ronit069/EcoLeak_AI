"""Modules K/O tables: scenarios, scenario_interventions, scenario_results (DB doc 13)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class Scenario(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("budget_limit >= 0", name="budget_nonnegative"),
        CheckConstraint(
            "target_reduction_pct >= 0 AND target_reduction_pct <= 100",
            name="target_reduction_range",
        ),
    )

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    scenario_type: Mapped[Optional[str]] = mapped_column(String(30))
    budget_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    target_reduction_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    created_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ScenarioIntervention(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scenario_interventions"
    __table_args__ = (
        CheckConstraint(
            "adoption_percentage >= 0 AND adoption_percentage <= 100",
            name="adoption_range",
        ),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scenarios.id"), nullable=False
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), nullable=False
    )
    adoption_percentage: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("100")
    )
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ScenarioResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scenario_results"

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scenarios.id"), nullable=False
    )
    baseline_emissions_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    projected_emissions_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    total_co2_saving_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    reduction_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    total_capex: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    annual_saving: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    payback_years: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
