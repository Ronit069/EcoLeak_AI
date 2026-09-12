"""Shared Phase-2 remediation seed helper (BLOCKER 1).

Maps P4's full 19-entry ``p4/interventions/intervention_library.json`` onto
frozen ``CircularIntervention`` contract rows so every `intervention_id` a
live J2 emits can resolve in the K1 simulator's data source (seed tables),
instead of 404ing on the 14 non-original ids.

Used by:
- ``tests/test_sql_source.py::_seed``  (SQLite test image of P2 tables)
- ``tools/seed_sql_lite.py``            (dev/E2E SQLite seed)
- ``backend/app/seed/run_seed.py``      (PG production seed, sidecar merge)

The 5 mock-dataset interventions are kept as-is (same ids, richer mock text);
the 14 library-only entries are added with their own ids. Total seed = 19,
matching the J2 emission set exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

from contracts.schemas import CircularIntervention

REPO_ROOT = Path(__file__).resolve().parent
LIBRARY = REPO_ROOT / "p4" / "interventions" / "intervention_library.json"


def load_library_contracts() -> list[CircularIntervention]:
    """All 19 library entries as frozen CircularIntervention rows."""
    raw = json.loads(LIBRARY.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw["interventions"]
    keys = set(CircularIntervention.model_fields.keys())
    out = []
    for item in items:
        d = {k: v for k, v in item.items() if k in keys}
        out.append(CircularIntervention.model_validate(d))
    return out


def seeded_intervention_ids(dataset: dict) -> set[str]:
    """The 5 original mock ids already present in mock_dataset.json."""
    return {i["id"] for i in dataset.get("circular_interventions", [])}


def full_intervention_rows(existing_rows: list[dict]) -> list[dict]:
    """existing mock rows + library-only rows (deduped by id)."""
    have = {r["id"] for r in existing_rows}
    extra = [i for i in load_library_contracts() if str(i.id) not in have]
    rows = list(existing_rows)
    for i in extra:
        rows.append({k: (str(v) if k == "id" else v) for k, v in i.model_dump(mode="json").items()})
    return rows