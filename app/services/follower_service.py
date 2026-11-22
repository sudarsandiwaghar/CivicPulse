"""
CivicPulse Community Follower Service

Provides functionality for citizens to follow and unfollow public complaints,
and to view their personal followed complaints feed.

Invariants:
    - Only authenticated citizens can follow, unfollow, or view following feeds.
    - Only complaints with is_public == True can be followed.
    - Unpublishing immediately removes complaints from the following feed.
    - Single unique follow record per (complaint_id, citizen_id).
    - Idempotent operations with graceful handling of duplicate follows.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.constants import ComplaintStatus, UserRole
from app.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
)
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.user import User
from app.schemas.follower import FollowActionResponse
from app.schemas.public_complaint import PublicComplaintItem
from app.services.public_complaint_service import map_complaint_to_public_item


def follow_complaint(
    db: Session,
    complaint_id: uuid.UUID,
    citizen_user: User,
) -> FollowActionResponse:
    """
    Citizen follows a public complaint.

    Guarantees:
        - Only CITIZEN role allowed.
        - Complaint must currently be is_public == True and not REJECTED or DUPLICATE.
        - Returns 404 for private complaints so private existence is never disclosed.
        - Idempotent: repeated follow requests do not duplicate records and return success.
        - Database unique constraint handles race conditions.
    """
    if citizen_user.role.name != UserRole.CITIZEN.value:
        raise AuthorizationError("Only citizens can follow complaints")

    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if (
        not complaint
        or not complaint.is_public
        or complaint.status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}
    ):
        raise EntityNotFoundError("Complaint", complaint_id)

    # Check for existing follow record
    existing = (
        db.query(ComplaintFollower)
        .filter(
            ComplaintFollower.complaint_id == complaint_id,
            ComplaintFollower.citizen_id == citizen_user.id,
        )
        .first()
    )
    if existing:
        return FollowActionResponse(
            complaint_id=complaint_id,
            is_following=True,
            followed_at=existing.followed_at,
            message="Already following this complaint",
        )

    now_utc = datetime.now(timezone.utc)
    follower = ComplaintFollower(
        complaint_id=complaint_id,
        citizen_id=citizen_user.id,
        followed_at=now_utc,
    )
    try:
        db.add(follower)
        db.commit()
        db.refresh(follower)
        return FollowActionResponse(
            complaint_id=complaint_id,
            is_following=True,
            followed_at=follower.followed_at,
            message="Complaint followed successfully",
        )
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(ComplaintFollower)
            .filter(
                ComplaintFollower.complaint_id == complaint_id,
                ComplaintFollower.citizen_id == citizen_user.id,
            )
            .first()
        )
        return FollowActionResponse(
            complaint_id=complaint_id,
            is_following=True,
            followed_at=existing.followed_at if existing else now_utc,
            message="Already following this complaint",
        )


def unfollow_complaint(
    db: Session,
    complaint_id: uuid.UUID,
    citizen_user: User,
) -> FollowActionResponse:
    """
    Citizen unfollows a complaint.

    Guarantees:
        - Only CITIZEN role allowed.
        - A citizen can only delete their own follow record.
        - Returns consistent success response even if the follow record did not exist.
    """
    if citizen_user.role.name != UserRole.CITIZEN.value:
        raise AuthorizationError("Only citizens can unfollow complaints")

    follower = (
        db.query(ComplaintFollower)
        .filter(
            ComplaintFollower.complaint_id == complaint_id,
            ComplaintFollower.citizen_id == citizen_user.id,
        )
        .first()
    )
    if not follower:
        return FollowActionResponse(
            complaint_id=complaint_id,
            is_following=False,
            followed_at=None,
            message="Complaint is not currently followed",
        )

    db.delete(follower)
    db.commit()

    return FollowActionResponse(
        complaint_id=complaint_id,
        is_following=False,
        followed_at=None,
        message="Unfollowed complaint successfully",
    )


def list_followed_complaints(
    db: Session,
    citizen_user: User,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PublicComplaintItem], int, int]:
    """
    Retrieve paginated feed of published complaints followed by the citizen.

    Guarantees:
        - Scoped strictly to authenticated citizen (never leaks other citizens' followed complaints).
        - Returns only complaints that are currently published (is_public == True).
        - Unpublished, rejected, or duplicate complaints automatically disappear.
        - Ordered by follow timestamp (most recently followed first).

    Returns:
        tuple of (items_list, total_count, total_pages)
    """
    if citizen_user.role.name != UserRole.CITIZEN.value:
        raise AuthorizationError("Only citizens can view followed complaints feed")

    safe_page = max(1, page)
    safe_page_size = max(1, min(50, page_size))

    query = (
        db.query(Complaint)
        .join(ComplaintFollower, ComplaintFollower.complaint_id == Complaint.id)
        .options(
            joinedload(Complaint.category),
            joinedload(Complaint.location),
        )
        .filter(
            ComplaintFollower.citizen_id == citizen_user.id,
            Complaint.is_public.is_(True),
            Complaint.status.notin_([ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE]),
        )
    )

    total_count = query.count()
    total_pages = max(1, math.ceil(total_count / safe_page_size)) if total_count > 0 else 0

    offset = (safe_page - 1) * safe_page_size
    complaints = (
        query.order_by(ComplaintFollower.followed_at.desc(), Complaint.id.desc())
        .offset(offset)
        .limit(safe_page_size)
        .all()
    )

    items = [map_complaint_to_public_item(c) for c in complaints]
    return items, total_count, total_pages
