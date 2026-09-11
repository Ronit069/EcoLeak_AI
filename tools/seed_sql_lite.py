"""Seed a portable SQLite image of the P2 tables from mocks/mock_dataset.json.

Used by the end-to-end smoke test and dev runs of the merged API with
ECOLEAK_SQL_DSN pointing at the produced file:

    python -m tools.seed_sql_lite var/ecoleak.sqlite3
    ECOLEAK_SQL_DSN=sqlite+pysqlite:///var/ecoleak.sqlite3 uvicorn app.main:app --app-dir backend

Reuses the seeding routine from tests/test_sql_source.py (single source).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from tests.test_sql_source import _seed  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "var/ecoleak.sqlite3")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # idempotent: fresh image each run
    engine = create_engine(f"sqlite+pysqlite:///{out}", future=True)
    _seed(engine)
    print(f"seeded {len(engine.dialect.name)} tables -> {out}")


if __name__ == "__main__":
    main()