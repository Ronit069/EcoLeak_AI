"""FastAPI application factory for the EcoLeak AI backend (P2 Phase 1).

Merged Phase 1 surface: P2's A–E/I/P routers + P3's engine router (F/G/H/K/L)
+ P4's recommendation/dashboard router (J1/J2/M1/N1/N2) under one ASGI app /
base URL. Engine domain errors share the frozen error shape.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Repo-root bootstrap so ``engine`` / ``p4`` are importable when this app is
# launched from backend/ (uvicorn app.main:app).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import get_settings
from app.contracts_compat import schemas as contract_schemas  # noqa: F401 (fail fast if missing)
from app.errors import error_payload, register_exception_handlers
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

from engine.api import router as engine_router  # noqa: E402  (path bootstrap above)
from engine.errors import CarbonPlatformError  # noqa: E402
from p4.api import router as p4_router  # noqa: E402
from p4.feedback import FeedbackError  # noqa: E402


_registered_carbon_handler = False


def create_app() -> FastAPI:
    global _registered_carbon_handler
    settings = get_settings()
    app = FastAPI(
        title="EcoLeak AI - Backend Platform & Data Engine (merged Phase 1)",
        version="1.0.0",
        description=(
            "Phase 1 merged surface: P2 PostgreSQL platform (Modules A-E, I, P) + "
            "P3 carbon engine (F, G, H, K, L) + P4 recommendation ranker (J, M, N). "
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

    # One consistent error shape for engine domain errors on the merged surface.
    if not _registered_carbon_handler:
        @app.exception_handler(CarbonPlatformError)
        async def _carbon_domain(_: Request, exc: CarbonPlatformError) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content=error_payload(exc.error_code, exc.message, exc.severity, exc.details),
            )

        @app.exception_handler(FeedbackError)
        async def _feedback_domain(_: Request, exc: FeedbackError) -> JSONResponse:
            return JSONResponse(
                status_code=422,
                content=error_payload("FEEDBACK_VALIDATION", str(exc), "ERROR", {}),
            )

        _registered_carbon_handler = True

    for router in (
        organizations.router,
        facilities.router,
        processes.router,
        activity.router,
        units.router,
        factors.router,
        interventions.router,
        reports.router,
        engine_router,
        p4_router,
    ):
        app.include_router(router)

    @app.get("/api/health", tags=["ops"])
    def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.environment,
            "use_mock_data": settings.use_mock_data,
        }

    return app


app = create_app()
