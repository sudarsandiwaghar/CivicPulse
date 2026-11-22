"""
CivicPulse Complaint Model

Defines the complaints table representing civic issue reports submitted by
citizens, tracked through review, assignment, resolution, and verification.

Design decisions:
    - UUID primary key for secure global identification.
    - Human-readable unique complaint_number (e.g., CP-2026-10001).
    - Links to reporting Citizen (users), Category, and Location.
    - Tracks current status and priority using standardized system enums.
    - Explicit relationship orchestration with assignments, attachments,
      status transitions history, citizen feedback, and AI assessments.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ComplaintStatus, PriorityLevel
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai_assessment import AIAssessment
    from app.models.assignment import Assignment
    from app.models.attachment import Attachment
    from app.models.category import Category
    from app.models.complaint_follower import ComplaintFollower
    from app.models.complaint_sla_history import ComplaintSLAHistory
    from app.models.feedback import Feedback
    from app.models.location import Location
    from app.models.notification import Notification
    from app.models.sla_policy import SLAPolicy
    from app.models.status_history import ComplaintStatusHistory
    from app.models.user import User


class Complaint(Base, TimestampMixin):
    """
    Civic complaint filed by a citizen.

    Attributes:
        id: Primary UUID identifier for complaint.
        complaint_number: Human-readable unique complaint tracking code.
        citizen_id: Foreign key referencing reporting user account.
        category_id: Foreign key referencing issue category.
        location_id: Foreign key referencing physical incident location.
        title: Summary headline of the reported issue.
        description: Comprehensive problem description.
        status: Current lifecycle state (SUBMITTED, UNDER_REVIEW, ASSIGNED, etc.).
        priority: Assessed urgency priority level (LOW, MEDIUM, HIGH, CRITICAL).
        resolved_at: Timestamp when field worker submitted resolution.
        closed_at: Timestamp when citizen or admin approved closure.
    """

    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint("response_pause_duration_seconds >= 0", name="ck_complaints_response_pause_duration"),
        CheckConstraint("resolution_pause_duration_seconds >= 0", name="ck_complaints_resolution_pause_duration"),
        CheckConstraint("response_escalation_level BETWEEN 0 AND 2", name="ck_complaints_response_escalation_level"),
        CheckConstraint("resolution_escalation_level BETWEEN 0 AND 3", name="ck_complaints_resolution_escalation_level"),
        CheckConstraint("sla_cycle_number >= 1", name="ck_complaints_sla_cycle_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for complaint",
    )
    complaint_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Human-readable tracking code (e.g. CP-2026-10001)",
    )
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing citizen user account",
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing category of issue",
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key referencing location coordinates record",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Short summary headline of civic problem",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full detailed problem description provided by citizen",
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, native_enum=False, length=50),
        default=ComplaintStatus.SUBMITTED,
        server_default=ComplaintStatus.SUBMITTED.value,
        nullable=False,
        index=True,
        comment="Current lifecycle status of complaint",
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, native_enum=False, length=20),
        default=PriorityLevel.MEDIUM,
        server_default=PriorityLevel.MEDIUM.value,
        nullable=False,
        index=True,
        comment="Operational priority level",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when field resolution was submitted",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when complaint reached final CLOSED state",
    )

    # Phase 6.2: Public Moderation & Visibility Fields
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
        index=True,
        comment="Whether complaint is approved and published for public discovery",
    )
    public_title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Administrator-sanitized and approved title for public display",
    )
    public_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Administrator-sanitized and approved description for public display",
    )
    moderated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when administrator last published or moderated public content (UTC)",
    )
    moderated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key referencing administrator who last moderated public visibility",
    )
    unpublish_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when citizen requested unpublishing (UTC)",
    )
    unpublish_requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key referencing user who requested unpublishing",
    )
    unpublish_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Citizen explanation or notes for requesting unpublishing",
    )

    # Phase 6.3: Dual-Clock SLA Management Fields
    response_sla_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sla_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="SLA policy used for response clock target",
    )
    response_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Target UTC deadline for initial response",
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp when response clock completed (UTC)",
    )
    response_pause_duration_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="Total accumulated pause duration for response clock in seconds",
    )
    response_pause_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when current response pause started (UTC)",
    )
    response_escalation_level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        index=True,
        comment="Current response escalation level: 0=Normal, 1=Warning, 2=Breached",
    )

    resolution_sla_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sla_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="SLA policy used for resolution clock target",
    )
    resolution_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Target UTC deadline for complaint resolution",
    )
    resolution_pause_duration_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="Total accumulated pause duration for resolution clock in seconds",
    )
    resolution_pause_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when current resolution pause started (UTC)",
    )
    resolution_escalation_level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        index=True,
        comment="Current resolution escalation level: 0=Normal, 1=Warning, 2=Breached, 3=Severe",
    )

    sla_cycle_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
        nullable=False,
        comment="Current SLA resolution cycle number (>= 1, increments on reopen)",
    )
    last_sla_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last on-demand or transition SLA evaluation (UTC)",
    )

    # Relationships
    citizen: Mapped["User"] = relationship(
        back_populates="complaints",
        foreign_keys=[citizen_id],
    )
    moderated_by: Mapped["User | None"] = relationship(
        foreign_keys=[moderated_by_id],
    )
    unpublish_requested_by: Mapped["User | None"] = relationship(
        foreign_keys=[unpublish_requested_by_id],
    )
    followers: Mapped[list["ComplaintFollower"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintFollower.followed_at.desc()",
    )
    category: Mapped["Category"] = relationship(
        back_populates="complaints",
    )
    location: Mapped["Location | None"] = relationship(
        back_populates="complaints",
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="Assignment.created_at.desc()",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintStatusHistory.created_at.desc()",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="complaint",
        uselist=False,
        cascade="all, delete-orphan",
    )
    ai_assessments: Mapped[list["AIAssessment"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
    )
    response_sla_policy: Mapped["SLAPolicy | None"] = relationship(
        foreign_keys=[response_sla_policy_id],
    )
    resolution_sla_policy: Mapped["SLAPolicy | None"] = relationship(
        foreign_keys=[resolution_sla_policy_id],
    )
    sla_history: Mapped[list["ComplaintSLAHistory"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintSLAHistory.cycle_number.asc()",
    )

    def __repr__(self) -> str:
        return f"<Complaint id={self.id} number='{self.complaint_number}' status='{self.status}'>"
