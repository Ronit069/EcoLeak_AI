"""B3: real-factor run vs the frozen mock — divergence is documented, not hidden.

Decision (recorded in CONTRACTS_README, Phase 1 change requests): the frozen
mock is an *illustrative reference* (shape + rank order + contribution %), not
an exact reproduction target. P2's seeded real factors (CEA FY24-25 0.71,
DEFRA 2023 NG 2.0384 / diesel 2.6594) shift operational emissions by +0.23%
and severity bands differ (Boiler HIGH on real factors vs CRITICAL in the
mock). This test pins the real-factor numbers so the gap stays visible and
never silently regresses.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.schemas import EmissionFactor  # noqa: E402
from engine.data_source import load_mock_data_source  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402

REAL_FACTORS = ROOT / "backend" / "app" / "seed" / "real_factors.json"


def _real_factors() -> list[EmissionFactor]:
    out = []
    for item in json.loads(REAL_FACTORS.read_text(encoding="utf-8")):
        d = {k: v for k, v in item.items() if k not in ("supplier_id", "supplier_specific")}
        d["created_at"] = datetime(2026, 1, 1, tzinfo=timezone.utc)
        out.append(EmissionFactor.model_validate(d))
    return out


class FactorOverrideSource:
    """Mock rows with the factor table swapped to P2's real seed."""

    def __init__(self, delegate, factors):
        self._delegate = delegate
        self._factors = factors

    def get_emission_factors(self, active_only=True):
        return self._factors

    def get_benchmarks(self, facility_id=None):
        return self._delegate.get_benchmarks(facility_id)

    def __getattr__(self, name):
        return getattr(self._delegate, name)


def _context():
    src = load_mock_data_source()
    fid = str(src.list_facilities()[0].id)
    pid = str(src.list_reporting_periods(fid)[0].id)
    return src, fid, pid


def test_real_factors_shift_operational_totals_by_known_amount() -> None:
    src, fid, pid = _context()
    engine = EcoLeakEngine(data_source=FactorOverrideSource(src, _real_factors()))
    inv = engine.calculate_inventory(fid, pid)
    # Grid is identical (CEA 0.71 == mock 0.71); NG/DEFRA and diesel/DEFRA shift.
    assert inv.scope2_kgco2e == Decimal("340800")
    assert inv.scope1_kgco2e == Decimal("225560.800000")
    assert inv.operational_kgco2e == Decimal("566360.800000")
    # ...versus the mock baseline 565050 (recorded divergence).
    assert abs(inv.operational_kgco2e - Decimal("565050")) == Decimal("1310.800000")


def test_real_factors_leave_scope3_activities_explicitly_unresolved() -> None:
    src, fid, pid = _context()
    engine = EcoLeakEngine(data_source=FactorOverrideSource(src, _real_factors()))
    inv = engine.calculate_inventory(fid, pid)
    # P2's Phase-1 seed has no Scope-3 factors yet -> honest unresolved states,
    # never fabricated values.
    codes = {u.code for u in inv.unresolved}
    assert codes == {"EMISSION_FACTOR_NOT_FOUND"}
    categories = {u.activity_category for u in inv.unresolved}
    assert categories == {"MATERIAL", "WATER", "WASTE", "TRANSPORT"}
    assert inv.total_kgco2e == inv.operational_kgco2e  # scope3 contributes 0


def test_real_factor_hotspot_severity_labels_recorded() -> None:
    src, fid, pid = _context()
    engine = EcoLeakEngine(data_source=FactorOverrideSource(src, _real_factors()))
    result = engine.hotspot_result(fid, pid)
    labels = [(h.process_name, h.hotspot_score, h.severity.value, h.contribution_percent) for h in result.hotspots]
    # Pinned reference (documented in PHASE1_AUDIT.md §1/B3): severity bands are
    # NOT the mock's (Boiler CRITICAL 88.5), because the mock is illustrative.
    assert labels[0] == ("Boiler", Decimal("76.41"), "HIGH", Decimal("39.8263"))
    assert labels[1][2] == "MODERATE"  # Dyeing
    assert [l[3] for l in labels] == [
        Decimal("39.8263"), Decimal("26.3260"), Decimal("18.8043"),
        Decimal("10.0289"), Decimal("5.0145"),
    ]