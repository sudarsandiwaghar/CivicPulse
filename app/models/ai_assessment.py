"""
CivicPulse AI Assessment Model

Defines the ai_assessments table storing automated AI/ML predictions,
classifications, duplicate detections, and severity recommendations.

Design decisions:
    - Multiple assessments per complaint are permitted (e.g., initial image classification,
      text triage, duplicate detection, and severity scoring).
    - Database check constraint enforces confidence score between 0.0 and 1.0.
    - AI provides advisory recommendations; decisions remain in administrative control.
    - Tracks model version and raw JSON inference payload for reproducibility and auditability.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PriorityLevel
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.complaint import Complaint


class AIAssessment(Base):
    """
    Automated machine learning inference result for a civic complaint.

    Attributes:
        id: Primary UUID identifier for AI assessment record.
        complaint_id: Foreign key referencing the evaluated complaint.
        assessment_type: Category of analysis (CATEGORY_PREDICTION, SEVERITY_PREDICTION, etc.).
        predicted_category_id: Optional foreign key to suggested category.
        predicted_priority: Optional recommended priority level (LOW, MEDIUM, HIGH, CRITICAL).
        confidence_score: Model confidence probability between 0.0 and 1.0.
        explanation: Human-readable rationale or feature attribution for the recommendation.
        model_version: Version identifier of the inference model pipeline.
        raw_response: Full JSON dictionary of raw model outputs and tokens.
        created_at: Timestamp when inference was generated (UTC).
    """

    __tablename__ = "ai_assessments"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="chk_ai_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for AI assessment entry",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing evaluated complaint",
    )
    assessment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of inference: CATEGORY_PREDICTION, SEVERITY_PREDICTION, DUPLICATE_DETECTION",
    )
    predicted_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        comment="Recommended category predicted by AI",
    )
    predicted_priority: Mapped[PriorityLevel | None] = mapped_column(
        Enum(PriorityLevel, native_enum=False, length=20),
        nullable=True,
        comment="Recommended priority level suggested by model",
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Inference confidence probability (0.0 to 1.0)",
    )
    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable explanation of why this prediction was made",
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Identifier/tag of AI model used for inference",
    )
    raw_response: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Full JSON payload of model inference metrics and features",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when assessment was performed (UTC)",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="ai_assessments",
    )
    predicted_category: Mapped["Category | None"] = relationship(
        back_populates="ai_predictions",
    )

    def __repr__(self) -> str:
        return f"<AIAssessment id={self.id} complaint_id={self.complaint_id} type='{self.assessment_type}' score={self.confidence_score}>"
