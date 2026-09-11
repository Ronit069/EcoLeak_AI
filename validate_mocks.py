"""
Phase 0 mock validator for EcoLeak AI.

Loads every file in /mocks through its corresponding Pydantic contract in
/contracts/schemas.py and prints PASS/FAIL per file (and per entity section).

Run from the project root:
    python validate_mocks.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "contracts"))

from schemas import (  # noqa: E402  (import after sys.path setup)
    ActivityData,
    CircularIntervention,
    EmissionFactor,
    Facility,
    HotspotDetectionResult,
    Organization,
    Process,
    RecommendationGenerationResult,
    ReportingPeriod,
)

DATASET_MAPPING: list[tuple[str, type[BaseModel]]] = [
    ("organization", Organization),
    ("facilities", Facility),
    ("reporting_periods", ReportingPeriod),
    ("processes", Process),
    ("activity_data", ActivityData),
    ("emission_factors", EmissionFactor),
    ("circular_interventions", CircularIntervention),
]

FILE_MAPPING: list[tuple[str, type[BaseModel]]] = [
    ("mock_hotspot_output.json", HotspotDetectionResult),
    ("mock_recommendation_output.json", RecommendationGenerationResult),
]


def check(label: str, model: type[BaseModel], payload: Any) -> bool:
    try:
        if isinstance(payload, list):
            for item in payload:
                model.model_validate(item)
            count = len(payload)
            plural = "s" if count != 1 else ""
            print(f"[PASS] {label} ({count} record{plural})")
        else:
            model.model_validate(payload)
            print(f"[PASS] {label} (1 record)")
        return True
    except ValidationError as exc:
        print(f"[FAIL] {label}")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "<root>"
            print(f"       {location}: {error['msg']} (type={error['type']})")
        return False
    except Exception as exc:  # noqa: BLE001 - report any loading problem as FAIL
        print(f"[FAIL] {label}: {exc}")
        return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    mocks_dir = PROJECT_ROOT / "mocks"
    checks_passed = 0
    checks_total = 0
    overall_ok = True

    dataset_path = mocks_dir / "mock_dataset.json"
    print(f"== {dataset_path.name} ==")
    dataset = load_json(dataset_path)
    for key, model in DATASET_MAPPING:
        checks_total += 1
        if key not in dataset:
            print(f"[FAIL] mock_dataset.json :: {key} (missing key)")
            overall_ok = False
            continue
        if check(f"mock_dataset.json :: {key}", model, dataset[key]):
            checks_passed += 1
        else:
            overall_ok = False

    for filename, model in FILE_MAPPING:
        path = mocks_dir / filename
        print(f"== {path.name} ==")
        checks_total += 1
        if check(filename, model, load_json(path)):
            checks_passed += 1
        else:
            overall_ok = False

    print("-" * 48)
    if overall_ok:
        print(f"ALL CHECKS PASSED ({checks_passed}/{checks_total})")
        return 0

    print(f"FAILED: {checks_total - checks_passed} of {checks_total} checks failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
