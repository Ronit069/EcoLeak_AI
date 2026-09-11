"""FastAPI application factory for the EcoLeak AI backend (P2 Phase 1)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.contracts_compat import schemas as contract_schemas  # noqa: F401 (fail fast if missing)
from app.errors import register_exception_handlers
from app.routers import (
    activity,
    facilities,
    factors,
    interventions,
    organizations,
    processes,
    reports,
    units,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EcoLeak AI - Backend Platform & Data Engine",
        version="1.0.0",
        description=(
            "Phase 1: real PostgreSQL schema, CSV/Excel ingestion, Pint unit "
            "normalization, data-quality scoring and the versioned emission-factor KB. "
            "Response shapes follow contracts/schemas.py exactly."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-Role", "X-Actor-Id"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response

    register_exception_handlers(app)

    for router in (
        organizations.router,
        facilities.router,
        processes.router,
        activity.router,
        units.router,
        factors.router,
        interventions.router,
        reports.router,
    ):
        app.include_router(router)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    return app


app = create_app()
