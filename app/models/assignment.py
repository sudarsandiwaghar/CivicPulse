"""
CivicPulse Assignment Model

Defines the assignments table tracking complaint allocations to field workers.

Design decisions:
    - Maintains a complete audit trail of assignments rather than overwriting
      records upon reassignment.
    - Captures the assigning administrator, assigned field worker, operational
      status (ASSIGNED, IN_PROGRESS, COMPLETED, REASSIGNED), and timestamps.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AssignmentStatus
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.assignment_progress import AssignmentProgress
    from app.models.complaint import Complaint
    from app.models.user import User
    from app.models.worker import Worker


class Assignment(Base, TimestampMixin):
    """
    Task allocation linking a complaint to a designated field worker.

    Attributes:
        id: Primary UUID identifier for assignment.
        complaint_id: Foreign key referencing the complaint.
        worker_id: Foreign key referencing designated worker profile.
        assigned_by_id: Foreign key referencing the administrator who made the assignment.
        status: Assignment progress state (ASSIGNED, IN_PROGRESS, COMPLETED, REASSIGNED).
        assigned_at: Timestamp when assignment was initiated.
        completed_at: Timestamp when field work was marked completed.
        notes: Administrative instructions or field dispatch remarks.
    """

    __tablename__ = "assignments"

    __table_args__ = (
        Index(
            "uq_active_assignment_per_complaint",
            "complaint_id",
            unique=True,
            postgresql_where=text("status IN ('ASSIGNED', 'IN_PROGRESS')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for assignment record",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing assigned complaint",
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing assigned field worker",
    )
    assigned_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing administrator who assigned worker",
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, native_enum=False, length=30),
        default=AssignmentStatus.ASSIGNED,
        server_default=AssignmentStatus.ASSIGNED.value,
        nullable=False,
        index=True,
        comment="Current status of this specific assignment",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when assignment was made (UTC)",
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when worker accepted the assignment (UTC)",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when worker initiated work (UTC)",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when worker completed assigned work (UTC)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Administrator notes, instructions, or resolution remarks",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="assignments",
    )
    worker: Mapped["Worker"] = relationship(
        back_populates="assignments",
    )
    assigned_by: Mapped["User"] = relationship(
        back_populates="assigned_complaints",
        foreign_keys=[assigned_by_id],
    )
    progress_updates: Mapped[list["AssignmentProgress"]] = relationship(
        "AssignmentProgress",
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="AssignmentProgress.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Assignment id={self.id} complaint_id={self.complaint_id} worker_id={self.worker_id} status='{self.status}'>"
