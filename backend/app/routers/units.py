"""Module D1: unit normalization endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import api_rate_limit
from app.schemas.requests import NormalizeRequest
from app.security import Principal, get_current_principal
from app.services import units

router = APIRouter(prefix="/api", tags=["Module D - Units"])


@router.post("/units/normalize", dependencies=[Depends(api_rate_limit)])
def normalize_unit(
    payload: NormalizeRequest,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    result = units.normalize(payload.value, payload.from_unit, payload.to_unit)
    return result.as_dict()
