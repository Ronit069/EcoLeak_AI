"""Shared FastAPI dependencies (auth, rate limit, roles)."""
from __future__ import annotations

from fastapi import Depends, Request

from app.config import get_settings
from app.security import Principal, get_current_principal
from app.services.ratelimit import enforce_rate_limit


def current_principal(principal: Principal = Depends(get_current_principal)) -> Principal:
    return principal


def require_roles(*roles: str):
    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.has_role(*roles):
            from app.errors import ForbiddenError

            raise ForbiddenError(
                "Caller does not have the required role.",
                details={"required_roles": list(roles), "actual_role": principal.role},
            )
        return principal

    return _dependency


def api_rate_limit(request: Request) -> None:
    enforce_rate_limit(request, "api")


def upload_rate_limit(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit(request, "upload", settings.upload_rate_limit_per_minute)
