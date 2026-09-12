"""Phase 2 P3: F/G/K/L against P2's real data path.

Runs the engine over ``engine.sql_source.SQLActivityDataSource`` (P2 table names)
seeded with P2's real emission factors (``backend/app/seed/real_factors.json``),
then pins:

- the known operational-total shift (+0.23% vs the Phase 1 mock),
- the genuine missing-factor gaps in P2's real factor table (Scope 3 unresolved),
- that the hotspot output still validates the frozen contract and keeps a stable
  rank order for P4.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.schemas import HotspotDetectionResult  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402
from engine.sql_source import SQLActivityDataSource  # noqa: E402
from tests.test_sql_source import FID, PID, _seed  # noqa: E402

REAL_FACTORS = ROOT / "backend" / "app" / "seed" / "real_factors.json"


@pytest.fixture(scope="module")
def real_engine(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("phase2_real") / "ecoleak.sqlite3"
    sql_engine = create_engine(f"sqlite+pysqlite:///{tmp}", future=True)
    _seed(sql_engine, factors=json.loads(REAL_FACTORS.read_text(encoding="utf-8")))
    return EcoLeakEngine(data_source=SQLActivityDataSource(sql_engine))


def test_real_source_is_sql_activity_data_source(real_engine):
    assert type(real_engine.data_source).__name__ == "SQLActivityDataSource"


def test_operational_total_matches_recorded_real_factor_shift(real_engine):
    inv = real_engine.calculate_inventory(FID, PID)
    assert inv.scope2_kgco2e == Decimal("340800")
    assert inv.scope1_kgco2e == Decimal("225560.800000")
    assert inv.operational_kgco2e == Decimal("566360.800000")
    # +0.23% vs the Phase 1 mock baseline 565,050 (documented divergence).
    assert inv.operational_kgco2e - Decimal("565050") == Decimal("1310.800000")


def test_missing_factor_is_unresolved_on_real_factor_gaps(real_engine):
    inv = real_engine.calculate_inventory(FID, PID)
    codes = {u.code for u in inv.unresolved}
    assert codes == {"EMISSION_FACTOR_NOT_FOUND"}
    # P2's real Phase-2 seed has no Scope-3 factors yet: every Scope-3 category
    # must degrade to an explicit unresolved row, never a fabricated value.
    assert {u.activity_category for u in inv.unresolved} == {"MATERIAL", "WATER", "WASTE", "TRANSPORT"}
    assert inv.scope3_kgco2e == Decimal("0")
    assert inv.total_kgco2e == inv.operational_kgco2e


def test_resolved_factors_keep_provenance(real_engine):
    inv = real_engine.calculate_inventory(FID, PID)
    provenance = list(inv.factor_provenance().values())
    assert provenance, "expected resolved factors to carry provenance"
    for entry in provenance:
        assert entry["factor_code"]
        assert entry["version"]
        assert entry["source_name"]
        assert entry["source_year"]


def test_hotspot_shape_stable_and_rank_order_for_p4(real_engine):
    result = real_engine.hotspot_result(FID, PID)
    # frozen contract still validates
    HotspotDetectionResult.model_validate(result.model_dump(mode="python"))
    assert [h.process_name for h in result.hotspots] == [
        "Boiler", "Dyeing", "Drying", "Finishing", "Packaging"
    ]
    assert result.hotspots[0].process_name == "Boiler"
    # field set is exactly the frozen contract (drop-in for P4)
    expected = set(HotspotDetectionResult.model_fields)
    assert set(result.model_dump(mode="python").keys()) == expected
    assert set(result.hotspots[0].model_dump(mode="python").keys()) == set(
        type(result.hotspots[0]).model_fields
    )


def test_simulator_and_circularity_run_on_real_data(real_engine):
    from engine.simulator import InterventionSelection

    interventions = real_engine.data_source.get_interventions()
    result = real_engine.simulate(
        FID, PID, [InterventionSelection(interventions[0], Decimal("100"))], scenario_id="phase2-test"
    )
    assert result.assessment.baseline_emissions_kg > 0
    assert result.assessment.projected_emissions_kg >= 0

    circularity = real_engine.circularity_score(FID, PID)
    assert circularity.is_internal_metric is True
    assert circularity.disclaimer
    assert Decimal("0") <= circularity.total_score <= Decimal("100")
