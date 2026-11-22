"""
CivicPulse User Model

Defines the users table storing core authentication and identity data
for Citizens, Administrators, and Field Workers.

Design decisions:
    - UUID primary key for secure, unguessable entity identification.
    - References the roles table via role_id foreign key.
    - Single authentication identity per person; field workers have an
      extended profile in the workers table linked 1-to-1 with no credential duplication.
    - Unique indexed email and indexed phone number for fast lookups.
    - Explicit cascade and restriction rules to protect historical audit records.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, false, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.attachment import Attachment
    from app.models.complaint import Complaint
    from app.models.feedback import Feedback
    from app.models.notification import Notification
    from app.models.role import Role
    from app.models.status_history import ComplaintStatusHistory
    from app.models.worker import Worker


class User(Base, TimestampMixin):
    """
    Core user account for all CivicPulse actors.

    Attributes:
        id: UUID primary key.
        role_id: Foreign key referencing roles.id.
        email: Unique verified email address.
        hashed_password: Argon2 or bcrypt password hash.
        full_name: User's complete legal or display name.
        phone_number: Contact telephone number.
        is_active: Whether account is enabled.
        is_verified: Whether citizen/worker identity is verified.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID for user identity",
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing authorization role",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique email address for authentication",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Securely hashed password string",
    )
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Full name of user",
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Contact phone number",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
        comment="Account active status flag",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
        comment="Citizen or worker verification flag",
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        back_populates="users",
    )
    worker_profile: Mapped["Worker | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="citizen",
        foreign_keys="Complaint.citizen_id",
        passive_deletes=True,
    )
    assigned_complaints: Mapped[list["Assignment"]] = relationship(
        back_populates="assigned_by",
        foreign_keys="Assignment.assigned_by_id",
        passive_deletes=True,
    )
    status_changes: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="changed_by",
        foreign_keys="ComplaintStatusHistory.changed_by_id",
        passive_deletes=True,
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="uploaded_by",
        foreign_keys="Attachment.uploaded_by_id",
        passive_deletes=True,
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="recipient",
        foreign_keys="Notification.recipient_id",
        cascade="all, delete-orphan",
    )
    feedback_submissions: Mapped[list["Feedback"]] = relationship(
        back_populates="citizen",
        foreign_keys="Feedback.citizen_id",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role_id={self.role_id}>"
