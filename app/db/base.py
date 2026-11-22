"""
CivicPulse Declarative Base and Shared Model Mixins

Defines the SQLAlchemy declarative base class that all ORM models
inherit from, along with standard mixins for consistent timestamp
tracking across all entities.

Centralising the base here prevents circular imports:
models import Base and TimestampMixin from this module, and the
session module imports metadata from here for engine binding.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all CivicPulse SQLAlchemy ORM models.

    Inheriting from DeclarativeBase (SQLAlchemy 2.x style) enables:
        - Mapped column declarations with type annotations
        - Automatic table metadata collection
        - Alembic migration auto-detection via Base.metadata
    """
    pass


class TimestampMixin:
    """
    Mixin providing created_at and updated_at timestamp columns.

    All timestamps are stored in UTC with timezone awareness.
    server_default=func.now() ensures database-level timestamp assignment
    even if records are inserted outside the ORM.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when record was created in UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when record was last updated in UTC",
    )
