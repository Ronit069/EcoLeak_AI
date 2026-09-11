"""Tenant-ownership resolvers (checklist item 3).

Every path parameter that reaches an organization-owned row is resolved here
before any mutation, so an org A caller can never touch org B's data.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ForbiddenError, NotFoundError
from app.models.activity import ActivityData
from app.models.core import Facility, Organization, ReportingPeriod
from app.models.process import Process
from app.security import Principal


def require_org_access(principal: Principal, organization_id: UUID) -> None:
    if not principal.is_global and principal.organization_id != organization_id:
        raise ForbiddenError("Caller does not own this organization's data.")


def get_organization(db: Session, organization_id: UUID, principal: Principal) -> Organization:
    org = db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Organization not found.")
    require_org_access(principal, org.id)
    return org


def get_facility(db: Session, facility_id: UUID, principal: Principal) -> Facility:
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise NotFoundError("Facility not found.")
    require_org_access(principal, facility.organization_id)
    return facility


def get_period(
    db: Session, period_id: UUID, principal: Principal, *, facility: Facility | None = None
) -> ReportingPeriod:
    period = db.get(ReportingPeriod, period_id)
    if period is None:
        raise NotFoundError("Reporting period not found.")
    if facility is not None and period.facility_id != facility.id:
        raise NotFoundError("Reporting period does not belong to this facility.")
    if facility is None:
        facility = get_facility(db, period.facility_id, principal)
    return period


def get_process(db: Session, process_id: UUID, principal: Principal) -> Process:
    process = db.get(Process, process_id)
    if process is None:
        raise NotFoundError("Process not found.")
    get_facility(db, process.facility_id, principal)
    return process


def get_activity(db: Session, activity_id: UUID, principal: Principal) -> ActivityData:
    activity = db.get(ActivityData, activity_id)
    if activity is None:
        raise NotFoundError("Activity record not found.")
    get_facility(db, activity.facility_id, principal)
    return activity


def find_facility_by_code(
    db: Session, organization_id: UUID, facility_code: str
) -> Facility | None:
    return db.scalar(
        select(Facility).where(
            Facility.organization_id == organization_id,
            Facility.facility_code == facility_code,
        )
    )
