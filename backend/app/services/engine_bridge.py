"""Phase 2 bridge between the P2 platform and the P3 (F/G/L) / P4 (J) engines.

Everything here is read-only and gated by ``settings.use_mock_data``:

    USE_MOCK_DATA=true  -> Phase 1 mock data source (instant fallback).
    USE_MOCK_DATA=false -> SQL data source over this app's PostgreSQL tables,
                           DSN overridable with ECOLEAK_SQL_DSN / ENGINE_DSN.

P2 remains the dependency root, so this module never mutates engine internals:
it constructs a *fresh* :class:`EcoLeakEngine` per request instead of touching
the merged app's global engine singleton.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _sql_data_source():
    from sqlalchemy import create_engine

    from engine.sql_source import SQLActivityDataSource

    settings = get_settings()
    dsn = settings.engine_dsn or settings.database_url
    connect_args = {"connect_timeout": 3} if dsn.startswith("postgresql") else {}
    return SQLActivityDataSource(create_engine(dsn, future=True, connect_args=connect_args))


def mock_data_source():
    from engine.data_source import load_mock_data_source

    return load_mock_data_source()


def build_engine():
    """Return an engine bound to the flag-selected data source."""
    from engine.service import EcoLeakEngine

    settings = get_settings()
    source = mock_data_source() if settings.use_mock_data else _sql_data_source()
    return EcoLeakEngine(data_source=source)


def real_inventory(engine, facility_id: str, period_id: str) -> dict[str, Any]:
    from engine.serialization import to_jsonable

    inventory = engine.calculate_inventory(facility_id, period_id)
    provenance = to_jsonable(list(inventory.factor_provenance().values()))
    for unresolved in inventory.unresolved:
        provenance.append({"status": "UNRESOLVED", **unresolved.to_issue()})
    return {
        "summary": to_jsonable(inventory.inventory_summary()),
        "factor_provenance": provenance,
        "unresolved": [u.to_issue() for u in inventory.unresolved],
        "onsite_generation_kgco2e": to_jsonable(inventory.onsite_generation_kgco2e),
        "exported_electricity_kgco2e": to_jsonable(inventory.exported_electricity_kgco2e),
        "data_quality_score": to_jsonable(inventory.data_quality_score),
    }


def real_hotspots(engine, facility_id: str, period_id: str) -> dict[str, Any]:
    from engine.serialization import to_jsonable

    result = engine.hotspot_result(facility_id, period_id)
    return to_jsonable(result)


def real_circularity(engine, facility_id: str, period_id: str) -> dict[str, Any]:
    from engine.serialization import to_jsonable

    return to_jsonable(engine.circularity_score(facility_id, period_id).to_dict())


def real_recommendations(
    engine, facility_id: str, period_id: str
) -> Optional[dict[str, Any]]:
    """Best-effort live J (P4). Returns None if the P4 ranker is unavailable."""
    try:
        from engine.serialization import to_jsonable
        from p4.data_source import (
            build_facility_context,
            load_facility_dataset,
            resource_factors_from_factors,
        )
        from p4.engine import generate_with_diagnostics
        from p4.explainability import TemplateExplainer

        # GA-01/P4-C1 fix: previously these came from mocks/mock_dataset.json
        # and p4/demo/demo_context.json, so a non-demo facility raised
        # "context.facility_id does not match facility.id" and the Module P
        # recommendations section was silently dropped.
        organization, facility, processes = load_facility_dataset(engine, facility_id)
        if organization is None or facility is None:
            return None
        hotspots = engine.hotspot_result(facility_id, period_id)
        run = generate_with_diagnostics(
            hotspots,
            facility,
            organization=organization,
            processes=processes,
            context=build_facility_context(engine, facility_id, period_id),
            emission_factors=resource_factors_from_factors(
                engine.data_source.get_emission_factors(), facility.country
            ),
            constraints=None,
            explainer=TemplateExplainer(),
        )
        # J2/RecommendationGenerationResult -> canonical API dict.
        from p4.serialization import to_api_dict

        return to_jsonable(to_api_dict(run.result))
    except Exception as exc:  # noqa: BLE001 - degrade to UNAVAILABLE, never break the report
        return {"__unavailable__": f"{type(exc).__name__}: {exc}"}


def flag_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "use_mock_data": settings.use_mock_data,
        "engine_dsn_configured": bool(settings.engine_dsn),
    }
