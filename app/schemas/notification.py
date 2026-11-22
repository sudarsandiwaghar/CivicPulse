"""
CivicPulse Notification Schemas

Pydantic V2 schemas for notification inbox retrieval, unread counts,
and read state management.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import NotificationType


class NotificationResponse(BaseModel):
    """
    Standard serialized representation of an in-app notification.
    """
    id: uuid.UUID
    recipient_id: uuid.UUID
    complaint_id: uuid.UUID | None = None
    notification_type: NotificationType
    title: str
    message: str
    event_key: str | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """
    Paginated notification inbox response.
    """
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    unread_count: int

    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    """
    Current unread notification count for badge display.
    """
    unread_count: int = Field(ge=0, description="Total unread notifications for authenticated user")

    model_config = ConfigDict(from_attributes=True)
