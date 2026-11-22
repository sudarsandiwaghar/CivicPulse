"""
CivicPulse Complaint SLA History Model

Defines the complaint_sla_history table representing immutable append-only snapshots
of completed SLA cycles for complaints.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.sla_policy import SLAPolicy


class ComplaintSLAHistory(Base):
    """
    Immutable audit history record capturing the performance of a completed SLA cycle.

    Enforced immutable at the PostgreSQL level via trigger `trg_prevent_sla_history_mutation`.
    """

    __tablename__ = "complaint_sla_history"
    __table_args__ = (
        UniqueConstraint("complaint_id", "cycle_number", name="uq_complaint_sla_history_cycle"),
        CheckConstraint("cycle_number >= 1", name="ck_complaint_sla_history_cycle_number"),
        CheckConstraint("actual_response_seconds IS NULL OR actual_response_seconds >= 0", name="ck_complaint_sla_history_response_seconds"),
        CheckConstraint("actual_resolution_seconds IS NULL OR actual_resolution_seconds >= 0", name="ck_complaint_sla_history_resolution_seconds"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for SLA history entry",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cycle_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="SLA cycle sequence number (>= 1)",
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sla_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    policy_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    policy_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Snapshot of policy parameters at cycle completion",
    )
    response_target_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Target response duration in seconds",
    )
    resolution_target_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Target resolution duration in seconds",
    )
    actual_response_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Actual elapsed response seconds (null if unobserved)",
    )
    actual_resolution_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Actual elapsed resolution seconds (null if unobserved)",
    )
    response_breached: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether response SLA breached (null if unknown)",
    )
    resolution_breached: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether resolution SLA breached (null if unknown)",
    )
    response_escalation_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    resolution_escalation_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    cycle_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Cycle start timestamp (UTC)",
    )
    cycle_ended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Cycle completion/end timestamp (UTC)",
    )
    end_reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Lifecycle event ending the cycle (REOPENED, RESOLVED, REJECTED, DUPLICATE)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="sla_history",
    )
    policy: Mapped["SLAPolicy | None"] = relationship(
        foreign_keys=[policy_id],
    )

    def __repr__(self) -> str:
        return (
            f"<ComplaintSLAHistory id={self.id} complaint_id={self.complaint_id} "
            f"cycle={self.cycle_number} reason='{self.end_reason}'>"
        )
