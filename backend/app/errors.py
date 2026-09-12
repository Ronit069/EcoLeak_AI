"""Domain exceptions and the frozen safe-error response shape (DB doc section 28)."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.enums import ValidationSeverity

logger = logging.getLogger("ecoleak.errors")


def error_payload(
    error_code: str,
    message: str,
    severity: str = "ERROR",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error_code": error_code,
        "message": message,
        "severity": severity,
        "details": details or {},
    }


class PlatformError(Exception):
    """Base class for all domain errors. Never leaks stack traces."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "PLATFORM_ERROR"
    severity: str = "ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(PlatformError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ConflictError(PlatformError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    severity = "WARNING"


class DuplicateActivityError(ConflictError):
    error_code = "DUPLICATE_ACTIVITY"


class DuplicateImportError(ConflictError):
    error_code = "DUPLICATE_IMPORT"


class UnauthorizedError(PlatformError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"


class ForbiddenError(PlatformError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


class RateLimitedError(PlatformError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMITED"
    severity = "WARNING"


class PlatformValidationError(PlatformError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"


class ConfirmationRequiredError(PlatformError):
    """Ambiguous unit / data: never silently converted (Module D rule)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "CONFIRMATION_REQUIRED"
    severity = ValidationSeverity.CONFIRMATION_REQUIRED.value


class InvalidUnitError(PlatformValidationError):
    error_code = "INVALID_UNIT"


class EmissionFactorNotFoundError(PlatformError):
    """Missing factor is an explicit unresolved state, never a fabricated default."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "EMISSION_FACTOR_NOT_FOUND"
    severity = "WARNING"


class FileValidationError(PlatformValidationError):
    error_code = "FILE_VALIDATION_ERROR"


class PeriodLockedError(ConflictError):
    error_code = "PERIOD_LOCKED"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlatformError)
    async def _platform(_: Request, exc: PlatformError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.error_code, exc.message, exc.severity, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [
            {
                "severity": ValidationSeverity.ERROR.value,
                "code": err.get("type", "invalid"),
                "message": err.get("msg", "Invalid value"),
                "field": ".".join(str(p) for p in err.get("loc", []) if p != "body") or None,
                "details": None,
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(
                "VALIDATION_ERROR",
                "Request payload failed schema validation.",
                details={"issues": issues},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        # F-14: log the real cause with request context so production
        # incidents are debuggable; the response stays the frozen safe shape.
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "unhandled error path=%s method=%s request_id=%s",
            request.url.path, request.method, request_id,
        )
        # P1-04 fix: Starlette runs this handler at ServerErrorMiddleware level,
        # OUTSIDE CORSMiddleware and the security-headers middleware, so 5xx
        # responses previously carried no CORS/security/request-id headers and
        # browsers surfaced them as opaque ERR_FAILED. Re-apply them here.
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
        origin = request.headers.get("origin")
        if origin:
            from app.config import get_settings

            if origin in get_settings().cors_origins_list:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"
                headers["Vary"] = "Origin"
        if request_id:
            headers["X-Request-Id"] = request_id
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_payload(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Please retry later.",
                "ERROR",
                {"request_id": request_id} if request_id else {},
            ),
            headers=headers,
        )
