"""
CivicPulse Feedback Model

Defines the feedback table storing citizen reviews, ratings, and comments
upon resolution of their complaints.

Design decisions:
    - 1-to-1 relationship with complaint: unique constraint on complaint_id
      prevents duplicate or fraudulent multiple feedback submissions.
    - Database check constraint enforces rating boundaries (1 to 5 stars).
    - Preserves citizen association for analytics and accountability.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class Feedback(Base, TimestampMixin):
    """
    Citizen satisfaction feedback and rating for a resolved complaint.

    Attributes:
        id: Primary UUID identifier for feedback entry.
        complaint_id: Unique foreign key referencing the resolved complaint (1-to-1).
        citizen_id: Foreign key referencing the citizen author.
        rating: Integer satisfaction score between 1 and 5.
        comments: Citizen remarks, critique, or compliments regarding the resolution.
    """

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="chk_feedback_rating_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for feedback entry",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique foreign key linking feedback to resolved complaint (1-to-1)",
    )
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing citizen submitting feedback",
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Satisfaction rating score (1 to 5 stars)",
    )
    comments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Citizen feedback comments and review notes",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="feedback",
    )
    citizen: Mapped["User"] = relationship(
        back_populates="feedback_submissions",
        foreign_keys=[citizen_id],
    )

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} complaint_id={self.complaint_id} rating={self.rating}>"
