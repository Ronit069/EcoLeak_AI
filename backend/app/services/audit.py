"""Audit trail (DB doc 17.1 + checklist item 7).

Every business write (activity_data, emission calculations, factor changes,
imports, report generation, recommendation overrides) appends an AuditLog row.
Never store secrets or full payloads here.
"""
from __future__ import annotations

import hashlib
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.audit import AuditLog
from app.security import Principal


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record(
    db: Session,
    *,
    principal: Optional[Principal],
    organization_id: Optional[UUID],
    event_type: str,
    entity_type: str,
    entity_id: Optional[UUID],
    old_value: Optional[dict[str, Any]] = None,
    new_value: Optional[dict[str, Any]] = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=principal.actor_id if principal else None,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_hash=_hash(ip),
        user_agent_hash=_hash(user_agent),
        created_at=utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry
