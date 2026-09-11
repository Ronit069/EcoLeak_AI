"""FastAPI-compatible JSON serialization for the frozen contract models.

Pydantic's `model_dump(mode="json")` renders `Decimal` as a JSON *string*;
FastAPI's `jsonable_encoder` (what P2 will actually serve) renders it as a
*number*. To keep the demo artifacts, tests, and the future API identical
(and to match the Phase 0 mock, where scores/CAPEX are numbers), P4 emits its
DTOs through `to_api_dict`:

    Decimal  -> float      (numeric, matches mocks/*.json)
    datetime -> ISO string (parseable by Zod/Date)
    UUID     -> string
    Enum     -> value
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def _convert(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return to_api_dict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _convert(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_convert(item) for item in value]
    return value


def to_api_dict(model: BaseModel) -> dict:
    """Serialize any contract model into a JSON-ready dict (numbers stay numeric)."""

    return {key: _convert(value) for key, value in model.model_dump(mode="python").items()}
