"""FastAPI application factory for the EcoLeak AI backend (P2 Phase 1).

Merged Phase 1 surface: P2's A–E/I/P routers + P3's engine router (F/G/H/K/L)
+ P4's recommendation/dashboard router (J1/J2/M1/N1/N2) under one ASGI app /
base URL. Engine domain errors share the frozen error shape.
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Repo-root bootstrap so ``engine`` / ``p4`` are importable when this app is
# launched from backend/ (uvicorn app.main:app).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import get_settings
from app.contracts_compat import schemas as contract_schemas  # noqa: F401 (fail fast if missing)
from app.db import engine
from app.deps import api_rate_limit  # noqa: F401 (re-export for routers)
from app.errors import error_payload, register_exception_handlers
from app.logging_setup import configure_logging
from app.security import get_current_principal
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
from p4.o_routes import router as o_router  # noqa: E402
from p4.feedback import FeedbackError  # noqa: E402
from p4.scenarios import ScenarioError  # noqa: E402

logger = logging.getLogger("ecoleak.api")

# F-4: bounded health probe pool — guarantees /api/health answers fast even
# when the database is unreachable (no indefinite hang on startup checks).
_HEALTH_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="health")
_HEALTH_DB_TIMEOUT_S = 4.0


def _database_probe() -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 - probe reports, never raises
        return f"error: {type(exc).__name__}"


_registered_carbon_handler = False


def create_app() -> FastAPI:
    global _registered_carbon_handler
    configure_logging()
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
        # F-14: structured request logging with correlation ids; failures are
        # logged with full context by the 500 handler in app/errors.py.
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        response.headers["X-Request-Id"] = request_id
        logger.info(
            "request method=%s path=%s status=%s request_id=%s elapsed_ms=%s",
            request.method, request.url.path, response.status_code, request_id,
            round((time.perf_counter() - started) * 1000, 2),
        )
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

        @app.exception_handler(ScenarioError)
        async def _scenario_domain(_: Request, exc: ScenarioError) -> JSONResponse:
            status = {"NOT_FOUND": 404, "FORBIDDEN": 403, "TOO_MANY": 429}.get(exc.code, 422)
            return JSONResponse(
                status_code=status,
                content=error_payload(exc.code, exc.message, "ERROR", exc.details),
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
    ):
        app.include_router(router)

    # T0-3: AuthN is enforced on the engine/P4 surface (router-level), and
    # each route adds its tenant-ownership guard (see app/guards.py).
    app.include_router(
        engine_router,
        dependencies=[Depends(get_current_principal)],
    )
    app.include_router(
        p4_router,
        dependencies=[Depends(get_current_principal)],
    )
    app.include_router(
        o_router,
        dependencies=[Depends(get_current_principal)],
    )

    @app.get("/api/health", tags=["ops"])
    def health() -> dict:
        # F-4: health checks real dependencies (bounded) instead of reporting
        # ok blindly. The DB probe is capped so a dead DB answers in seconds.
        components: dict[str, str] = {}
        future = _HEALTH_POOL.submit(_database_probe)
        try:
            components["database"] = future.result(timeout=_HEALTH_DB_TIMEOUT_S)
        except FuturesTimeoutError:
            components["database"] = "error: timeout"
        try:
            from engine.api import get_engine as _get_engine

            components["engine"] = (
                "ok"
                if _get_engine().data_source.get_organization() is not None
                else "degraded: no organization in data source"
            )
        except Exception as exc:  # noqa: BLE001 - probe reports, never raises
            components["engine"] = f"error: {type(exc).__name__}: {exc}"
        healthy = all(value.startswith("ok") for value in components.values())
        if not healthy:
            return JSONResponse(
                status_code=503,
                content=error_payload(
                    "HEALTH_DEPENDENCY_UNAVAILABLE",
                    "One or more dependencies are unavailable.",
                    "ERROR",
                    {"components": components},
                ),
            )
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.environment,
            "use_mock_data": settings.use_mock_data,
            "components": components,
        }

    return app


app = create_app()
