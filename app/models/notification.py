"""
CivicPulse Notification Model

Defines the notifications table storing in-app notifications generated for
citizens, administrators, and field workers during complaint events.

Design decisions:
    - Stores event type (STATUS_CHANGE, ASSIGNMENT, FEEDBACK_RECEIVED, etc.).
    - Links to recipient user and optionally to the relevant complaint.
    - Tracks read status and timestamp for frontend notification badges.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import NotificationType
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class Notification(Base):
    """
    In-app notification message delivered to a platform user.

    Attributes:
        id: Primary UUID identifier for notification.
        recipient_id: Foreign key referencing the receiving user.
        complaint_id: Optional foreign key referencing the associated complaint.
        notification_type: Classification of event (e.g. STATUS_CHANGE, ASSIGNMENT).
        title: Short subject headline.
        message: Detailed notification message body.
        is_read: Read status flag.
        read_at: Timestamp when recipient opened/read the notification.
        created_at: Timestamp when notification was generated (UTC).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "event_key IS NULL OR length(trim(event_key)) > 0",
            name="ck_notifications_event_key_not_empty",
        ),
        Index(
            "uq_notifications_recipient_event_key",
            "recipient_id",
            "event_key",
            unique=True,
            postgresql_where=text("event_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for notification record",
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing receiving user account",
    )
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Optional foreign key referencing related complaint",
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=50),
        nullable=False,
        comment="Event classification category",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Subject title for notification banner",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full notification message text",
    )
    event_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Unique event identifier for idempotent notification delivery",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
        index=True,
        comment="Flag indicating whether notification has been read",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when notification was marked read (UTC)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when notification was generated (UTC)",
    )

    # Relationships
    recipient: Mapped["User"] = relationship(
        back_populates="notifications",
        foreign_keys=[recipient_id],
    )
    complaint: Mapped["Complaint | None"] = relationship(
        back_populates="notifications",
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} recipient_id={self.recipient_id} type='{self.notification_type}' is_read={self.is_read}>"
