"""
CivicPulse Department Model

Defines the departments table representing municipal or civic departments
(e.g., Road Maintenance, Sanitation, Water Supply, Public Health).

Design decisions:
    - Auto-incrementing integer identifier with stable, unique departmental code.
    - Departments own complaint categories and have assigned field workers.
    - Inactivation preserves historical references without data deletion.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.worker import Worker


class Department(Base, TimestampMixin):
    """
    Municipal department managing specific public infrastructure and services.

    Attributes:
        id: Auto-incrementing department identifier.
        name: Full departmental name (e.g. Department of Public Works).
        code: Short alphanumeric code (e.g. ROADS, SANITATION, WATER).
        description: Functional responsibilities of the department.
        contact_email: Official departmental contact email.
        contact_phone: Departmental helpline or office phone.
        is_active: Whether department is actively accepting complaints.
    """

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Primary key for department",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Full departmental name",
    )
    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
        comment="Short unique department identifier code",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Scope of civic responsibilities managed by this department",
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Official department contact email address",
    )
    contact_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Official department telephone number",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
        comment="Operational active status flag",
    )

    # Relationships
    categories: Mapped[list["Category"]] = relationship(
        back_populates="department",
        passive_deletes=True,
    )
    workers: Mapped[list["Worker"]] = relationship(
        back_populates="department",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} code='{self.code}' name='{self.name}'>"
