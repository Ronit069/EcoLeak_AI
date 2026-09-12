"""Manual Phase 2 volume check (evidence for the integration log).

Runs the messy dataset through the real ingestion service against the test DB and
prints the severity breakdown. Usage (from backend/):

    python -m tools.messy_ingestion_check
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _use_test_db() -> str:
    env = BACKEND / ".env"
    url = None
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url or "postgresql+psycopg://postgres:postgres@localhost:5432/ecoleak_test"
    os.environ["DATABASE_URL"] = url
    return url


def main() -> int:
    url = _use_test_db()
    from app.db import Base, SessionLocal, engine, utcnow
    import app.models as m
    from app.security import Principal
    from app.seed.messy_dataset import build_messy_csv
    from app.services import ingestion

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    org = m.Organization(
        name="Volume Check Org", industry_sector="Textile", country="India",
        currency_code="INR", organization_size="MEDIUM", created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(org)
    db.flush()
    facility = m.Facility(
        organization_id=org.id, name="Volume Facility", country="India",
        annual_production=1000, production_unit="tonne", created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(facility)
    db.flush()
    period = m.ReportingPeriod(
        facility_id=facility.id, period_type="ANNUAL",
        start_date=date(2025, 4, 1), end_date=date(2026, 3, 31), status="DRAFT", created_at=utcnow(),
    )
    db.add(period)
    db.flush()
    db.add(m.Process(facility_id=facility.id, name="Boiler", process_code="PRC-X", sequence_no=1, created_at=utcnow()))
    db.commit()

    body, expected, _ = build_messy_csv(scale=12)
    principal = Principal(actor_id=None, organization_id=org.id, role="SYSTEM_ADMIN")
    batch = ingestion.import_activity(
        db, facility=facility, period=period, content=body.encode("utf-8"),
        filename="messy.csv", sheet_name=None, principal=principal, dry_run=False,
    )
    job = ingestion.batch_to_job(batch, db)

    from collections import Counter

    severities = Counter(i["severity"] for i in job["row_issues"])
    codes = Counter(i["code"] for i in job["row_issues"])
    print(f"DB: {url}")
    print(f"status={batch.status} total={batch.total_rows} accepted={batch.accepted_rows} "
          f"rejected={batch.rejected_rows} warnings={batch.warning_rows}")
    print("severities:", dict(severities))
    print("issue codes:", dict(codes))

    import app.models as models
    stored = db.query(models.ActivityData).count()
    audit_rows = db.query(models.AuditLog).filter_by(event_type="ACTIVITY_IMPORTED").count()
    print(f"stored_activity_rows={stored} imported_audit_rows={audit_rows}")

    ok = (
        batch.accepted_rows == expected["accepted"]
        and batch.rejected_rows == expected["rejected"]
        and severities.get("ERROR", 0) == expected["rejected"]
        and severities.get("WARNING", 0) == expected["warning_rows"]
        and severities.get("INFO", 0) == expected["info_issues"]
        and stored == expected["accepted"]
        and audit_rows == expected["accepted"]
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    db.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
