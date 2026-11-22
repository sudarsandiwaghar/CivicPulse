"""
CivicPulse Notifications API Endpoints

Provides authenticated user notification inbox retrieval, unread count badge,
and read-state management endpoints under /api/v1/notifications.
"""

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.common import StandardResponse
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification_service import (
    get_unread_notification_count,
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)

router = APIRouter()


@router.get(
    "/unread-count",
    response_model=StandardResponse,
    summary="Get unread notification count",
    description="Retrieve the total count of unread notifications for the authenticated user badge.",
)
def get_unread_count(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardResponse:
    count = get_unread_notification_count(db=db, user_id=current_user.id)
    return StandardResponse(
        message="Unread notification count retrieved successfully",
        data={"unread_count": count},
    )


@router.post(
    "/read-all",
    response_model=StandardResponse,
    summary="Mark all notifications as read",
    description="Mark all unread notifications belonging to the authenticated user as read.",
)
def mark_all_read(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardResponse:
    count = mark_all_notifications_as_read(db=db, user_id=current_user.id)
    return StandardResponse(
        message="All notifications marked as read",
        data={"marked_read_count": count},
    )


@router.get(
    "",
    response_model=StandardResponse,
    summary="List notifications",
    description="Retrieve paginated in-app notifications for the authenticated user, optionally filtered by unread status.",
)
@router.get(
    "/",
    response_model=StandardResponse,
    include_in_schema=False,
)
def list_notifications(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    unread_only: bool = Query(False, description="Filter strictly to unread notifications"),
) -> StandardResponse:
    items, total = get_user_notifications(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    unread_count = get_unread_notification_count(db=db, user_id=current_user.id)

    response_data = NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        unread_count=unread_count,
    )
    return StandardResponse(
        message="Notifications retrieved successfully",
        data=response_data.model_dump(mode="json"),
    )


@router.patch(
    "/{notification_id}/read",
    response_model=StandardResponse,
    summary="Mark notification as read",
    description="Mark an individual notification as read. Enforces strict recipient ownership.",
)
def mark_read(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardResponse:
    notification = mark_notification_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )
    return StandardResponse(
        message="Notification marked as read successfully",
        data=NotificationResponse.model_validate(notification).model_dump(mode="json"),
    )
