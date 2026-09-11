"""Domain-specific exceptions (library doc §28).

The API layer maps these onto the frozen error shape from ``api_contract.md``:

    {"error_code": ..., "message": ..., "severity": ..., "details": {}}
"""

from __future__ import annotations

from typing import Any


class CarbonPlatformError(Exception):
    """Base class for all engine domain errors."""

    error_code = "CARBON_PLATFORM_ERROR"
    severity = "ERROR"
    status_code = 422

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_error_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


class InvalidUnitError(CarbonPlatformError):
    error_code = "INVALID_UNIT"


class EmissionFactorNotFoundError(CarbonPlatformError):
    error_code = "EMISSION_FACTOR_NOT_FOUND"
    severity = "WARNING"


class DuplicateActivityError(CarbonPlatformError):
    error_code = "DUPLICATE_ACTIVITY"
    severity = "CONFIRMATION_REQUIRED"


class NegativeActivityError(CarbonPlatformError):
    error_code = "NEGATIVE_ACTIVITY"


class InvalidScenarioError(CarbonPlatformError):
    error_code = "INVALID_SCENARIO"


class InterventionNotApplicableError(CarbonPlatformError):
    error_code = "INTERVENTION_NOT_APPLICABLE"
    severity = "WARNING"


class InsufficientDataError(CarbonPlatformError):
    error_code = "INSUFFICIENT_DATA"
    severity = "WARNING"


class BudgetExceededError(CarbonPlatformError):
    error_code = "BUDGET_EXCEEDED"
    severity = "WARNING"


class EntityNotFoundError(CarbonPlatformError):
    error_code = "NOT_FOUND"
    status_code = 404


class MissingParameterError(CarbonPlatformError):
    error_code = "MISSING_PARAMETER"
    severity = "WARNING"
