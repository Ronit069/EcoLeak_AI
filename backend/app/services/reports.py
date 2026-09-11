"""Module P - Compliance & Sustainability Report generator (Phase 1 stub).

Phase 1 builds the real report envelope from live profile/factor/quality data but
substitutes Module F/G/J outputs with `mocks/mock_hotspot_output.json` and
`mocks/mock_recommendation_output.json` until P3/P4 engines land. The payload
shape is frozen so swapping the source requires no API change.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.errors import NotFoundError, PlatformError
from app.models.activity import ActivityData
from app.models.core import Facility, Organization, ReportingPeriod
from app.models.report import Report
from app.security import Principal
from app.services import audit, quality
from app.schemas.serialize import facility_to_dict, organization_to_dict

REPO_ROOT = Path(__file__).resolve().parents[3]
MOCK_HOTSPOTS = REPO_ROOT / "mocks" / "mock_hotspot_output.json"
MOCK_RECOMMENDATIONS = REPO_ROOT / "mocks" / "mock_recommendation_output.json"


class PdfNotAvailableError(PlatformError):
    status_code = 501
    error_code = "PDF_EXPORT_NOT_IMPLEMENTED"
    severity = "INFO"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _factor_provenance(db: Session, facility: Facility, period: ReportingPeriod) -> list[dict[str, Any]]:
    activities = list(
        db.scalars(
            select(ActivityData).where(
                ActivityData.facility_id == facility.id,
                ActivityData.reporting_period_id == period.id,
                ActivityData.deleted_at.is_(None),
            )
        )
    )
    seen: dict[str, dict[str, Any]] = {}
    for activity in activities:
        factor = quality.match_factor(db, activity)
        if factor is None:
            seen.setdefault(
                "UNRESOLVED",
                {
                    "status": "UNRESOLVED",
                    "activity_category": activity.activity_category,
                    "normalized_unit": activity.normalized_unit,
                    "message": "No compatible factor; not calculated (no default fabricated).",
                },
            )
            continue
        seen.setdefault(
            factor.factor_code,
            {
                "factor_code": factor.factor_code,
                "item_name": factor.item_name,
                "source_name": factor.source_name,
                "source_year": factor.source_year,
                "version": factor.version,
                "scope": factor.scope,
                "confidence_level": factor.confidence_level,
            },
        )
    return list(seen.values())


def build_payload(
    db: Session,
    *,
    facility: Facility,
    period: ReportingPeriod,
    organization: Organization,
    template_version: str,
    include_scope3: bool,
) -> dict[str, Any]:
    hotspots_mock = _load_json(MOCK_HOTSPOTS)
    recommendations_mock = _load_json(MOCK_RECOMMENDATIONS)
    assessment = quality.assess_period(db, facility, period, persist=False)

    boundary = ["SCOPE_1", "SCOPE_2"]
    if include_scope3:
        boundary.append("SCOPE_3")

    total = hotspots_mock.get("total_emissions_kgco2e")
    recommendations = recommendations_mock.get("recommendations", [])
    total_capex = sum(
        float((r.get("impact") or {}).get("estimated_capex") or 0) for r in recommendations
    )
    total_annual_saving = sum(
        float((r.get("impact") or {}).get("estimated_annual_saving") or 0) for r in recommendations
    )
    total_co2_saving = sum(
        float((r.get("impact") or {}).get("estimated_co2_saving_kg") or 0) for r in recommendations
    )

    return {
        "report_meta": {
            "template_version": template_version,
            "include_scope3": include_scope3,
            "generated_at": utcnow().isoformat(),
            "data_is_stub": True,
            "stub_sources": [
                "mocks/mock_hotspot_output.json (Module G pending P3)",
                "mocks/mock_recommendation_output.json (Module J pending P4)",
            ],
        },
        "profile": {
            "organization": organization_to_dict(organization),
            "facility": facility_to_dict(facility),
            "reporting_period": {
                "id": str(period.id),
                "period_type": period.period_type,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "status": period.status,
            },
        },
        "boundary": {"scopes": boundary},
        "factor_provenance": _factor_provenance(db, facility, period),
        "scope_summary": {
            "scope1_kgco2e": None,
            "scope2_kgco2e": None,
            "scope3_kgco2e": None,
            "total_kgco2e": total,
            "note": "Scope 1/2/3 split is produced by Module F (P3); total is the stub fixture.",
        },
        "data_quality_score": {
            "total_score": assessment.total_score,
            "components": {
                "completeness": assessment.completeness_score,
                "source": assessment.source_quality_score,
                "factor": assessment.factor_quality_score,
                "temporal": assessment.temporal_quality_score,
                "unit": assessment.unit_quality_score,
            },
            "issues": assessment.issues or [],
        },
        "hotspot_analysis": {
            "status": "STUB",
            "total_emissions_kgco2e": total,
            "hotspots": hotspots_mock.get("hotspots", []),
        },
        "circularity_assessment": {
            "status": "UNAVAILABLE",
            "note": "Module L output not yet available (P3/P4).",
        },
        "recommendations": {
            "status": "STUB",
            "budget_limit": recommendations_mock.get("budget_limit"),
            "items": recommendations,
        },
        "financial_assessment": {
            "total_capex": total_capex or None,
            "total_annual_saving": total_annual_saving or None,
            "total_co2_saving_kg": total_co2_saving or None,
        },
        "roadmap": [
            {
                "rank": r.get("rank"),
                "intervention_code": r.get("intervention_code"),
                "intervention_title": r.get("intervention_title"),
                "payback_years": (r.get("impact") or {}).get("payback_years"),
            }
            for r in recommendations
        ],
        "assumptions": [
            "Hotspot and recommendation sections are Phase 1 stubs from frozen mocks.",
            "Scope summary uses the stub fixture total until Module F is live.",
            "Report labelled DRAFT/INCOMPLETE where factors are UNRESOLVED.",
        ],
        "disclaimer": (
            "This report contains estimated and stub data. It does not assert regulatory "
            "compliance and must be reviewed before any external use."
        ),
    }


def generate_report(
    db: Session,
    *,
    facility: Facility,
    period: ReportingPeriod,
    organization: Organization,
    principal: Principal,
    template_version: str,
    include_scope3: bool,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Report:
    payload = build_payload(
        db,
        facility=facility,
        period=period,
        organization=organization,
        template_version=template_version,
        include_scope3=include_scope3,
    )
    # JSONB requires JSON-native types (UUID/Decimal/date -> str).
    payload = json.loads(json.dumps(payload, default=str))
    canonical = json.dumps(payload, sort_keys=True, default=str)
    report_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    current_version = db.scalar(
        select(Report.version)
        .where(
            Report.facility_id == facility.id,
            Report.reporting_period_id == period.id,
        )
        .order_by(Report.version.desc())
        .limit(1)
    )
    status = "DRAFT" if any(
        p.get("status") == "UNRESOLVED" for p in payload["factor_provenance"]
    ) else "COMPLETE"

    report = Report(
        facility_id=facility.id,
        reporting_period_id=period.id,
        organization_id=facility.organization_id,
        template_version=template_version,
        include_scope3=include_scope3,
        status=status,
        version=(current_version or 0) + 1,
        report_hash=report_hash,
        payload=payload,
        generated_at=utcnow(),
        generated_by=principal.actor_id,
    )
    db.add(report)
    db.flush()
    audit.record(
        db, principal=principal, organization_id=facility.organization_id,
        event_type="REPORT_GENERATED", entity_type="report", entity_id=report.id,
        new_value={"version": report.version, "status": report.status, "template_version": template_version},
        ip=ip, user_agent=user_agent,
    )
    db.commit()
    return report


def get_report(db: Session, report_id: UUID, principal: Principal) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found.")
    if not principal.is_global and principal.organization_id != report.organization_id:
        raise NotFoundError("Report not found.")
    return report


def report_receipt(report: Report) -> dict[str, Any]:
    return {
        "report_id": report.id,
        "status": report.status,
        "version": report.version,
        "generated_at": report.generated_at,
        "report_hash": report.report_hash,
    }


def export_report(report: Report, fmt: str) -> tuple[bytes, str, str]:
    fmt = (fmt or "").lower()
    if fmt == "pdf":
        raise PdfNotAvailableError("PDF export is planned for Phase 2.")
    if fmt in {"json", ""}:
        body = json.dumps(report.payload or {}, indent=2, default=str).encode("utf-8")
        return body, "application/json", f"report-{report.id}.json"
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["section", "key", "value"])
        writer.writerow(["meta", "template_version", report.template_version])
        writer.writerow(["meta", "status", report.status])
        writer.writerow(["meta", "version", report.version])
        payload = report.payload or {}
        writer.writerow(["scope_summary", "total_kgco2e", (payload.get("scope_summary") or {}).get("total_kgco2e")])
        for hotspot in (payload.get("hotspot_analysis") or {}).get("hotspots", []):
            writer.writerow(["hotspot", hotspot.get("rank"), hotspot.get("process_name")])
        for rec in (payload.get("recommendations") or {}).get("items", []):
            writer.writerow(["recommendation", rec.get("rank"), rec.get("intervention_code")])
        return buffer.getvalue().encode("utf-8"), "text/csv", f"report-{report.id}.csv"
    raise PlatformError("Unsupported export format.", details={"format": fmt})
