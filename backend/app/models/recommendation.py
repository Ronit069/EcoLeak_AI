"""Modules J/Q tables: recommendations, assessments, feedback (DB doc 12, 15)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class Recommendation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("idx_recommendation_facility", "facility_id", "reporting_period_id"),
    )

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facilities.id"), nullable=False
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reporting_periods.id"), nullable=False
    )
    hotspot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("emission_hotspots.id"), nullable=False
    )
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("circular_interventions.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    carbon_saving_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    financial_return_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    feasibility_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    circularity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    implementation_speed_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    final_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUGGESTED")
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class RecommendationAssessment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recommendation_assessments"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), nullable=False
    )
    estimated_capex: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    estimated_annual_opex_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    estimated_annual_saving: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    estimated_co2_saving_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    estimated_energy_saving: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    estimated_waste_reduction: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    payback_years: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    cost_per_tonne_co2_avoided: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    assumptions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))


class RecommendationFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recommendation_feedback"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), nullable=False
    )
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    actual_capex: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    actual_annual_saving: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    actual_co2_saving_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
