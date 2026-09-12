"""Deterministic larger/messier ingestion dataset for Phase 2 volume checks.

Produces a CSV whose severity mix is computable, so tests and the manual check
script can assert exact ERROR / WARNING / INFO / CONFIRMATION_REQUIRED outcomes:

per iteration (scale):
  1 valid FUEL diesel (L)                         -> accepted
  1 valid MATERIAL tonne -> kg                    -> accepted + INFO UNIT_CONVERTED
  1 valid ELECTRICITY MWh -> kWh                  -> accepted + INFO UNIT_CONVERTED
  1 negative value                                -> ERROR  NEGATIVE_VALUE
  1 missing unit                                  -> ERROR  MISSING_VALUE
  1 unknown unit (furlong)                        -> ERROR  INVALID_UNIT
  1 implausible magnitude                         -> WARNING IMPLAUSIBLE_MAGNITUDE (imported)
  1 in-file duplicate of row 1                    -> ERROR  DUPLICATE_IN_FILE
  1 reporting-period mismatch                     -> ERROR  PERIOD_MISMATCH

CONFIRMATION_REQUIRED is not reachable through a plain CSV (no target unit); it
is exercised by the D1 /units/normalize endpoint (see test_ingestion_volume.py).
"""
from __future__ import annotations

from uuid import uuid4

HEADER = (
    "process_code,activity_category,activity_subcategory,original_value,original_unit,"
    "source_name,data_source_type,measured_or_estimated,confidence_score,reporting_period_id\n"
)


def build_messy_csv(scale: int = 12, process_code: str = "PRC-X", wrong_period_id=None):
    wrong = str(wrong_period_id or uuid4())
    lines: list[str] = []
    for i in range(scale):
        lines.append(
            f"{process_code},FUEL,Messy diesel generator {i},{100 + i},L,Fuel register,CSV,MEASURED,90,\n"
        )
        lines.append(
            f"{process_code},MATERIAL,Cotton fabric batch {i},{1 + i},tonne,Purchase register,CSV,MEASURED,85,\n"
        )
        lines.append(
            f"{process_code},ELECTRICITY,Grid electricity block {i},{1 + i},MWh,Utility,CSV,MEASURED,88,\n"
        )
        lines.append(
            f"{process_code},ELECTRICITY,Negative meter {i},-5,kWh,Bad meter,CSV,MEASURED,80,\n"
        )
        lines.append(
            f"{process_code},WATER,Missing unit {i},{10 + i},,Meter,CSV,MEASURED,80,\n"
        )
        lines.append(
            f"{process_code},FUEL,Unknown unit {i},{10 + i},furlong,Odd,CSV,MEASURED,80,\n"
        )
        lines.append(
            f"{process_code},ELECTRICITY,Implausible load {i},90000000,kWh,Main meter,CSV,MEASURED,88,\n"
        )
        lines.append(
            f"{process_code},FUEL,Messy diesel generator {i},{100 + i},L,Fuel register,CSV,MEASURED,90,\n"
        )
        lines.append(
            f"{process_code},FUEL,Period mismatch {i},{50 + i},L,Reg,CSV,MEASURED,80,{wrong}\n"
        )
    expected = {
        "total": 9 * scale,
        "accepted": 4 * scale,
        "rejected": 5 * scale,
        "warning_rows": 1 * scale,
        "info_issues": 2 * scale,
        "error_issues": 3 * scale,  # negative, missing unit, unknown unit
        "duplicate_issues": 1 * scale,
        "period_mismatch_issues": 1 * scale,
    }
    return HEADER + "".join(lines), expected, wrong
