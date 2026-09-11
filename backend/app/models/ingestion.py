"""Module C ingestion tracking tables (additive; support C4 ImportJob)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class IngestionBatch(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ingestion_batches"

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    import_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    file_type: Mapped[Optional[str]] = mapped_column(String(10))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RECEIVED")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime]


class IngestionError(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ingestion_errors"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingestion_batches.id"), nullable=False
    )
    row_number: Mapped[Optional[int]] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    field: Mapped[Optional[str]] = mapped_column(String(200))
    raw_row: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime]
