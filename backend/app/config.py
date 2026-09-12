"""Application settings (12-factor, pydantic-settings). Secrets come from .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "EcoLeak AI - Backend Platform & Data Engine"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/ecoleak"
    )
    test_database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/ecoleak_test"
    )

    cors_allow_origins: str = "http://localhost:5173,http://localhost:3000"

    max_upload_bytes: int = 10 * 1024 * 1024
    max_import_rows: int = 20_000

    rate_limit_per_minute: int = 120
    upload_rate_limit_per_minute: int = 10

    # Phase 2 mock-to-real swap gate (shared Phase 2 rule).
    #   true  (default) -> Module P and the report generator keep Phase 1's
    #                      known-good mock behavior (instant fallback).
    #   false           -> Module P pulls live F/G/J/L engine output.
    # The engine data source DSN can be overridden independently; default is
    # this app's DATABASE_URL so the engine reads the same P2 tables.
    use_mock_data: bool = True
    engine_dsn: Optional[str] = None

    # Phase 1 uses a stub auth layer ("stub"); Phase 2 swaps in "jwt".
    auth_mode: str = "stub"
    # No default secret (D2): must come from .env / environment. With
    # auth_mode=jwt a missing or placeholder secret fails fast at load time so
    # it can never leak into any deployed configuration.
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def _enforce_jwt_secret(self) -> "Settings":
        secret = (self.jwt_secret or "").strip()
        # BLOCKER-3 remediation: known placeholders are rejected everywhere;
        # ANY non-development environment must fail fast when the secret is
        # unset or placeholder-shaped — never silently run with a default.
        placeholders = {"change-me-in-production", "dev-only-secret-change-in-production"}
        placeholder_shaped = secret.startswith("dev-only") or secret.startswith("change-me")
        if secret in placeholders or placeholder_shaped:
            raise ValueError(
                "jwt_secret must not be a placeholder value even in development; "
                "set a real secret via JWT_SECRET."
            )
        if self.auth_mode == "jwt" and not secret:
            raise ValueError(
                "jwt_secret must be set via environment when auth_mode='jwt'; "
                "no hardcoded default is allowed."
            )
        if self.environment != "development" and not secret:
            raise ValueError(
                "jwt_secret must be set via environment in non-development "
                f"environments (got environment={self.environment!r}); refusing to start."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
