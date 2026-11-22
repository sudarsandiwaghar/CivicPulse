"""
CivicPulse Role Model

Defines the roles table storing the primary user authorization categories:
CITIZEN, ADMINISTRATOR, and FIELD_WORKER.

Design decisions:
    - Stable integer primary key with a unique, indexed role name.
    - Role names correspond to core.constants.UserRole.
    - Users hold a foreign key reference to this table.
    - Deletion of a role is restricted if any users are assigned to it.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Role(Base, TimestampMixin):
    """
    User authorization role record.

    Attributes:
        id: Auto-incrementing primary key.
        name: Unique role name (e.g. CITIZEN, ADMINISTRATOR, FIELD_WORKER).
        description: Human-readable role description and scope.
        is_active: Whether the role is currently active in the platform.
        users: Relationship to all users assigned to this role.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Primary key for role identifier",
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique role name (e.g. CITIZEN, ADMINISTRATOR, FIELD_WORKER)",
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Description of permissions and scope of the role",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
        comment="Flag indicating if the role is active",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        back_populates="role",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name='{self.name}'>"
