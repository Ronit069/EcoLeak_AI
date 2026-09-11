"""Application settings (12-factor, pydantic-settings). Secrets come from .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


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
        if self.auth_mode == "jwt":
            secret = (self.jwt_secret or "").strip()
            if not secret or secret.startswith("dev-only"):
                raise ValueError(
                    "jwt_secret must be set via environment when auth_mode='jwt'; "
                    "no hardcoded default is allowed."
                )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
