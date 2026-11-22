"""
CivicPulse Phase 6.1 Tests: Citizen Dashboard & Unified Complaint Timeline

Verifies:
    1. Citizen personal dashboard endpoint (GET /api/v1/citizens/me/dashboard):
        - Empty dashboard returns zero counts, exhaustive status/priority keys, and empty lists.
        - Status breakdown accurately counts all 10 approved statuses.
        - Priority breakdown accurately counts all 4 priority levels.
        - Awaiting verification and action-required metrics.
        - Activity lists (recent submissions, recent updates, action required) are capped at 5
          and ordered appropriately.
        - Strict citizen ownership scoping (no data leakage from other citizens).
        - Role enforcement (Admin and Field Worker roles are rejected with 403).
        - Unauthenticated requests are rejected with 401.

    2. Unified complaint timeline endpoint (GET /api/v1/complaints/{id}/timeline):
        - Author citizen can access timeline.
        - Non-author citizen receives 403 Forbidden.
        - Unassigned field worker receives 403 Forbidden.
        - Assigned field worker can access timeline.
        - Previously assigned worker access is bounded by reassignment cutoff timestamp.
        - Administrator has full unrestricted access to timeline and internal remarks.
        - Chronological sorting across submission, status history, assignments, and progress.
        - Privacy redaction: internal administrative remarks and dispatch instructions are hidden from citizens.
        - Non-existent complaint ID returns 404 EntityNotFoundError.
        - Newly created complaints without assignments/progress return clean timeline.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.constants import (
    AssignmentStatus,
    ComplaintStatus,
    PriorityLevel,
    UserRole,
)
from app.core.security import create_access_token, hash_password
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.models.worker import Worker


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
def citizen_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Aarav Sharma",
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
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Neha Gupta",
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
        email=f"admin_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin Chief",
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
def department(db_session: Session) -> Department:
    dept = db_session.query(Department).first()
    if not dept:
        dept = Department(
            name="Roads & Infrastructure",
            code=f"RI_{uuid.uuid4().hex[:4].upper()}",
            description="Road maintenance",
            is_active=True,
        )
        db_session.add(dept)
        db_session.flush()
    return dept


@pytest.fixture
def category(db_session: Session, department: Department) -> Category:
    cat = db_session.query(Category).filter(Category.department_id == department.id).first()
    if not cat:
        cat = Category(
            name=f"Pothole Repair {uuid.uuid4().hex[:4]}",
            department_id=department.id,
            description="Road repair issues",
            is_active=True,
        )
        db_session.add(cat)
        db_session.flush()
    return cat


@pytest.fixture
def worker_user(db_session: Session, worker_role: Role, department: Department) -> tuple[User, Worker]:
    user = User(
        email=f"worker_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Rajesh Kumar",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=department.id,
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        designation="Field Technician",
        is_available=True,
        employment_status="ACTIVE",
    )
    db_session.add(worker)
    db_session.flush()
    return user, worker


@pytest.fixture
def worker_headers(worker_user: tuple[User, Worker]) -> dict[str, str]:
    user, _ = worker_user
    token = create_access_token(
        subject=str(user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_worker_user(db_session: Session, worker_role: Role, department: Department) -> tuple[User, Worker]:
    user = User(
        email=f"worker2_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Suresh Verma",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=department.id,
        employee_id=f"EMP2-{uuid.uuid4().hex[:6].upper()}",
        designation="Senior Technician",
        is_available=True,
        employment_status="ACTIVE",
    )
    db_session.add(worker)
    db_session.flush()
    return user, worker


@pytest.fixture
def other_worker_headers(other_worker_user: tuple[User, Worker]) -> dict[str, str]:
    user, _ = other_worker_user
    token = create_access_token(
        subject=str(user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": user.email},
    )
    return {"Authorization": f"Bearer {token}"}


def _create_complaint(
    db: Session,
    citizen: User,
    category: Category,
    status: ComplaintStatus = ComplaintStatus.SUBMITTED,
    priority: PriorityLevel = PriorityLevel.MEDIUM,
    title: str = "Test Complaint",
    created_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> Complaint:
    now_utc = datetime.now(timezone.utc)
    ts = created_at or now_utc
    complaint = Complaint(
        complaint_number=f"CP-2026-{uuid.uuid4().hex[:8].upper()}",
        citizen_id=citizen.id,
        category_id=category.id,
        title=title,
        description="Detailed description of the issue for test execution.",
        status=status,
        priority=priority,
        created_at=ts,
        updated_at=ts,
        resolved_at=resolved_at,
    )
    db.add(complaint)
    db.flush()

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=citizen.id,
        previous_status=None,
        new_status=status,
        remarks="Initial test creation",
        created_at=ts,
    )
    db.add(history)
    db.flush()
    return complaint


# =============================================================================
# Dashboard Tests (GET /api/v1/citizens/me/dashboard)
# =============================================================================

def test_citizen_dashboard_empty(client: TestClient, citizen_headers: dict[str, str]):
    """Citizen with no complaints receives zero metrics and empty lists."""
    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK

    res = response.json()
    assert res["success"] is True
    data = res["data"]

    metrics = data["metrics"]
    assert metrics["total_complaints"] == 0
    assert metrics["active_complaints"] == 0
    assert metrics["awaiting_verification"] == 0
    assert metrics["closed_complaints"] == 0
    assert metrics["rejected_complaints"] == 0
    assert metrics["duplicate_complaints"] == 0
    assert metrics["action_required_count"] == 0

    # Verify all 10 approved statuses exist in breakdown with 0
    for s in ComplaintStatus:
        assert metrics["status_breakdown"][s.value] == 0

    # Verify all 4 priority levels exist in breakdown with 0
    for p in PriorityLevel:
        assert metrics["priority_breakdown"][p.value] == 0

    # Activity lists are empty
    assert data["recent_submissions"] == []
    assert data["recent_updates"] == []
    assert data["action_required"] == []


def test_citizen_dashboard_status_breakdown(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Counts correctly reflect all supported complaint statuses."""
    all_statuses = list(ComplaintStatus)
    for s in all_statuses:
        _create_complaint(
            db=db_session,
            citizen=citizen_user,
            category=category,
            status=s,
            title=f"Complaint in {s.value}",
        )

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    metrics = data["metrics"]
    assert metrics["total_complaints"] == len(all_statuses)
    for s in all_statuses:
        assert metrics["status_breakdown"][s.value] == 1


def test_citizen_dashboard_priority_breakdown(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Priority breakdown is correct across all supported priority levels."""
    _create_complaint(db_session, citizen_user, category, priority=PriorityLevel.LOW)
    _create_complaint(db_session, citizen_user, category, priority=PriorityLevel.MEDIUM)
    _create_complaint(db_session, citizen_user, category, priority=PriorityLevel.MEDIUM)
    _create_complaint(db_session, citizen_user, category, priority=PriorityLevel.HIGH)
    _create_complaint(db_session, citizen_user, category, priority=PriorityLevel.CRITICAL)

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    metrics = response.json()["data"]["metrics"]

    assert metrics["priority_breakdown"][PriorityLevel.LOW.value] == 1
    assert metrics["priority_breakdown"][PriorityLevel.MEDIUM.value] == 2
    assert metrics["priority_breakdown"][PriorityLevel.HIGH.value] == 1
    assert metrics["priority_breakdown"][PriorityLevel.CRITICAL.value] == 1


def test_citizen_dashboard_awaiting_verification_count(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Awaiting verification and action required counts are correctly aggregated."""
    now_utc = datetime.now(timezone.utc)
    _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        resolved_at=now_utc,
    )
    _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        resolved_at=now_utc,
    )
    _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.IN_PROGRESS)

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    metrics = response.json()["data"]["metrics"]

    assert metrics["awaiting_verification"] == 2
    assert metrics["action_required_count"] == 2
    assert metrics["active_complaints"] == 1


def test_citizen_dashboard_recent_submissions_capped(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Recent submissions list is ordered by creation time descending and capped at five."""
    base_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(8):
        _create_complaint(
            db=db_session,
            citizen=citizen_user,
            category=category,
            title=f"Submission {i}",
            created_at=base_time + timedelta(hours=i),
        )

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    recent_submissions = response.json()["data"]["recent_submissions"]

    assert len(recent_submissions) == 5
    # Most recent should be Submission 7, then 6, 5, 4, 3
    assert recent_submissions[0]["title"] == "Submission 7"
    assert recent_submissions[1]["title"] == "Submission 6"
    assert recent_submissions[4]["title"] == "Submission 3"


def test_citizen_dashboard_recent_updates_capped(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Recent updates list is ordered by updated_at descending and capped at five."""
    base_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    complaints = []
    for i in range(7):
        c = _create_complaint(
            db=db_session,
            citizen=citizen_user,
            category=category,
            title=f"Complaint {i}",
            created_at=base_time + timedelta(minutes=i),
        )
        complaints.append(c)

    # Artificially modify updated_at of complaint 2 to be the newest
    complaints[2].updated_at = base_time + timedelta(days=5)
    db_session.flush()

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    recent_updates = response.json()["data"]["recent_updates"]

    assert len(recent_updates) == 5
    assert recent_updates[0]["title"] == "Complaint 2"


def test_citizen_dashboard_action_required_list(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Action required list contains only complaints in RESOLVED_AWAITING_VERIFICATION."""
    now_utc = datetime.now(timezone.utc)
    _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        title="Needs Verification 1",
        resolved_at=now_utc - timedelta(hours=2),
    )
    _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        title="Needs Verification 2",
        resolved_at=now_utc - timedelta(hours=1),
    )
    _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.IN_PROGRESS,
        title="Not Awaiting",
    )

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    action_required = response.json()["data"]["action_required"]

    assert len(action_required) == 2
    assert all(item["status"] == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION.value for item in action_required)
    assert action_required[0]["title"] == "Needs Verification 2"


def test_citizen_dashboard_ownership_scoping(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_user: User,
    category: Category,
):
    """Dashboard never includes another citizen's complaints."""
    _create_complaint(db_session, citizen_user, category, title="Citizen's Own Issue")
    _create_complaint(db_session, other_citizen_user, category, title="Other Citizen's Issue")

    response = client.get("/api/v1/citizens/me/dashboard", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    assert data["metrics"]["total_complaints"] == 1
    assert len(data["recent_submissions"]) == 1
    assert data["recent_submissions"][0]["title"] == "Citizen's Own Issue"


def test_citizen_dashboard_forbidden_roles(
    client: TestClient,
    admin_headers: dict[str, str],
    worker_headers: dict[str, str],
):
    """Worker and administrator roles cannot access the citizen dashboard."""
    res_admin = client.get("/api/v1/citizens/me/dashboard", headers=admin_headers)
    assert res_admin.status_code == status.HTTP_403_FORBIDDEN

    res_worker = client.get("/api/v1/citizens/me/dashboard", headers=worker_headers)
    assert res_worker.status_code == status.HTTP_403_FORBIDDEN


def test_citizen_dashboard_unauthenticated(client: TestClient):
    """Unauthenticated request to dashboard is rejected with 401."""
    response = client.get("/api/v1/citizens/me/dashboard")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Timeline Tests (GET /api/v1/complaints/{id}/timeline)
# =============================================================================

def test_timeline_author_citizen_access(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Author citizen can retrieve their complaint timeline."""
    complaint = _create_complaint(db_session, citizen_user, category, title="Broken Pavement")

    response = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK

    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert data["complaint_id"] == str(complaint.id)
    assert data["complaint_number"] == complaint.complaint_number
    assert len(data["events"]) >= 1
    assert data["events"][0]["event_type"] == "COMPLAINT_SUBMITTED"


def test_timeline_non_author_citizen_forbidden(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    other_citizen_headers: dict[str, str],
    category: Category,
):
    """Non-author citizen receives 403 Forbidden."""
    complaint = _create_complaint(db_session, citizen_user, category, title="Author Complaint")

    response = client.get(
        f"/api/v1/complaints/{complaint.id}/timeline",
        headers=other_citizen_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["message"] == "Forbidden"
    assert "permission" in response.json()["detail"].lower()


def test_timeline_unauthenticated_rejected(client: TestClient, db_session: Session, citizen_user: User, category: Category):
    """Unauthenticated requests are rejected with 401."""
    complaint = _create_complaint(db_session, citizen_user, category)
    response = client.get(f"/api/v1/complaints/{complaint.id}/timeline")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_timeline_assigned_worker_access(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    other_worker_headers: dict[str, str],
    category: Category,
):
    """Worker access follows assignment authorization: assigned worker allowed, unassigned forbidden."""
    complaint = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.UNDER_REVIEW)
    _, worker = worker_user

    # Assign worker to complaint
    assignment = Assignment(
        complaint_id=complaint.id,
        worker_id=worker.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.ASSIGNED,
        notes="Inspect water leakage on site",
    )
    db_session.add(assignment)
    db_session.flush()

    # Assigned worker succeeds
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()["data"]["events"]) >= 2

    # Unassigned worker receives 403 Forbidden
    res_other = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=other_worker_headers)
    assert res_other.status_code == status.HTTP_403_FORBIDDEN


def test_timeline_previously_assigned_worker_boundary(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    other_worker_user: tuple[User, Worker],
    category: Category,
):
    """Previously assigned worker can only see events up to their reassignment timestamp."""
    base_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(
        db_session, citizen_user, category, created_at=base_time
    )
    _, worker1 = worker_user
    _, worker2 = other_worker_user

    # Assignment 1 to worker 1 at base + 1h
    asgn1 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.REASSIGNED,
        assigned_at=base_time + timedelta(hours=1),
        updated_at=base_time + timedelta(hours=3),
        notes="Initial assignment",
    )
    db_session.add(asgn1)
    db_session.flush()

    # Progress by worker 1 at base + 2h
    p1 = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Worker 1 inspected area",
        created_at=base_time + timedelta(hours=2),
    )
    db_session.add(p1)

    # Reassignment progress at base + 3h (reassignment moment)
    p_reassign = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Reassigned to replacement worker",
        created_at=base_time + timedelta(hours=3),
    )
    db_session.add(p_reassign)

    # Assignment 2 to worker 2 at base + 3h
    asgn2 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker2.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.IN_PROGRESS,
        assigned_at=base_time + timedelta(hours=3),
    )
    db_session.add(asgn2)
    db_session.flush()

    # Progress by worker 2 at base + 5h (AFTER worker 1 reassignment)
    p2 = AssignmentProgress(
        assignment_id=asgn2.id,
        worker_id=worker2.id,
        description="Worker 2 repaired the pothole",
        created_at=base_time + timedelta(hours=5),
    )
    db_session.add(p2)
    db_session.flush()

    # Worker 1 requests timeline: should NOT see events from base + 5h
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]

    event_descs = [e["description"] for e in events]
    assert "Worker 1 inspected area" in event_descs
    assert "Worker 2 repaired the pothole" not in event_descs


def test_timeline_admin_access(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Administrator can retrieve complete timeline unrestricted."""
    complaint = _create_complaint(db_session, citizen_user, category)
    response = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True


def test_timeline_chronological_ordering(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    admin_headers: dict[str, str],
    category: Category,
):
    """Events from different tables are sorted chronologically."""
    base = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base)
    _, worker = worker_user

    # Add status transition at base + 1h
    h1 = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.UNDER_REVIEW,
        remarks="Triage complete",
        created_at=base + timedelta(hours=1),
    )
    db_session.add(h1)

    # Add assignment at base + 2h
    asgn = Assignment(
        complaint_id=complaint.id,
        worker_id=worker.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.IN_PROGRESS,
        assigned_at=base + timedelta(hours=2),
        started_at=base + timedelta(hours=3),
    )
    db_session.add(asgn)
    db_session.flush()

    # Add progress at base + 4h
    prog = AssignmentProgress(
        assignment_id=asgn.id,
        worker_id=worker.id,
        description="Work progress update",
        created_at=base + timedelta(hours=4),
    )
    db_session.add(prog)
    db_session.flush()

    response = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    events = response.json()["data"]["events"]

    timestamps = [e["timestamp"] for e in events]
    # Verify strictly monotonic or non-decreasing timestamps
    for i in range(len(timestamps) - 1):
        assert timestamps[i] <= timestamps[i + 1]


def test_timeline_internal_remarks_redacted_for_citizen(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    admin_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Internal remarks and dispatch instructions are redacted for citizens but visible to admin."""
    complaint = _create_complaint(db_session, citizen_user, category)

    # Status transition with internal remark
    h = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.UNDER_REVIEW,
        remarks="CONFIDENTIAL: Potential high profile resident, expedite.",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(h)
    db_session.flush()

    # Citizen view: remarks must be None
    res_citizen = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert res_citizen.status_code == status.HTTP_200_OK
    c_events = res_citizen.json()["data"]["events"]
    status_events = [e for e in c_events if e["event_type"] == "STATUS_TRANSITION"]
    assert len(status_events) >= 1
    assert status_events[0]["remarks"] is None

    # Admin view: remarks must be visible
    res_admin = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert res_admin.status_code == status.HTTP_200_OK
    a_events = res_admin.json()["data"]["events"]
    admin_status_events = [e for e in a_events if e["event_type"] == "STATUS_TRANSITION"]
    assert admin_status_events[0]["remarks"] == "CONFIDENTIAL: Potential high profile resident, expedite."


def test_timeline_missing_complaint_404(client: TestClient, citizen_headers: dict[str, str]):
    """Missing complaint IDs return 404 EntityNotFoundError."""
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/complaints/{random_id}/timeline", headers=citizen_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["message"].lower()


def test_timeline_partial_or_newly_submitted_complaint(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Empty or newly submitted complaint timeline works cleanly."""
    complaint = _create_complaint(db_session, citizen_user, category, title="Clean Fresh Complaint")

    response = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    assert data["complaint_id"] == str(complaint.id)
    assert len(data["events"]) == 1
    assert data["events"][0]["event_type"] == "COMPLAINT_SUBMITTED"
    assert data["events"][0]["title"] == "Complaint Submitted"


# =============================================================================
# Phase 6.1.1 Targeted Security & Privacy Tests
# =============================================================================

def test_timeline_rejection_remarks_redacted_for_citizen(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    admin_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Administrative rejection remarks must be redacted for citizens but visible to administrators."""
    complaint = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.SUBMITTED)

    h_reject = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.REJECTED,
        remarks="INTERNAL ADMIN NOTE: Submitter has outstanding verification flags, rejecting.",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(h_reject)
    complaint.status = ComplaintStatus.REJECTED
    db_session.flush()

    # Citizen request: remarks MUST be None
    res_cit = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert res_cit.status_code == status.HTTP_200_OK
    cit_events = res_cit.json()["data"]["events"]
    reject_events_cit = [e for e in cit_events if e["metadata"].get("new_status") == "REJECTED"]
    assert len(reject_events_cit) == 1
    assert reject_events_cit[0]["remarks"] is None

    # Admin request: complete remarks MUST be present
    res_adm = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert res_adm.status_code == status.HTTP_200_OK
    adm_events = res_adm.json()["data"]["events"]
    reject_events_adm = [e for e in adm_events if e["metadata"].get("new_status") == "REJECTED"]
    assert len(reject_events_adm) == 1
    assert reject_events_adm[0]["remarks"] == "INTERNAL ADMIN NOTE: Submitter has outstanding verification flags, rejecting."


def test_timeline_duplicate_remarks_redacted_for_citizen(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    admin_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Administrative duplicate remarks must be redacted for citizens but visible to administrators."""
    complaint = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.SUBMITTED)

    h_dup = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.DUPLICATE,
        remarks="INTERNAL NOTE: Merged with confidential civic inquiry CP-2026-99999",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(h_dup)
    complaint.status = ComplaintStatus.DUPLICATE
    db_session.flush()

    # Citizen: remarks is None
    res_cit = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert res_cit.status_code == status.HTTP_200_OK
    cit_dup_events = [e for e in res_cit.json()["data"]["events"] if e["metadata"].get("new_status") == "DUPLICATE"]
    assert len(cit_dup_events) == 1
    assert cit_dup_events[0]["remarks"] is None

    # Admin: remarks is visible
    res_adm = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert res_adm.status_code == status.HTTP_200_OK
    adm_dup_events = [e for e in res_adm.json()["data"]["events"] if e["metadata"].get("new_status") == "DUPLICATE"]
    assert len(adm_dup_events) == 1
    assert adm_dup_events[0]["remarks"] == "INTERNAL NOTE: Merged with confidential civic inquiry CP-2026-99999"


def test_timeline_citizen_authored_remarks_visible(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    admin_headers: dict[str, str],
    category: Category,
):
    """Citizen-authored remarks are visible when actor reliably proves complaint owner authorship."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        resolved_at=datetime.now(timezone.utc),
    )

    # Citizen closes complaint with own feedback remark
    h_close = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=citizen_user.id,
        previous_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        new_status=ComplaintStatus.CLOSED,
        remarks="Citizen note: Verified on site, street light is working properly now. Thank you!",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(h_close)
    complaint.status = ComplaintStatus.CLOSED
    db_session.flush()

    # Citizen sees their own remark
    res_cit = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert res_cit.status_code == status.HTTP_200_OK
    cit_close_events = [e for e in res_cit.json()["data"]["events"] if e["metadata"].get("new_status") == "CLOSED"]
    assert len(cit_close_events) == 1
    assert cit_close_events[0]["remarks"] == "Citizen note: Verified on site, street light is working properly now. Thank you!"

    # Admin also sees the citizen's remark
    res_adm = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert res_adm.status_code == status.HTTP_200_OK
    adm_close_events = [e for e in res_adm.json()["data"]["events"] if e["metadata"].get("new_status") == "CLOSED"]
    assert len(adm_close_events) == 1
    assert adm_close_events[0]["remarks"] == "Citizen note: Verified on site, street light is working properly now. Thank you!"


def test_timeline_unrelated_assignment_update_does_not_extend_worker_access(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    other_worker_user: tuple[User, Worker],
    category: Category,
):
    """An unrelated update to assignment.updated_at cannot accidentally extend a previous worker's historical access."""
    base_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base_time)
    _, worker1 = worker_user
    _, worker2 = other_worker_user

    # Worker 1 assigned at base + 1h
    asgn1 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.REASSIGNED,
        assigned_at=base_time + timedelta(hours=1),
        notes="Initial assignment",
    )
    db_session.add(asgn1)
    db_session.flush()

    # Worker 1 progress at base + 2h
    p1 = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Worker 1 arrived on site",
        created_at=base_time + timedelta(hours=2),
    )
    db_session.add(p1)

    # Reassignment progress at base + 3h (official reassignment event)
    p_reassign = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Reassigned to replacement worker",
        created_at=base_time + timedelta(hours=3),
    )
    db_session.add(p_reassign)

    # Worker 2 assigned at base + 3h
    asgn2 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker2.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.IN_PROGRESS,
        assigned_at=base_time + timedelta(hours=3),
    )
    db_session.add(asgn2)
    db_session.flush()

    # Unrelated update to asgn1: admin updates notes days later
    # This modifies asgn1.updated_at to base + 10 days
    asgn1.notes = "ADMIN AUDIT: Archived assignment review completed."
    asgn1.updated_at = base_time + timedelta(days=10)
    db_session.flush()

    # Worker 2 does work at base + 5h (well before base + 10 days, but AFTER reassignment at base + 3h)
    p2 = AssignmentProgress(
        assignment_id=asgn2.id,
        worker_id=worker2.id,
        description="Worker 2 completed field replacement",
        created_at=base_time + timedelta(hours=5),
    )
    db_session.add(p2)
    db_session.flush()

    # Worker 1 checks timeline: MUST NOT see Worker 2's event at base + 5h!
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]

    event_descs = [e["description"] for e in events]
    assert "Worker 1 arrived on site" in event_descs
    assert "Worker 2 completed field replacement" not in event_descs


def test_timeline_worker_no_assignment_forbidden(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    other_worker_headers: dict[str, str],
    category: Category,
):
    """Worker with no assignment relationship to the complaint receives 403 Forbidden."""
    complaint = _create_complaint(db_session, citizen_user, category)
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=other_worker_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "not assigned" in res.json()["detail"].lower()


# =============================================================================
# Phase 6.1.2 Targeted Security & Worker Access-Boundary Tests
# =============================================================================

def test_timeline_reassignment_trusted_service_marker_accepted(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    other_worker_user: tuple[User, Worker],
    category: Category,
):
    """
    Scenario 1: Reassignment marker created through trusted reassignment service
    is accepted as the verified historical access boundary.
    """
    from app.services.assignment_service import reassign_complaint

    base_time = datetime(2026, 11, 3, 9, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(
        db_session, citizen_user, category, created_at=base_time, status=ComplaintStatus.ASSIGNED
    )
    _, worker1 = worker_user
    _, worker2 = other_worker_user

    # Initial assignment to worker 1
    asgn1 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.ASSIGNED,
        assigned_at=base_time + timedelta(hours=1),
        notes="Inspect initial site",
    )
    db_session.add(asgn1)
    db_session.flush()

    # Worker 1 logs progress
    p1 = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Worker 1 arrived on site",
        created_at=base_time + timedelta(hours=2),
    )
    db_session.add(p1)
    db_session.flush()

    # Reassign complaint to worker 2 using trusted reassignment service
    new_asgn, _ = reassign_complaint(
        db=db_session,
        complaint_id=complaint.id,
        new_worker_id=worker2.id,
        admin_user=admin_user,
        reason="Technician reassigned due to priority shift",
    )

    # Worker 2 logs progress after reassignment
    p2 = AssignmentProgress(
        assignment_id=new_asgn.id,
        worker_id=worker2.id,
        description="Worker 2 completed site inspection",
        created_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(p2)
    db_session.flush()

    # Worker 1 requests timeline: should see up to reassignment marker, but NOT Worker 2's post-reassignment progress
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]
    descs = [e["description"] for e in events]

    assert "Worker 1 arrived on site" in descs
    assert any("Reassigned to" in d for d in descs)
    assert "Worker 2 completed site inspection" not in descs


def test_timeline_worker_progress_cannot_impersonate_reassignment_marker(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    category: Category,
):
    """
    Scenario 2: Worker-generated progress entry containing 'Reassigned to ...' text
    cannot impersonate an authentic reassignment marker.
    """
    base_time = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base_time)
    _, worker1 = worker_user

    # Worker 1 is assigned but status is maliciously or manually marked REASSIGNED
    # with only a spoofed progress update and NO matching replacement assignment
    asgn = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.REASSIGNED,
        assigned_at=base_time + timedelta(hours=1),
    )
    db_session.add(asgn)
    db_session.flush()

    # Spoofed worker progress note pretending to be a system reassignment marker
    spoofed_p = AssignmentProgress(
        assignment_id=asgn.id,
        worker_id=worker1.id,
        description="Reassigned to John Doe (EMP999) - spoofed marker",
        created_at=base_time + timedelta(hours=2),
    )
    db_session.add(spoofed_p)
    db_session.flush()

    # Requesting timeline MUST fail with 403 because no replacement assignment correlates with the marker
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "cannot reliably establish assignment boundary" in res.json()["detail"].lower()


def test_timeline_missing_or_unreliable_reassignment_marker_denies_access(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    other_worker_user: tuple[User, Worker],
    category: Category,
):
    """
    Scenario 3: Missing or unreliable reassignment marker denies previous-worker
    access (returns 403 / AuthorizationError). Ensures no fallback to worker activity.
    """
    base_time = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base_time)
    _, worker1 = worker_user
    _, worker2 = other_worker_user

    # Assignment marked REASSIGNED
    asgn1 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.REASSIGNED,
        assigned_at=base_time + timedelta(hours=1),
        started_at=base_time + timedelta(hours=2),
    )
    db_session.add(asgn1)

    # Replacement assignment exists at base + 4h
    asgn2 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker2.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.IN_PROGRESS,
        assigned_at=base_time + timedelta(hours=4),
    )
    db_session.add(asgn2)
    db_session.flush()

    # Notice: No AssignmentProgress with "Reassigned to " was logged on asgn1!
    # Under old logic, it would unsafely fall back to started_at or assigned_at.
    # Under Phase 6.1.2: It MUST deny access!
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "cannot reliably establish assignment boundary" in res.json()["detail"].lower()


def test_timeline_completed_assignment_verified_boundary(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    category: Category,
):
    """
    Scenario 4: Completed assignment uses verified completion boundary.
    Events after completed_at are hidden from the completed worker.
    """
    base_time = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(
        db_session, citizen_user, category, created_at=base_time, status=ComplaintStatus.IN_PROGRESS
    )
    _, worker1 = worker_user

    completion_time = base_time + timedelta(hours=3)
    asgn = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.COMPLETED,
        assigned_at=base_time + timedelta(hours=1),
        started_at=base_time + timedelta(hours=2),
        completed_at=completion_time,
    )
    db_session.add(asgn)
    db_session.flush()

    p_comp = AssignmentProgress(
        assignment_id=asgn.id,
        worker_id=worker1.id,
        description="Work completed: valve replaced",
        created_at=completion_time,
    )
    db_session.add(p_comp)

    # Subsequent event after completion_time (e.g. status transition to CLOSED at base + 6h)
    h_closed = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=citizen_user.id,
        previous_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        new_status=ComplaintStatus.CLOSED,
        remarks="Verified on site",
        created_at=base_time + timedelta(hours=6),
    )
    db_session.add(h_closed)
    db_session.flush()

    # Worker requests timeline: can see up to completed_at, but CANNOT see event at base + 6h
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]
    descs = [e["description"] for e in events]

    assert "Work completed: valve replaced" in descs
    assert not any(e["event_type"] == "COMPLAINT_CLOSED" for e in events)

    # Edge case: If COMPLETED assignment has completed_at = None, access is denied
    asgn.completed_at = None
    db_session.flush()
    res_err = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res_err.status_code == status.HTTP_403_FORBIDDEN


def test_timeline_multiple_assignments_interval_authorization(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    other_worker_user: tuple[User, Worker],
    category: Category,
):
    """
    Scenario 5: Reassignment followed by second assignment to the same worker:
    - Worker CAN see events during assignment 1.
    - Worker CANNOT see events during intervening period.
    - Worker CAN see events during assignment 2.
    - Worker CANNOT see events after assignment 2.
    """
    base_time = datetime(2026, 11, 4, 8, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base_time)
    _, worker1 = worker_user
    _, worker2 = other_worker_user

    # 1. Assignment 1 to Worker 1 at 09:00, reassigned at 11:00
    t_asgn1 = base_time + timedelta(hours=1)  # 09:00
    t_prog1 = base_time + timedelta(hours=2)  # 10:00
    t_reassign1 = base_time + timedelta(hours=3)  # 11:00

    asgn1 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.REASSIGNED,
        assigned_at=t_asgn1,
    )
    db_session.add(asgn1)
    db_session.flush()

    p1 = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Worker 1 - Phase 1 investigation",
        created_at=t_prog1,
    )
    db_session.add(p1)

    p_reassign1 = AssignmentProgress(
        assignment_id=asgn1.id,
        worker_id=worker1.id,
        description="Reassigned to Worker 2",
        created_at=t_reassign1,
    )
    db_session.add(p_reassign1)

    # 2. Intervening Assignment to Worker 2 at 11:00, reassigned at 13:00
    t_intervening_prog = base_time + timedelta(hours=4)  # 12:00
    t_reassign2 = base_time + timedelta(hours=5)  # 13:00

    asgn2 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker2.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.REASSIGNED,
        assigned_at=t_reassign1,
    )
    db_session.add(asgn2)
    db_session.flush()

    p_intervening = AssignmentProgress(
        assignment_id=asgn2.id,
        worker_id=worker2.id,
        description="Worker 2 intervening progress note",
        created_at=t_intervening_prog,
    )
    db_session.add(p_intervening)

    p_reassign2 = AssignmentProgress(
        assignment_id=asgn2.id,
        worker_id=worker2.id,
        description="Reassigned to Worker 1",
        created_at=t_reassign2,
    )
    db_session.add(p_reassign2)

    # 3. Assignment 2 to Worker 1 at 13:00, completed at 15:00
    t_prog2 = base_time + timedelta(hours=6)  # 14:00
    t_comp2 = base_time + timedelta(hours=7)  # 15:00

    asgn3 = Assignment(
        complaint_id=complaint.id,
        worker_id=worker1.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.COMPLETED,
        assigned_at=t_reassign2,
        completed_at=t_comp2,
    )
    db_session.add(asgn3)
    db_session.flush()

    p2 = AssignmentProgress(
        assignment_id=asgn3.id,
        worker_id=worker1.id,
        description="Worker 1 - Phase 2 final fix",
        created_at=t_prog2,
    )
    db_session.add(p2)

    # 4. Post-tenure event at 17:00 (after Worker 1's tenure ended)
    t_post = base_time + timedelta(hours=9)  # 17:00
    h_post = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        new_status=ComplaintStatus.CLOSED,
        remarks="Admin post-closure review",
        created_at=t_post,
    )
    db_session.add(h_post)
    db_session.flush()

    # Worker 1 requests timeline:
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]
    descs = [e["description"] for e in events]

    # Worker CAN see events during Assignment 1
    assert "Worker 1 - Phase 1 investigation" in descs
    assert any("Reassigned to Worker 2" in d for d in descs)

    # Worker CANNOT see events during intervening period
    assert "Worker 2 intervening progress note" not in descs

    # Worker CAN see events during Assignment 2
    assert "Worker 1 - Phase 2 final fix" in descs

    # Worker CANNOT see events after Assignment 2
    assert not any(e["event_type"] == "COMPLAINT_CLOSED" for e in events)


def test_timeline_worker_administrative_remarks_redacted(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    worker_user: tuple[User, Worker],
    worker_headers: dict[str, str],
    category: Category,
):
    """
    Scenario 6: Worker cannot see administrative remarks that are not established as safe.
    Only worker's own remarks and dispatch remarks designating the worker are visible.
    """
    base_time = datetime(2026, 11, 4, 9, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base_time)
    worker_user_obj, worker_profile = worker_user

    # 1. Admin triage note (MUST be redacted)
    h_triage = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.UNDER_REVIEW,
        remarks="CONFIDENTIAL TRIAGE: Sensitive political address. Handle with caution.",
        created_at=base_time + timedelta(hours=1),
    )
    db_session.add(h_triage)

    # 2. Admin hold note (MUST be redacted)
    h_hold = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.UNDER_REVIEW,
        new_status=ComplaintStatus.ON_HOLD,
        remarks="INTERNAL ADMIN: Awaiting departmental funding authorization.",
        created_at=base_time + timedelta(hours=2),
    )
    db_session.add(h_hold)

    # 3. Dispatch note designating this worker (SAFE and visible)
    dispatch_remarks = f"Assigned to {worker_user_obj.full_name} ({worker_profile.employee_id})"
    h_assign = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.ON_HOLD,
        new_status=ComplaintStatus.ASSIGNED,
        remarks=dispatch_remarks,
        created_at=base_time + timedelta(hours=3),
    )
    db_session.add(h_assign)

    asgn = Assignment(
        complaint_id=complaint.id,
        worker_id=worker_profile.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.IN_PROGRESS,
        assigned_at=base_time + timedelta(hours=3),
    )
    db_session.add(asgn)

    # 4. Worker's own authored remark (SAFE and visible)
    h_progress = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=worker_user_obj.id,
        previous_status=ComplaintStatus.ASSIGNED,
        new_status=ComplaintStatus.IN_PROGRESS,
        remarks="Technician on site: valve replacement commenced.",
        created_at=base_time + timedelta(hours=4),
    )
    db_session.add(h_progress)
    db_session.flush()

    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=worker_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]

    triage_event = next(e for e in events if e["metadata"].get("new_status") == "UNDER_REVIEW")
    assert triage_event["remarks"] is None

    hold_event = next(e for e in events if e["metadata"].get("new_status") == "ON_HOLD")
    assert hold_event["remarks"] is None

    assign_event = next(e for e in events if e["metadata"].get("new_status") == "ASSIGNED")
    assert assign_event["remarks"] == dispatch_remarks

    progress_event = next(e for e in events if e["metadata"].get("new_status") == "IN_PROGRESS")
    assert progress_event["remarks"] == "Technician on site: valve replacement commenced."


def test_timeline_admin_retains_full_visibility(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    admin_headers: dict[str, str],
    worker_user: tuple[User, Worker],
    category: Category,
):
    """
    Scenario 7: Administrator retains full timeline visibility, including all internal
    administrative deliberations, triage notes, and hold reasons.
    """
    base_time = datetime(2026, 11, 4, 9, 0, 0, tzinfo=timezone.utc)
    complaint = _create_complaint(db_session, citizen_user, category, created_at=base_time)
    _, worker_profile = worker_user

    h_triage = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.UNDER_REVIEW,
        remarks="ADMIN SENSITIVE: Resident VIP tag confirmed.",
        created_at=base_time + timedelta(hours=1),
    )
    db_session.add(h_triage)

    h_hold = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.UNDER_REVIEW,
        new_status=ComplaintStatus.ON_HOLD,
        remarks="BUDGET COMMITTEE: Awaiting procurement release.",
        created_at=base_time + timedelta(hours=2),
    )
    db_session.add(h_hold)
    db_session.flush()

    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    events = res.json()["data"]["events"]

    triage_event = next(e for e in events if e["metadata"].get("new_status") == "UNDER_REVIEW")
    assert triage_event["remarks"] == "ADMIN SENSITIVE: Resident VIP tag confirmed."

    hold_event = next(e for e in events if e["metadata"].get("new_status") == "ON_HOLD")
    assert hold_event["remarks"] == "BUDGET COMMITTEE: Awaiting procurement release."


def test_timeline_citizen_privacy_regression_preserved(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_headers: dict[str, str],
    admin_user: User,
    category: Category,
):
    """
    Scenario 8: Citizen privacy tests from Phase 6.1.1 continue to pass:
    - Author sees timeline.
    - Non-author receives 403 Forbidden.
    - Administrative rejection and duplicate remarks are redacted.
    - Citizen-authored remarks are visible.
    """
    complaint = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.SUBMITTED)

    # Rejection remark by admin
    h_reject = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=admin_user.id,
        previous_status=ComplaintStatus.SUBMITTED,
        new_status=ComplaintStatus.REJECTED,
        remarks="INTERNAL ADMIN: Spam submission discarded.",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(h_reject)
    db_session.flush()

    # Author citizen: rejection remarks must be None
    res = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=citizen_headers)
    assert res.status_code == status.HTTP_200_OK
    reject_events = [e for e in res.json()["data"]["events"] if e["metadata"].get("new_status") == "REJECTED"]
    assert len(reject_events) == 1
    assert reject_events[0]["remarks"] is None

    # Non-author citizen: 403 Forbidden
    res_other = client.get(f"/api/v1/complaints/{complaint.id}/timeline", headers=other_citizen_headers)
    assert res_other.status_code == status.HTTP_403_FORBIDDEN


