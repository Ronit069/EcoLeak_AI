"""Authentication for Phase 1.

Phase 1 ships a *stub* principal derived from trusted headers so every endpoint
already implements the full 8-point checklist (auth -> authz -> tenant -> ...).
The dependency signature is identical to a JWT implementation, so Phase 2 only
has to replace `get_current_principal` internals (PyJWT decode is provided).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Header
from pwdlib import PasswordHash

from app.config import get_settings
from app.enums import ROLES
from app.errors import ForbiddenError, UnauthorizedError

_password_hash = PasswordHash.recommended()
DEFAULT_ROLE = "SUSTAINABILITY_ANALYST"


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


def create_access_token(claims: dict) -> str:
    settings = get_settings()
    payload = dict(claims)
    payload.setdefault("iat", datetime.now(timezone.utc))
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:  # pragma: no cover - exercised in Phase 2
        raise UnauthorizedError("Invalid or expired access token.") from exc


@dataclass(frozen=True)
class Principal:
    """Caller identity after authentication."""

    actor_id: Optional[UUID]
    organization_id: Optional[UUID]
    role: str

    @property
    def is_global(self) -> bool:
        return self.role in {"SYSTEM_ADMIN", "REGULATOR_READ_ONLY"}

    def assert_org(self, organization_id: UUID | None) -> None:
        if self.is_global:
            return
        if organization_id is None or self.organization_id != organization_id:
            raise ForbiddenError("Caller does not own this organization's data.")

    def has_role(self, *roles: str) -> bool:
        return self.role in roles


def _parse_uuid(value: str | None, field: str) -> Optional[UUID]:
    if value is None or value == "":
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise UnauthorizedError(f"Malformed {field} header.") from exc


def get_current_principal(
    authorization: Optional[str] = Header(default=None),
    x_organization_id: Optional[str] = Header(default=None),
    x_role: str = Header(default=DEFAULT_ROLE),
    x_actor_id: Optional[str] = Header(default=None),
) -> Principal:
    settings = get_settings()

    if settings.auth_mode == "jwt":
        # T0-2 fix: JWT mode is strict. A missing or malformed Authorization
        # header must 401 here — it must never fall through to the stub
        # header branch (that fallback was a full auth bypass).
        if not authorization or not authorization.lower().startswith("bearer "):
            raise UnauthorizedError("Authorization header with a Bearer token is required.")
        claims = decode_access_token(authorization.split(" ", 1)[1].strip())
        return Principal(
            actor_id=_parse_uuid(claims.get("sub"), "sub"),
            organization_id=_parse_uuid(claims.get("organization_id"), "organization_id"),
            role=claims.get("role", DEFAULT_ROLE),
        )

    if settings.auth_mode != "stub":
        raise UnauthorizedError(
            f"Unsupported AUTH_MODE {settings.auth_mode!r}; expected 'stub' or 'jwt'."
        )

    # Stub mode (dev/demo): trusted headers. Organization header is optional
    # at the auth layer (bootstrap endpoints such as organization creation
    # have no tenant yet); tenant ownership is enforced by per-endpoint
    # access resolvers and the merged-surface tenant guards. A PRESENT but
    # wrong org header is rejected by those resolvers/guards.
    if x_role not in ROLES:
        raise UnauthorizedError("Unknown role header value.")
    return Principal(
        actor_id=_parse_uuid(x_actor_id, "X-Actor-Id"),
        organization_id=_parse_uuid(x_organization_id, "X-Organization-Id"),
        role=x_role,
    )
