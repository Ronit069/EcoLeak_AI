"""Module E table: emission_factors (DB doc 6.1). Versioned, never overwritten."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class EmissionFactor(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "emission_factors"
    __table_args__ = (
        CheckConstraint("total_co2e_factor >= 0", name="total_factor_nonnegative"),
        CheckConstraint("co2_factor >= 0", name="co2_factor_nonnegative"),
        CheckConstraint("ch4_factor >= 0", name="ch4_factor_nonnegative"),
        CheckConstraint("n2o_factor >= 0", name="n2o_factor_nonnegative"),
        CheckConstraint(
            "scope IN ('SCOPE_1', 'SCOPE_2', 'SCOPE_3')", name="scope_valid"
        ),
        CheckConstraint(
            "confidence_level IS NULL OR confidence_level IN ('HIGH', 'MEDIUM', 'LOW')",
            name="confidence_level_valid",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_to >= valid_from",
            name="valid_dates_order",
        ),
        CheckConstraint(
            "source_year >= 1900 AND source_year <= 2100", name="source_year_range"
        ),
        Index("idx_emission_factor_lookup", "category", "subcategory", "region_country", "active"),
    )

    factor_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    region_country: Mapped[Optional[str]] = mapped_column(String(100))
    region_state: Mapped[Optional[str]] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    input_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    output_unit: Mapped[str] = mapped_column(String(30), nullable=False, default="kgCO2e")
    co2_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    ch4_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    n2o_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    total_co2e_factor: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    source_year: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)
    methodology: Mapped[Optional[str]] = mapped_column(Text)
    confidence_level: Mapped[Optional[str]] = mapped_column(String(20))
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime]

    # Module E: supplier-specific overrides.
    supplier_id: Mapped[Optional[str]] = mapped_column(String(80))
    supplier_specific: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
