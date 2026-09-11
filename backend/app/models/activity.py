"""Modules C/D table: activity_data (DB doc 4.1) with additive ingestion columns."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
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

_ACTIVITY_CATEGORIES = (
    "ELECTRICITY",
    "FUEL",
    "MATERIAL",
    "WATER",
    "TRANSPORT",
    "WASTE",
    "REFRIGERANT",
    "STEAM",
    "OTHER",
)
_DATA_SOURCES = ("MANUAL", "CSV", "EXCEL", "API", "SENSOR", "OCR")


class ActivityData(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "activity_data"
    __table_args__ = (
        CheckConstraint("original_value >= 0", name="original_value_nonnegative"),
        CheckConstraint("normalized_value >= 0", name="normalized_value_nonnegative"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100", name="confidence_range"
        ),
        CheckConstraint(
            "carbon_data_quality_score >= 0 AND carbon_data_quality_score <= 100",
            name="carbon_dq_range",
        ),
        CheckConstraint(
            "activity_category IN " + str(_ACTIVITY_CATEGORIES), name="activity_category_valid"
        ),
        CheckConstraint(
            "data_source_type IN " + str(_DATA_SOURCES), name="data_source_type_valid"
        ),
        CheckConstraint(
            "measured_or_estimated IN ('MEASURED', 'ESTIMATED')",
            name="measured_or_estimated_valid",
        ),
        Index("idx_activity_facility_period", "facility_id", "reporting_period_id"),
        Index("idx_activity_process", "process_id"),
        Index(
            "uq_activity_source_row",
            "facility_id",
            "reporting_period_id",
            "source_row_hash",
            unique=True,
            postgresql_where=None,
        ),
    )

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    process_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("processes.id")
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("process_assets.id")
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    activity_category: Mapped[str] = mapped_column(String(40), nullable=False)
    activity_subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[Optional[str]] = mapped_column(String(150))
    original_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    original_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    normalized_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    normalized_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    data_source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="MANUAL")
    measured_or_estimated: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MEASURED"
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime]

    # Additive Phase 1 columns (not part of the frozen contract response shape).
    carbon_data_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    source_row_hash: Mapped[Optional[str]] = mapped_column(String(64))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
