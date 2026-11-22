"""
CivicPulse Notification Service

Centralized business logic for in-app notification management, idempotent event delivery,
role-based recipient resolution, follower privacy filtering, and read-state lifecycle.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.constants import AssignmentStatus, ComplaintStatus, NotificationType
from app.core.exceptions import EntityNotFoundError
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.notification import Notification
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User


# =============================================================================
# Core Notification Creation & Idempotency
# =============================================================================

def create_notifications(
    db: Session,
    recipient_ids: list[uuid.UUID] | set[uuid.UUID],
    notification_type: NotificationType,
    title: str,
    message: str,
    complaint_id: uuid.UUID | None = None,
    event_key: str | None = None,
) -> int:
    """
    Idempotently create notification records for a set of recipients in bulk.

    Guarantees:
        - Recipient IDs are deduplicated before insertion.
        - Uses PostgreSQL ON CONFLICT (recipient_id, event_key) WHERE event_key IS NOT NULL DO NOTHING.
        - Concurrent event emissions do not produce duplicate notifications.
        - Participates in the active database transaction without committing.
        - Legacy notifications without event_key remain supported.

    Args:
        db: Active SQLAlchemy database session.
        recipient_ids: Collection of recipient user UUIDs.
        notification_type: Enum classification category.
        title: Notification headline banner.
        message: Notification body description.
        complaint_id: Optional UUID of the associated complaint.
        event_key: Optional deterministic event identifier for idempotency.

    Returns:
        Number of candidate recipient rows scheduled for insertion.
    """
    if not recipient_ids:
        return 0

    clean_event_key = None
    if event_key is not None:
        clean_event_key = event_key.strip()
        if not clean_event_key:
            raise ValueError("event_key cannot be empty or whitespace-only")

    # Deduplicate recipients
    unique_recipients = {r for r in recipient_ids if r is not None}
    if not unique_recipients:
        return 0

    now_utc = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(),
            "recipient_id": r_id,
            "complaint_id": complaint_id,
            "notification_type": notification_type,
            "title": title.strip(),
            "message": message.strip(),
            "event_key": clean_event_key,
            "is_read": False,
            "read_at": None,
            "created_at": now_utc,
        }
        for r_id in unique_recipients
    ]

    stmt = pg_insert(Notification).values(rows)
    if clean_event_key is not None:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["recipient_id", "event_key"],
            index_where=text("event_key IS NOT NULL"),
        )
    db.execute(stmt)
    db.flush()
    return len(rows)


def create_notification(
    db: Session,
    recipient_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    complaint_id: uuid.UUID | None = None,
    event_key: str | None = None,
) -> int:
    """
    Convenience wrapper to create a notification for a single recipient.
    """
    return create_notifications(
        db=db,
        recipient_ids=[recipient_id],
        notification_type=notification_type,
        title=title,
        message=message,
        complaint_id=complaint_id,
        event_key=event_key,
    )


# =============================================================================
# Recipient Resolution Helpers
# =============================================================================

def _get_active_worker_user_id(complaint: Complaint) -> uuid.UUID | None:
    """
    Retrieve user ID of worker currently assigned and active on the complaint.
    """
    for a in complaint.assignments:
        if a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}:
            if a.worker and a.worker.user_id:
                return a.worker.user_id
    return None


def _get_public_follower_ids(db: Session, complaint: Complaint) -> list[uuid.UUID]:
    """
    Retrieve citizen follower user IDs strictly when the complaint is public.
    If the complaint is private (is_public=False), returns empty list.
    """
    if not complaint.is_public:
        return []

    followers = (
        db.query(ComplaintFollower.citizen_id)
        .filter(ComplaintFollower.complaint_id == complaint.id)
        .all()
    )
    return [f[0] for f in followers]


# =============================================================================
# Event-Specific Dispatch Handlers
# =============================================================================

def notify_complaint_submitted(
    db: Session,
    complaint: Complaint,
    actor: User | None = None,
) -> None:
    """
    Notify citizen that their complaint has been officially registered.
    Complaint creation confirmation to the submitting citizen is an explicit
    exception to the actor exclusion rule.
    """
    if complaint.citizen_id:
        create_notification(
            db=db,
            recipient_id=complaint.citizen_id,
            notification_type=NotificationType.STATUS_CHANGE,
            title=f"Complaint Submitted: {complaint.complaint_number}",
            message=f"Your complaint has been successfully registered with tracking number {complaint.complaint_number} and is awaiting administrative triage.",
            complaint_id=complaint.id,
            event_key=f"complaint:{complaint.id}:submitted",
        )


def notify_complaint_status_change(
    db: Session,
    complaint: Complaint,
    history: ComplaintStatusHistory,
    actor: User | None = None,
) -> None:
    """
    Dispatch notifications on complaint lifecycle state transitions.
    Respects recipient roles, publication status, and actor exclusion.
    """
    actor_id = actor.id if actor else None
    new_status = history.new_status
    c_num = complaint.complaint_number

    owner_id = complaint.citizen_id
    worker_id = _get_active_worker_user_id(complaint)
    follower_ids = _get_public_follower_ids(db, complaint)

    # 1. UNDER_REVIEW
    if new_status == ComplaintStatus.UNDER_REVIEW:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Complaint Under Review: {c_num}",
                message=f"Complaint {c_num} is currently undergoing administrative review and assessment.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )
        f_recipients = [f for f in follower_ids if f != actor_id and f != owner_id]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Public Complaint Under Review: {c_num}",
                message=f"Complaint {c_num} is now under administrative review.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:followers",
            )

    # 2. ON_HOLD
    elif new_status == ComplaintStatus.ON_HOLD:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Complaint Placed on Hold: {c_num}",
                message=f"Remediation for complaint {c_num} has been temporarily placed on hold pending further investigation.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )
        if worker_id and worker_id != actor_id and worker_id != owner_id:
            create_notification(
                db=db,
                recipient_id=worker_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Task Placed on Hold: {c_num}",
                message=f"Complaint {c_num} has been placed on hold.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:worker",
            )
        f_recipients = [f for f in follower_ids if f not in {actor_id, owner_id, worker_id}]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Complaint Placed on Hold: {c_num}",
                message=f"Complaint {c_num} has been temporarily placed on hold.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:followers",
            )

    # 3. RESOLVED_AWAITING_VERIFICATION
    elif new_status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.RESOLUTION_SUBMITTED,
                title=f"Complaint Resolved — Verification Required: {c_num}",
                message=f"Work on complaint {c_num} has been completed by the assigned field worker. Please review and verify the resolution.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )
        f_recipients = [f for f in follower_ids if f != actor_id and f != owner_id]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.RESOLUTION_SUBMITTED,
                title=f"Public Complaint Resolved: {c_num}",
                message=f"Remediation work for complaint {c_num} has been completed.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:followers",
            )

    # 4. CLOSED
    elif new_status == ComplaintStatus.CLOSED:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Complaint Closed: {c_num}",
                message=f"Complaint {c_num} has been verified and officially closed.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )
        if worker_id and worker_id != actor_id and worker_id != owner_id:
            create_notification(
                db=db,
                recipient_id=worker_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Task Verified and Closed: {c_num}",
                message=f"Remediation for complaint {c_num} has been verified and officially closed.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:worker",
            )
        f_recipients = [f for f in follower_ids if f not in {actor_id, owner_id, worker_id}]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Public Complaint Closed: {c_num}",
                message=f"Complaint {c_num} has been verified and closed.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:followers",
            )

    # 5. REOPENED
    elif new_status == ComplaintStatus.REOPENED:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.COMPLAINT_REOPENED,
                title=f"Complaint Reopened: {c_num}",
                message=f"Complaint {c_num} has been reopened for further investigation and remediation.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )
        if worker_id and worker_id != actor_id and worker_id != owner_id:
            create_notification(
                db=db,
                recipient_id=worker_id,
                notification_type=NotificationType.COMPLAINT_REOPENED,
                title=f"Complaint Reopened: {c_num}",
                message=f"Complaint {c_num} has been reopened by the resident for further attention.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:worker",
            )
        f_recipients = [f for f in follower_ids if f not in {actor_id, owner_id, worker_id}]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.COMPLAINT_REOPENED,
                title=f"Public Complaint Reopened: {c_num}",
                message=f"Complaint {c_num} has been reopened.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:followers",
            )

    # 6. REJECTED
    elif new_status == ComplaintStatus.REJECTED:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Complaint Rejected: {c_num}",
                message=f"Your complaint {c_num} could not be processed following administrative review.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )

    # 7. DUPLICATE
    elif new_status == ComplaintStatus.DUPLICATE:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Complaint Marked as Duplicate: {c_num}",
                message=f"Your complaint {c_num} has been identified as a duplicate of an existing municipal issue.",
                complaint_id=complaint.id,
                event_key=f"status:{history.id}:owner",
            )


def notify_assignment_dispatched(
    db: Session,
    complaint: Complaint,
    assignment: Assignment,
    actor: User | None = None,
) -> None:
    """
    Notify assigned worker, complaint owner, and public followers of new assignment.
    """
    actor_id = actor.id if actor else None
    c_num = complaint.complaint_number
    worker_user_id = assignment.worker.user_id if assignment.worker else None
    owner_id = complaint.citizen_id

    # 1. Newly assigned worker
    if worker_user_id and worker_user_id != actor_id:
        create_notification(
            db=db,
            recipient_id=worker_user_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"New Task Dispatched: {c_num}",
            message=f"You have been assigned to investigate and remediate complaint {c_num}.",
            complaint_id=complaint.id,
            event_key=f"assignment:{assignment.id}:worker",
        )

    # 2. Complaint owner
    if owner_id and owner_id != actor_id and owner_id != worker_user_id:
        create_notification(
            db=db,
            recipient_id=owner_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"Technician Dispatched: {c_num}",
            message=f"A field technician has been dispatched to address your complaint {c_num}.",
            complaint_id=complaint.id,
            event_key=f"assignment:{assignment.id}:owner",
        )

    # 3. Followers (if public)
    follower_ids = _get_public_follower_ids(db, complaint)
    f_recipients = [f for f in follower_ids if f not in {actor_id, owner_id, worker_user_id}]
    if f_recipients:
        create_notifications(
            db=db,
            recipient_ids=f_recipients,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"Technician Dispatched: {c_num}",
            message=f"A field technician has been dispatched for complaint {c_num}.",
            complaint_id=complaint.id,
            event_key=f"assignment:{assignment.id}:followers",
        )


def notify_assignment_reassigned(
    db: Session,
    complaint: Complaint,
    old_assignment: Assignment,
    new_assignment: Assignment,
    actor: User | None = None,
) -> None:
    """
    Notify replacement worker, previous worker, and complaint owner on reassignment.
    """
    actor_id = actor.id if actor else None
    c_num = complaint.complaint_number
    new_worker_user_id = new_assignment.worker.user_id if new_assignment.worker else None
    old_worker_user_id = old_assignment.worker.user_id if old_assignment.worker else None
    owner_id = complaint.citizen_id

    # 1. New worker
    if new_worker_user_id and new_worker_user_id != actor_id:
        create_notification(
            db=db,
            recipient_id=new_worker_user_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"New Task Dispatched: {c_num}",
            message=f"You have been assigned to investigate and remediate complaint {c_num}.",
            complaint_id=complaint.id,
            event_key=f"assignment:{new_assignment.id}:worker",
        )

    # 2. Previous worker
    if old_worker_user_id and old_worker_user_id != actor_id and old_worker_user_id != new_worker_user_id:
        create_notification(
            db=db,
            recipient_id=old_worker_user_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"Task Reassigned: {c_num}",
            message=f"Your assignment for complaint {c_num} has been reassigned to another technician.",
            complaint_id=complaint.id,
            event_key=f"assignment:{old_assignment.id}:reassigned",
        )

    # 3. Complaint owner
    if owner_id and owner_id != actor_id and owner_id not in {new_worker_user_id, old_worker_user_id}:
        create_notification(
            db=db,
            recipient_id=owner_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"Technician Reassigned: {c_num}",
            message=f"A replacement technician has been assigned to handle your complaint {c_num}.",
            complaint_id=complaint.id,
            event_key=f"assignment:{new_assignment.id}:owner",
        )


def notify_worker_activity(
    db: Session,
    complaint: Complaint,
    assignment: Assignment,
    activity_type: str,
    progress: AssignmentProgress | None = None,
    actor: User | None = None,
) -> None:
    """
    Notify complaint owner and public followers of worker milestone activity.
    Activity types: ACCEPTED, STARTED, PROGRESS.
    """
    actor_id = actor.id if actor else None
    c_num = complaint.complaint_number
    owner_id = complaint.citizen_id
    follower_ids = _get_public_follower_ids(db, complaint)

    if activity_type == "ACCEPTED":
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Task Acknowledged: {c_num}",
                message=f"The assigned technician has acknowledged and accepted complaint {c_num}.",
                complaint_id=complaint.id,
                event_key=f"assignment:{assignment.id}:accepted",
            )

    elif activity_type == "STARTED":
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Work Started on Site: {c_num}",
                message=f"Remediation work has commenced on site for complaint {c_num}.",
                complaint_id=complaint.id,
                event_key=f"assignment:{assignment.id}:started",
            )
        f_recipients = [f for f in follower_ids if f != actor_id and f != owner_id]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Work Started: {c_num}",
                message=f"On-site remediation work has commenced for complaint {c_num}.",
                complaint_id=complaint.id,
                event_key=f"assignment:{assignment.id}:started:followers",
            )

    elif activity_type == "PROGRESS" and progress is not None:
        if owner_id and owner_id != actor_id:
            create_notification(
                db=db,
                recipient_id=owner_id,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Progress Update: {c_num}",
                message=f"A progress milestone update was logged for complaint {c_num}.",
                complaint_id=complaint.id,
                event_key=f"progress:{progress.id}:owner",
            )
        f_recipients = [f for f in follower_ids if f != actor_id and f != owner_id]
        if f_recipients:
            create_notifications(
                db=db,
                recipient_ids=f_recipients,
                notification_type=NotificationType.STATUS_CHANGE,
                title=f"Progress Update: {c_num}",
                message=f"A progress update was logged for complaint {c_num}.",
                complaint_id=complaint.id,
                event_key=f"progress:{progress.id}:followers",
            )


def notify_sla_escalation(
    db: Session,
    complaint: Complaint,
    clock_type: str,
    prev_level: int,
    new_level: int,
    actor: User | None = None,
) -> None:
    """
    Dispatch notifications when an SLA escalation level genuinely increases.
    Strictly delivered to complaint owner and active assigned worker only.
    Never broadcast to public followers or all users.
    """
    if new_level <= prev_level:
        return

    actor_id = actor.id if actor else None
    c_num = complaint.complaint_number
    owner_id = complaint.citizen_id
    worker_id = _get_active_worker_user_id(complaint)

    # Determine titles and messages based on clock and level
    title = ""
    message = ""

    if clock_type == "response":
        if new_level == 1:
            title = f"Response SLA Warning: {c_num}"
            message = f"Initial response for complaint {c_num} has consumed 75% of allocated time."
        elif new_level >= 2:
            title = f"Response SLA Breached: {c_num}"
            message = f"Initial response target for complaint {c_num} has exceeded its SLA deadline."
    elif clock_type == "resolution":
        if new_level == 1:
            title = f"Resolution SLA Warning: {c_num}"
            message = f"Remediation duration for complaint {c_num} has consumed 75% of allocated time."
        elif new_level == 2:
            title = f"Resolution SLA Breached: {c_num}"
            message = f"Remediation duration for complaint {c_num} has exceeded its SLA deadline."
        elif new_level >= 3:
            title = f"Resolution SLA Critical Breach: {c_num}"
            message = f"Remediation duration for complaint {c_num} has exceeded 150% of its SLA target."

    if not title:
        return

    # Cycle-aware deterministic event key ensures new cycles generate their own distinct notifications
    event_key = f"sla:{complaint.id}:cycle:{complaint.sla_cycle_number}:{clock_type}:level:{new_level}"

    notif_type = NotificationType.SLA_WARNING if new_level == 1 else NotificationType.SLA_BREACH
    recipients = {r for r in [owner_id, worker_id] if r is not None and r != actor_id}
    if recipients:
        create_notifications(
            db=db,
            recipient_ids=recipients,
            notification_type=notif_type,
            title=title,
            message=message,
            complaint_id=complaint.id,
            event_key=event_key,
        )


# =============================================================================
# Inbox & Notification Management Queries
# =============================================================================

def get_unread_notification_count(db: Session, user_id: uuid.UUID) -> int:
    """
    Retrieve current unread notification count for authenticated user.
    """
    return (
        db.query(func.count(Notification.id))
        .filter(Notification.recipient_id == user_id, Notification.is_read.is_(False))
        .scalar()
        or 0
    )


def get_user_notifications(
    db: Session,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
) -> tuple[list[Notification], int]:
    """
    Retrieve paginated notification history for authenticated recipient.
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    query = db.query(Notification).filter(Notification.recipient_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def mark_notification_as_read(
    db: Session,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
    commit: bool = True,
) -> Notification:
    """
    Mark an individual notification as read. Enforces user ownership IDOR protection.
    """
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.recipient_id == user_id)
        .first()
    )
    if not notification:
        raise EntityNotFoundError("Notification", notification_id)

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        if commit:
            db.commit()
            db.refresh(notification)
        else:
            db.flush()

    return notification


def mark_all_notifications_as_read(
    db: Session,
    user_id: uuid.UUID,
    commit: bool = True,
) -> int:
    """
    Mark all unread notifications as read for the authenticated recipient.
    """
    now_utc = datetime.now(timezone.utc)
    updated_count = (
        db.query(Notification)
        .filter(Notification.recipient_id == user_id, Notification.is_read.is_(False))
        .update(
            {"is_read": True, "read_at": now_utc},
            synchronize_session=False,
        )
    )
    if commit:
        db.commit()
    else:
        db.flush()

    return updated_count
