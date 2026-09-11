"""Phase 1 gate: confirm the real P3 engine output matches the Phase 0 mock
shape field-for-field.

This does NOT compare numeric values (the live engine is expected to differ).
It compares the JSON *structure* - every key at every level - so P1's dashboard
and P4's recommendation engine can swap the mock file for the live endpoint
without any code change.

Run from the project root:

    python validate_against_mock.py

Exit code 0 = all shapes match; 1 = at least one structural mismatch.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from contracts.schemas import (  # noqa: E402
    HotspotDetectionResult,
    ImpactAssessment,
)
from engine.data_source import load_mock_data_source  # noqa: E402
from engine.serialization import to_jsonable  # noqa: E402
from engine.service import EcoLeakEngine  # noqa: E402
from engine.simulator import InterventionSelection  # noqa: E402

MOCKS = PROJECT_ROOT / "mocks"

# L1 response keys from contracts/api_contract.md (Module L) - the engine adds
# mandatory internal-metric labelling on top of these.
L1_CONTRACT_KEYS = {
    "recycled_input_score",
    "waste_recovery_score",
    "energy_recovery_score",
    "water_reuse_score",
    "reuse_score",
    "total_score",
    "methodology_version",
    "calculated_at",
}
L1_LABELLING_KEYS = {"is_internal_metric", "not_a_certified_standard", "disclaimer", "score_complete"}


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def shape_of(value: Any) -> Any:
    """Structural descriptor: dict -> {key: shape}, list -> [shape], scalar -> kind."""
    if isinstance(value, dict):
        return {k: shape_of(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape_of(value[0])] if value else []
    return _kind(value)


def compare(expected_shape: Any, actual_shape: Any, path: str, mismatches: list[str]) -> None:
    if isinstance(expected_shape, dict) and isinstance(actual_shape, dict):
        missing = sorted(set(expected_shape) - set(actual_shape))
        extra = sorted(set(actual_shape) - set(expected_shape))
        for key in missing:
            mismatches.append(f"{path}.{key}: missing in engine output")
        for key in extra:
            mismatches.append(f"{path}.{key}: unexpected extra field in engine output")
        for key in sorted(set(expected_shape) & set(actual_shape)):
            compare(expected_shape[key], actual_shape[key], f"{path}.{key}", mismatches)
    elif isinstance(expected_shape, list) and isinstance(actual_shape, list):
        if expected_shape and actual_shape:
            compare(expected_shape[0], actual_shape[0], f"{path}[0]", mismatches)
    else:
        # Leaf: container types must match. A null (Optional field with no value)
        # is compatible with any scalar, but two non-null scalars must share a type
        # (this is what catches Decimal-as-string regressions).
        if isinstance(expected_shape, (dict, list)) or isinstance(actual_shape, (dict, list)):
            mismatches.append(f"{path}: structure mismatch ({expected_shape!r} vs {actual_shape!r})")
            return
        if expected_shape == "null" or actual_shape == "null":
            return
        if expected_shape != actual_shape:
            mismatches.append(f"{path}: type mismatch ({expected_shape} vs {actual_shape})")


def check(label: str, expected: Any, actual: Any, check_exact_keys: bool = True) -> bool:
    mismatches: list[str] = []
    compare(shape_of(expected), shape_of(actual), "root", mismatches)
    if not check_exact_keys:
        mismatches = [m for m in mismatches if "unexpected extra field" not in m]
    if mismatches:
        print(f"[FAIL] {label}")
        for m in mismatches:
            print(f"       {m}")
        return False
    print(f"[PASS] {label}")
    return True


def build_engine() -> EcoLeakEngine:
    ds = load_mock_data_source(MOCKS / "mock_dataset.json")
    return EcoLeakEngine(data_source=ds)


def main() -> int:
    ok = True
    engine = build_engine()
    ctx = engine.default_context()
    facility_id, period_id = ctx["facility_id"], ctx["reporting_period_id"]

    # ------------------------------------------------------------------ G
    print("== Module G: hotspot output vs mock_hotspot_output.json ==")
    mock_hotspot = json.loads((MOCKS / "mock_hotspot_output.json").read_text(encoding="utf-8"))
    analysis = engine.detect_hotspots(facility_id, period_id)
    engine_hotspot = to_jsonable(analysis.result)

    # engine output must itself satisfy the frozen contract
    try:
        HotspotDetectionResult.model_validate(engine_hotspot)
        print("[PASS] engine hotspot output validates against HotspotDetectionResult")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] engine hotspot output failed contract validation: {exc}")
        ok = False

    ok &= check("hotspot shape (field-for-field)", mock_hotspot, engine_hotspot)

    # ------------------------------------------------------------------ F
    print("== Module F: baseline reproducibility ==")
    inventory = engine.calculate_inventory(facility_id, period_id)
    expected_scope1 = Decimal("224250")
    expected_scope2 = Decimal("340800")
    expected_operational = Decimal("565050")
    checks = [
        ("scope1_kgco2e", inventory.scope1_kgco2e, expected_scope1),
        ("scope2_kgco2e", inventory.scope2_kgco2e, expected_scope2),
        ("scope1+scope2", inventory.operational_kgco2e, expected_operational),
    ]
    for label, actual, expected in checks:
        if actual == expected:
            print(f"[PASS] {label} = {actual}")
        else:
            print(f"[FAIL] {label}: expected {expected}, got {actual}")
            ok = False

    # ------------------------------------------------------------------ K
    print("== Module K: ImpactAssessment shape ==")
    interventions = engine.data_source.get_interventions()
    selections = [
        InterventionSelection(intervention=interventions[0], adoption_percentage=Decimal("100")),
    ]
    sim = engine.simulate(facility_id, period_id, selections, scenario_id="validate-scenario")
    assessment = sim.assessment.model_dump(mode="json")
    try:
        ImpactAssessment.model_validate(assessment)
        print("[PASS] simulator output validates against ImpactAssessment")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] simulator output failed contract validation: {exc}")
        ok = False
    expected_assessment_keys = set(ImpactAssessment.model_fields.keys())
    actual_keys = set(assessment.keys())
    if expected_assessment_keys == actual_keys:
        print("[PASS] ImpactAssessment keys match contract")
    else:
        print(f"[FAIL] ImpactAssessment key mismatch: extra={actual_keys - expected_assessment_keys} "
              f"missing={expected_assessment_keys - actual_keys}")
        ok = False

    # ------------------------------------------------------------------ L
    print("== Module L: circularity response keys ==")
    circular = engine.circularity_score(facility_id, period_id).to_dict()
    required = L1_CONTRACT_KEYS | L1_LABELLING_KEYS
    missing = sorted(required - set(circular))
    if missing:
        print(f"[FAIL] circularity response missing keys: {missing}")
        ok = False
    else:
        print("[PASS] circularity response carries contract keys + internal-metric labelling")
    if circular.get("is_internal_metric") is not True or not circular.get("disclaimer"):
        print("[FAIL] circularity response is not labelled as an internal, non-certified metric")
        ok = False

    print("-" * 60)
    if ok:
        print("ALL SHAPE CHECKS PASSED - live engine is drop-in compatible with the Phase 0 mock")
        return 0
    print("SHAPE CHECKS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
