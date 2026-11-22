"""
CivicPulse Public Complaint & Moderation Service

Provides functionality for:
    1. Public complaint feed and detail discovery (unauthenticated, strict allowlist).
    2. Administrator public moderation (publish, update public text, revoke publication).
    3. Citizen author unpublishing requests.

Privacy & Security Invariants:
    - Never exposes raw citizen complaint title or description publicly.
    - Never exposes citizen personal identifiable information (PII).
    - Never exposes exact latitude, longitude, or street addresses.
    - Exposes only administrator-sanitized public_title and public_description.
    - Unauthenticated requests can only access is_public == True records.
    - 404 EntityNotFoundError returned for non-public or private complaints to prevent enumeration.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.constants import ComplaintStatus, UserRole
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
)
from app.models.complaint import Complaint
from app.models.user import User
from app.schemas.moderation import (
    ModeratePublicAction,
    ModeratePublicRequest,
    ModeratePublicResponse,
    UnpublishResponse,
)
from app.schemas.public_complaint import PublicComplaintItem


def map_complaint_to_public_item(complaint: Complaint) -> PublicComplaintItem:
    """
    Map a Complaint ORM instance strictly to the public-safe response schema.

    Strictly excludes:
        - Citizen names, emails, phones, user IDs.
        - Original complaint title and description.
        - Exact geographic coordinates (latitude, longitude).
        - Street addresses, landmarks, pincodes.
        - Internal remarks and assignment details.
    """
    category_name = complaint.category.name if complaint.category else "Uncategorized"
    ward_or_district = complaint.location.area_name if complaint.location else None
    city = complaint.location.city if complaint.location else None

    return PublicComplaintItem(
        id=complaint.id,
        complaint_number=complaint.complaint_number,
        category_name=category_name,
        status=complaint.status,
        created_at=complaint.created_at,
        public_title=complaint.public_title or "",
        public_description=complaint.public_description or "",
        ward_or_district=ward_or_district,
        city=city,
    )


def list_public_complaints(
    db: Session,
    category_id: int | None = None,
    status_filter: ComplaintStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PublicComplaintItem], int, int]:
    """
    Retrieve paginated list of published complaints.

    Guarantees:
        - Only is_public == True complaints are returned.
        - REJECTED and DUPLICATE complaints are strictly excluded.
        - Stable deterministic ordering (created_at DESC, id DESC).
        - Avoids N+1 queries via eager loading of category and location.

    Returns:
        tuple of (items_list, total_count, total_pages)
    """
    safe_page = max(1, page)
    safe_page_size = max(1, min(50, page_size))

    query = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.category),
            joinedload(Complaint.location),
        )
        .filter(
            Complaint.is_public.is_(True),
            Complaint.status.notin_([ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE]),
        )
    )

    if category_id is not None:
        query = query.filter(Complaint.category_id == category_id)

    if status_filter is not None:
        query = query.filter(Complaint.status == status_filter)

    total_count = query.count()
    total_pages = max(1, math.ceil(total_count / safe_page_size)) if total_count > 0 else 0

    offset = (safe_page - 1) * safe_page_size
    complaints = (
        query.order_by(Complaint.created_at.desc(), Complaint.id.desc())
        .offset(offset)
        .limit(safe_page_size)
        .all()
    )

    items = [map_complaint_to_public_item(c) for c in complaints]
    return items, total_count, total_pages


def get_public_complaint(db: Session, complaint_id: uuid.UUID) -> PublicComplaintItem:
    """
    Retrieve single published complaint for public view.

    Guarantees:
        - Returns 404 for private, unpublished, rejected, or duplicate complaints.
        - Never reveals whether a private complaint exists.
    """
    complaint = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.category),
            joinedload(Complaint.location),
        )
        .filter(
            Complaint.id == complaint_id,
            Complaint.is_public.is_(True),
            Complaint.status.notin_([ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE]),
        )
        .first()
    )

    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    return map_complaint_to_public_item(complaint)


def moderate_complaint_public(
    db: Session,
    complaint_id: uuid.UUID,
    admin_user: User,
    request: ModeratePublicRequest,
) -> ModeratePublicResponse:
    """
    Administrator moderation of complaint public visibility.

    Supports:
        - PUBLISH: Validate approved public content and set is_public = True.
        - UPDATE: Update approved public title and description.
        - REVOKE: Revoke publication (is_public = False), preserving text for audit.

    Guarantees:
        - Row-level lock protects against race conditions.
        - Publishing REJECTED or DUPLICATE complaints is strictly blocked.
        - Never modifies complaint lifecycle state machine status.
    """
    if admin_user.role.name != UserRole.ADMINISTRATOR.value:
        raise AuthorizationError("Only administrators can moderate public complaint visibility")

    # Lock complaint row for update
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .with_for_update()
        .first()
    )
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    now_utc = datetime.now(timezone.utc)

    if request.action == ModeratePublicAction.PUBLISH:
        if complaint.status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
            raise BusinessRuleViolationError(
                f"Cannot publish complaint with terminal status '{complaint.status.value}'"
            )

        complaint.is_public = True
        complaint.public_title = request.public_title
        complaint.public_description = request.public_description
        complaint.moderated_at = now_utc
        complaint.moderated_by_id = admin_user.id
        message = "Complaint approved and published successfully"

    elif request.action == ModeratePublicAction.UPDATE:
        if complaint.status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
            raise BusinessRuleViolationError(
                f"Cannot update public content for complaint with status '{complaint.status.value}'"
            )

        complaint.public_title = request.public_title
        complaint.public_description = request.public_description
        complaint.moderated_at = now_utc
        complaint.moderated_by_id = admin_user.id
        message = "Public complaint content updated successfully"

    elif request.action == ModeratePublicAction.REVOKE:
        complaint.is_public = False
        complaint.moderated_at = now_utc
        complaint.moderated_by_id = admin_user.id
        message = "Complaint publication revoked successfully"

    else:
        raise BusinessRuleViolationError(f"Unsupported moderation action: '{request.action}'")

    db.commit()
    db.refresh(complaint)

    return ModeratePublicResponse(
        complaint_id=complaint.id,
        complaint_number=complaint.complaint_number,
        is_public=complaint.is_public,
        public_title=complaint.public_title,
        public_description=complaint.public_description,
        moderated_at=complaint.moderated_at,
        moderated_by_id=complaint.moderated_by_id,
        message=message,
    )


def request_unpublish(
    db: Session,
    complaint_id: uuid.UUID,
    citizen_user: User,
    reason: str | None = None,
) -> UnpublishResponse:
    """
    Complaint author citizen requests unpublishing of their complaint.

    Guarantees:
        - Only complaint owner can request unpublishing.
        - Other citizens receive 403 Forbidden without leaking private complaint status.
        - Immediately sets is_public = False.
        - Records unpublish audit metadata (requester ID, timestamp, reason).
        - Preserves previous moderation audit history and approved text.
    """
    if citizen_user.role.name != UserRole.CITIZEN.value:
        raise AuthorizationError("Only citizens can request unpublishing")

    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .with_for_update()
        .first()
    )
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    # Ownership check
    if complaint.citizen_id != citizen_user.id:
        raise AuthorizationError("You do not have permission to request unpublishing for this complaint")

    now_utc = datetime.now(timezone.utc)
    if complaint.is_public:
        complaint.is_public = False
        complaint.unpublish_requested_at = now_utc
        complaint.unpublish_requested_by_id = citizen_user.id
        complaint.unpublish_reason = reason.strip() if reason and reason.strip() else None
    else:
        # Already unpublished: ensure is_public remains False and preserve initial audit metadata.
        # Do not allow subsequent idempotent requests to silently erase or overwrite original audit data.
        if not complaint.unpublish_requested_at:
            complaint.unpublish_requested_at = now_utc
            complaint.unpublish_requested_by_id = citizen_user.id
        if not complaint.unpublish_reason and reason and reason.strip():
            complaint.unpublish_reason = reason.strip()

    db.commit()
    db.refresh(complaint)

    return UnpublishResponse(
        complaint_id=complaint.id,
        is_public=complaint.is_public,
        unpublish_requested_at=complaint.unpublish_requested_at,
        unpublish_reason=complaint.unpublish_reason,
        message="Complaint unpublished successfully",
    )
