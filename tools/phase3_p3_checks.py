"""Phase 3 P3 audit checks (executed evidence for docs/phase3/p3_audit.md).

Runs the 6-item audit checklist against the shipped engine and prints a
machine-checkable evidence table. No code under audit is modified.

    python -m tools.phase3_p3_checks

Exit 0 = all checks performed and their assertions held; 1 = an assertion failed.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from contracts.schemas import ActivityCategory, ActivityData, EmissionFactor, Scope  # noqa: E402
from engine.config import EngineConfig  # noqa: E402
from engine.data_source import InMemoryDataSource, load_mock_data_source  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402
from engine.simulator import InterventionSelection  # noqa: E402
from engine.sql_source import SQLActivityDataSource  # noqa: E402

MOCK = ROOT / "mocks" / "mock_dataset.json"
REAL_FACTORS = ROOT / "backend" / "app" / "seed" / "real_factors.json"
P4_DEMO_OUT = ROOT / "p4" / "demo" / "output" / "demo_recommendation_output.json"
P4_DEMO_OUT_ALT = ROOT / "docs" / "phase2" / "p4_baseline_output.json"
FID = "0a1b2c3d-0002-4002-8002-000000000002"
PID = "0a1b2c3d-0003-4003-8003-000000000003"
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


# =====================================================================
# 1. Hand-derive real emission calculations
# =====================================================================
def check_hand_derived() -> None:
    print("\n== 1. Hand-derived emission calculations (raw activity x factor) ==")
    engine = EcoLeakEngine(data_source=load_mock_data_source())
    inv = engine.calculate_inventory(FID, PID)
    by_activity = {str(r.activity.id): r for r in inv.records}

    # (activity_id, raw value, raw unit, expected factor, expected co2e)
    # Derived independently from mocks/mock_dataset.json, not from the engine.
    manual = [
        ("0a1b2c3d-00a1-40a1-80a1-0000000000a1", Decimal("210000"), "kWh", Decimal("0.71"),
         Decimal("210000") * Decimal("0.71")),
        ("0a1b2c3d-00a5-40a5-80a5-0000000000a5", Decimal("95000"), "m3", Decimal("2.022"),
         Decimal("95000") * Decimal("2.022")),
        ("0a1b2c3d-00a6-40a6-80a6-0000000000a6", Decimal("12000"), "L", Decimal("2.68"),
         Decimal("12000") * Decimal("2.68")),
        ("0a1b2c3d-00a7-40a7-80a7-0000000000a7", Decimal("1100000"), "kg", Decimal("5.9"),
         Decimal("1100000") * Decimal("5.9")),
        ("0a1b2c3d-00ad-40ad-80ad-0000000000ad", Decimal("320000"), "tonne_km", Decimal("0.105"),
         Decimal("320000") * Decimal("0.105")),
    ]
    all_ok = True
    for aid, value, unit, factor, expected in manual:
        rec = by_activity[aid]
        actual = rec.co2e_kg
        ok = actual == expected
        all_ok &= ok
        print(f"    {aid[:13]}… {value} {unit} x {factor} = {expected} | engine={actual} "
              f"| factor={rec.calculation.assumptions['factor_code']} "
              f"v{rec.calculation.assumptions['factor_version']}")
    check("hand-derived products match engine co2e exactly", all_ok)

    # real-factor hand derivation
    from tests.test_sql_source import _seed

    tmp = Path(tempfile.mkdtemp(prefix="p3c_")) / "r.sqlite3"
    se = create_engine(f"sqlite+pysqlite:///{tmp}", future=True)
    _seed(se, factors=json.loads(REAL_FACTORS.read_text(encoding="utf-8")))
    rinv = EcoLeakEngine(data_source=SQLActivityDataSource(se)).calculate_inventory(FID, PID)
    rby = {str(r.activity.id): r for r in rinv.records}
    ng = rby["0a1b2c3d-00a5-40a5-80a5-0000000000a5"].co2e_kg
    diesel = rby["0a1b2c3d-00a6-40a6-80a6-0000000000a6"].co2e_kg
    expected_ng = Decimal("95000") * Decimal("2.0384")
    expected_diesel = Decimal("12000") * Decimal("2.6594")
    print(f"    real NG    95000 m3 x 2.0384 = {expected_ng} | engine={ng}")
    print(f"    real diesel 12000 L x 2.6594 = {expected_diesel} | engine={diesel}")
    check("real-factor hand derivations match", ng == expected_ng and diesel == expected_diesel)


# =====================================================================
# 2. Hotspot weighted formula + graceful missing-component degradation
# =====================================================================
def check_hotspot_weights() -> None:
    print("\n== 2. Hotspot weighted formula + missing-component handling ==")
    engine = EcoLeakEngine(data_source=load_mock_data_source())
    analysis = engine.detect_hotspots(FID, PID, generated_at=NOW)
    w = engine.config.hotspot.weights.as_dict()
    print(f"    configured weights: {w}")
    all_ok = True
    for h in analysis.result.hotspots:
        comps = {
            "carbon_contribution": h.contribution_percent,
            "carbon_intensity": None,  # normalized internally, not exposed as a 0-100 score
            "inefficiency": h.inefficiency_score,
            "waste_ratio": h.waste_ratio_score,
            "improvement_potential": h.improvement_potential_score,
        }
        # Reconstruct using the exposed components + the intensity score the engine used.
        # The intensity score is derived from carbon_intensity / max(carbon_intensity).
        intensities = [x.carbon_intensity for x in analysis.result.hotspots if x.carbon_intensity is not None]
        max_i = max(intensities) if intensities else None
        if h.carbon_intensity is not None and max_i:
            comps["carbon_intensity"] = h.carbon_intensity / max_i * Decimal("100")
        avail = {k: v for k, v in comps.items() if v is not None}
        total_w = sum(Decimal(str(w[k])) for k in avail)
        manual = sum(Decimal(str(w[k])) * v for k, v in avail.items()) / total_w
        manual = min(Decimal("100"), max(Decimal("0"), manual)).quantize(Decimal("0.01"))
        # exposed carbon_intensity is rounded to 4dp, so allow a cent of drift
        ok = abs(manual - h.hotspot_score) <= Decimal("0.02")
        all_ok &= ok
        print(f"    {h.process_name:10s} manual={manual} engine={h.hotspot_score} "
              f"missing={[k for k, v in comps.items() if v is None]}")
    check("manual weighted recomputation matches engine hotspot_score", all_ok)

    # Missing benchmark => component None (not silently zero), and reweight applied.
    dry = [h for h in analysis.result.hotspots if h.process_name == "Drying"][0]
    check("missing improvement is None (not silently zeroed)", dry.improvement_potential_score is None)
    cfg = EngineConfig()
    cfg.hotspot.inefficiency_strategy = "UNAVAILABLE"
    cfg.hotspot.waste_ratio_strategy = "UNAVAILABLE"
    eng2 = EcoLeakEngine(data_source=load_mock_data_source(), config=cfg)
    a2 = eng2.detect_hotspots(FID, PID, generated_at=NOW)
    check("unavailable components stay None + ranking still produced",
          all(h.inefficiency_score is None for h in a2.result.hotspots) and a2.result.hotspots[0].process_name == "Boiler")

    # RANKING-IMPACT: missing improvement reweighted vs treated-as-zero.
    def score_zero_fill(h):
        comps = {
            "carbon_contribution": h.contribution_percent or Decimal("0"),
            "carbon_intensity": (h.carbon_intensity / max(x.carbon_intensity for x in analysis.result.hotspots
                                                          if x.carbon_intensity is not None) * Decimal("100"))
            if h.carbon_intensity is not None else Decimal("0"),
            "inefficiency": h.inefficiency_score or Decimal("0"),
            "waste_ratio": h.waste_ratio_score or Decimal("0"),
            "improvement_potential": h.improvement_potential_score or Decimal("0"),
        }
        return sum(Decimal(str(w[k])) * v for k, v in comps.items()).quantize(Decimal("0.01"))

    engine_rank = [h.process_name for h in analysis.result.hotspots]
    zero_rank = [h.process_name for h in sorted(analysis.result.hotspots, key=score_zero_fill, reverse=True)]
    print(f"    engine rank:    {engine_rank}")
    print(f"    zero-fill rank: {zero_rank}")
    check("missing-improvement policy does NOT change rank order", engine_rank == zero_rank,
          f"engine={engine_rank} zero_fill={zero_rank}")


# =====================================================================
# 3. Missing/unresolved factors under real data gaps
# =====================================================================
def check_unresolved() -> None:
    print("\n== 3. Unresolved factors under real data gaps ==")
    from tests.test_sql_source import _seed

    tmp = Path(tempfile.mkdtemp(prefix="p3u_")) / "r.sqlite3"
    se = create_engine(f"sqlite+pysqlite:///{tmp}", future=True)
    _seed(se, factors=json.loads(REAL_FACTORS.read_text(encoding="utf-8")))
    inv = EcoLeakEngine(data_source=SQLActivityDataSource(se)).calculate_inventory(FID, PID)
    codes = {u.code for u in inv.unresolved}
    cats = {u.activity_category for u in inv.unresolved}
    print(f"    unresolved={len(inv.unresolved)} codes={codes} categories={sorted(cats)}")
    print(f"    scope3={inv.scope3_kgco2e} total={inv.total_kgco2e} operational={inv.operational_kgco2e}")
    check("real gaps -> explicit unresolved only", codes == {"EMISSION_FACTOR_NOT_FOUND"})
    check("no fabricated Scope-3 value", inv.scope3_kgco2e == Decimal("0")
          and inv.total_kgco2e == inv.operational_kgco2e)

    # No factors at all: everything unresolved, total 0.
    empty = InMemoryDataSource(
        facilities=load_mock_data_source().list_facilities(),
        reporting_periods=[load_mock_data_source().get_reporting_period(PID)],
        activity_data=load_mock_data_source().get_activity_data(FID, PID),
        emission_factors=[],
    )
    e = EcoLeakEngine(data_source=empty)
    inv0 = e.calculate_inventory(FID, PID)
    check("zero factors -> all unresolved, total 0",
          len(inv0.unresolved) == 13 and inv0.total_kgco2e == Decimal("0"))


# =====================================================================
# 4. Simulator edge cases
# =====================================================================
def _p4_demo_recs() -> list[dict]:
    for p in (P4_DEMO_OUT, P4_DEMO_OUT_ALT):
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            recs = data.get("recommendations", [])
            if recs:
                return recs
    return []


def check_simulator() -> None:
    print("\n== 4. Simulator edge cases ==")
    engine = EcoLeakEngine(data_source=load_mock_data_source())
    recs = _p4_demo_recs()
    codes = [r.get("intervention_code") for r in recs]
    print(f"    P4 recommendation combination ({len(codes)}): {codes}")
    by_code = {iv.intervention_code: iv for iv in engine.data_source.get_interventions()}
    selections = [InterventionSelection(by_code[c], Decimal("100")) for c in codes if c in by_code]
    if len(selections) < 2:
        check("P4 combination resolvable on mock source", False,
              f"only {len(selections)} of {len(codes)} codes resolved")
        return
    combined = engine.simulate(FID, PID, selections, scenario_id="p3-audit-combined", generated_at=NOW)
    solo_sum = Decimal("0")
    for s in selections:
        solo = engine.simulate(FID, PID, [s], scenario_id="p3-audit-solo-" + s.intervention.intervention_code,
                               generated_at=NOW)
        solo_sum += solo.assessment.total_co2_saving_kg
    print(f"    combined_saving={combined.assessment.total_co2_saving_kg} "
          f"sum(solo)={solo_sum} projected={combined.assessment.projected_emissions_kg}")
    check("combined saving <= naive sum (no double count)",
          combined.assessment.total_co2_saving_kg <= solo_sum)
    check("projected emissions floored at >= 0", combined.assessment.projected_emissions_kg >= 0)
    check("combined saving < naive sum (overlapping Dyeing interventions interact)",
          combined.assessment.total_co2_saving_kg < solo_sum)

    # payback unavailable when saving <= 0
    zero = engine.simulate(FID, PID, [InterventionSelection(selections[0].intervention, Decimal("0"))],
                           scenario_id="p3-audit-zero", generated_at=NOW)
    print(f"    adoption=0 -> saving={zero.assessment.total_co2_saving_kg} "
          f"payback={zero.assessment.payback_years} status={zero.payback_status}")
    check("saving<=0 -> payback unavailable (no broken number)",
          zero.assessment.payback_years is None and zero.payback_status == "UNAVAILABLE")


# =====================================================================
# 5. Circularity internal-metric labelling
# =====================================================================
def check_circularity() -> None:
    print("\n== 5. Circularity internal-metric labelling ==")
    from fastapi.testclient import TestClient

    from engine.api import app

    engine = EcoLeakEngine(data_source=load_mock_data_source())
    d = engine.circularity_score(FID, PID, generated_at=NOW).to_dict()
    print(f"    to_dict: is_internal_metric={d.get('is_internal_metric')} "
          f"not_a_certified_standard={d.get('not_a_certified_standard')} "
          f"disclaimer={'present' if d.get('disclaimer') else 'MISSING'}")
    check("library response labelled internal + non-certified + disclaimer",
          d.get("is_internal_metric") is True and d.get("not_a_certified_standard") is True
          and bool(d.get("disclaimer")))

    client = TestClient(app)
    r = client.get(f"/api/facilities/{FID}/reporting-periods/{PID}/circularity-score")
    body = r.json()
    print(f"    L1 endpoint {r.status_code}: is_internal_metric={body.get('is_internal_metric')} "
          f"disclaimer={'present' if body.get('disclaimer') else 'MISSING'}")
    check("L1 API response labelled internal + not certified + disclaimer",
          r.status_code == 200 and body.get("is_internal_metric") is True
          and body.get("not_a_certified_standard") is True and bool(body.get("disclaimer")))


# =====================================================================
# 6. Reproducibility under a factor version update
# =====================================================================
def check_reproducibility() -> None:
    print("\n== 6. Reproducibility: factor version update leaves OLD calculation unchanged ==")
    activity = ActivityData(
        id="11111111-1111-4111-8111-111111111111",
        facility_id=FID,
        process_id=None,
        reporting_period_id=PID,
        activity_category=ActivityCategory.FUEL,
        activity_subcategory="Natural gas - stationary combustion",
        normalized_value=Decimal("1000"),
        normalized_unit="m3",
        original_value=Decimal("1000"),
        original_unit="m3",
        created_at=NOW,
    )
    v1 = EmissionFactor(
        id="22222222-2222-4222-8222-222222222222", factor_code="EF-NG-V1", category="FUEL",
        subcategory="Natural gas", item_name="Natural gas - stationary combustion",
        scope=Scope.SCOPE_1, input_unit="m3", total_co2e_factor=Decimal("2.022"),
        source_name="IPCC 2006", source_year=2006, version="2006.2", active=True, created_at=NOW,
    )
    v2 = EmissionFactor(
        id="33333333-3333-4333-8333-333333333333", factor_code="EF-NG-V2", category="FUEL",
        subcategory="Natural gas", item_name="Natural gas - stationary combustion",
        scope=Scope.SCOPE_1, input_unit="m3", total_co2e_factor=Decimal("2.0384"),
        source_name="DEFRA 2023", source_year=2023, version="DEFRA-2023", active=True, created_at=NOW,
    )
    fac = load_mock_data_source().get_facility(FID)
    period = load_mock_data_source().get_reporting_period(PID)

    ds1 = InMemoryDataSource(facilities=[fac], reporting_periods=[period], activity_data=[activity],
                             emission_factors=[v1])
    calc1 = EcoLeakEngine(data_source=ds1).calculate_inventory(FID, PID, generated_at=NOW)
    r1 = calc1.records[0].calculation
    snap1 = {
        "id": str(r1.id), "co2e": r1.co2e_kg, "factor_id": str(r1.emission_factor_id),
        "version": r1.assumptions["factor_version"], "source": r1.assumptions["factor_source"],
    }
    print(f"    v1: {snap1['co2e']} kg (factor {snap1['factor_id'][:8]} v{snap1['version']})")

    # Emulate E4 version update: old row deactivated (never overwritten), new row added.
    v1_old = v1.model_copy(update={"active": False})
    ds2 = InMemoryDataSource(facilities=[fac], reporting_periods=[period], activity_data=[activity],
                             emission_factors=[v1_old, v2])
    calc2 = EcoLeakEngine(data_source=ds2).calculate_inventory(FID, PID, generated_at=NOW)
    r2 = calc2.records[0].calculation
    print(f"    v2: {r2.co2e_kg} kg (factor {str(r2.emission_factor_id)[:8]} v{r2.assumptions['factor_version']})")

    # Old captured calculation object must be unchanged.
    unchanged = (str(r1.id) == snap1["id"] and r1.co2e_kg == snap1["co2e"]
                 and str(r1.emission_factor_id) == snap1["factor_id"]
                 and r1.assumptions["factor_version"] == snap1["version"])
    check("OLD calculation result is byte-stable after factor update", unchanged)
    check("NEW calculation uses the new factor version",
          str(r2.emission_factor_id) == str(v2.id) and r2.assumptions["factor_version"] == "DEFRA-2023")
    check("old factor row retained (deactivated, not overwritten)",
          any(f.id == v1.id and f.active is False for f in ds2.get_emission_factors(active_only=False)))
    # deterministic id reproducible
    expected_id = str(r1.id)
    ds1b = InMemoryDataSource(facilities=[fac], reporting_periods=[period], activity_data=[activity],
                              emission_factors=[v1])
    r1b = EcoLeakEngine(data_source=ds1b).calculate_inventory(FID, PID, generated_at=NOW).records[0].calculation
    check("recomputing v1 yields the same deterministic calculation id", str(r1b.id) == expected_id)

    # System-level caveat: nothing persisted (P3-07)
    print("    caveat: engine is stateless — the OLD result survives only if the caller stored it (P3-07).")


def main() -> int:
    check_hand_derived()
    check_hotspot_weights()
    check_unresolved()
    check_simulator()
    check_circularity()
    check_reproducibility()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"CHECKLIST: {len(FAILURES)} assertion(s) failed / flagged: {FAILURES}")
        return 1
    print("CHECKLIST: all assertions held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
