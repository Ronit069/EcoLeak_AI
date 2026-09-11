"""Module F/quality tables: calculations, inventory summary, data quality (DB doc 7-8)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class EmissionCalculation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "emission_calculations"
    __table_args__ = (
        Index("idx_emission_calc_activity", "activity_data_id"),
    )

    activity_data_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("activity_data.id"), nullable=False
    )
    emission_factor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("emission_factors.id"), nullable=False
    )
    calculation_version: Mapped[str] = mapped_column(String(30), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    co2e_kg: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    calculation_formula: Mapped[Optional[str]] = mapped_column(Text)
    assumptions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CarbonInventorySummary(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "carbon_inventory_summary"

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    scope1_kgco2e: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    scope2_kgco2e: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    scope3_kgco2e: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    total_kgco2e: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    carbon_intensity: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    production_unit: Mapped[Optional[str]] = mapped_column(String(30))
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DataQualityAssessment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_quality_assessments"

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    completeness_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    source_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    factor_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temporal_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    unit_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    total_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    issues: Mapped[Optional[list[Any]]] = mapped_column(JSONB)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
