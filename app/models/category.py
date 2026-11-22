"""
CivicPulse Category Model

Defines the categories table classifying civic complaints
(e.g., Pothole, Water Pipe Leakage, Garbage Accumulation, Illegal Dumping).

Design decisions:
    - Every category is explicitly linked to a responsible Department.
    - Complaint classification routes the issue to the appropriate department.
    - AI assessments can predict and suggest this category.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai_assessment import AIAssessment
    from app.models.complaint import Complaint
    from app.models.department import Department


class Category(Base, TimestampMixin):
    """
    Classification category for civic issues.

    Attributes:
        id: Auto-incrementing category identifier.
        department_id: Foreign key referencing the responsible department.
        name: Name of civic issue category (e.g. Pothole, Sewage Overflow).
        description: Guidance on issues falling under this category.
        is_active: Whether citizens can currently file complaints in this category.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Primary key for category",
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing managing department",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Unique civic issue category title",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed guidelines for classification under this category",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
        comment="Availability status for public complaint filing",
    )

    # Relationships
    department: Mapped["Department"] = relationship(
        back_populates="categories",
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )
    ai_predictions: Mapped[list["AIAssessment"]] = relationship(
        back_populates="predicted_category",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name='{self.name}' department_id={self.department_id}>"
