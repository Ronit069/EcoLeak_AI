"""Module Q - feedback capture tests."""

from decimal import Decimal
from uuid import UUID

import pytest

from p4.contracts import FeedbackType
from p4.feedback import FeedbackError, InMemoryFeedbackStore
from p4.models import RejectionReasonCode

REC_ID = UUID("0a1b2c3d-0d01-4d01-8d01-000000000d01")


def test_feedback_types_and_latest_and_history():
    store = InMemoryFeedbackStore()
    store.submit(REC_ID, FeedbackType.USEFUL)
    store.submit(REC_ID, FeedbackType.CONSIDER_LATER, reason="Budget cycle next year")

    latest = store.latest(REC_ID)
    history = store.history(REC_ID)
    assert latest is not None and latest.feedback_type == FeedbackType.CONSIDER_LATER
    assert len(history) == 2
    assert history[0].feedback_type == FeedbackType.USEFUL
    assert latest.previous_feedback_type == FeedbackType.USEFUL
    assert latest.sequence_no == 2


def test_rejected_requires_structured_reason_code():
    store = InMemoryFeedbackStore()
    with pytest.raises(FeedbackError):
        store.submit(REC_ID, FeedbackType.REJECTED, reason="no space")
    event = store.submit(
        REC_ID,
        FeedbackType.REJECTED,
        reason_code=RejectionReasonCode.SPACE_CONSTRAINTS,
        reason="No free roof area for this equipment",
    )
    assert event.reason_code == RejectionReasonCode.SPACE_CONSTRAINTS
    assert event.reason == "No free roof area for this equipment"


def test_repeated_changes_keep_full_history_without_overwrite():
    store = InMemoryFeedbackStore()
    store.submit(REC_ID, FeedbackType.USEFUL)
    store.submit(
        REC_ID,
        FeedbackType.NOT_APPLICABLE,
        reason_code=RejectionReasonCode.PROCESS_INCOMPATIBLE,
    )
    store.submit(REC_ID, FeedbackType.IMPLEMENTED)

    history = store.history(REC_ID)
    assert [event.sequence_no for event in history] == [1, 2, 3]
    assert [event.feedback_type for event in history][-1] == FeedbackType.IMPLEMENTED
    assert history[-1].previous_feedback_type == history[-2].feedback_type
    assert store.latest(REC_ID).feedback_type == FeedbackType.IMPLEMENTED


def test_implemented_without_evidence_is_flagged_self_reported():
    store = InMemoryFeedbackStore()
    event = store.submit(REC_ID, FeedbackType.IMPLEMENTED)
    assert event.is_self_reported_outcome is True
    assert any("evidence" in note for note in event.validation_notes)

    measured = store.submit(
        REC_ID,
        FeedbackType.IMPLEMENTED,
        actual_capex=Decimal("1600000"),
        actual_annual_saving=Decimal("790000"),
        actual_co2_saving_kg=Decimal("31000"),
    )
    assert measured.is_self_reported_outcome is False


def test_negative_actual_saving_is_a_valid_confirmed_outcome():
    store = InMemoryFeedbackStore()
    event = store.submit(
        REC_ID,
        FeedbackType.IMPLEMENTED,
        actual_annual_saving=Decimal("-25000"),
        actual_co2_saving_kg=Decimal("12000"),
    )
    assert event.actual_annual_saving == Decimal("-25000")
    assert any("negative actual saving" in note for note in event.validation_notes)


def test_history_is_isolated_per_recommendation():
    store = InMemoryFeedbackStore()
    store.submit(REC_ID, FeedbackType.NOT_APPLICABLE, reason_code=RejectionReasonCode.PROCESS_INCOMPATIBLE)
    other_id = UUID("0a1b2c3d-0d02-4d02-8d02-000000000d02")
    assert store.history(other_id) == []
    assert store.latest(other_id) is None
    assert store.known_recommendations() == [REC_ID]
