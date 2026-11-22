"""
CivicPulse Assignment Progress Model

Defines the assignment_progress table maintaining an immutable audit log
of work updates, milestones, and field notes submitted by assigned field workers.

Design decisions:
    - Immutable event log: each entry captures worker observations, notes,
      and timestamp without allowing editing or deletion through standard APIs.
    - Foreign key cascade on assignment deletion removes progress history.
    - Preserves worker accountability throughout investigation and resolution.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.worker import Worker


class AssignmentProgress(Base):
    """
    Immutable progress log entry for an active field assignment.

    Attributes:
        id: Primary UUID identifier for progress record.
        assignment_id: Foreign key referencing the assignment.
        worker_id: Foreign key referencing worker who recorded the progress update.
        description: Comprehensive notes, milestone details, or field observations.
        created_at: Exact timestamp when progress was recorded (UTC).
    """

    __tablename__ = "assignment_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for progress record",
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing associated assignment",
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing worker submitting progress update",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Work progress notes, milestone details, or field observations",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when progress update was recorded (UTC)",
    )

    # Relationships
    assignment: Mapped["Assignment"] = relationship(
        back_populates="progress_updates",
    )
    worker: Mapped["Worker"] = relationship()

    def __repr__(self) -> str:
        return f"<AssignmentProgress id={self.id} assignment_id={self.assignment_id} worker_id={self.worker_id}>"
