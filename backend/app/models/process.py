"""Module B tables: processes, process_links, process_assets (DB doc 3.1-3.3)."""
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
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class Process(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "processes"
    __table_args__ = (CheckConstraint("sequence_no > 0", name="sequence_positive"),)

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    process_code: Mapped[Optional[str]] = mapped_column(String(50))
    sequence_no: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    process_category: Mapped[Optional[str]] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]


class ProcessLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "process_links"
    __table_args__ = (
        CheckConstraint(
            "source_process_id <> target_process_id", name="no_self_loop"
        ),
    )

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    source_process_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False
    )
    target_process_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False
    )
    flow_type: Mapped[Optional[str]] = mapped_column(String(50))
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    unit: Mapped[Optional[str]] = mapped_column(String(30))
    description: Mapped[Optional[str]] = mapped_column(Text)


class ProcessAsset(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "process_assets"

    process_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False
    )
    asset_name: Mapped[Optional[str]] = mapped_column(String(150))
    asset_type: Mapped[Optional[str]] = mapped_column(String(100))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    rated_capacity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    capacity_unit: Mapped[Optional[str]] = mapped_column(String(30))
    operating_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    installation_year: Mapped[Optional[int]] = mapped_column(Integer)
    active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
