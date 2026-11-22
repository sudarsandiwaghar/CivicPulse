"""
CivicPulse Complaint Follower Model

Defines the complaint_followers table representing citizen subscriptions
to public complaint updates and community feeds.

Design decisions:
    - UUID primary key for each follow relationship record.
    - Foreign keys to complaints and users (citizens) with CASCADE deletion.
    - Unique constraint on (complaint_id, citizen_id) prevents duplicate follows.
    - Timestamp tracking when the follow action occurred.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class ComplaintFollower(Base):
    """
    Community follow record linking a citizen to a public complaint.

    Attributes:
        id: Primary UUID identifier for follow relationship record.
        complaint_id: Foreign key referencing followed complaint.
        citizen_id: Foreign key referencing following citizen account.
        followed_at: Timestamp when citizen subscribed to the complaint (UTC).
    """

    __tablename__ = "complaint_followers"

    __table_args__ = (
        UniqueConstraint(
            "complaint_id",
            "citizen_id",
            name="uq_complaint_follower_citizen",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for complaint follower record",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing followed complaint",
    )
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing following citizen",
    )
    followed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when citizen followed the complaint (UTC)",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="followers",
    )
    citizen: Mapped["User"] = relationship(
        foreign_keys=[citizen_id],
    )

    def __repr__(self) -> str:
        return f"<ComplaintFollower complaint_id={self.complaint_id} citizen_id={self.citizen_id}>"
