"""Domain exceptions and the frozen safe-error response shape (DB doc section 28)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.enums import ValidationSeverity


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
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_payload(
                "INTERNAL_ERROR", "An unexpected error occurred. Please retry later."
            ),
        )
