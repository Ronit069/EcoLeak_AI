"""Module I tables: circular_interventions, intervention_applicability (DB doc 11)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
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


class CircularIntervention(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "circular_interventions"
    __table_args__ = (
        CheckConstraint(
            "complexity IS NULL OR complexity IN ('LOW', 'MEDIUM', 'HIGH')",
            name="complexity_valid",
        ),
        CheckConstraint(
            "risk_level IS NULL OR risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="risk_level_valid",
        ),
        CheckConstraint(
            "expected_co2_reduction_min_pct IS NULL OR expected_co2_reduction_max_pct IS NULL "
            "OR expected_co2_reduction_max_pct >= expected_co2_reduction_min_pct",
            name="co2_reduction_range",
        ),
        CheckConstraint(
            "min_capex IS NULL OR max_capex IS NULL OR max_capex >= min_capex",
            name="capex_range",
        ),
    )

    intervention_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    industry_sector: Mapped[Optional[str]] = mapped_column(String(100))
    process_category: Mapped[Optional[str]] = mapped_column(String(100))
    current_practice: Mapped[Optional[str]] = mapped_column(Text)
    alternative_practice: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    min_capex: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    max_capex: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    expected_co2_reduction_min_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    expected_co2_reduction_max_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    energy_reduction_min_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    energy_reduction_max_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    waste_reduction_min_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    waste_reduction_max_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    implementation_months_min: Mapped[Optional[int]] = mapped_column(Integer)
    implementation_months_max: Mapped[Optional[int]] = mapped_column(Integer)
    complexity: Mapped[Optional[str]] = mapped_column(String(20))
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    evidence_source: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class InterventionApplicability(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "intervention_applicability"

    intervention_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("circular_interventions.id"), nullable=False
    )
    applicability_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    condition_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
