"""
CivicPulse Community Follower Schemas

Defines request and response models for citizen community following.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.public_complaint import PublicComplaintItem


class FollowActionResponse(BaseModel):
    """
    Response payload following follow or unfollow operations.
    """

    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID = Field(..., description="UUID of the followed or unfollowed complaint")
    is_following: bool = Field(..., description="True if complaint is currently followed, False if unfollowed")
    followed_at: datetime | None = Field(default=None, description="Timestamp when follow was recorded (UTC)")
    message: str = Field(..., description="Human-readable outcome description")


class FollowingListResponseData(BaseModel):
    """
    Paginated response payload for citizen's followed public complaints feed.
    """

    total: int = Field(..., description="Total count of public complaints followed by citizen")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items returned in this page")
    total_pages: int = Field(..., description="Total pages available")
    items: list[PublicComplaintItem] = Field(default_factory=list, description="Followed public complaints")
