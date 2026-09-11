"""Modules G/H/L tables: hotspots, anomalies, circularity (DB doc 9, 10, 14)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class EmissionHotspot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "emission_hotspots"
    __table_args__ = (
        Index("idx_hotspot_facility_period", "facility_id", "reporting_period_id"),
    )

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    process_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("processes.id")
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("process_assets.id")
    )
    hotspot_type: Mapped[Optional[str]] = mapped_column(String(30))
    emissions_kgco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    contribution_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    carbon_intensity: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    inefficiency_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    waste_ratio_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    improvement_potential_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    hotspot_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime]


class AnomalyResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "anomaly_results"

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    process_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("processes.id"))
    activity_data_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("activity_data.id")
    )
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    model_version: Mapped[Optional[str]] = mapped_column(String(50))
    anomaly_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    is_anomaly: Mapped[Optional[bool]] = mapped_column(Boolean)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Additive: Module H3 acknowledgement.
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_note: Mapped[Optional[str]] = mapped_column(Text)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class CircularityScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "circularity_scores"

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    recycled_input_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    waste_recovery_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    energy_recovery_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    water_reuse_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    reuse_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    total_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    methodology_version: Mapped[Optional[str]] = mapped_column(String(30))
    calculated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
