"""Canonical JSON encoding for engine output.

Pydantic's ``model_dump(mode="json")`` serialises ``Decimal`` as a *string*.
The frozen Phase 0 mocks use JSON *numbers*, and P1 renders them numerically, so
the engine must emit numbers too. This encoder walks any engine payload and:

- ``Decimal`` -> int when integral, else float (matching the mock's number type)
- ``Enum``    -> its ``.value``
- ``datetime``/``date`` -> ISO 8601 string
- ``UUID``    -> string
- ``BaseModel`` -> python dump, then recursed

Precision is preserved for the calculation itself (all arithmetic is Decimal);
only the wire representation is numeric.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {_key(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _key(key: Any) -> str:
    if isinstance(key, Enum):
        return str(key.value)
    return str(key)
