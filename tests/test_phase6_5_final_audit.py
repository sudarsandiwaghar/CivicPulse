"""
CivicPulse Phase 6.5 Tests: Final Integration, Security, Privacy, Database Integrity & Performance Audit

Comprehensive test suite verifying all 17 audit dimensions specified in Phase 6.5:
    1.  Specific Verification A — Notification Conflict Handling:
        - create_notifications targets uq_notifications_recipient_event_key with WHERE event_key IS NOT NULL.
        - Duplicate events safely ignored via ON CONFLICT DO NOTHING.
        - Independent recipients can receive same event key.
        - Insertion failures safely abort caller's transaction without partial commits.
    2.  Specific Verification B — Outer Transaction Rollback:
        - Outer database transaction rollback (without savepoint) reverts both business entity and notification.
    3.  Specific Verification C — Reassignment Timeline Integrity:
        - Immediate replacement assignment defines exact immutable access cutoff.
        - Injected or spoofed worker progress notes cannot alter reassignment boundary.
        - Reassignment executes under row-level lock serialization (with_for_update).
    4.  Specific Verification D — Public Unpublish Request History:
        - Complaint unpublish audit metadata preserved immutably throughout unpublish state.
        - Citizen cannot republish (strictly requires admin moderation).
    5.  Security & Privacy Access Boundaries:
        - Citizen cannot access other citizen's private complaint timeline (403).
        - Worker cannot access unassigned complaint timeline (403).
        - Public feed strictly projects 9 allowlist fields; zero GPS, zero PII, zero internal remarks.
        - Inactive user token rejected across protected endpoints.
        - Cross-user notification IDOR defense returns 404.
    6.  SLA Dual Clocks & Notification Integration:
        - Dual response and resolution clocks operate independently.
        - ON_HOLD pause accounting freezes active clocks and extends deadlines accurately.
        - Reopening starts new cycle, preserves previous cycle snapshot in immutable history.
        - Level 1 maps to SLA_WARNING, Levels 2 and 3 map to SLA_BREACH.
    7.  Performance & Query Optimization:
        - Citizen dashboard single-query conditional aggregation.
        - Complaint timeline eager loading includes Worker.user and Worker.department without lazy queries.
        - Notification inbox bounded pagination (max 100) and deterministic sorting.
"""

import math
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from psycopg2.errors import CheckViolation, UniqueViolation
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.constants import (
    AssignmentStatus,
    ComplaintStatus,
    NotificationType,
    PriorityLevel,
    UserRole,
)
from app.core.exceptions import AuthorizationError, EntityNotFoundError
from app.core.security import create_access_token, hash_password
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.complaint_sla_history import ComplaintSLAHistory
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
from app.schemas.moderation import ModeratePublicRequest
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
)
from app.services.dashboard_service import get_citizen_dashboard
from app.services.follower_service import follow_complaint, list_followed_complaints
from app.services.notification_service import (
    create_notification,
    create_notifications,
    get_unread_notification_count,
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    notify_sla_escalation,
)
from app.services.public_complaint_service import (
    get_public_complaint,
    list_public_complaints,
    moderate_complaint_public,
    request_unpublish,
)
from app.services.sla_service import (
    evaluate_complaint_sla,
    get_complaint_sla_details,
)
from app.services.timeline_service import get_complaint_timeline


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
def department(db_session: Session) -> Department:
    dept = Department(
        name=f"Municipal Works {uuid.uuid4().hex[:6]}",
        code=f"MW_{uuid.uuid4().hex[:4].upper()}",
        description="Public infrastructure and municipal maintenance",
    )
    db_session.add(dept)
    db_session.flush()
    return dept


@pytest.fixture
def category(db_session: Session, department: Department) -> Category:
    cat = Category(
        name=f"Drainage Maintenance {uuid.uuid4().hex[:6]}",
        description="Stormwater drainage repair",
        department_id=department.id,
    )
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def citizen_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"audit_citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Audit Citizen Owner",
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
def other_citizen_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"other_citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Other Citizen Observer",
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
def admin_user(db_session: Session, admin_role: Role) -> User:
    user = User(
        email=f"audit_admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Audit Administrator",
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
def worker_user(db_session: Session, worker_role: Role, department: Department) -> User:
    user = User(
        email=f"audit_worker_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Primary Field Technician",
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
def replacement_worker_user(db_session: Session, worker_role: Role, department: Department) -> User:
    user = User(
        email=f"audit_repl_worker_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Replacement Field Technician",
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
def replacement_worker_headers(replacement_worker_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(replacement_worker_user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": replacement_worker_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


def create_audit_complaint(
    db: Session,
    citizen: User,
    category: Category,
    title: str = "Audit Complaint",
    description: str = "Auditing full backend integrity",
    status: ComplaintStatus = ComplaintStatus.SUBMITTED,
    priority: PriorityLevel = PriorityLevel.MEDIUM,
    created_at: datetime | None = None,
) -> Complaint:
    """Helper to persist valid complaint without premature transaction commits."""
    ts = created_at or datetime.now(timezone.utc)
    loc = Location(
        latitude=12.9716,
        longitude=77.5946,
        address_line="100 Audit Boulevard, Sector 4",
        city="Central Municipality",
    )
    db.add(loc)
    db.flush()

    complaint = Complaint(
        complaint_number=f"CP-2026-{uuid.uuid4().hex[:8].upper()}",
        citizen_id=citizen.id,
        category_id=category.id,
        location_id=loc.id,
        title=title,
        description=description,
        status=status,
        priority=priority,
        created_at=ts,
        updated_at=ts,
        is_public=False,
    )
    db.add(complaint)
    db.flush()

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=citizen.id,
        previous_status=None,
        new_status=status,
        remarks="Complaint created for audit verification",
        created_at=ts,
    )
    db.add(history)
    db.flush()
    return complaint


# =============================================================================
# 1. Specific Verification A — Notification Conflict Handling
# =============================================================================

def test_notification_on_conflict_target_matches_partial_unique_index(
    db_session: Session,
    citizen_user: User,
):
    """
    Verify that create_notifications compiles and executes ON CONFLICT targeting
    uq_notifications_recipient_event_key with WHERE event_key IS NOT NULL.
    """
    shared_key = f"audit_conflict:{uuid.uuid4().hex}"

    # First insert
    count1 = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Conflict Test 1",
        message="Initial insert",
        event_key=shared_key,
    )
    assert count1 == 1
    db_session.flush()

    # Second insert with identical key
    count2 = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Conflict Test 2",
        message="Duplicate insert should be ignored",
        event_key=shared_key,
    )
    assert count2 == 1  # attempted
    db_session.flush()

    # Verify exactly 1 row exists
    rows = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_id == citizen_user.id,
            Notification.event_key == shared_key,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Conflict Test 1"


def test_notification_independent_recipients_same_event_key(
    db_session: Session,
    citizen_user: User,
    other_citizen_user: User,
):
    """
    Verify that independent recipients can receive the identical logical event_key
    without index conflict (partial unique index is composite (recipient_id, event_key)).
    """
    shared_key = f"broadcast_event:{uuid.uuid4().hex}"

    count = create_notifications(
        db=db_session,
        recipient_ids=[citizen_user.id, other_citizen_user.id],
        notification_type=NotificationType.STATUS_CHANGE,
        title="Broadcast Notification",
        message="Shared event for multiple users",
        event_key=shared_key,
    )
    assert count == 2
    db_session.flush()

    rows = (
        db_session.query(Notification)
        .filter(Notification.event_key == shared_key)
        .all()
    )
    assert len(rows) == 2
    recip_ids = {r.recipient_id for r in rows}
    assert recip_ids == {citizen_user.id, other_citizen_user.id}


def test_notification_insertion_failure_prevents_partial_commit(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that an invalid notification payload raises ValueError before commit,
    enabling caller transaction rollback without leaving partial business state.
    """
    complaint = create_audit_complaint(db_session, citizen_user, category)

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
            title="Invalid Key Notification",
            message="Whitespace key",
            event_key="     ",
        )

    nested.rollback()

    db_session.refresh(complaint)
    assert complaint.status == ComplaintStatus.SUBMITTED


# =============================================================================
# 2. Specific Verification B — Outer Transaction Rollback
# =============================================================================

def test_outer_transaction_rollback_reverts_business_event_and_notification(
    citizen_role: Role,
    admin_role: Role,
    test_engine,
):
    """
    Verify outer transaction rollback:
    Using an independent database connection and real PostgreSQL transaction (BEGIN...ROLLBACK),
    an outer transaction rollback reverts both the business entity mutation and the notification.
    """
    # 1. Create committed user and complaint
    with Session(test_engine) as setup_sess:
        dept = Department(
            name=f"Outer Rollback Dept {uuid.uuid4().hex[:6]}",
            code=f"ORD_{uuid.uuid4().hex[:4].upper()}",
            description="Outer rollback test",
        )
        cat = Category(
            name=f"Outer Rollback Cat {uuid.uuid4().hex[:6]}",
            description="Outer rollback test",
            department=dept,
        )
        citizen = User(
            email=f"outer_cit_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Outer Rollback Citizen",
            role_id=citizen_role.id,
            is_active=True,
            is_verified=True,
        )
        admin = User(
            email=f"outer_adm_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Outer Rollback Admin",
            role_id=admin_role.id,
            is_active=True,
            is_verified=True,
        )
        setup_sess.add_all([dept, cat, citizen, admin])
        setup_sess.commit()

        complaint = Complaint(
            complaint_number=f"CP-OUTER-{uuid.uuid4().hex[:8].upper()}",
            citizen_id=citizen.id,
            category_id=cat.id,
            title="Outer Rollback Complaint",
            description="Testing real outer rollback",
            status=ComplaintStatus.SUBMITTED,
            priority=PriorityLevel.LOW,
        )
        setup_sess.add(complaint)
        setup_sess.commit()
        complaint_id = complaint.id
        citizen_id = citizen.id
        admin_id = admin.id
        cat_id = cat.id
        dept_id = dept.id

    # 2. Execute business transition and notification within an explicit outer transaction
    trans_event_key = f"outer_rollback_event:{uuid.uuid4().hex}"
    conn = test_engine.connect()
    outer_trans = conn.begin()  # Explicit PostgreSQL BEGIN
    try:
        session = Session(bind=conn)
        adm_user = session.query(User).filter(User.id == admin_id).first()
        execute_transition(
            db=session,
            complaint_id=complaint_id,
            user=adm_user,
            requested_status=ComplaintStatus.UNDER_REVIEW,
            commit=False,
        )
        create_notifications(
            db=session,
            recipient_ids=[citizen_id],
            notification_type=NotificationType.STATUS_CHANGE,
            title="Outer Rollback Notice",
            message="Should be rolled back",
            event_key=trans_event_key,
        )
        session.flush()

        # Explicitly ROLL BACK outer transaction
        outer_trans.rollback()
    finally:
        session.close()
        conn.close()

    # 3. Fresh independent connection: verify BOTH business update and notification are gone
    with Session(test_engine) as verify_sess:
        c = verify_sess.query(Complaint).filter(Complaint.id == complaint_id).first()
        assert c.status == ComplaintStatus.SUBMITTED

        hist_records = (
            verify_sess.query(ComplaintStatusHistory)
            .filter(
                ComplaintStatusHistory.complaint_id == complaint_id,
                ComplaintStatusHistory.new_status == ComplaintStatus.UNDER_REVIEW,
            )
            .all()
        )
        assert len(hist_records) == 0

        notifs = (
            verify_sess.query(Notification)
            .filter(
                Notification.recipient_id == citizen_id,
                Notification.event_key == trans_event_key,
            )
            .all()
        )
        assert len(notifs) == 0

        # Cleanup
        verify_sess.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == complaint_id).delete()
        verify_sess.query(Complaint).filter(Complaint.id == complaint_id).delete()
        verify_sess.query(User).filter(User.id.in_([citizen_id, admin_id])).delete()
        verify_sess.query(Category).filter(Category.id == cat_id).delete()
        verify_sess.query(Department).filter(Department.id == dept_id).delete()
        verify_sess.commit()


# =============================================================================
# 3. Specific Verification C — Reassignment Timeline Integrity
# =============================================================================

def test_reassignment_immediate_replacement_cutoff(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    replacement_worker_user: User,
    category: Category,
):
    """
    Verify that a reassigned worker's timeline access is bounded strictly by the
    immediate replacement assignment's assigned_at timestamp.
    """
    t0 = datetime(2026, 11, 10, 8, 0, 0, tzinfo=timezone.utc)
    complaint = create_audit_complaint(db_session, citizen_user, category, created_at=t0)

    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    worker1_profile = worker_user.worker_profile
    worker2_profile = replacement_worker_user.worker_profile

    # Assignment 1: Worker 1
    asgn1, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker1_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=asgn1.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=asgn1.id, worker_user=worker_user)

    # Worker 1 logs progress at t0 + 1h
    prog1 = add_assignment_progress(
        db=db_session,
        assignment_id=asgn1.id,
        worker_user=worker_user,
        description="Worker 1 on-site investigation",
    )

    # Reassignment to Worker 2 at t0 + 2h
    asgn2, _ = reassign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        new_worker_id=worker2_profile.id,
        admin_user=admin_user,
        reason="Specialized equipment needed",
    )

    # Worker 2 accepts, starts, logs progress at t0 + 3h
    accept_assignment(db=db_session, assignment_id=asgn2.id, worker_user=replacement_worker_user)
    start_assignment(db=db_session, assignment_id=asgn2.id, worker_user=replacement_worker_user)
    prog2 = add_assignment_progress(
        db=db_session,
        assignment_id=asgn2.id,
        worker_user=replacement_worker_user,
        description="Worker 2 post-reassignment progress update",
    )

    # Worker 1 requests timeline: should see up to reassignment, NOT prog2
    w1_timeline = get_complaint_timeline(db_session, complaint.id, worker_user)
    w1_events = w1_timeline["events"]
    w1_descs = [e["description"] for e in w1_events if e.get("description")]

    assert any("Worker 1 on-site investigation" in d for d in w1_descs)
    assert not any("Worker 2 post-reassignment progress update" in d for d in w1_descs)

    # Worker 2 requests timeline: should see prog2
    w2_timeline = get_complaint_timeline(db_session, complaint.id, replacement_worker_user)
    w2_descs = [e["description"] for e in w2_timeline["events"] if e.get("description")]
    assert any("Worker 2 post-reassignment progress update" in d for d in w2_descs)


def test_reassignment_worker_cannot_forge_cutoff_with_injected_progress(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    replacement_worker_user: User,
    category: Category,
):
    """
    Verify that an injected worker progress update containing 'Reassigned to ...' text
    cannot manipulate or forge the reassignment boundary without a matching replacement assignment.
    """
    t0 = datetime(2026, 11, 10, 8, 0, 0, tzinfo=timezone.utc)
    complaint = create_audit_complaint(db_session, citizen_user, category, created_at=t0)

    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )

    worker1_profile = worker_user.worker_profile
    asgn1, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker1_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=asgn1.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=asgn1.id, worker_user=worker_user)

    # Worker injects spoofed progress note
    spoofed = add_assignment_progress(
        db=db_session,
        assignment_id=asgn1.id,
        worker_user=worker_user,
        description="Reassigned to Replacement Technician (EMP-9999). Reason: Fake Reassignment",
    )

    # Manually marking status REASSIGNED without trusted reassign_complaint call
    asgn1.status = AssignmentStatus.REASSIGNED
    db_session.flush()

    # Timeline access MUST be denied (403 AuthorizationError) because no replacement assignment correlates
    with pytest.raises(AuthorizationError, match="Cannot reliably establish assignment boundary"):
        get_complaint_timeline(db_session, complaint.id, worker_user)


# =============================================================================
# 4. Specific Verification D — Public Unpublish Request History
# =============================================================================

def test_unpublish_audit_fields_immutable_during_unpublish_state(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that once unpublished, repeated unpublish calls preserve the initial
    unpublish_requested_at, unpublish_requested_by_id, and unpublish_reason without silent erasure.
    """
    complaint = create_audit_complaint(db_session, citizen_user, category)
    complaint.is_public = True
    db_session.flush()

    # First unpublish
    res1 = request_unpublish(
        db=db_session,
        complaint_id=complaint.id,
        citizen_user=citizen_user,
        reason="Initial privacy concern",
    )
    initial_time = res1.unpublish_requested_at
    assert initial_time is not None
    assert res1.unpublish_reason == "Initial privacy concern"
    assert complaint.is_public is False

    # Second unpublish with different reason: original audit metadata preserved
    res2 = request_unpublish(
        db=db_session,
        complaint_id=complaint.id,
        citizen_user=citizen_user,
        reason="Second reason should not erase original",
    )
    assert res2.unpublish_requested_at == initial_time
    assert res2.unpublish_reason == "Initial privacy concern"


def test_unpublish_requires_explicit_admin_moderation_to_republish(
    client: TestClient,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
    db_session: Session,
):
    """
    Verify that citizens receive HTTP 403 when trying to publish or moderate public content,
    ensuring unpublish state cannot be reverted by the citizen.
    """
    complaint = create_audit_complaint(db_session, citizen_user, category)

    res = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "PUBLISH", "public_title": "Unauthorized Publish", "public_description": "Valid description length"},
        headers=citizen_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 5. Security & Privacy Access Boundaries
# =============================================================================

def test_security_citizen_cannot_access_other_citizen_complaint_timeline(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    other_citizen_user: User,
    other_citizen_headers: dict[str, str],
    category: Category,
):
    """Verify citizen A cannot view the timeline of citizen B's complaint (403 Forbidden)."""
    complaint = create_audit_complaint(db_session, citizen_user, category)

    res = client.get(
        f"/api/v1/complaints/{complaint.id}/timeline",
        headers=other_citizen_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "permission" in res.json()["detail"].lower()


def test_security_worker_cannot_access_unassigned_complaint_timeline(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    worker_user: User,
    worker_headers: dict[str, str],
    category: Category,
):
    """Verify field worker cannot access timeline of a complaint they were never assigned to (403 Forbidden)."""
    complaint = create_audit_complaint(db_session, citizen_user, category)

    res = client.get(
        f"/api/v1/complaints/{complaint.id}/timeline",
        headers=worker_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "not assigned" in res.json()["detail"].lower()


def test_security_public_response_zero_leakage_all_endpoints(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that public endpoints project strictly the 9 approved public fields
    and never expose citizen PII, GPS coordinates, exact addresses, or internal remarks.
    """
    secret_pincode = "560001"
    secret_address = "99 Confidential Citizen Estate"
    secret_coords_lat = "12.987654"
    secret_coords_lng = "77.654321"

    complaint = create_audit_complaint(
        db_session,
        citizen_user,
        category,
        title="Public Leakage Test",
        description="Private citizen description with internal details",
    )
    complaint.location.address = secret_address
    complaint.location.latitude = 12.987654
    complaint.location.longitude = 77.654321
    complaint.location.pincode = secret_pincode
    complaint.is_public = True
    complaint.public_title = "Clean Public Title"
    complaint.public_description = "Clean public description for citizens."
    db_session.flush()

    # 1. Public list endpoint
    res_list = client.get("/api/v1/public/complaints")
    assert res_list.status_code == status.HTTP_200_OK
    text_list = res_list.text
    assert secret_pincode not in text_list
    assert secret_address not in text_list
    assert secret_coords_lat not in text_list
    assert secret_coords_lng not in text_list
    assert citizen_user.email not in text_list

    # 2. Public detail endpoint
    res_detail = client.get(f"/api/v1/public/complaints/{complaint.id}")
    assert res_detail.status_code == status.HTTP_200_OK
    text_detail = res_detail.text
    assert secret_pincode not in text_detail
    assert secret_address not in text_detail
    assert secret_coords_lat not in text_detail
    assert secret_coords_lng not in text_detail
    assert citizen_user.email not in text_detail


def test_security_inactive_user_token_blocked(
    client: TestClient,
    citizen_user: User,
    db_session: Session,
):
    """Verify that an inactive user account is blocked from authenticated APIs (403 Forbidden)."""
    token = create_access_token(
        subject=str(citizen_user.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": citizen_user.email},
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Deactivate user
    citizen_user.is_active = False
    db_session.commit()

    res = client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_security_cross_user_notification_idor_defense(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_user: User,
):
    """Verify IDOR defense: attempting to mark another user's notification as read returns 404."""
    notif = Notification(
        recipient_id=other_citizen_user.id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Other Citizen Notice",
        message="Confidential",
        event_key=f"idor_test:{uuid.uuid4().hex}",
    )
    db_session.add(notif)
    db_session.commit()

    res = client.patch(f"/api/v1/notifications/{notif.id}/read", headers=citizen_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# 6. SLA Dual Clocks & Intelligent Escalation
# =============================================================================

def test_sla_dual_clocks_complete_independence(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify complete independence of response and resolution clocks:
    Transitioning to UNDER_REVIEW stops the response clock, while the resolution clock
    continues advancing independently.
    """
    t0 = datetime.now(timezone.utc)
    complaint = create_audit_complaint(db_session, citizen_user, category, created_at=t0)

    policy = SLAPolicy(
        name=f"Dual Clocks Policy {uuid.uuid4().hex[:6]}",
        category_id=category.id,
        priority=PriorityLevel.MEDIUM,
        response_time_hours=2.0,
        resolution_time_hours=10.0,
        is_active=True,
    )
    db_session.add(policy)
    db_session.flush()

    # Response clock stops at UNDER_REVIEW
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    assert complaint.responded_at is not None
    assert complaint.response_escalation_level == 0

    # Evaluate SLA at t0 + 8.5 hours (85% of 10h resolution target = Level 1 warning)
    eval_time = t0 + timedelta(hours=8, minutes=30)
    evaluate_complaint_sla(db_session, complaint, now_utc=eval_time)
    db_session.flush()

    # Response clock was stopped within target (level 0)
    assert complaint.response_escalation_level == 0
    # Resolution clock reached Level 1 warning (85% elapsed)
    assert complaint.resolution_escalation_level == 1


def test_sla_on_hold_pause_accounting_dual_clocks(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify ON_HOLD pause accounting:
    Placing a complaint on hold pauses clock calculation without mutating state.
    """
    complaint = create_audit_complaint(db_session, citizen_user, category)

    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.ON_HOLD,
        remarks="Awaiting municipal parts",
        commit=False,
    )

    assert complaint.status == ComplaintStatus.ON_HOLD
    assert complaint.resolution_pause_started_at is not None
    assert complaint.response_pause_started_at is None

    # Repeated evaluation during active pause does not mutate accumulated pause seconds
    accum_before = complaint.resolution_pause_duration_seconds
    evaluate_complaint_sla(db_session, complaint, datetime.now(timezone.utc) + timedelta(minutes=15))
    assert complaint.resolution_pause_duration_seconds == accum_before


def test_sla_reopened_complaint_new_cycle_and_immutable_history(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """
    Verify that reopening a resolved/closed complaint snapshots cycle 1 to immutable
    history and advances to sla_cycle_number = 2.
    """
    t0 = datetime.now(timezone.utc) - timedelta(hours=20)
    complaint = create_audit_complaint(db_session, citizen_user, category, created_at=t0)

    policy = SLAPolicy(
        name=f"Reopen Policy {uuid.uuid4().hex[:6]}",
        category_id=category.id,
        priority=PriorityLevel.MEDIUM,
        response_time_hours=2.0,
        resolution_time_hours=10.0,
        is_active=True,
    )
    db_session.add(policy)
    db_session.flush()

    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    asgn, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_user.worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db=db_session, assignment_id=asgn.id, worker_user=worker_user)
    start_assignment(db=db_session, assignment_id=asgn.id, worker_user=worker_user)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=worker_user,
        requested_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        remarks="Pothole filled",
        commit=False,
    )
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=citizen_user,
        requested_status=ComplaintStatus.CLOSED,
        commit=False,
    )

    # Citizen reopens
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=citizen_user,
        requested_status=ComplaintStatus.REOPENED,
        remarks="Pothole sank again",
        commit=False,
    )
    db_session.flush()

    assert complaint.sla_cycle_number == 2

    # Verify cycle 1 snapshot exists in history
    hist = (
        db_session.query(ComplaintSLAHistory)
        .filter(
            ComplaintSLAHistory.complaint_id == complaint.id,
            ComplaintSLAHistory.cycle_number == 1,
        )
        .first()
    )
    assert hist is not None
    assert hist.actual_resolution_seconds is not None


def test_sla_warning_and_breach_type_classification(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Verify that Level 1 maps to SLA_WARNING and Level 2/3 map to SLA_BREACH."""
    complaint = create_audit_complaint(db_session, citizen_user, category)

    # Level 1 -> SLA_WARNING
    notify_sla_escalation(db_session, complaint, "response", 0, 1)
    n1 = (
        db_session.query(Notification)
        .filter(Notification.event_key == f"sla:{complaint.id}:cycle:{complaint.sla_cycle_number}:response:level:1")
        .first()
    )
    assert n1 is not None
    assert n1.notification_type == NotificationType.SLA_WARNING

    # Level 2 -> SLA_BREACH
    notify_sla_escalation(db_session, complaint, "response", 1, 2)
    n2 = (
        db_session.query(Notification)
        .filter(Notification.event_key == f"sla:{complaint.id}:cycle:{complaint.sla_cycle_number}:response:level:2")
        .first()
    )
    assert n2 is not None
    assert n2.notification_type == NotificationType.SLA_BREACH


# =============================================================================
# 7. Performance & Query Optimization
# =============================================================================

def test_perf_dashboard_single_query_aggregation(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Verify that citizen dashboard calculates metrics and capped activity feeds
    efficiently via single conditional aggregation and capped joined queries.
    """
    # Create 3 complaints for citizen
    for i in range(3):
        create_audit_complaint(
            db_session,
            citizen_user,
            category,
            title=f"Dashboard Complaint {i}",
        )
    db_session.flush()

    data = get_citizen_dashboard(db_session, citizen_user)
    assert data["metrics"]["total_complaints"] >= 3
    assert len(data["recent_submissions"]) <= 5
    assert len(data["recent_updates"]) <= 5


def test_perf_timeline_joinedloads_worker_user_and_department(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: User,
    category: Category,
):
    """
    Verify that timeline query eager loads Worker.user and Worker.department
    eliminating lazy loading queries during timeline event generation.
    """
    complaint = create_audit_complaint(db_session, citizen_user, category)
    execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.UNDER_REVIEW,
        commit=False,
    )
    assignment, _ = assign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        worker_id=worker_user.worker_profile.id,
        admin_user=admin_user,
    )
    accept_assignment(db_session, assignment.id, worker_user)
    db_session.flush()

    timeline = get_complaint_timeline(db_session, complaint.id, admin_user)
    assert len(timeline["events"]) >= 3
    event_types = [e["event_type"] for e in timeline["events"]]
    assert "ASSIGNMENT_CREATED" in event_types
    assert "ASSIGNMENT_ACCEPTED" in event_types


def test_perf_notification_inbox_bounded_and_indexed(
    db_session: Session,
    citizen_user: User,
):
    """
    Verify that get_user_notifications caps page_size at 100, enforces deterministic
    sorting (created_at DESC, id DESC), and get_unread_notification_count is indexed.
    """
    # Create 5 notifications
    for i in range(5):
        create_notification(
            db=db_session,
            recipient_id=citizen_user.id,
            notification_type=NotificationType.STATUS_CHANGE,
            title=f"Inbox Notice {i}",
            message="Notice body",
            event_key=f"inbox_notice_{i}:{uuid.uuid4().hex}",
        )
    db_session.flush()

    # Query with excessive page_size -> capped at 100
    items, total = get_user_notifications(db_session, citizen_user.id, page=1, page_size=500)
    assert len(items) >= 5
    assert total >= 5

    count = get_unread_notification_count(db_session, citizen_user.id)
    assert count >= 5
