"""
CivicPulse Public Moderation Schemas

Defines request and response models for administrator moderation of public content
and citizen unpublishing requests.
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModeratePublicAction(str, Enum):
    """
    Administrator moderation actions for public complaint visibility.
    """

    PUBLISH = "PUBLISH"
    UPDATE = "UPDATE"
    REVOKE = "REVOKE"


class ModeratePublicRequest(BaseModel):
    """
    Payload for administrator moderation of complaint public visibility.
    """

    action: ModeratePublicAction = Field(
        ...,
        description="Moderation action: PUBLISH, UPDATE, or REVOKE",
    )
    public_title: str | None = Field(
        default=None,
        description="Administrator-approved headline (required for PUBLISH and UPDATE, 5–200 characters)",
    )
    public_description: str | None = Field(
        default=None,
        description="Administrator-approved description (required for PUBLISH and UPDATE, 10–2000 characters)",
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> "ModeratePublicRequest":
        if self.action in {ModeratePublicAction.PUBLISH, ModeratePublicAction.UPDATE}:
            # Validate public_title
            if not self.public_title or not self.public_title.strip():
                raise ValueError("public_title is required and cannot be empty when publishing or updating")
            cleaned_title = self.public_title.strip()
            if len(cleaned_title) < 5 or len(cleaned_title) > 200:
                raise ValueError(
                    f"public_title must be between 5 and 200 characters (got {len(cleaned_title)})"
                )
            self.public_title = cleaned_title

            # Validate public_description
            if not self.public_description or not self.public_description.strip():
                raise ValueError("public_description is required and cannot be empty when publishing or updating")
            cleaned_desc = self.public_description.strip()
            if len(cleaned_desc) < 10 or len(cleaned_desc) > 2000:
                raise ValueError(
                    f"public_description must be between 10 and 2000 characters (got {len(cleaned_desc)})"
                )
            self.public_description = cleaned_desc

        return self


class ModeratePublicResponse(BaseModel):
    """
    Response payload following an administrator public moderation action.
    """

    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID = Field(..., description="UUID of the moderated complaint")
    complaint_number: str = Field(..., description="Complaint tracking number")
    is_public: bool = Field(..., description="Whether complaint is currently published")
    public_title: str | None = Field(default=None, description="Approved public title")
    public_description: str | None = Field(default=None, description="Approved public description")
    moderated_at: datetime | None = Field(default=None, description="Timestamp of moderation action (UTC)")
    moderated_by_id: uuid.UUID | None = Field(default=None, description="Admin UUID who performed action")
    message: str = Field(..., description="Human-readable outcome description")


class UnpublishRequest(BaseModel):
    """
    Payload for complaint author citizen requesting unpublishing.
    """

    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional citizen explanation for unpublishing request (max 1000 characters)",
    )

    @model_validator(mode="after")
    def clean_reason(self) -> "UnpublishRequest":
        if self.reason is not None:
            cleaned = self.reason.strip()
            self.reason = cleaned if cleaned else None
        return self


class UnpublishResponse(BaseModel):
    """
    Response payload following a citizen unpublishing request.
    """

    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID = Field(..., description="UUID of the unpublished complaint")
    is_public: bool = Field(..., description="Whether complaint is currently published (False)")
    unpublish_requested_at: datetime = Field(..., description="Timestamp when unpublishing was recorded (UTC)")
    unpublish_reason: str | None = Field(default=None, description="Recorded unpublishing reason")
    message: str = Field(..., description="Human-readable outcome confirmation")
