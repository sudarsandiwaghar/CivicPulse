"""
CivicPulse Complaint Service

Implements the business logic for complaint submission, retrieval, filtering,
lifecycle state machine transitions, and administrator review.

Architecture:
    - Centralized transition engine enforcing the legal transition matrix.
    - PostgreSQL row-level locking (with_for_update) for concurrency protection.
    - Atomic database updates combining complaint state and audit history.
    - Strict role and ownership verification preventing IDOR vulnerabilities.
    - Concurrency-safe complaint number generation via PostgreSQL sequences.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.core.constants import (
    COMPLAINT_STATUS_TRANSITIONS,
    AssignmentStatus,
    ComplaintStatus,
    PriorityLevel,
    UserRole,
)
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.location import Location
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintReviewRequest,
)
from app.services.sla_service import (
    evaluate_complaint_sla,
    on_complaint_created_sla_init,
    on_complaint_status_transition_sla_update,
)

# =============================================================================
# Lifecycle State Transition Matrix (Mirrors approved Phase 4 constants)
# =============================================================================

LEGAL_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = COMPLAINT_STATUS_TRANSITIONS


# =============================================================================
# Complaint Reference Number Generator
# =============================================================================

def generate_complaint_number(db: Session) -> str:
    """
    Generate an atomic, collision-free human-readable complaint reference number.

    Format: CP-YYYY-XXXXX (e.g. CP-2026-10001)
    Uses the PostgreSQL complaint_number_seq sequence to guarantee uniqueness
    across concurrent threads and transactions without locking table rows.
    """
    year = datetime.now(timezone.utc).year
    try:
        seq_val = db.execute(text("SELECT nextval('complaint_number_seq')")).scalar()
    except Exception:
        # Fallback in environments where sequence might not be installed
        db.rollback()
        count = db.query(Complaint).count()
        seq_val = 10001 + count
    return f"CP-{year}-{seq_val:05d}"


# =============================================================================
# Complaint Creation
# =============================================================================

def create_complaint(
    db: Session,
    citizen: User,
    data: ComplaintCreateRequest,
) -> Complaint:
    """
    Persist a new complaint filed by an authenticated citizen.

    Guarantees:
        - Category exists and is active.
        - Geographic coordinates are validated within WGS84 range.
        - Location and Complaint records are created in a single transaction.
        - Initial status is locked to SUBMITTED.
        - Default priority is locked to MEDIUM.
        - Unique tracking code generated server-side.
        - Initial status history record created atomically in the same transaction.

    Args:
        db: Active database session.
        citizen: Authenticated citizen User record.
        data: Validated complaint creation payload.

    Returns:
        The newly created Complaint entity.
    """
    # 1. Validate Category
    category = db.query(Category).filter(Category.id == data.category_id).first()
    if not category:
        raise EntityNotFoundError("Category", data.category_id)
    if not category.is_active:
        raise BusinessRuleViolationError(
            f"Category '{category.name}' is currently inactive and cannot accept new complaints"
        )

    # 2. Validate Coordinates (additional service-layer check)
    loc_data = data.location
    if not (-90.0 <= loc_data.latitude <= 90.0):
        raise BusinessRuleViolationError("Latitude must be between -90.0 and 90.0 degrees")
    if not (-180.0 <= loc_data.longitude <= 180.0):
        raise BusinessRuleViolationError("Longitude must be between -180.0 and 180.0 degrees")

    # 3. Create Location
    location = Location(
        latitude=loc_data.latitude,
        longitude=loc_data.longitude,
        address_line=loc_data.address_line,
        area_name=loc_data.area_name,
        city=loc_data.city or "Default City",
        pincode=loc_data.pincode,
        landmark=loc_data.landmark,
    )
    db.add(location)
    db.flush()

    # 4. Generate Complaint Number
    complaint_number = generate_complaint_number(db)

    # 5. Create Complaint (Strict server-side defaults)
    complaint = Complaint(
        complaint_number=complaint_number,
        citizen_id=citizen.id,
        category_id=category.id,
        location_id=location.id,
        title=data.title,
        description=data.description,
        status=ComplaintStatus.SUBMITTED,
        priority=PriorityLevel.MEDIUM,
    )
    db.add(complaint)
    db.flush()

    # 6. Create Initial Status History Record (Atomic)
    initial_history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=citizen.id,
        previous_status=None,
        new_status=ComplaintStatus.SUBMITTED,
        remarks="Initial complaint submission by citizen",
        created_at=datetime.now(timezone.utc),
    )
    db.add(initial_history)

    # 7. Initialize Dual SLA Clocks (Phase 6.3)
    on_complaint_created_sla_init(db, complaint, datetime.now(timezone.utc))

    # 8. In-App Notification Dispatch (Phase 6.4)
    from app.services.notification_service import notify_complaint_submitted
    notify_complaint_submitted(db, complaint, actor=citizen)

    db.commit()
    db.refresh(complaint)
    return complaint


# =============================================================================
# Complaint Retrieval & Filtering
# =============================================================================

def get_complaint_by_id(
    db: Session,
    complaint_id: uuid.UUID,
    user: User,
) -> Complaint:
    """
    Retrieve single complaint details with ownership and authorization validation.

    Authorization:
        - CITIZEN: Can only view complaints they authored.
        - ADMINISTRATOR: Can view any complaint.
        - FIELD_WORKER: Blocked from direct complaint access in Phase 4.

    Raises:
        EntityNotFoundError: If complaint does not exist.
        AuthorizationError: If citizen attempts to view another citizen's complaint.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    # Enforce role-based access scoping
    user_role = user.role.name
    if user_role == UserRole.CITIZEN.value:
        if complaint.citizen_id != user.id:
            raise AuthorizationError("You do not have permission to access this complaint")
    elif user_role == UserRole.FIELD_WORKER.value:
        is_assigned = any(a.worker.user_id == user.id for a in complaint.assignments)
        if not is_assigned:
            raise AuthorizationError("You do not have permission to access this complaint")

    return complaint


def get_complaint_history(
    db: Session,
    complaint_id: uuid.UUID,
    user: User,
) -> list[ComplaintStatusHistory]:
    """
    Retrieve chronological transition history for a complaint after verifying access.
    """
    # Verify access to complaint first (handles 404 and 403)
    get_complaint_by_id(db, complaint_id, user)

    return (
        db.query(ComplaintStatusHistory)
        .filter(ComplaintStatusHistory.complaint_id == complaint_id)
        .order_by(ComplaintStatusHistory.created_at.desc())
        .all()
    )


def list_complaints(
    db: Session,
    user: User,
    filters: dict[str, Any],
    pagination: PaginationParams,
) -> tuple[list[Complaint], int]:
    """
    Paginated search and retrieval of complaints.

    Scoping:
        - CITIZEN: Strictly scoped to current_user.id.
        - ADMINISTRATOR: Unrestricted access across all complaints with rich filtering.
        - FIELD_WORKER: Blocked in Phase 4.

    Returns:
        tuple of (matching_complaints_list, total_matching_items_count)
    """
    user_role = user.role.name
    if user_role == UserRole.FIELD_WORKER.value:
        raise AuthorizationError("Worker complaint task endpoints will be available in Phase 5")

    query = db.query(Complaint).join(Complaint.category).outerjoin(Complaint.location)

    # Apply role scoping
    if user_role == UserRole.CITIZEN.value:
        query = query.filter(Complaint.citizen_id == user.id)

    # Apply optional filters
    if filters.get("status"):
        query = query.filter(Complaint.status == filters["status"])

    if filters.get("priority"):
        query = query.filter(Complaint.priority == filters["priority"])

    if filters.get("category_id"):
        query = query.filter(Complaint.category_id == filters["category_id"])

    if filters.get("complaint_number"):
        query = query.filter(Complaint.complaint_number.ilike(f"%{filters['complaint_number'].strip()}%"))

    if filters.get("start_date"):
        query = query.filter(Complaint.created_at >= filters["start_date"])

    if filters.get("end_date"):
        query = query.filter(Complaint.created_at <= filters["end_date"])

    if filters.get("search"):
        term = f"%{filters['search'].strip()}%"
        query = query.filter(
            or_(
                Complaint.title.ilike(term),
                Complaint.description.ilike(term),
                Complaint.complaint_number.ilike(term),
            )
        )

    # Total count before pagination
    total_items = query.count()

    # Dynamic sorting
    sort_column_name = pagination.sort_by
    if hasattr(Complaint, sort_column_name):
        sort_col = getattr(Complaint, sort_column_name)
    else:
        sort_col = Complaint.created_at

    if pagination.sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Pagination slice
    items = query.offset(pagination.offset).limit(pagination.page_size).all()
    return items, total_items


# =============================================================================
# State Machine Lifecycle Engine
# =============================================================================

def execute_transition(
    db: Session,
    complaint_id: uuid.UUID,
    user: User,
    requested_status: ComplaintStatus,
    remarks: str | None = None,
    original_complaint_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Complaint:
    """
    Centralized complaint status transition engine.

    Enforces:
        - Row-level lock (with_for_update) to serialize concurrent transitions.
        - Current status to requested status transition matrix validation.
        - Role authority and permission checks.
        - Transition-specific precondition validations (reasons, duplicate target, assignments).
        - Atomic status change and audit history insertion.

    Raises:
        EntityNotFoundError: If complaint does not exist.
        AuthorizationError: If user role or ownership prohibits the transition.
        InvalidStateTransitionError: If the transition violates the lifecycle matrix.
        BusinessRuleViolationError: If required reasons, duplicate targets, or preconditions fail.
    """
    # 1. Lock complaint row for update (serializes concurrent transactions)
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .with_for_update()
        .first()
    )
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    current_status = complaint.status

    # Idempotent no-op
    if current_status == requested_status:
        return complaint

    user_role = user.role.name

    # 2. Role-based transition authority check
    if user_role == UserRole.CITIZEN.value:
        # Citizens can ONLY transition their own complaints
        if complaint.citizen_id != user.id:
            raise AuthorizationError("You do not have permission to transition this complaint")

        # Citizens can transition their own complaints from RESOLVED_AWAITING_VERIFICATION (to CLOSED or REOPENED)
        # or from CLOSED (to REOPENED within grace period).
        if current_status not in {ComplaintStatus.RESOLVED_AWAITING_VERIFICATION, ComplaintStatus.CLOSED}:
            raise AuthorizationError(
                f"Citizens cannot transition complaints currently in '{current_status.value}' status"
            )

        if current_status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION:
            if requested_status not in {ComplaintStatus.CLOSED, ComplaintStatus.REOPENED}:
                raise AuthorizationError(
                    f"Citizens can only transition to CLOSED or REOPENED, not '{requested_status.value}'"
                )
        elif current_status == ComplaintStatus.CLOSED:
            if requested_status != ComplaintStatus.REOPENED:
                raise AuthorizationError(
                    f"Citizens can only transition from CLOSED to REOPENED, not '{requested_status.value}'"
                )

    elif user_role == UserRole.FIELD_WORKER.value:
        # Field workers can only transition complaints they are actively assigned to
        active_assignment = next(
            (
                a
                for a in complaint.assignments
                if a.worker.user_id == user.id
                and (
                    a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}
                    or (
                        current_status == ComplaintStatus.IN_PROGRESS
                        and requested_status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION
                        and a.status == AssignmentStatus.COMPLETED
                    )
                )
            ),
            None,
        )
        if not active_assignment:
            raise AuthorizationError(
                "You are not the assigned worker for this complaint or the assignment is no longer active"
            )

        if current_status == ComplaintStatus.ASSIGNED:
            if requested_status != ComplaintStatus.IN_PROGRESS:
                raise AuthorizationError(
                    f"Assigned workers can only transition to 'IN_PROGRESS', not '{requested_status.value}'"
                )
        elif current_status == ComplaintStatus.IN_PROGRESS:
            if requested_status != ComplaintStatus.RESOLVED_AWAITING_VERIFICATION:
                raise AuthorizationError(
                    f"Workers in progress can only transition to 'RESOLVED_AWAITING_VERIFICATION', not '{requested_status.value}'"
                )
        else:
            raise AuthorizationError(
                f"Workers cannot transition complaints currently in '{current_status.value}' status"
            )

    # 3. Transition matrix check
    allowed_targets = LEGAL_TRANSITIONS.get(current_status, set())
    if requested_status not in allowed_targets:
        raise InvalidStateTransitionError(
            current_status.value,
            requested_status.value,
            f"Legal next states from '{current_status.value}' are: "
            f"{', '.join(s.value for s in allowed_targets) if allowed_targets else 'None (Terminal state)'}",
        )

    # 4. Precondition checks
    final_remarks = remarks.strip() if remarks else None

    # Rejection requires reason
    if requested_status == ComplaintStatus.REJECTED:
        if not final_remarks:
            raise BusinessRuleViolationError("Rejection requires a non-empty explanation or reason")

    # Duplicate requires valid original complaint
    if requested_status == ComplaintStatus.DUPLICATE:
        if not original_complaint_id:
            raise BusinessRuleViolationError("Marking a complaint as duplicate requires a valid original complaint UUID")
        if original_complaint_id == complaint.id:
            raise BusinessRuleViolationError("A complaint cannot be marked as a duplicate of itself")

        original_complaint = (
            db.query(Complaint)
            .filter(Complaint.id == original_complaint_id)
            .first()
        )
        if not original_complaint:
            raise EntityNotFoundError("Original Complaint", original_complaint_id)

        if original_complaint.status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
            raise BusinessRuleViolationError(
                f"Referenced original complaint '{original_complaint.complaint_number}' "
                f"cannot be used as a master duplicate because its status is '{original_complaint.status.value}'"
            )

        dup_note = f"Duplicate of master complaint {original_complaint.complaint_number} (ID: {original_complaint.id})"
        final_remarks = f"{dup_note}. {final_remarks}" if final_remarks else dup_note

    # On hold requires reason
    if requested_status == ComplaintStatus.ON_HOLD:
        if not final_remarks:
            raise BusinessRuleViolationError("Placing a complaint on hold requires a recorded reason")

    # Reopened requires reason and within 14-day grace period
    if requested_status == ComplaintStatus.REOPENED:
        if not final_remarks:
            raise BusinessRuleViolationError("Reopening a complaint requires a recorded reason")

        reference_time = complaint.closed_at or complaint.resolved_at
        if not reference_time:
            raise BusinessRuleViolationError(
                "Cannot reopen a complaint that lacks a verified resolution or closure timestamp"
            )
        now_utc = datetime.now(timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        if now_utc - reference_time > timedelta(days=14):
            raise BusinessRuleViolationError(
                "The 14-day grace period for reopening this complaint has expired. Please submit a new complaint."
            )

    # ASSIGNED and IN_PROGRESS require active assignment precondition
    if requested_status in {ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS}:
        has_active_assignment = any(
            a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}
            for a in complaint.assignments
        )
        if not has_active_assignment:
            raise InvalidStateTransitionError(
                current_status.value,
                requested_status.value,
                f"Transition to {requested_status.value} requires an active worker assignment (Phase 5 assignment workflow)",
            )

    # 5. Update Timestamps
    now_utc = datetime.now(timezone.utc)
    if requested_status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION:
        complaint.resolved_at = now_utc
    elif requested_status == ComplaintStatus.CLOSED:
        complaint.closed_at = now_utc
    elif requested_status == ComplaintStatus.REOPENED:
        complaint.closed_at = None
        # Note: complaint.resolved_at is preserved until on_complaint_status_transition_sla_update
        # snapshots the completed cycle history, after which it is cleared for the new cycle.

    # 6. Apply Status Change
    complaint.status = requested_status

    # Phase 6.2: Automatic Privacy Enforcement
    # Automatically revoke publication in the same transaction when transitioning to REJECTED or DUPLICATE
    if requested_status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
        complaint.is_public = False

    # 7. Create Audit History Entry (Same transaction)
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=user.id,
        previous_status=current_status,
        new_status=requested_status,
        remarks=final_remarks,
        created_at=datetime.now(timezone.utc),
    )
    db.add(history)
    db.flush()

    # 8. Dual Clock SLA Lifecycle Transition Hooks (Phase 6.3)
    on_complaint_status_transition_sla_update(
        db=db,
        complaint=complaint,
        previous_status=current_status,
        new_status=requested_status,
        now_utc=now_utc,
        actor=user,
    )

    # 9. In-App Notification Dispatch (Phase 6.4)
    from app.services.notification_service import notify_complaint_status_change
    notify_complaint_status_change(db=db, complaint=complaint, history=history, actor=user)

    if commit:
        db.commit()
        db.refresh(complaint)
    else:
        db.flush()
        db.refresh(complaint)
    return complaint


# =============================================================================
# Administrator Review Operations
# =============================================================================

def review_complaint(
    db: Session,
    complaint_id: uuid.UUID,
    admin_user: User,
    review: ComplaintReviewRequest,
) -> Complaint:
    """
    Execute administrator triage, category update, priority adjustment, or status transition.

    Enforces:
        - Administrator role check.
        - Row locking for concurrency.
        - Recorded justification for priority adjustments.
        - Category verification and reclassification.
        - State transition through execute_transition if status change requested.
        - Status history audit recording for all modifications.
    """
    if admin_user.role.name != UserRole.ADMINISTRATOR.value:
        raise AuthorizationError("Only administrators are authorized to review complaints")

    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .with_for_update()
        .first()
    )
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    audit_logs: list[str] = []

    # 1. Update Category if requested
    if review.category_id is not None and review.category_id != complaint.category_id:
        new_category = db.query(Category).filter(Category.id == review.category_id).first()
        if not new_category:
            raise EntityNotFoundError("Category", review.category_id)
        if not new_category.is_active:
            raise BusinessRuleViolationError(f"Category '{new_category.name}' is inactive")

        old_cat_id = complaint.category_id
        complaint.category_id = new_category.id
        audit_logs.append(f"Category changed from ID {old_cat_id} to '{new_category.name}' (ID {new_category.id})")

    # 2. Adjust Priority if requested
    if review.priority is not None and review.priority != complaint.priority:
        if not review.reason or not review.reason.strip():
            raise BusinessRuleViolationError("Adjusting complaint priority requires a recorded justification reason")
        old_priority = complaint.priority
        complaint.priority = review.priority
        audit_logs.append(f"Priority changed from {old_priority.value} to {review.priority.value}. Reason: {review.reason.strip()}")

    # 3. Handle Status Transition if requested
    if review.new_status is not None and review.new_status != complaint.status:
        # Commit pending changes before calling transition engine
        db.commit()
        transition_remarks = review.reason.strip() if review.reason else None
        if audit_logs:
            prefix = "; ".join(audit_logs)
            transition_remarks = f"{prefix}. {transition_remarks}" if transition_remarks else prefix

        return execute_transition(
            db=db,
            complaint_id=complaint_id,
            user=admin_user,
            requested_status=review.new_status,
            remarks=transition_remarks,
            original_complaint_id=review.original_complaint_id,
        )

    # 4. If status did not change but priority or category changed, record history audit
    if audit_logs:
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_id=admin_user.id,
            previous_status=complaint.status,
            new_status=complaint.status,
            remarks="; ".join(audit_logs),
            created_at=datetime.now(timezone.utc),
        )
        db.add(history)

        # Phase 6.3: Recalculate SLA targets and evaluate escalation
        evaluate_complaint_sla(db, complaint, datetime.now(timezone.utc))

        db.commit()
        db.refresh(complaint)

    return complaint
