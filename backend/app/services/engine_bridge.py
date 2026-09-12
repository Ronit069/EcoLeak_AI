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
    return SQLActivityDataSource(create_engine(dsn, future=True))


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
        from p4.demo.run_demo import _load_json, _resource_factors
        from p4.engine import generate_with_diagnostics
        from p4.explainability import TemplateExplainer
        from p4.models import FacilityContext

        repo_root = _REPO_ROOT
        dataset = _load_json(repo_root / "mocks" / "mock_dataset.json")
        context = FacilityContext.model_validate(
            _load_json(repo_root / "p4" / "demo" / "demo_context.json")
        )
        organization = engine.data_source.get_organization()
        facility = engine.data_source.get_facility(facility_id)
        processes = engine.data_source.get_processes(facility_id)
        if organization is None or facility is None:
            return None
        hotspots = engine.hotspot_result(facility_id, period_id)
        run = generate_with_diagnostics(
            hotspots,
            facility,
            organization=organization,
            processes=processes,
            context=context,
            emission_factors=_resource_factors(dataset),
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
