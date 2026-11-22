"""
CivicPulse SLA Policy Model

Defines the sla_policies table representing Service Level Agreement definitions
scoped by complaint category, priority, or global fallback.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PriorityLevel
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category


class SLAPolicy(Base, TimestampMixin):
    """
    SLA Policy defining target response and resolution durations.

    Attributes:
        id: Primary UUID identifier.
        name: Human-readable policy name.
        description: Optional notes describing policy scope.
        category_id: Optional category dimension.
        priority: Optional priority dimension.
        response_time_hours: Positive integer hours to initial response.
        resolution_time_hours: Positive integer hours to complaint resolution.
        is_active: Whether policy is currently active for SLA assignment.
    """

    __tablename__ = "sla_policies"
    __table_args__ = (
        CheckConstraint("response_time_hours > 0", name="ck_sla_policies_response_time_hours"),
        CheckConstraint("resolution_time_hours > 0", name="ck_sla_policies_resolution_time_hours"),
        CheckConstraint("priority IS NULL OR priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_sla_policies_priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for SLA policy",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Descriptive name of SLA policy",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Policy scope and description notes",
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Category dimension (nullable for fallback/priority policies)",
    )
    priority: Mapped[PriorityLevel | None] = mapped_column(
        Enum(PriorityLevel, native_enum=False, length=20),
        nullable=True,
        index=True,
        comment="Priority dimension (nullable for fallback/category policies)",
    )
    response_time_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Target initial response time in hours (> 0)",
    )
    resolution_time_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Target resolution time in hours (> 0)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        index=True,
        comment="Whether policy is currently active for new resolutions",
    )

    # Relationships
    category: Mapped["Category | None"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<SLAPolicy id={self.id} name='{self.name}' "
            f"category_id={self.category_id} priority={self.priority} active={self.is_active}>"
        )
