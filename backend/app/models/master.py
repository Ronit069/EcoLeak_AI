"""Master reference tables (DB doc 5.1-5.3, 16.1)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class EnergySource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "energy_sources"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    renewable: Mapped[Optional[bool]] = mapped_column(Boolean)
    standard_unit: Mapped[Optional[str]] = mapped_column(String(30))


class Material(UUIDPrimaryKeyMixin, Base):
    """MaterialMaster (DB doc 5.2)."""

    __tablename__ = "materials"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    standard_unit: Mapped[Optional[str]] = mapped_column(String(30))
    recyclable: Mapped[Optional[bool]] = mapped_column(Boolean)
    renewable_material: Mapped[Optional[bool]] = mapped_column(Boolean)


class WasteType(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "waste_types"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    hazardous: Mapped[Optional[bool]] = mapped_column(Boolean)
    recyclable: Mapped[Optional[bool]] = mapped_column(Boolean)
    standard_unit: Mapped[Optional[str]] = mapped_column(String(30))


class IndustryBenchmark(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "industry_benchmarks"

    industry_sector: Mapped[Optional[str]] = mapped_column(String(100))
    process_category: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    metric_name: Mapped[Optional[str]] = mapped_column(String(100))
    p25: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    median: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    p75: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    unit: Mapped[Optional[str]] = mapped_column(String(30))
    source: Mapped[Optional[str]] = mapped_column(Text)
    source_year: Mapped[Optional[int]] = mapped_column(Integer)
