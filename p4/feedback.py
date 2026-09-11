"""Module Q - feedback capture with latest state + full history.

Rules implemented (security doc section 21, Module Q):
- Useful / Not Applicable / Consider Later / Implemented / Rejected states
- structured rejection reason (`reason_code`) required for REJECTED
- repeated feedback changes keep the full history (append-only)
- IMPLEMENTED with no actual outcome values is flagged as self-reported
- negative actual saving is a valid confirmed outcome
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from p4.contracts import FeedbackType, RecommendationFeedback
from p4.models import RejectionReasonCode


class FeedbackEvent(RecommendationFeedback):
    """P4-local extension of the frozen feedback row (extra fields additive)."""

    reason_code: Optional[RejectionReasonCode] = None
    sequence_no: int
    previous_feedback_type: Optional[FeedbackType] = None
    is_self_reported_outcome: bool = False
    validation_notes: list[str] = []


class FeedbackError(ValueError):
    pass


class InMemoryFeedbackStore:
    """Append-only feedback store. Swap for SQLAlchemy in P2's layer."""

    def __init__(self) -> None:
        self._history: dict[UUID, list[FeedbackEvent]] = {}

    def submit(
        self,
        recommendation_id: UUID,
        feedback_type: FeedbackType,
        *,
        reason: Optional[str] = None,
        reason_code: Optional[RejectionReasonCode] = None,
        actual_capex: Optional[Decimal] = None,
        actual_annual_saving: Optional[Decimal] = None,
        actual_co2_saving_kg: Optional[Decimal] = None,
        submitted_at: Optional[datetime] = None,
    ) -> FeedbackEvent:
        if feedback_type == FeedbackType.REJECTED and reason_code is None:
            raise FeedbackError(
                "a structured reason_code is required when feedback_type is REJECTED"
            )

        events = self._history.setdefault(recommendation_id, [])
        previous = events[-1].feedback_type if events else None

        validation_notes: list[str] = []
        is_self_reported = (
            feedback_type == FeedbackType.IMPLEMENTED
            and actual_capex is None
            and actual_annual_saving is None
            and actual_co2_saving_kg is None
        )
        if is_self_reported:
            validation_notes.append("implementation reported without measured outcome evidence")
        if actual_co2_saving_kg is not None and actual_co2_saving_kg < Decimal("0"):
            validation_notes.append("negative actual saving stored as a confirmed outcome")
        elif actual_annual_saving is not None and actual_annual_saving < Decimal("0"):
            validation_notes.append("negative actual saving stored as a confirmed outcome")
        if reason_code is not None and reason is None:
            reason = reason_code.value.replace("_", " ").title()

        event = FeedbackEvent(
            id=uuid5(
                NAMESPACE_URL,
                f"ecoleak/feedback/{recommendation_id}/{len(events) + 1}",
            ),
            recommendation_id=recommendation_id,
            feedback_type=feedback_type,
            reason=reason,
            actual_capex=actual_capex,
            actual_annual_saving=actual_annual_saving,
            actual_co2_saving_kg=actual_co2_saving_kg,
            submitted_at=submitted_at or datetime.now(timezone.utc),
            reason_code=reason_code,
            sequence_no=len(events) + 1,
            previous_feedback_type=previous,
            is_self_reported_outcome=is_self_reported,
            validation_notes=validation_notes,
        )
        events.append(event)
        return event

    def latest(self, recommendation_id: UUID) -> Optional[FeedbackEvent]:
        events = self._history.get(recommendation_id, [])
        return events[-1] if events else None

    def history(self, recommendation_id: UUID) -> list[FeedbackEvent]:
        return list(self._history.get(recommendation_id, []))

    def known_recommendations(self) -> list[UUID]:
        return list(self._history)
