"""Application settings (12-factor, pydantic-settings). Secrets come from .env."""
from __future__ import annotations

from functools import lru_cache

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

    # Phase 1 uses a stub auth layer ("stub"); Phase 2 swaps in "jwt".
    auth_mode: str = "stub"
    jwt_secret: str = "dev-only-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
