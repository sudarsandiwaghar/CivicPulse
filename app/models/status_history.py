"""
CivicPulse Complaint Status History Model

Defines the complaint_status_history table maintaining an immutable audit log
of every status transition throughout the complaint lifecycle.

Design decisions:
    - Immutable event log: records previous status, new status, timestamp,
      responsible user, and optional transition notes/remarks.
    - Preserves historical records even if a user is deactivated.
    - Foreign key cascade on complaint deletion removes audit history for that complaint.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ComplaintStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class ComplaintStatusHistory(Base):
    """
    Immutable historical audit log of complaint status transitions.

    Attributes:
        id: Primary UUID identifier for status transition record.
        complaint_id: Foreign key referencing the complaint.
        changed_by_id: Foreign key referencing the user who triggered the transition.
        previous_status: Lifecycle status before the transition occurred (null on creation).
        new_status: New lifecycle status established by the transition.
        remarks: Optional explanation, rationale, or administrative notes for the transition.
        created_at: Exact timestamp when transition was recorded (UTC).
    """

    __tablename__ = "complaint_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for status history event",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing associated complaint",
    )
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing user who authorized/executed status transition",
    )
    previous_status: Mapped[ComplaintStatus | None] = mapped_column(
        Enum(ComplaintStatus, native_enum=False, length=50),
        nullable=True,
        comment="Previous status before transition (null for initial submission)",
    )
    new_status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, native_enum=False, length=50),
        nullable=False,
        comment="New status after transition",
    )
    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional administrative justification or citizen note for transition",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when status transition occurred (UTC)",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="status_history",
    )
    changed_by: Mapped["User"] = relationship(
        back_populates="status_changes",
        foreign_keys=[changed_by_id],
    )

    def __repr__(self) -> str:
        return f"<ComplaintStatusHistory id={self.id} complaint_id={self.complaint_id} {self.previous_status}->{self.new_status}>"
