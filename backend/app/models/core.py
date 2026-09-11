"""Module A tables: organizations, facilities, reporting_periods (DB doc 2.1-2.3)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "organization_size IN ('SMALL', 'MEDIUM')",
            name="organization_size_valid",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry_sector: Mapped[str] = mapped_column(String(100), nullable=False)
    industry_subtype: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    organization_size: Mapped[str] = mapped_column(String(30), nullable=False)

    facilities: Mapped[list["Facility"]] = relationship(back_populates="organization")


class Facility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("organization_id", "facility_code", name="uq_org_facility_code"),
        CheckConstraint("annual_production >= 0", name="production_nonnegative"),
        CheckConstraint(
            "working_days_per_year >= 0 AND working_days_per_year <= 366",
            name="working_days_range",
        ),
        CheckConstraint(
            "working_hours_per_day >= 0 AND working_hours_per_day <= 24",
            name="working_hours_range",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_code: Mapped[Optional[str]] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    annual_production: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    production_unit: Mapped[Optional[str]] = mapped_column(String(30))
    working_days_per_year: Mapped[Optional[int]] = mapped_column(Integer)
    working_hours_per_day: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="facilities")


class ReportingPeriod(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "reporting_periods"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="end_after_start"),
    )

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime]
