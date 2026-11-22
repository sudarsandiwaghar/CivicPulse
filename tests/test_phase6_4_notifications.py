"""
CivicPulse Phase 6.4 Tests: In-App Notifications & Event Integration

Comprehensive test suite covering all 11 implementation areas specified in Phase 6.4:
    1.  Database Migration & Schema Integrity:
        - Partial unique index uq_notifications_recipient_event_key exists with WHERE event_key IS NOT NULL predicate.
        - Check constraint ck_notifications_event_key_not_empty enforces non-empty, non-whitespace event_key.
        - Null event_key allows multiple rows per recipient.
        - Duplicate event_key for same recipient violates partial unique index on raw insert.
    2.  Notification Service Idempotency & Concurrency:
        - create_notifications uses ON CONFLICT DO NOTHING for idempotent multi-recipient dispatch.
        - Deduplication of recipients in single dispatch call.
        - Empty recipients returns 0 without database insert.
        - Empty/whitespace event_key raises ValueError.
        - Transaction rollback atomicity (notifications revert with failed outer transaction).
    3.  Complaint Lifecycle Event Integration:
        - Citizen notified upon complaint submission with tracking number.
        - UNDER_REVIEW notifies owner and public followers (if public).
        - ON_HOLD notifies owner and assigned worker.
        - RESOLVED_AWAITING_VERIFICATION notifies owner with RESOLUTION_SUBMITTED.
        - CLOSED notifies assigned worker.
        - REOPENED notifies assigned worker and owner.
        - REJECTED notifies owner; no follower notification; no internal remarks leaked.
        - DUPLICATE notifies owner; no follower notification; no internal remarks leaked.
    4.  Worker Assignment & Milestone Events:
        - Assignment dispatch notifies assigned worker and owner.
        - Worker acceptance (ACCEPTED) notifies owner.
        - Work started (STARTED) notifies owner and public followers.
        - Progress milestone (PROGRESS) notifies owner and public followers.
        - Reassignment notifies replacement worker, previous worker, and owner.
    5.  SLA Escalation Notifications:
        - Response SLA Level 1 (warning) and Level 2 (breach) dispatch notifications.
        - Resolution SLA Level 1 (warning), Level 2 (breach), and Level 3 (critical breach) dispatch notifications.
        - Escalation notifications sent only when new_level > prev_level.
        - Repeated SLA evaluation at same level is idempotent.
        - SLA notifications delivered strictly to owner and active worker, never followers.
        - Reopened complaints generate cycle-aware event keys allowing distinct cycle notifications.
    6.  Follower Privacy Boundaries:
        - Private complaints (is_public=False) never dispatch notifications to followers across any event.
        - Public complaints (is_public=True) dispatch notifications to followers.
        - Redaction: no PII, no coordinates, no internal remarks in notification titles or bodies.
        - Actor exclusion: user performing action never receives echo notification (except submit confirmation).
        - Recipient deduplication if owner is also a follower.
    7.  Authenticated REST API Endpoints:
        - GET /api/v1/notifications: paginated user inbox ordered created_at DESC.
        - GET /api/v1/notifications?unread_only=true: filtered unread notifications.
        - GET /api/v1/notifications/unread-count: badge count.
        - PATCH /api/v1/notifications/{id}/read: marks notification read, sets read_at.
        - IDOR defense: marking another user's notification returns 404 EntityNotFoundError.
        - 404 on non-existent UUID.
        - POST /api/v1/notifications/read-all: marks all unread read for current user.
        - Route ordering sanity: /unread-count and /read-all do not collide with UUID path parameter.
        - 401 Unauthorized for unauthenticated requests.
"""

import math
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from psycopg2.errors import CheckViolation, UniqueViolation
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.constants import (
    AssignmentStatus,
    ComplaintStatus,
    NotificationType,
    PriorityLevel,
    UserRole,
)
from app.core.exceptions import EntityNotFoundError
from app.core.security import create_access_token, hash_password
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.department import Department
from app.models.location import Location
from app.models.notification import Notification
from app.models.role import Role
from app.models.sla_policy import SLAPolicy
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.models.worker import Worker
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintTransitionRequest,
    LocationCreate,
)
from app.services.assignment_service import (
    accept_assignment,
    add_assignment_progress,
    assign_complaint,
    reassign_complaint,
    start_assignment,
)
from app.services.complaint_service import (
    create_complaint,
    execute_transition,
    review_complaint,
)
from app.services.follower_service import follow_complaint
from app.services.notification_service import (
    create_notification,
    create_notifications,
    get_unread_notification_count,
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    notify_assignment_dispatched,
    notify_assignment_reassigned,
    notify_complaint_status_change,
    notify_complaint_submitted,
    notify_sla_escalation,
    notify_worker_activity,
)
from app.services.public_complaint_service import moderate_complaint_public
from app.services.sla_service import evaluate_complaint_sla, get_complaint_sla_details


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def citizen_role(db_session: Session) -> Role:
    return db_session.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()


@pytest.fixture
def admin_role(db_session: Session) -> Role:
    return db_session.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()


@pytest.fixture
def worker_role(db_session: Session) -> Role:
    return db_session.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()


@pytest.fixture
def admin_user(db_session: Session, admin_role: Role) -> User:
    user = User(
        email=f"admin64_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Notification Admin",
        role_id=admin_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(admin_user.id),
        role=UserRole.ADMINISTRATOR.value,
        extra_claims={"email": admin_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def citizen_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"citizen64_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Notification Citizen Owner",
        role_id=citizen_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def citizen_headers(citizen_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(citizen_user.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": citizen_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def follower_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"follower64_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Public Follower",
        role_id=citizen_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def follower_headers(follower_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(follower_user.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": follower_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_citizen_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"othercitizen64_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Other Citizen",
        role_id=citizen_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def other_citizen_headers(other_citizen_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(other_citizen_user.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": other_citizen_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def department(db_session: Session) -> Department:
    dept = Department(
        name=f"Roads & Infrastructure {uuid.uuid4().hex[:6]}",
        code=f"RI_{uuid.uuid4().hex[:4].upper()}",
        description="Road repairs and civil maintenance",
    )
    db_session.add(dept)
    db_session.flush()
    return dept


@pytest.fixture
def category(db_session: Session, department: Department) -> Category:
    cat = Category(
        name=f"Pothole Repair {uuid.uuid4().hex[:6]}",
        description="Fixing surface potholes",
        department_id=department.id,
    )
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def worker_user(db_session: Session, worker_role: Role, department: Department) -> User:
    user = User(
        email=f"worker64_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Primary Field Worker",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker_profile = Worker(
        user_id=user.id,
        department_id=department.id,
        employee_id=f"EMP-{uuid.uuid4().hex[:5].upper()}",
        is_available=True,
    )
    db_session.add(worker_profile)
    db_session.flush()
    return user


@pytest.fixture
def worker_headers(worker_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(worker_user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": worker_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_worker_user(db_session: Session, worker_role: Role, department: Department) -> User:
    user = User(
        email=f"otherworker64_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Replacement Field Worker",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker_profile = Worker(
        user_id=user.id,
        department_id=department.id,
        employee_id=f"EMP-{uuid.uuid4().hex[:5].upper()}",
        is_available=True,
    )
    db_session.add(worker_profile)
    db_session.flush()
    return user


@pytest.fixture
def other_worker_headers(other_worker_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(other_worker_user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": other_worker_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


def create_test_complaint(
    db: Session,
    citizen: User,
    category: Category,
    title: str = "Test Complaint",
    description: str = "Needs urgent municipal repair",
    priority: PriorityLevel = PriorityLevel.MEDIUM,
) -> Complaint:
    """Helper to create and persist a valid complaint."""
    req = ComplaintCreateRequest(
        title=title,
        description=description,
        category_id=category.id,
        location=LocationCreate(
            latitude=12.9716,
            longitude=77.5946,
            address_line="MG Road, Bengaluru",
            area_name="Central",
            city="Bengaluru",
            pincode="560001",
        ),
    )
    complaint = create_complaint(db, citizen, req)
    return complaint


# =============================================================================
# 1. Database Migration & Schema Integrity Tests
# =============================================================================

def test_migration_007_partial_unique_index_exists(db_session: Session):
    """Verify that partial unique index uq_notifications_recipient_event_key exists on notifications."""
    result = db_session.execute(
        text(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'notifications' AND indexname = 'uq_notifications_recipient_event_key';
            """
        )
    ).first()
    assert result is not None, "Partial unique index uq_notifications_recipient_event_key must exist"
    assert "WHERE (event_key IS NOT NULL)" in result[1] or "WHERE event_key IS NOT NULL" in result[1]


def test_migration_007_check_constraint_empty_event_key(db_session: Session, citizen_user: User):
    """Verify check constraint rejects empty string event_key."""
    notif = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Check Test",
        message="Message",
        event_key="",
    )
    db_session.add(notif)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_migration_007_check_constraint_whitespace_event_key(db_session: Session, citizen_user: User):
    """Verify check constraint rejects whitespace-only event_key."""
    notif = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Check Test",
        message="Message",
        event_key="   ",
    )
    db_session.add(notif)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_migration_007_null_event_key_allows_duplicates(db_session: Session, citizen_user: User):
    """Verify that rows with event_key=None can be inserted multiple times for the same recipient."""
    notif1 = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Null Key 1",
        message="Message 1",
        event_key=None,
    )
    notif2 = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Null Key 2",
        message="Message 2",
        event_key=None,
    )
    db_session.add(notif1)
    db_session.add(notif2)
    db_session.flush()
    assert notif1.id is not None
    assert notif2.id is not None


def test_migration_007_duplicate_event_key_rejected(db_session: Session, citizen_user: User):
    """Verify that inserting duplicate (recipient_id, event_key) directly violates unique index."""
    shared_key = f"event:{uuid.uuid4().hex}"
    notif1 = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Key 1",
        message="Message 1",
        event_key=shared_key,
    )
    db_session.add(notif1)
    db_session.flush()

    notif2 = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Key 2",
        message="Message 2",
        event_key=shared_key,
    )
    db_session.add(notif2)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# =============================================================================
# 2. Notification Service Unit & Idempotency Tests
# =============================================================================

def test_create_notifications_idempotent_on_conflict(db_session: Session, citizen_user: User):
    """Verify create_notifications uses ON CONFLICT DO NOTHING without raising errors or duplicating."""
    shared_key = f"event:test:{uuid.uuid4().hex}"
    count1 = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="First Call",
        message="Body 1",
        event_key=shared_key,
    )
    assert count1 == 1

    # Second call with identical recipient and event_key
    count2 = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Second Call",
        message="Body 2",
        event_key=shared_key,
    )
    assert count2 == 1

    # Only one record in database
    records = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == citizen_user.id, Notification.event_key == shared_key)
        .all()
    )
    assert len(records) == 1
    assert records[0].title == "First Call"


def test_create_notifications_deduplicates_recipients(db_session: Session, citizen_user: User):
    """Verify passing duplicate recipient IDs schedules only 1 row."""
    shared_key = f"event:dedup:{uuid.uuid4().hex}"
    count = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id, citizen_user.id, citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Dedup",
        message="Body",
        event_key=shared_key,
    )
    assert count == 1
    records = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == citizen_user.id, Notification.event_key == shared_key)
        .all()
    )
    assert len(records) == 1


def test_create_notifications_empty_recipients(db_session: Session):
    """Verify empty recipient list returns 0 without error."""
    assert create_notifications(
        db=db_session,
        recipient_ids=[],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Empty",
        message="None",
    ) == 0


def test_create_notifications_empty_or_whitespace_event_key_raises(db_session: Session, citizen_user: User):
    """Verify passing empty or whitespace-only event_key raises ValueError."""
    with pytest.raises(ValueError, match="event_key cannot be empty"):
        create_notifications(
            db=db_session,
            recipient_ids=[citizen_user.id],
            notification_type=NotificationType.STATUS_CHANGE,
            title="Empty Key",
            message="Body",
            event_key="   ",
        )


def test_notification_transaction_rollback_atomicity(db_session: Session, citizen_user: User):
    """Verify notifications created in an outer transaction are completely rolled back on error."""
    nested = db_session.begin_nested()
    shared_key = f"rollback:{uuid.uuid4().hex}"
    create_notification(
        db=db_session,
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Rollback Test",
        message="Should not persist",
        event_key=shared_key,
    )
    # Check it exists in savepoint
    notif = db_session.query(Notification).filter(Notification.event_key == shared_key).first()
    assert notif is not None

    # Roll back savepoint
    nested.rollback()

    notif_after = db_session.query(Notification).filter(Notification.event_key == shared_key).first()
    assert notif_after is None


# =============================================================================
# 3. Complaint Lifecycle Event Integration Tests
# =============================================================================

def test_complaint_submitted_notification(db_session: Session, citizen_user: User, category: Category):
    """Citizen filing a complaint receives submission confirmation notification with tracking number."""
    complaint = create_test_complaint(db_session, citizen_user, category)

    notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key == f"complaint:{complaint.id}:submitted",
        )
        .first()
    )
    assert notif is not None
    assert complaint.complaint_number in notif.title
    assert complaint.complaint_number in notif.message
    assert notif.notification_type == NotificationType.STATUS_CHANGE
    assert not notif.is_read


def test_complaint_submitted_idempotent(db_session: Session, citizen_user: User, category: Category):
    """Calling notify_complaint_submitted multiple times does not produce duplicate notifications."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    notify_complaint_submitted(db_session, complaint, actor=citizen_user)

    count = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key == f"complaint:{complaint.id}:submitted",
        )
        .count()
    )
    assert count == 1


def test_transition_under_review_notifies_owner(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """Transitioning to UNDER_REVIEW notifies owner; admin actor excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)

    # Admin reviews complaint -> UNDER_REVIEW
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        remarks="Under administrative assessment",
        commit=False,
    )

    # Owner should have UNDER_REVIEW notification
    owner_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Under Review%"),
        )
        .first()
    )
    assert owner_notif is not None

    # Admin actor should NOT receive notification (actor exclusion)
    admin_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == admin_user.id,
            Notification.complaint_id == complaint.id,
        )
        .first()
    )
    assert admin_notif is None


def test_transition_under_review_notifies_followers_if_public(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    category: Category,
):
    """Followers receive notification only if complaint is public."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()

    # Citizen follows public complaint
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)

    # Admin transitions to UNDER_REVIEW
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        remarks="Under review",
        commit=False,
    )

    # Follower should have notification
    f_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.complaint_id == complaint.id,
        )
        .first()
    )
    assert f_notif is not None
    assert "Public Complaint Under Review" in f_notif.title


def test_transition_on_hold_notifies_owner_and_worker(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """Transitioning to ON_HOLD notifies owner and assigned worker."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    # Put on hold by admin
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.ON_HOLD,
        remarks="Waiting for specialized asphalt",
        commit=False,
    )

    owner_hold = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Hold%"),
        )
        .first()
    )
    assert owner_hold is not None

    worker_hold = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == worker_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Hold%"),
        )
        .first()
    )
    assert worker_hold is not None


def test_transition_resolved_notifies_owner(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """Worker marking resolved notifies owner with RESOLUTION_SUBMITTED; worker excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    # Worker completes work
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=worker_user,
        requested_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        remarks="Pothole filled and sealed",
        commit=False,
    )

    owner_res = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.notification_type == NotificationType.RESOLUTION_SUBMITTED,
        )
        .first()
    )
    assert owner_res is not None
    assert "Verification Required" in owner_res.title


def test_transition_closed_notifies_worker(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """Citizen closing complaint notifies worker; citizen excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=worker_user,
        requested_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        remarks="Pothole filled",
        commit=False,
    )

    # Citizen confirms resolution -> CLOSED
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=citizen_user,
        requested_status=ComplaintStatus.CLOSED,
        remarks="Looks great, thank you",
        commit=False,
    )

    worker_closed = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == worker_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Closed%"),
        )
        .first()
    )
    assert worker_closed is not None


def test_transition_reopened_notifies_worker(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """Citizen reopening complaint notifies assigned worker; citizen excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=worker_user,
        requested_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        remarks="Pothole filled",
        commit=False,
    )

    # Citizen rejects resolution -> REOPENED
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=citizen_user,
        requested_status=ComplaintStatus.REOPENED,
        remarks="Surface cracked again overnight",
        commit=False,
    )

    worker_reopened = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == worker_user.id,
            Notification.complaint_id == complaint.id,
            Notification.notification_type == NotificationType.COMPLAINT_REOPENED,
        )
        .first()
    )
    assert worker_reopened is not None


def test_transition_rejected_notifies_owner_only(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    category: Category,
):
    """REJECTED notifies owner only; no followers notified even if previously public; no internal remarks leaked."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)

    # Admin rejects complaint
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.REJECTED,
        remarks="Private property — not a municipal road",
        commit=False,
    )

    # Owner notified
    owner_rej = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Rejected%"),
        )
        .first()
    )
    assert owner_rej is not None
    assert "Private property" not in owner_rej.message

    # Follower receives NO notification for rejected
    follower_rej = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Rejected%"),
        )
        .first()
    )
    assert follower_rej is None


def test_transition_duplicate_notifies_owner_only(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """DUPLICATE notifies owner only; no internal remarks leaked."""
    master = Complaint(
        complaint_number=f"CP-MASTER-{uuid.uuid4().hex[:6].upper()}",
        citizen_id=citizen_user.id,
        category_id=category.id,
        title="Master Issue",
        description="Master issue details",
        status=ComplaintStatus.UNDER_REVIEW,
        priority=PriorityLevel.MEDIUM,
    )
    db_session.add(master)
    db_session.flush()

    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.DUPLICATE,
        remarks="Internal reference to CP-1002",
        original_complaint_id=master.id,
        commit=False,
    )

    owner_dup = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Duplicate%"),
        )
        .first()
    )
    assert owner_dup is not None
    assert "Internal reference" not in owner_dup.message


# =============================================================================
# 4. Worker Assignment & Milestone Event Tests
# =============================================================================

def test_assignment_dispatched_notifies_worker_and_owner(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """Dispatching an assignment notifies worker (ASSIGNMENT) and owner (ASSIGNMENT); admin actor excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )

    # Worker notification
    worker_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == worker_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key == f"assignment:{assignment.id}:worker",
        )
        .first()
    )
    assert worker_notif is not None
    assert worker_notif.notification_type == NotificationType.ASSIGNMENT

    # Owner notification
    owner_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key == f"assignment:{assignment.id}:owner",
        )
        .first()
    )
    assert owner_notif is not None
    assert owner_notif.notification_type == NotificationType.ASSIGNMENT


def test_assignment_dispatched_notifies_public_followers(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    worker_user: User,
    category: Category,
):
    """Assignment dispatch notifies public followers when complaint is public."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )

    f_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key == f"assignment:{assignment.id}:followers",
        )
        .first()
    )
    assert f_notif is not None


def test_worker_activity_accepted_notifies_owner(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """Worker accepting assignment notifies owner; worker excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )

    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    owner_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key == f"assignment:{assignment.id}:accepted",
        )
        .first()
    )
    assert owner_notif is not None
    assert "Acknowledged" in owner_notif.title


def test_worker_activity_started_notifies_owner_and_followers(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    worker_user: User,
    category: Category,
):
    """Worker starting work notifies owner and public followers."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    owner_started = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == f"assignment:{assignment.id}:started",
        )
        .first()
    )
    assert owner_started is not None

    follower_started = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.event_key == f"assignment:{assignment.id}:started:followers",
        )
        .first()
    )
    assert follower_started is not None


def test_worker_activity_progress_notifies_owner_and_followers(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    worker_user: User,
    category: Category,
):
    """Worker logging progress update notifies owner and public followers."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    progress = add_assignment_progress(
        db=db_session,
        assignment_id=assignment.id,
        worker_user=worker_user,
        description="Excavated damaged road section",
    )

    owner_prog = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == f"progress:{progress.id}:owner",
        )
        .first()
    )
    assert owner_prog is not None

    follower_prog = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.event_key == f"progress:{progress.id}:followers",
        )
        .first()
    )
    assert follower_prog is not None


def test_assignment_reassigned_notifies_new_worker_old_worker_owner(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    other_worker_user: User,
    category: Category,
):
    """Reassigning complaint notifies replacement worker, previous worker, and owner; admin excluded."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile1 = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    worker_profile2 = db_session.query(Worker).filter(Worker.user_id == other_worker_user.id).first()

    old_assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile1.id,
        admin_user=admin_user,
    )
    new_assignment, _ = reassign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        new_worker_id=worker_profile2.id,
        admin_user=admin_user,
        reason="Specialist required",
    )

    # 1. New worker notified
    new_worker_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == other_worker_user.id,
            Notification.event_key == f"assignment:{new_assignment.id}:worker",
        )
        .first()
    )
    assert new_worker_notif is not None

    # 2. Old worker notified
    old_worker_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == worker_user.id,
            Notification.event_key == f"assignment:{old_assignment.id}:reassigned",
        )
        .first()
    )
    assert old_worker_notif is not None

    # 3. Owner notified
    owner_notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == f"assignment:{new_assignment.id}:owner",
        )
        .first()
    )
    assert owner_notif is not None
    assert "Reassigned" in owner_notif.title


# =============================================================================
# 5. SLA Escalation Notification Tests
# =============================================================================

def test_sla_response_warning_level_1(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Response SLA Level 1 warning generates notification with SLA_WARNING type and cycle-aware event_key."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.sla_cycle_number = 1

    notify_sla_escalation(
        db=db_session,
        complaint=complaint,
        clock_type="response",
        prev_level=0,
        new_level=1,
    )

    notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == f"sla:{complaint.id}:cycle:1:response:level:1",
        )
        .first()
    )
    assert notif is not None
    assert "Response SLA Warning" in notif.title
    assert notif.notification_type == NotificationType.SLA_WARNING


def test_sla_response_breach_level_2(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Response SLA Level 2 breach generates notification with SLA_BREACH type."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.sla_cycle_number = 1

    notify_sla_escalation(
        db=db_session,
        complaint=complaint,
        clock_type="response",
        prev_level=1,
        new_level=2,
    )

    notif = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == f"sla:{complaint.id}:cycle:1:response:level:2",
        )
        .first()
    )
    assert notif is not None
    assert "Response SLA Breached" in notif.title
    assert notif.notification_type == NotificationType.SLA_BREACH


def test_sla_resolution_warning_and_breaches(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Resolution SLA Level 1 (SLA_WARNING), Level 2 (SLA_BREACH), and Level 3 (SLA_BREACH) generate distinct notifications."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.sla_cycle_number = 1

    # Level 1 -> SLA_WARNING
    notify_sla_escalation(db_session, complaint, "resolution", 0, 1)
    n1 = db_session.query(Notification).filter(Notification.event_key == f"sla:{complaint.id}:cycle:1:resolution:level:1").first()
    assert n1 is not None
    assert "Resolution SLA Warning" in n1.title
    assert n1.notification_type == NotificationType.SLA_WARNING

    # Level 2 -> SLA_BREACH
    notify_sla_escalation(db_session, complaint, "resolution", 1, 2)
    n2 = db_session.query(Notification).filter(Notification.event_key == f"sla:{complaint.id}:cycle:1:resolution:level:2").first()
    assert n2 is not None
    assert "Resolution SLA Breached" in n2.title
    assert n2.notification_type == NotificationType.SLA_BREACH

    # Level 3 -> SLA_BREACH
    notify_sla_escalation(db_session, complaint, "resolution", 2, 3)
    n3 = db_session.query(Notification).filter(Notification.event_key == f"sla:{complaint.id}:cycle:1:resolution:level:3").first()
    assert n3 is not None
    assert "Critical Breach" in n3.title
    assert n3.notification_type == NotificationType.SLA_BREACH


def test_sla_escalation_only_on_increase(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Evaluating SLA when new_level <= prev_level generates 0 notifications."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    before_count = db_session.query(Notification).count()

    # Same level
    notify_sla_escalation(db_session, complaint, "resolution", 1, 1)
    # De-escalation
    notify_sla_escalation(db_session, complaint, "resolution", 2, 1)

    after_count = db_session.query(Notification).count()
    assert before_count == after_count


def test_sla_escalation_idempotent(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Repeated evaluation with identical level does not duplicate notifications."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    notify_sla_escalation(db_session, complaint, "resolution", 0, 1)
    notify_sla_escalation(db_session, complaint, "resolution", 0, 1)

    records = db_session.query(Notification).filter(Notification.event_key == f"sla:{complaint.id}:cycle:1:resolution:level:1").all()
    assert len(records) == 1


def test_sla_escalation_never_broadcast_to_followers(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    category: Category,
):
    """SLA escalation notifications are never delivered to complaint followers."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)

    notify_sla_escalation(db_session, complaint, "resolution", 0, 2)

    follower_sla = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%SLA%"),
        )
        .first()
    )
    assert follower_sla is None


def test_sla_cycle_aware_event_keys_on_reopening(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Reopening increments cycle, generating distinct cycle 2 SLA notifications."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.sla_cycle_number = 1
    notify_sla_escalation(db_session, complaint, "resolution", 0, 1)

    # Reopening increments cycle
    complaint.sla_cycle_number = 2
    notify_sla_escalation(db_session, complaint, "resolution", 0, 1)

    c1_notif = db_session.query(Notification).filter(Notification.event_key == f"sla:{complaint.id}:cycle:1:resolution:level:1").first()
    c2_notif = db_session.query(Notification).filter(Notification.event_key == f"sla:{complaint.id}:cycle:2:resolution:level:1").first()

    assert c1_notif is not None
    assert c2_notif is not None
    assert c1_notif.id != c2_notif.id


# =============================================================================
# 6. Follower Privacy Boundaries & Content Redaction Tests
# =============================================================================

def test_private_complaint_zero_follower_notifications(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    follower_user: User,
    worker_user: User,
    category: Category,
):
    """Private complaint (is_public=False) never sends notifications to followers."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    assert not complaint.is_public

    # Directly insert follow record (simulating legacy or edge case)
    follow_rec = ComplaintFollower(citizen_id=follower_user.id, complaint_id=complaint.id)
    db_session.add(follow_rec)
    db_session.flush()

    # Admin reviews
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    # Worker assigns, accepts, starts
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assign, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assign.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assign.id, worker_user=worker_user)

    # Follower should have ZERO notifications
    f_count = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == follower_user.id, Notification.complaint_id == complaint.id)
        .count()
    )
    assert f_count == 0


def test_notification_content_no_pii_no_coordinates_no_remarks(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """Notification titles and bodies must not leak coordinates, user PII, or internal remarks."""
    complaint = create_test_complaint(
        db_session,
        citizen_user,
        category,
        title="Pothole near Park",
        description="Near 12.9716, 77.5946 citizen email secret",
    )
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    notifs = (
        db_session.query(Notification)
        .filter(Notification.complaint_id == complaint.id)
        .all()
    )
    assert len(notifs) > 0
    for n in notifs:
        assert "12.9716" not in n.message
        assert "77.5946" not in n.message
        assert "secret" not in n.message
        assert citizen_user.email not in n.message


def test_actor_exclusion_worker_own_action(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """When a worker submits progress or resolution, they do not receive an echo notification."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)

    progress = add_assignment_progress(
        db=db_session,
        assignment_id=assignment.id,
        worker_user=worker_user,
        description="Laying gravel",
    )

    worker_echo = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == worker_user.id,
            Notification.event_key == f"progress:{progress.id}:owner",
        )
        .first()
    )
    assert worker_echo is None


def test_recipient_deduplication_owner_is_follower(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """If the owner is somehow also registered as a follower, they receive only 1 notification."""
    complaint = create_test_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()

    # Manually add owner as follower
    db_session.add(ComplaintFollower(citizen_id=citizen_user.id, complaint_id=complaint.id))
    db_session.flush()

    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    owner_notifs = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.title.like("%Under Review%"),
        )
        .all()
    )
    assert len(owner_notifs) == 1


# =============================================================================
# 7. Authenticated REST API & IDOR Security Tests
# =============================================================================

def test_api_list_notifications_paginated(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
):
    """GET /api/v1/notifications returns paginated list of user's notifications."""
    # Seed 5 notifications
    for i in range(5):
        create_notification(
            db=db_session,
            recipient_id=citizen_user.id,
            notification_type=NotificationType.STATUS_CHANGE,
            title=f"Notification {i}",
            message=f"Message {i}",
            event_key=f"api:seed:{uuid.uuid4().hex}",
        )

    response = client.get("/api/v1/notifications?page=1&page_size=3", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert len(data["items"]) == 3
    assert data["total"] >= 5
    assert data["page"] == 1
    assert data["page_size"] == 3
    assert data["total_pages"] >= 2


def test_api_list_notifications_unread_only(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
):
    """GET /api/v1/notifications?unread_only=true returns only unread notifications."""
    key1 = f"unread:{uuid.uuid4().hex}"
    key2 = f"read:{uuid.uuid4().hex}"

    create_notification(
        db=db_session,
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Unread",
        message="Unread msg",
        event_key=key1,
    )
    create_notification(
        db=db_session,
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Read",
        message="Read msg",
        event_key=key2,
    )
    # Mark one read
    notif2 = db_session.query(Notification).filter(Notification.event_key == key2).first()
    notif2.is_read = True
    db_session.flush()

    response = client.get("/api/v1/notifications?unread_only=true", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["data"]["items"]
    for item in items:
        assert item["is_read"] is False


def test_api_unread_count(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
):
    """GET /api/v1/notifications/unread-count returns accurate badge count."""
    initial_resp = client.get("/api/v1/notifications/unread-count", headers=citizen_headers)
    initial_count = initial_resp.json()["data"]["unread_count"]

    create_notification(
        db=db_session,
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Count Test",
        message="Count msg",
        event_key=f"count:{uuid.uuid4().hex}",
    )

    new_resp = client.get("/api/v1/notifications/unread-count", headers=citizen_headers)
    assert new_resp.status_code == status.HTTP_200_OK
    assert new_resp.json()["data"]["unread_count"] == initial_count + 1


def test_api_mark_notification_as_read(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
):
    """PATCH /api/v1/notifications/{id}/read marks notification read and sets read_at."""
    create_notification(
        db=db_session,
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="To Read",
        message="Read me",
        event_key=f"markread:{uuid.uuid4().hex}",
    )
    notif = db_session.query(Notification).filter(Notification.recipient_id == citizen_user.id).first()
    assert not notif.is_read

    response = client.patch(f"/api/v1/notifications/{notif.id}/read", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["is_read"] is True
    assert data["read_at"] is not None


def test_api_mark_notification_as_read_idor_defense(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    other_citizen_user: User,
    other_citizen_headers: dict[str, str],
):
    """PATCH /api/v1/notifications/{id}/read for another user's notification returns 404 (IDOR defense)."""
    create_notification(
        db=db_session,
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Owner's Private Notif",
        message="Secret info",
        event_key=f"idor:{uuid.uuid4().hex}",
    )
    notif = db_session.query(Notification).filter(Notification.recipient_id == citizen_user.id).first()

    # other_citizen tries to mark citizen's notification read
    response = client.patch(f"/api/v1/notifications/{notif.id}/read", headers=other_citizen_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_api_mark_notification_as_read_non_existent(
    client: TestClient,
    citizen_headers: dict[str, str],
):
    """PATCH /api/v1/notifications/{random_uuid}/read returns 404."""
    random_id = uuid.uuid4()
    response = client.patch(f"/api/v1/notifications/{random_id}/read", headers=citizen_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_api_mark_all_read(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
):
    """POST /api/v1/notifications/read-all marks all unread notifications read for current user."""
    for i in range(3):
        create_notification(
            db=db_session,
            recipient_id=citizen_user.id,
            notification_type=NotificationType.STATUS_CHANGE,
            title=f"All Read {i}",
            message=f"Msg {i}",
            event_key=f"allread:{uuid.uuid4().hex}",
        )

    response = client.post("/api/v1/notifications/read-all", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["marked_read_count"] >= 3

    # Verify unread count is now 0
    count_resp = client.get("/api/v1/notifications/unread-count", headers=citizen_headers)
    assert count_resp.json()["data"]["unread_count"] == 0


def test_api_route_ordering_no_uuid_collision(
    client: TestClient,
    citizen_headers: dict[str, str],
):
    """Verify fixed routes /unread-count and /read-all are not captured as UUID path parameters."""
    resp1 = client.get("/api/v1/notifications/unread-count", headers=citizen_headers)
    assert resp1.status_code == status.HTTP_200_OK

    resp2 = client.post("/api/v1/notifications/read-all", headers=citizen_headers)
    assert resp2.status_code == status.HTTP_200_OK


def test_api_unauthenticated_forbidden(client: TestClient):
    """Verify unauthenticated requests return 401 Unauthorized."""
    resp_list = client.get("/api/v1/notifications")
    assert resp_list.status_code == status.HTTP_401_UNAUTHORIZED

    resp_count = client.get("/api/v1/notifications/unread-count")
    assert resp_count.status_code == status.HTTP_401_UNAUTHORIZED

    resp_read_all = client.post("/api/v1/notifications/read-all")
    assert resp_read_all.status_code == status.HTTP_401_UNAUTHORIZED

    resp_read = client.patch(f"/api/v1/notifications/{uuid.uuid4()}/read")
    assert resp_read.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Phase 6.4.1: Transaction Integrity, Idempotency & Security Verification Tests
# =============================================================================

def test_transaction_atomicity_complaint_and_notification(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Verify transaction atomicity: creating a complaint persists the initial submission
    notification in the same database transaction.
    """
    complaint = create_test_complaint(
        db_session,
        citizen_user,
        category,
        title="Atomicity Test Complaint",
        description="Testing complaint and notification transactional coupling",
    )

    notifs = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.notification_type == NotificationType.STATUS_CHANGE,
        )
        .all()
    )
    assert len(notifs) >= 1
    assert notifs[-1].complaint_id == complaint.id


def test_transaction_rollback_business_event_reverts_notification(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that rolling back a transaction that performed a business event and
    dispatched a notification reverts both the business entity update and notification row.
    """
    complaint = create_test_complaint(
        db_session,
        citizen_user,
        category,
        title="Rollback Test Complaint",
        description="Testing rollback reverts notification",
    )

    nested = db_session.begin_nested()
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    notifs_pre = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key.like("status:%"),
        )
        .all()
    )
    assert len(notifs_pre) >= 1

    nested.rollback()

    notifs_post = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.complaint_id == complaint.id,
            Notification.event_key.like("status:%"),
        )
        .all()
    )
    assert len(notifs_post) == 0


def test_notification_helper_never_independently_commits(
    db_session: Session,
    citizen_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Verify notification creation and dispatch helpers never independently commit
    the caller's transaction.
    """
    def forbid_commit(*args, **kwargs):
        pytest.fail("commit() was unexpectedly called by a notification dispatch helper!")

    monkeypatch.setattr(db_session, "commit", forbid_commit)

    inserted = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Uncommitted Helper Test",
        message="This must not commit the session",
        event_key=f"uncommitted_helper:{uuid.uuid4().hex}",
    )
    assert inserted == 1


def test_notification_failure_aborts_business_transaction(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that if a notification dispatch fails (e.g. invalid empty event_key),
    it raises a ValueError before commit and the business operation in the savepoint
    can be rolled back completely.
    """
    complaint = create_test_complaint(
        db_session,
        citizen_user,
        category,
        title="Abort Test Complaint",
    )

    nested = db_session.begin_nested()
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    with pytest.raises(ValueError, match="event_key"):
        create_notifications(
            db=db_session,
            recipient_ids=[citizen_user.id],
            notification_type=NotificationType.STATUS_CHANGE,
            title="Failed Notification",
            message="Invalid key",
            event_key="   ",
        )

    nested.rollback()

    db_session.refresh(complaint)
    assert complaint.status == ComplaintStatus.SUBMITTED


def test_concurrent_idempotency_multithreaded_sessions(
    citizen_role: Role,
    test_engine,
):
    """
    Verify concurrent idempotency across multiple independent threads and database sessions:
    Simultaneous creation calls for the same (recipient_id, event_key) insert exactly one row
    without errors, leveraging PostgreSQL's ON CONFLICT DO NOTHING.
    """
    with Session(test_engine) as setup_session:
        user = User(
            email=f"concurrent_user_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Concurrent Test User",
            role_id=citizen_role.id,
            is_active=True,
            is_verified=True,
        )
        setup_session.add(user)
        setup_session.commit()
        committed_user_id = user.id

    shared_event_key = f"concurrent_sla_event:{uuid.uuid4().hex}"

    def worker_thread_task(thread_id: int) -> int:
        with Session(test_engine) as thread_session:
            try:
                count = create_notifications(
                    db=thread_session,
                    recipient_ids=[committed_user_id],
                    notification_type=NotificationType.SLA_WARNING,
                    title=f"Concurrent Notice from Thread {thread_id}",
                    message="Testing concurrent dispatch with identical event key",
                    event_key=shared_event_key,
                )
                thread_session.commit()
                return count
            except Exception:
                thread_session.rollback()
                raise

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(worker_thread_task, range(5)))

        assert len(results) == 5

        with Session(test_engine) as verify_session:
            rows = (
                verify_session.query(Notification)
                .filter(
                    Notification.recipient_id == committed_user_id,
                    Notification.event_key == shared_event_key,
                )
                .all()
            )
            assert len(rows) == 1
            assert rows[0].notification_type == NotificationType.SLA_WARNING
    finally:
        with Session(test_engine) as cleanup_session:
            cleanup_session.query(Notification).filter(
                Notification.recipient_id == committed_user_id
            ).delete()
            cleanup_session.query(User).filter(User.id == committed_user_id).delete()
            cleanup_session.commit()


def test_concurrent_different_recipients_same_event_key(
    db_session: Session,
    citizen_user: User,
    other_citizen_user: User,
):
    """
    Verify that different recipients can independently receive notifications
    sharing the same logical event_key (partial unique index is composite (recipient_id, event_key)).
    """
    shared_key = f"broadcast_event:{uuid.uuid4().hex}"

    count = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id, other_citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Multi-Recipient Event",
        message="Both users should receive this notification",
        event_key=shared_key,
    )
    assert count == 2
    db_session.flush()

    notif1 = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == shared_key,
        )
        .first()
    )
    notif2 = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == other_citizen_user.id,
            Notification.event_key == shared_key,
        )
        .first()
    )
    assert notif1 is not None
    assert notif2 is not None
    assert notif1.recipient_id != notif2.recipient_id
    assert notif1.event_key == notif2.event_key


def test_partial_unique_index_used_by_postgres(db_session: Session, citizen_user: User):
    """
    Verify PostgreSQL catalog metadata and conflict arbiter requirements:
    1. uq_notifications_recipient_event_key exists with predicate WHERE (event_key IS NOT NULL).
    2. ck_notifications_event_key_not_empty check constraint exists.
    3. ON CONFLICT requires the matching partial index predicate.
    """
    idx_row = db_session.execute(
        text(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'notifications'
              AND indexname = 'uq_notifications_recipient_event_key';
            """
        )
    ).fetchone()
    assert idx_row is not None
    assert "event_key IS NOT NULL" in idx_row[1]

    con_row = db_session.execute(
        text(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = CAST('notifications' AS regclass)
              AND conname = 'ck_notifications_event_key_not_empty';
            """
        )
    ).fetchone()
    assert con_row is not None
    assert con_row[0] == "ck_notifications_event_key_not_empty"

    key = f"test_arbiter:{uuid.uuid4().hex}"
    stmt_no_where = text(
        """
        INSERT INTO notifications (id, recipient_id, notification_type, title, message, event_key, is_read, created_at)
        VALUES (:id, :recipient_id, :type, :title, :message, :event_key, false, NOW())
        ON CONFLICT (recipient_id, event_key) DO NOTHING;
        """
    )
    with pytest.raises((IntegrityError, ProgrammingError)) as exc_info:
        with db_session.begin_nested():
            db_session.execute(
                stmt_no_where,
                {
                    "id": uuid.uuid4(),
                    "recipient_id": citizen_user.id,
                    "type": NotificationType.STATUS_CHANGE.value,
                    "title": "Arbiter Test",
                    "message": "Testing arbiter mismatch",
                    "event_key": key,
                },
            )
    assert "42P10" in str(exc_info.value.orig) or "unique or exclusion constraint matching" in str(exc_info.value)


def test_sla_admin_read_without_escalation_generates_zero_notifications(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
    department: Department,
):
    """
    Verify that reading SLA details or evaluating SLA without any persisted level increase
    generates strictly zero duplicate notifications.
    """
    policy = db_session.query(SLAPolicy).filter(
        SLAPolicy.category_id == category.id,
        SLAPolicy.priority == PriorityLevel.MEDIUM,
    ).first()
    if not policy:
        policy = SLAPolicy(
            name=f"Policy_{uuid.uuid4().hex[:6]}",
            category_id=category.id,
            priority=PriorityLevel.MEDIUM,
            response_time_hours=2.0,
            resolution_time_hours=12.0,
            is_active=True,
        )
        db_session.add(policy)
        db_session.flush()

    complaint = create_test_complaint(db_session, citizen_user, category, priority=PriorityLevel.MEDIUM)
    db_session.flush()

    evaluate_complaint_sla(db_session, complaint)
    db_session.flush()

    count_before = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.notification_type.in_([NotificationType.SLA_WARNING, NotificationType.SLA_BREACH]),
        )
        .count()
    )
    assert count_before == 0

    evaluate_complaint_sla(db_session, complaint)
    db_session.flush()

    count_after_eval = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.notification_type.in_([NotificationType.SLA_WARNING, NotificationType.SLA_BREACH]),
        )
        .count()
    )
    assert count_after_eval == count_before

    details = get_complaint_sla_details(db_session, complaint.id, admin_user)
    assert details is not None

    count_after_read = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.notification_type.in_([NotificationType.SLA_WARNING, NotificationType.SLA_BREACH]),
        )
        .count()
    )
    assert count_after_read == count_before


def test_sla_terminated_complaint_receives_zero_resolution_escalations(
    db_session: Session,
    citizen_user: User,
    category: Category,
    admin_user: User,
):
    """
    Verify that terminated complaints (REJECTED or DUPLICATE) do not evaluate resolution SLA
    or dispatch resolution escalation notifications even if elapsed time exceeds the target.
    """
    policy = db_session.query(SLAPolicy).filter(
        SLAPolicy.category_id == category.id,
        SLAPolicy.priority == PriorityLevel.MEDIUM,
    ).first()
    if not policy:
        policy = SLAPolicy(
            name=f"Policy_{uuid.uuid4().hex[:6]}",
            category_id=category.id,
            priority=PriorityLevel.MEDIUM,
            response_time_hours=2.0,
            resolution_time_hours=12.0,
            is_active=True,
        )
        db_session.add(policy)
        db_session.flush()

    complaint = create_test_complaint(db_session, citizen_user, category, priority=PriorityLevel.MEDIUM)
    db_session.flush()

    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.REJECTED,
        remarks="Invalid municipal issue",
        commit=False,
    )
    db_session.flush()

    complaint.created_at = datetime.now(timezone.utc) - timedelta(hours=50)
    db_session.flush()

    evaluate_complaint_sla(db_session, complaint)
    db_session.flush()

    res_notifs = (
        db_session.query(Notification)
        .filter(
            Notification.complaint_id == complaint.id,
            Notification.event_key.like("%:resolution:%"),
        )
        .all()
    )
    assert len(res_notifs) == 0


def test_sla_event_key_structure(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Verify that SLA escalation event keys adhere strictly to the approved specification:
    sla:{complaint_id}:cycle:{sla_cycle_number}:{clock_type}:level:{level}
    """
    policy = db_session.query(SLAPolicy).filter(
        SLAPolicy.category_id == category.id,
        SLAPolicy.priority == PriorityLevel.MEDIUM,
    ).first()
    if not policy:
        policy = SLAPolicy(
            name=f"Policy_{uuid.uuid4().hex[:6]}",
            category_id=category.id,
            priority=PriorityLevel.MEDIUM,
            response_time_hours=2.0,
            resolution_time_hours=12.0,
            is_active=True,
        )
        db_session.add(policy)
        db_session.flush()

    complaint = create_test_complaint(db_session, citizen_user, category, priority=PriorityLevel.MEDIUM)
    db_session.flush()

    complaint.created_at = datetime.now(timezone.utc) - timedelta(hours=1, minutes=45)
    db_session.flush()

    evaluate_complaint_sla(db_session, complaint)
    db_session.flush()

    notif = (
        db_session.query(Notification)
        .filter(
            Notification.complaint_id == complaint.id,
            Notification.notification_type == NotificationType.SLA_WARNING,
        )
        .first()
    )
    assert notif is not None
    expected_key = f"sla:{complaint.id}:cycle:{complaint.sla_cycle_number}:response:level:1"
    assert notif.event_key == expected_key


def test_reassignment_old_worker_receives_only_reassignment_notification(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    other_worker_user: User,
    category: Category,
):
    """
    Verify worker lifecycle notification boundaries on reassignment:
    - Initial worker receives ASSIGNMENT notification on dispatch.
    - Upon reassignment, initial worker receives ASSIGNMENT notification for reassignment.
    - Replacement worker receives ASSIGNMENT notification on dispatch.
    - Subsequent progress updates notify owner and followers, but NOT the initial worker.
    """
    complaint = create_test_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    worker_profile1 = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    worker_profile2 = db_session.query(Worker).filter(Worker.user_id == other_worker_user.id).first()

    # 1. Assign to worker 1
    assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile1.id,
        admin_user=admin_user,
    )
    db_session.flush()

    worker1_notifs_1 = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == worker_user.id, Notification.complaint_id == complaint.id)
        .all()
    )
    assert len(worker1_notifs_1) == 1
    assert worker1_notifs_1[0].notification_type == NotificationType.ASSIGNMENT

    # 2. Reassign to worker 2
    new_assignment, _ = reassign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        new_worker_id=worker_profile2.id,
        admin_user=admin_user,
        reason="Workload rebalancing",
    )
    db_session.flush()

    worker1_notifs_2 = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == worker_user.id, Notification.complaint_id == complaint.id)
        .all()
    )
    assert len(worker1_notifs_2) == 2
    assert "reassigned" in worker1_notifs_2[1].event_key

    worker2_notifs_1 = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == other_worker_user.id, Notification.complaint_id == complaint.id)
        .all()
    )
    assert len(worker2_notifs_1) == 1
    assert worker2_notifs_1[0].notification_type == NotificationType.ASSIGNMENT

    # 3. Worker 2 accepts, starts, and adds progress
    accept_assignment(db=db_session, assignment_id=new_assignment.id, worker_user=other_worker_user)
    start_assignment(db=db_session, assignment_id=new_assignment.id, worker_user=other_worker_user)
    add_assignment_progress(
        db=db_session,
        assignment_id=new_assignment.id,
        worker_user=other_worker_user,
        description="Repairs half completed",
    )
    db_session.flush()

    # Initial worker must still have exactly 2 notifications (no progress notifications)
    worker1_notifs_3 = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == worker_user.id, Notification.complaint_id == complaint.id)
        .all()
    )
    assert len(worker1_notifs_3) == 2


def test_notification_payload_redaction_comprehensive(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    follower_user: User,
    category: Category,
):
    """
    Verify complete privacy redaction in notification payloads:
    Notification titles and messages delivered to public followers never contain:
    - GPS coordinates (latitude / longitude)
    - Private street address
    - Citizen identity, email, or contact information
    - Internal admin remarks or dispatch notes
    - Internal worker progress notes
    """
    secret_address = "42 Classified Underground Bunker Lane"

    complaint = create_test_complaint(
        db_session,
        citizen_user,
        category,
        title="Secret Infrastructure Flaw",
        description="Private description with sensitive context",
    )
    complaint.location.address = secret_address
    complaint.location.latitude = 12.987654
    complaint.location.longitude = 77.654321
    db_session.flush()

    # Set public
    complaint.is_public = True
    db_session.flush()

    # Follower follows
    follow_complaint(db=db_session, complaint_id=complaint.id, citizen_user=follower_user)
    db_session.flush()

    # Admin reviews
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        remarks="CONFIDENTIAL INTERNAL NOTE: Escalated by mayor's office",
        commit=False,
    )

    worker_profile = db_session.query(Worker).filter(Worker.user_id == worker_user.id).first()
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        admin_user=admin_user,
    )
    db_session.flush()

    accept_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=assignment.id, worker_user=worker_user)
    add_assignment_progress(
        db=db_session,
        assignment_id=assignment.id,
        worker_user=worker_user,
        description="INTERNAL REMARK: Specialized parts installed",
    )
    db_session.flush()

    follower_notifs = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == follower_user.id,
            Notification.complaint_id == complaint.id,
        )
        .all()
    )
    assert len(follower_notifs) > 0

    for notif in follower_notifs:
        full_text = f"{notif.title} {notif.message}"
        assert secret_address not in full_text
        assert "12.987654" not in full_text
        assert "77.654321" not in full_text
        assert citizen_user.email not in full_text
        assert "CONFIDENTIAL" not in full_text
        assert "INTERNAL REMARK" not in full_text
        assert "Specialized parts installed" not in full_text


def test_api_cross_user_isolation(
    client: TestClient,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_user: User,
    other_citizen_headers: dict[str, str],
    db_session: Session,
):
    """
    Verify cross-user notification isolation via REST API:
    - Citizen A cannot see Citizen B's notifications in GET /api/v1/notifications.
    - Citizen A attempting to mark Citizen B's notification read receives 404 EntityNotFoundError (IDOR defense).
    """
    notif_b = Notification(
        recipient_id=other_citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Notice for Citizen B",
        message="Confidential message for Citizen B",
        event_key=f"isolation_b:{uuid.uuid4().hex}",
    )
    db_session.add(notif_b)
    db_session.flush()

    resp = client.get("/api/v1/notifications", headers=citizen_headers)
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()["data"]["items"]
    b_ids = [item["id"] for item in items]
    assert str(notif_b.id) not in b_ids

    patch_resp = client.patch(f"/api/v1/notifications/{notif_b.id}/read", headers=citizen_headers)
    assert patch_resp.status_code == status.HTTP_404_NOT_FOUND


def test_api_mark_read_idempotent(
    client: TestClient,
    citizen_user: User,
    citizen_headers: dict[str, str],
    db_session: Session,
):
    """
    Verify marking an already read notification as read is idempotent:
    Returns HTTP 200 and preserves the original read_at timestamp.
    """
    notif = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Idempotent Read Test",
        message="Testing read timestamp preservation",
        event_key=f"idempotent_read:{uuid.uuid4().hex}",
    )
    db_session.add(notif)
    db_session.flush()

    resp1 = client.patch(f"/api/v1/notifications/{notif.id}/read", headers=citizen_headers)
    assert resp1.status_code == status.HTTP_200_OK
    first_read_at = resp1.json()["data"]["read_at"]
    assert first_read_at is not None

    resp2 = client.patch(f"/api/v1/notifications/{notif.id}/read", headers=citizen_headers)
    assert resp2.status_code == status.HTTP_200_OK
    second_read_at = resp2.json()["data"]["read_at"]
    assert second_read_at == first_read_at


def test_api_mark_all_read_isolation(
    client: TestClient,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_user: User,
    other_citizen_headers: dict[str, str],
    db_session: Session,
):
    """
    Verify POST /api/v1/notifications/read-all scopes strictly to the authenticated user:
    Citizen A marking all read leaves Citizen B's unread notifications untouched.
    """
    notif_a = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Unread A",
        message="Msg A",
        event_key=f"read_all_a:{uuid.uuid4().hex}",
    )
    notif_b = Notification(
        recipient_id=other_citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Unread B",
        message="Msg B",
        event_key=f"read_all_b:{uuid.uuid4().hex}",
    )
    db_session.add(notif_a)
    db_session.add(notif_b)
    db_session.flush()

    resp_a = client.post("/api/v1/notifications/read-all", headers=citizen_headers)
    assert resp_a.status_code == status.HTTP_200_OK

    count_a = client.get("/api/v1/notifications/unread-count", headers=citizen_headers)
    assert count_a.json()["data"]["unread_count"] == 0

    count_b = client.get("/api/v1/notifications/unread-count", headers=other_citizen_headers)
    assert count_b.json()["data"]["unread_count"] >= 1

    db_session.refresh(notif_b)
    assert notif_b.is_read is False
    assert notif_b.read_at is None


def test_api_idor_cross_role_access(
    client: TestClient,
    citizen_user: User,
    citizen_headers: dict[str, str],
    worker_user: User,
    worker_headers: dict[str, str],
    admin_user: User,
    admin_headers: dict[str, str],
    db_session: Session,
):
    """
    Verify cross-role IDOR defense:
    - Worker cannot read citizen's notification (404).
    - Citizen cannot read worker's notification (404).
    - Admin cannot modify citizen's notification via user endpoint (404).
    """
    notif_citizen = Notification(
        recipient_id=citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Citizen Notification",
        message="For citizen eyes only",
        event_key=f"idor_cit:{uuid.uuid4().hex}",
    )
    notif_worker = Notification(
        recipient_id=worker_user.id,
        notification_type=NotificationType.ASSIGNMENT,
        title="Worker Notification",
        message="For worker eyes only",
        event_key=f"idor_wrk:{uuid.uuid4().hex}",
    )
    db_session.add(notif_citizen)
    db_session.add(notif_worker)
    db_session.flush()

    resp1 = client.patch(f"/api/v1/notifications/{notif_citizen.id}/read", headers=worker_headers)
    assert resp1.status_code == status.HTTP_404_NOT_FOUND

    resp2 = client.patch(f"/api/v1/notifications/{notif_worker.id}/read", headers=citizen_headers)
    assert resp2.status_code == status.HTTP_404_NOT_FOUND

    resp3 = client.patch(f"/api/v1/notifications/{notif_citizen.id}/read", headers=admin_headers)
    assert resp3.status_code == status.HTTP_404_NOT_FOUND

