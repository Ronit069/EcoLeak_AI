"""Throwaway adversarial fixture: SQLite image of the P2 tables with ONLY
the 5 original mock interventions, reproducing the pre-fix K1 state where
13 of the 18 live J2 intervention_ids cannot resolve. NOT for production."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from tests.test_sql_source import _seed

FIVE = (
    "0a1b2c3d-0011-4011-8011-000000000011",
    "0a1b2c3d-0012-4012-8012-000000000012",
    "0a1b2c3d-0013-4013-8013-000000000013",
    "0a1b2c3d-0014-4014-8014-000000000014",
    "0a1b2c3d-0015-4015-8015-000000000015",
)

def main() -> None:
    out = Path("var/ecoleak_broken.sqlite3")
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        out.unlink()
    engine = create_engine(f"sqlite+pysqlite:///{out}", future=True)
    _seed(engine)
    import json, uuid as _uuid
    from engine.sql_source import circular_interventions as tbl
    data = json.loads((Path(__file__).resolve().parents[1] / "mocks" / "mock_dataset.json").read_text(encoding="utf-8"))
    with engine.begin() as conn:
        conn.execute(tbl.delete())
        for iv in data["circular_interventions"]:
            row = {k: (_uuid.UUID(v) if k == "id" else v) for k, v in iv.items()}
            conn.execute(tbl.insert(), [row])
        n = conn.execute(tbl.select()).scalars().all(); n = len(n)
        print("BROKEN seed interventions:", n)

if __name__ == "__main__":
    main()
