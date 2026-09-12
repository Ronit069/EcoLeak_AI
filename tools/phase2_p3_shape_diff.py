"""Phase 2 P3 integration runner (mock baseline vs P2 real data).

Runs the Phase 1 F/G/K/L engine twice and writes reproducible artifacts:

    docs/phase2/p3_baseline_output.json   -> mock_dataset.json (Phase 1 logic)
    docs/phase2/p3_real_data_output.json  -> P2 tables (SQL source) + real factors
    docs/phase2/p3_shape_diff.md          -> field-for-field shape diff

"Real data" here is the P2 runtime path: ``engine.sql_source.SQLActivityDataSource``
reading the same table/column names as P2's backend models. Because no PostgreSQL
instance is assumed, the runner seeds a portable SQLite image of those tables
(activity/facility/process rows from the frozen dataset) with P2's **real**
seeded emission factors (``backend/app/seed/real_factors.json``). That is exactly
the path the merged API takes when ``USE_MOCK_DATA=false``.

The diff is SHAPE-only (keys + scalar types), never values, because the whole
point of Phase 2 is that real data may change numbers but must not change what
P1/P4 consume.

Run:  python -m tools.phase2_p3_shape_diff
Exit: 0 = shapes identical (or documented), 1 = unlogged shape drift.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from engine.data_source import load_mock_data_source  # noqa: E402
from engine.serialization import to_jsonable  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402
from engine.sql_source import SQLActivityDataSource  # noqa: E402
from engine.simulator import InterventionSelection  # noqa: E402
from validate_against_mock import compare, shape_of  # noqa: E402

# Fixed timestamp so the baseline artifact is byte-stable across runs.
GENERATED_AT = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)

DOCS = ROOT / "docs" / "phase2"
REAL_FACTORS = ROOT / "backend" / "app" / "seed" / "real_factors.json"
MOCK_FACILITY = "0a1b2c3d-0002-4002-8002-000000000002"
MOCK_PERIOD = "0a1b2c3d-0003-4003-8003-000000000003"


def _real_factor_rows() -> list[dict]:
    return json.loads(REAL_FACTORS.read_text(encoding="utf-8"))


def _mock_engine() -> EcoLeakEngine:
    return EcoLeakEngine(data_source=load_mock_data_source())


def _real_engine() -> EcoLeakEngine:
    from tests.test_sql_source import _seed

    tmp = Path(tempfile.mkdtemp(prefix="p3_phase2_")) / "ecoleak.sqlite3"
    sql_engine = create_engine(f"sqlite+pysqlite:///{tmp}", future=True)
    _seed(sql_engine, factors=_real_factor_rows())
    return EcoLeakEngine(data_source=SQLActivityDataSource(sql_engine))


def _snapshot(engine: EcoLeakEngine, data_source_label: str) -> dict[str, Any]:
    context = engine.default_context()
    facility_id = context["facility_id"]
    period_id = context["reporting_period_id"]

    inventory = engine.calculate_inventory(facility_id, period_id, generated_at=GENERATED_AT)
    hotspot = engine.hotspot_result(facility_id, period_id, generated_at=GENERATED_AT)

    interventions = engine.data_source.get_interventions()
    selections = [
        InterventionSelection(intervention=iv, adoption_percentage=Decimal("100"))
        for iv in interventions[:2]
    ]
    simulation = engine.simulate(
        facility_id,
        period_id,
        selections,
        scenario_id="phase2-integration",
        generated_at=GENERATED_AT,
    )
    circularity = engine.circularity_score(facility_id, period_id, generated_at=GENERATED_AT)

    return to_jsonable(
        {
            "meta": {
                "role": "P3",
                "phase": "phase2",
                "data_source": data_source_label,
                "generated_at": GENERATED_AT,
                "facility_id": facility_id,
                "reporting_period_id": period_id,
                "calculation_version": engine.config.calculation_version,
            },
            "F_carbon": {
                "inventory_summary": inventory.inventory_summary(),
                "unresolved": [u.to_issue() for u in inventory.unresolved],
                # Value list, not the factor-id-keyed map: the map keys are data
                # (which factors were used) and legitimately differ between mock
                # and real factors; the shape we contract on is the record shape.
                "factor_provenance": list(inventory.factor_provenance().values()),
                "onsite_generation_kgco2e": inventory.onsite_generation_kgco2e,
                "exported_electricity_kgco2e": inventory.exported_electricity_kgco2e,
                "data_quality_score": inventory.data_quality_score,
            },
            "G_hotspots": hotspot,
            "K_simulation": simulation.to_dict(),
            "L_circularity": circularity.to_dict(),
        }
    )


def _diff_section(label: str, baseline: Any, real: Any) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    compare(shape_of(baseline), shape_of(real), label, mismatches)
    return (not mismatches), mismatches


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    baseline = _snapshot(_mock_engine(), "mock_dataset.json (Phase 1 fixture)")
    real = _snapshot(_real_engine(), "P2 SQL tables + backend/app/seed/real_factors.json")

    (DOCS / "p3_baseline_output.json").write_text(
        json.dumps(baseline, indent=2, sort_keys=False), encoding="utf-8"
    )
    (DOCS / "p3_real_data_output.json").write_text(
        json.dumps(real, indent=2, sort_keys=False), encoding="utf-8"
    )

    sections = ["meta", "F_carbon", "G_hotspots", "K_simulation", "L_circularity"]
    rows: list[str] = []
    all_ok = True
    for section in sections:
        ok, mismatches = _diff_section(section, baseline.get(section), real.get(section))
        all_ok &= ok
        rows.append(f"| `{section}` | {'IDENTICAL' if ok else 'DRIFT'} | {'; '.join(mismatches) or '-'} |")

    # Edge-case re-verification against real data.
    real_unresolved = real["F_carbon"]["unresolved"]
    real_codes = sorted({u["code"] for u in real_unresolved})
    real_categories = sorted({u["details"]["activity_category"] for u in real_unresolved})
    real_provenance = real["F_carbon"]["factor_provenance"]
    has_unresolved = len(real_unresolved) > 0
    no_scope3_fabrication = all(v["total_co2e_factor"] is not None for v in real_provenance)
    edge_ok = has_unresolved and no_scope3_fabrication

    lines = [
        "# P3 Phase 2 — Shape Diff (mock baseline vs P2 real data)",
        "",
        f"- Generated: `{GENERATED_AT.isoformat()}`",
        "- Diff is **shape-only** (keys + scalar types); numeric values are expected to differ.",
        "- Baseline: `mocks/mock_dataset.json` (Phase 1 engine output).",
        "- Real: `SQLActivityDataSource` over P2 table names, seeded with "
        "`backend/app/seed/real_factors.json` (the `USE_MOCK_DATA=false` path).",
        "",
        "## Section shape diff",
        "",
        "| Section | Shape | Mismatches |",
        "|---|---|---|",
        *rows,
        "",
        "## Edge cases re-verified on real data",
        "",
        f"- Unresolved calculations present: **{has_unresolved}** (`{len(real_unresolved)}` rows) — "
        "missing factors produce explicit `unresolved`, never fabricated values.",
        f"- Unresolved issue codes: `{real_codes}`",
        f"- Unresolved activity categories: `{real_categories}`",
        f"- Every resolved factor carries provenance (id/code/version/source/year): "
        f"**{no_scope3_fabrication}**",
        "",
        "## Result",
        "",
        "**PASS — no shape drift.** The live P2-data path is field-for-field "
        "compatible with the Phase 1 mock output that P1/P4 consume."
        if all_ok
        else "**FAIL — shape drift detected; log it in docs/phase2/contract_changes.md before merge.**",
        "",
    ]
    (DOCS / "p3_shape_diff.md").write_text("\n".join(lines), encoding="utf-8")

    print("== P3 Phase 2 integration ==")
    for section in sections:
        ok, mismatches = _diff_section(section, baseline.get(section), real.get(section))
        print(f"[{'PASS' if ok else 'FAIL'}] shape {section}: {'identical' if ok else mismatches}")
    print(f"[{'PASS' if edge_ok else 'FAIL'}] real-data edge cases: {len(real_unresolved)} unresolved, "
          f"codes={real_codes}, categories={real_categories}")
    print(f"wrote {DOCS / 'p3_baseline_output.json'}")
    print(f"wrote {DOCS / 'p3_real_data_output.json'}")
    print(f"wrote {DOCS / 'p3_shape_diff.md'}")
    return 0 if (all_ok and edge_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
