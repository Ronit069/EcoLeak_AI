"""Module P1-P3: compliance & sustainability report endpoints.

P1 generate (202), P2 fetch, P3 export (json/csv now, PDF -> 501 in Phase 1).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import api_rate_limit, require_roles
from app.errors import NotFoundError
from app.models.core import Organization
from app.routers.common import WRITE_ROLES, audit_ctx
from app.schemas.requests import ReportCreate
from app.security import Principal, get_current_principal
from app.services import access, reports as report_service

router = APIRouter(prefix="/api", tags=["Module P - Reports"])


@router.post(
    "/facilities/{facility_id}/reporting-periods/{period_id}/reports",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(api_rate_limit)],
)
def generate_report(
    facility_id: str,
    period_id: str,
    payload: ReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*WRITE_ROLES)),
) -> dict:
    facility = access.get_facility(db, UUID(facility_id), principal)
    period = access.get_period(db, UUID(period_id), principal, facility=facility)
    organization = db.get(Organization, facility.organization_id)
    report = report_service.generate_report(
        db,
        facility=facility,
        period=period,
        organization=organization,
        principal=principal,
        template_version=payload.template_version,
        include_scope3=payload.include_scope3,
        **audit_ctx(request),
    )
    return report_service.report_receipt(report)


@router.get("/reports/{report_id}")
def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    report = report_service.get_report(db, report_id, principal)
    return {
        "report_id": str(report.id),
        "status": report.status,
        "version": report.version,
        "report_hash": report.report_hash,
        "generated_at": report.generated_at,
        "payload": report.payload,
    }


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: UUID,
    format: str = "json",
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    report = report_service.get_report(db, report_id, principal)
    body, media_type, filename = report_service.export_report(report, format)
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports")
def list_reports(
    facility_id: UUID | None = None,
    reporting_period_id: UUID | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    from app.models.report import Report

    stmt = select(Report)
    if facility_id:
        access.get_facility(db, facility_id, principal)
        stmt = stmt.where(Report.facility_id == facility_id)
    elif principal.organization_id and not principal.is_global:
        stmt = stmt.where(Report.organization_id == principal.organization_id)
    elif not principal.is_global:
        raise NotFoundError("No reports found.")
    if reporting_period_id:
        stmt = stmt.where(Report.reporting_period_id == reporting_period_id)
    reports = db.scalars(stmt.order_by(Report.generated_at.desc()))
    return [report_service.report_receipt(r) for r in reports]
