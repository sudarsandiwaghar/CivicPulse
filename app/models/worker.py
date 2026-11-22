"""
CivicPulse Worker Model

Defines the workers table extending the user profile for field workers
and resolution team personnel.

Design decisions:
    - 1-to-1 relationship with the users table: worker profile extends an
      existing user identity without duplicating email or credentials.
    - Associated with a specific municipal Department.
    - Tracks employee identification, field availability, and active status.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.department import Department
    from app.models.user import User


class Worker(Base, TimestampMixin):
    """
    Profile extension for resolution field workers and technicians.

    Attributes:
        id: Primary UUID identifier for worker profile.
        user_id: Unique foreign key referencing the underlying user account.
        department_id: Foreign key referencing the employing department.
        employee_id: Unique municipal employee or contractor ID.
        designation: Job title / trade (e.g. Electrician, Road Repair Crew Leader).
        is_available: Field availability for accepting new assignments.
        employment_status: Current status (e.g. ACTIVE, ON_LEAVE, TERMINATED).
    """

    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for worker profile",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Foreign key linking to base user account (1-to-1)",
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing managing department",
    )
    employee_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique employer badge or employee identification code",
    )
    designation: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Field role designation or trade specialty",
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
        comment="Current assignment availability status",
    )
    employment_status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        server_default="ACTIVE",
        nullable=False,
        comment="Employment state: ACTIVE, ON_LEAVE, INACTIVE",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="worker_profile",
    )
    department: Mapped["Department"] = relationship(
        back_populates="workers",
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="worker",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Worker id={self.id} employee_id='{self.employee_id}' department_id={self.department_id}>"
