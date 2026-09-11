"""Shared router helpers."""
from __future__ import annotations

from fastapi import Request

from app.errors import PeriodLockedError
from app.models.core import ReportingPeriod

WRITE_ROLES = (
    "SYSTEM_ADMIN",
    "ORGANIZATION_ADMIN",
    "SUSTAINABILITY_ANALYST",
    "FACTORY_OPERATOR",
)
ADMIN_ROLES = ("SYSTEM_ADMIN", "ORGANIZATION_ADMIN")


def audit_ctx(request: Request) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def ensure_period_editable(period: ReportingPeriod) -> None:
    if period.status in {"LOCKED", "CLOSED"}:
        raise PeriodLockedError(
            "Reporting period is locked; unlock with an audit event before editing.",
            details={"status": period.status},
        )
