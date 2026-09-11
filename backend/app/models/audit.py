"""Audit table (DB doc 17.1). Every business write appends one row."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("idx_audit_entity", "entity_type", "entity_id"),)

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    old_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    new_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(128))
    user_agent_hash: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
