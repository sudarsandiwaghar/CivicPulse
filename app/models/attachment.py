"""
CivicPulse Attachment Model

Defines the attachments table recording metadata and storage references
for files uploaded during complaint submission or resolution verification.

Design decisions:
    - Never stores raw file binaries in PostgreSQL columns.
    - Stores relative filesystem paths (or future object store keys).
    - Classifies attachments by purpose (COMPLAINT_EVIDENCE or RESOLUTION_EVIDENCE).
    - Stores file size, MIME type, and original file name for safe serving and validation.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AttachmentType
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class Attachment(Base, TimestampMixin):
    """
    Metadata and filesystem reference for uploaded evidence.

    Attributes:
        id: Primary UUID identifier for attachment.
        complaint_id: Foreign key referencing the associated complaint.
        uploaded_by_id: Foreign key referencing the user who uploaded the file.
        attachment_type: Classification (COMPLAINT_EVIDENCE or RESOLUTION_EVIDENCE).
        file_name: Original sanitised file name.
        file_path: Secure relative storage path on disk or object storage.
        file_size_bytes: File size in bytes.
        mime_type: Validated MIME content type (e.g. image/jpeg, application/pdf).
    """

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary UUID identifier for attachment record",
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing associated complaint",
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Foreign key referencing user who uploaded the attachment",
    )
    attachment_type: Mapped[AttachmentType] = mapped_column(
        Enum(AttachmentType, native_enum=False, length=30),
        default=AttachmentType.COMPLAINT_EVIDENCE,
        server_default=AttachmentType.COMPLAINT_EVIDENCE.value,
        nullable=False,
        comment="Purpose: COMPLAINT_EVIDENCE (citizen) or RESOLUTION_EVIDENCE (worker)",
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original client file name (sanitised)",
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Secure relative file storage path on disk",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Size of uploaded file in bytes",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME content type string",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        back_populates="attachments",
    )
    uploaded_by: Mapped["User"] = relationship(
        back_populates="attachments",
        foreign_keys=[uploaded_by_id],
    )

    def __repr__(self) -> str:
        return f"<Attachment id={self.id} complaint_id={self.complaint_id} file_name='{self.file_name}'>"
