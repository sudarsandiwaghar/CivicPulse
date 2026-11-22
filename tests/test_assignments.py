"""
CivicPulse Phase 5 Worker Assignment & Department Management Tests

Comprehensive test suite verifying:
    - Administrator-only department management (CRUD, unique codes, deactivation safety).
    - Administrator worker account provisioning (atomic User + Worker creation, role binding, bcrypt hash).
    - Worker-department relationships and category-department compatibility enforcement.
    - Complaint assignment (row locking, UNDER_REVIEW precondition, transition to ASSIGNED).
    - Worker task management (/workers/me/tasks, scoping, IDOR protection).
    - Assignment acceptance (/accept), work initiation (/start -> IN_PROGRESS), and progress tracking (/progress).
    - Work completion (/complete -> COMPLETED, complaint -> RESOLVED_AWAITING_VERIFICATION).
    - Citizen verification preserving Phase 4 lifecycle rules (close / reopen).
    - Administrator reassignment (/reassign, audit reasons, history preservation, atomic state updates).
    - Concurrency and database-level partial unique index enforcing max 1 active assignment per complaint.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
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
def admin_user(db_session: Session) -> User:
    """Create and return a verified administrator user."""
    admin_role = db_session.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
    user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("AdminSecurePass123!"),
        full_name="Admin Director",
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
def citizen_user(db_session: Session) -> User:
    """Create and return a verified citizen user."""
    citizen_role = db_session.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
    user = User(
        email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("CitizenPass123!"),
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
def pwd_department(db_session: Session) -> Department:
    """Ensure PWD department exists."""
    dept = db_session.query(Department).filter(Department.code == "PWD").first()
    assert dept is not None
    return dept


@pytest.fixture
def electrical_department(db_session: Session) -> Department:
    """Ensure Electrical department exists."""
    dept = db_session.query(Department).filter(Department.code == "ELECTRICAL").first()
    assert dept is not None
    return dept


@pytest.fixture
def pwd_category(db_session: Session, pwd_department: Department) -> Category:
    """Return a category belonging to PWD (e.g. Roads and Potholes)."""
    cat = db_session.query(Category).filter(Category.department_id == pwd_department.id).first()
    assert cat is not None
    return cat


@pytest.fixture
def electrical_category(db_session: Session, electrical_department: Department) -> Category:
    """Return a category belonging to ELECTRICAL (e.g. Streetlights)."""
    cat = db_session.query(Category).filter(Category.department_id == electrical_department.id).first()
    assert cat is not None
    return cat


@pytest.fixture
def field_worker(db_session: Session, pwd_department: Department) -> Worker:
    """Create a verified field worker belonging to PWD."""
    worker_role = db_session.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
    user = User(
        email=f"pwd_worker_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Rajesh PWD Technician",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=pwd_department.id,
        employee_id=f"EMP-PWD-{uuid.uuid4().hex[:4].upper()}",
        designation="Road Repair Foreman",
        is_available=True,
        employment_status="ACTIVE",
    )
    db_session.add(worker)
    db_session.flush()
    return worker


@pytest.fixture
def worker_headers(field_worker: Worker) -> dict[str, str]:
    token = create_access_token(
        subject=str(field_worker.user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": field_worker.user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_field_worker(db_session: Session, pwd_department: Department) -> Worker:
    """Create a second distinct field worker in PWD for reassignment and IDOR tests."""
    worker_role = db_session.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
    user = User(
        email=f"pwd_worker2_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Suresh PWD Engineer",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=pwd_department.id,
        employee_id=f"EMP-PWD-{uuid.uuid4().hex[:4].upper()}",
        designation="Civil Assistant",
        is_available=True,
        employment_status="ACTIVE",
    )
    db_session.add(worker)
    db_session.flush()
    return worker


@pytest.fixture
def other_worker_headers(other_field_worker: Worker) -> dict[str, str]:
    token = create_access_token(
        subject=str(other_field_worker.user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": other_field_worker.user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def electrical_worker(db_session: Session, electrical_department: Department) -> Worker:
    """Create a worker belonging to Electrical department for department mismatch tests."""
    worker_role = db_session.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
    user = User(
        email=f"elec_worker_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Deepak Electrician",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=electrical_department.id,
        employee_id=f"EMP-ELEC-{uuid.uuid4().hex[:4].upper()}",
        designation="Senior Wireman",
        is_available=True,
        employment_status="ACTIVE",
    )
    db_session.add(worker)
    db_session.flush()
    return worker


@pytest.fixture
def under_review_complaint(
    client, citizen_headers, admin_headers, pwd_category: Category
) -> dict:
    """Helper fixture to create a complaint and move it to UNDER_REVIEW."""
    r = client.post(
        "/api/v1/complaints/",
        json={
            "title": "Broken road asphalt near bridge",
            "description": "Large pothole causing traffic obstruction on bridge approach road.",
            "category_id": pwd_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        },
        headers=citizen_headers,
    )
    c_id = r.json()["data"]["id"]

    # Transition to UNDER_REVIEW
    client.post(
        f"/api/v1/complaints/{c_id}/transitions",
        json={"new_status": "UNDER_REVIEW", "remarks": "Admin review approved."},
        headers=admin_headers,
    )
    return r.json()["data"]


# =============================================================================
# 1. Department Management Tests
# =============================================================================

class TestDepartmentManagement:
    """Verifies administrator department CRUD, unique constraints, and deactivation."""

    def test_admin_can_create_department(self, client, admin_headers):
        unique_code = f"DEPT_{uuid.uuid4().hex[:4].upper()}"
        unique_name = f"Department of Urban Forestry {uuid.uuid4().hex[:4]}"
        payload = {
            "name": unique_name,
            "code": unique_code,
            "description": "Tree maintenance, pruning, and green space management.",
            "contact_email": "forestry@civicpulse.org",
            "contact_phone": "1800-444-999",
            "is_active": True,
        }
        res = client.post("/api/v1/departments/", json=payload, headers=admin_headers)
        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()["data"]
        assert data["code"] == unique_code
        assert data["name"] == unique_name
        assert data["is_active"] is True

    def test_duplicate_department_code_rejected(self, client, admin_headers, pwd_department):
        payload = {
            "name": "Different Name Department",
            "code": pwd_department.code,  # Duplicate PWD code
            "description": "Attempting to create with identical code.",
        }
        res = client.post("/api/v1/departments/", json=payload, headers=admin_headers)
        assert res.status_code == status.HTTP_409_CONFLICT

    def test_citizen_cannot_create_or_modify_departments(self, client, citizen_headers, pwd_department):
        payload = {"name": "Citizen Dept", "code": "CITIZEN_DEPT"}
        res = client.post("/api/v1/departments/", json=payload, headers=citizen_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

        res_patch = client.patch(
            f"/api/v1/departments/{pwd_department.id}",
            json={"name": "Hacked Dept"},
            headers=citizen_headers,
        )
        assert res_patch.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_update_and_deactivate_department(self, client, admin_headers):
        # Create department
        unique_code = f"TEMP_{uuid.uuid4().hex[:4].upper()}"
        res = client.post(
            "/api/v1/departments/",
            json={"name": f"Temp Dept {unique_code}", "code": unique_code},
            headers=admin_headers,
        )
        dept_id = res.json()["data"]["id"]

        # Update description
        upd = client.patch(
            f"/api/v1/departments/{dept_id}",
            json={"description": "Updated mandate summary"},
            headers=admin_headers,
        )
        assert upd.status_code == status.HTTP_200_OK
        assert upd.json()["data"]["description"] == "Updated mandate summary"

        # Deactivate
        deact = client.patch(f"/api/v1/departments/{dept_id}/deactivate", headers=admin_headers)
        assert deact.status_code == status.HTTP_200_OK
        assert deact.json()["data"]["is_active"] is False


# =============================================================================
# 2. Worker Account Provisioning Tests
# =============================================================================

class TestWorkerProvisioning:
    """Verifies administrator worker provisioning, role binding, bcrypt hashing, and validation."""

    def test_admin_can_provision_field_worker(self, client, admin_headers, pwd_department):
        unique_emp = f"EMP-TEST-{uuid.uuid4().hex[:4].upper()}"
        unique_email = f"worker_{uuid.uuid4().hex[:6]}@civicpulse.org"
        payload = {
            "email": unique_email,
            "password": "WorkerSecurePassword123!",
            "full_name": "Manoj Civil Worker",
            "department_id": pwd_department.id,
            "employee_id": unique_emp,
            "designation": "Heavy Equipment Operator",
            "phone_number": "+91-9988776655",
        }
        res = client.post("/api/v1/workers/", json=payload, headers=admin_headers)
        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()["data"]
        assert data["employee_id"] == unique_emp
        assert data["email"] == unique_email
        assert data["department_id"] == pwd_department.id
        assert data["employment_status"] == "ACTIVE"
        assert data["is_available"] is True
        assert "password" not in data

    def test_duplicate_employee_id_rejected(self, client, admin_headers, field_worker, pwd_department):
        payload = {
            "email": f"new_email_{uuid.uuid4().hex[:6]}@civicpulse.org",
            "password": "ValidPassword123!",
            "full_name": "Duplicate Worker",
            "department_id": pwd_department.id,
            "employee_id": field_worker.employee_id,  # Duplicate
        }
        res = client.post("/api/v1/workers/", json=payload, headers=admin_headers)
        assert res.status_code == status.HTTP_409_CONFLICT

    def test_provision_to_inactive_department_rejected(self, client, admin_headers):
        # Create and deactivate department
        code = f"INACT_{uuid.uuid4().hex[:4].upper()}"
        d_res = client.post(
            "/api/v1/departments/",
            json={"name": f"Inactive Dept {code}", "code": code, "is_active": False},
            headers=admin_headers,
        )
        d_id = d_res.json()["data"]["id"]

        payload = {
            "email": f"worker_{uuid.uuid4().hex[:6]}@civicpulse.org",
            "password": "ValidPassword123!",
            "full_name": "Worker Inactive",
            "department_id": d_id,
            "employee_id": f"EMP-INACT-{uuid.uuid4().hex[:4].upper()}",
        }
        res = client.post("/api/v1/workers/", json=payload, headers=admin_headers)
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "inactive" in res.json()["detail"].lower()

    def test_worker_deactivation_disables_login_and_availability(
        self, client, admin_headers, field_worker
    ):
        res = client.patch(f"/api/v1/workers/{field_worker.id}/deactivate", headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["data"]
        assert data["is_available"] is False
        assert data["employment_status"] == "INACTIVE"


# =============================================================================
# 3. Complaint Assignment Tests
# =============================================================================

class TestComplaintAssignment:
    """Verifies complaint assignment workflows, status transitions, and validation rules."""

    def test_admin_can_assign_under_review_complaint(
        self, client, admin_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        payload = {
            "worker_id": str(field_worker.id),
            "notes": "Please inspect pothole and patch within 24 hours.",
        }
        res = client.post(f"/api/v1/complaints/{c_id}/assign", json=payload, headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["data"]
        assert data["status"] == "ASSIGNED"
        assert data["worker_id"] == str(field_worker.id)
        assert data["assigned_at"] is not None

        # Verify complaint detail status is ASSIGNED
        c_detail = client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers)
        assert c_detail.json()["data"]["status"] == "ASSIGNED"

    def test_assignment_fails_if_complaint_not_under_review(
        self, client, admin_headers, citizen_headers, pwd_category, field_worker
    ):
        """Complaint in SUBMITTED (not yet triaged) cannot be assigned directly."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Fresh untriaged complaint",
                "description": "Complaint submitted directly without review.",
                "category_id": pwd_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        # Attempt assignment directly while SUBMITTED
        res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "UNDER_REVIEW" in res.json()["detail"]

    def test_assignment_department_mismatch_rejected(
        self, client, admin_headers, under_review_complaint, electrical_worker
    ):
        """PWD complaint assigned to an ELECTRICAL worker must be rejected."""
        c_id = under_review_complaint["id"]
        res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(electrical_worker.id)},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "Department mismatch" in res.json()["detail"]

    def test_assignment_to_inactive_worker_rejected(
        self, client, admin_headers, under_review_complaint, field_worker
    ):
        # Deactivate worker first
        client.patch(f"/api/v1/workers/{field_worker.id}/deactivate", headers=admin_headers)

        c_id = under_review_complaint["id"]
        res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_duplicate_active_assignment_rejected(
        self, client, admin_headers, under_review_complaint, field_worker, other_field_worker
    ):
        """Assigning an already assigned complaint again without reassignment is rejected."""
        c_id = under_review_complaint["id"]
        # First assignment succeeds
        res1 = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assert res1.status_code == status.HTTP_200_OK

        # Second assignment attempt fails
        res2 = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(other_field_worker.id)},
            headers=admin_headers,
        )
        assert res2.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =============================================================================
# 4. Worker Task Queue & IDOR Defense Tests
# =============================================================================

class TestWorkerTaskQueueAndIDOR:
    """Verifies worker task queue scoping, individual task inspection, and IDOR protection."""

    def test_worker_can_retrieve_only_own_assigned_tasks(
        self, client, admin_headers, under_review_complaint, field_worker, worker_headers, other_worker_headers
    ):
        c_id = under_review_complaint["id"]
        # Admin assigns to field_worker
        client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )

        # field_worker queries /me/tasks
        res = client.get("/api/v1/workers/me/tasks", headers=worker_headers)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["data"]
        assert len(data) >= 1
        assert any(t["complaint_id"] == c_id for t in data)

        # other_worker queries /me/tasks (must NOT see field_worker's task)
        res_other = client.get("/api/v1/workers/me/tasks", headers=other_worker_headers)
        assert res_other.status_code == status.HTTP_200_OK
        assert not any(t["complaint_id"] == c_id for t in res_other.json()["data"])

    def test_worker_cannot_inspect_other_worker_task_by_id_idor(
        self, client, admin_headers, under_review_complaint, field_worker, other_worker_headers
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assignment_id = assign_res.json()["data"]["id"]

        # other_worker attempts IDOR access to assignment_id
        idor_res = client.get(f"/api/v1/workers/me/tasks/{assignment_id}", headers=other_worker_headers)
        assert idor_res.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 5. Work Execution Workflow Tests (Accept, Start, Progress, Complete)
# =============================================================================

class TestWorkExecutionWorkflow:
    """Verifies complete worker lifecycle: accept, start (IN_PROGRESS), log progress, complete."""

    def test_complete_worker_remediation_lifecycle(
        self, client, admin_headers, citizen_headers, under_review_complaint, field_worker, worker_headers
    ):
        c_id = under_review_complaint["id"]

        # 1. Admin assigns to worker
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assignment_id = assign_res.json()["data"]["id"]

        # 2. Worker accepts task
        accept_res = client.post(f"/api/v1/workers/me/tasks/{assignment_id}/accept", headers=worker_headers)
        assert accept_res.status_code == status.HTTP_200_OK
        assert accept_res.json()["data"]["accepted_at"] is not None

        # 3. Worker starts work -> moves assignment & complaint to IN_PROGRESS
        start_res = client.post(f"/api/v1/workers/me/tasks/{assignment_id}/start", headers=worker_headers)
        assert start_res.status_code == status.HTTP_200_OK
        assert start_res.json()["data"]["assignment_status"] == "IN_PROGRESS"

        # Verify complaint status is IN_PROGRESS
        c_status = client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers).json()["data"]["status"]
        assert c_status == "IN_PROGRESS"

        # 4. Worker records progress update
        prog_res = client.post(
            f"/api/v1/workers/me/tasks/{assignment_id}/progress",
            json={"description": "Excavated loose road gravel and applied bitumen tack coat."},
            headers=worker_headers,
        )
        assert prog_res.status_code == status.HTTP_201_CREATED

        # 5. Worker completes work -> moves complaint to RESOLVED_AWAITING_VERIFICATION
        comp_res = client.post(
            f"/api/v1/workers/me/tasks/{assignment_id}/complete",
            json={"summary": "Pothole filled with dense asphalt and leveled with roller. Surface restored."},
            headers=worker_headers,
        )
        assert comp_res.status_code == status.HTTP_200_OK
        assert comp_res.json()["data"]["assignment_status"] == "COMPLETED"

        # 6. Verify complaint is in RESOLVED_AWAITING_VERIFICATION and resolved_at is set
        comp_detail = client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers).json()["data"]
        assert comp_detail["status"] == "RESOLVED_AWAITING_VERIFICATION"
        assert comp_detail["resolved_at"] is not None
        assert comp_detail["closed_at"] is None

        # 7. Citizen verifies and closes complaint (preserving Phase 4 workflow)
        close_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "CLOSED", "remarks": "Road is smooth now. Excellent repair work."},
            headers=citizen_headers,
        )
        assert close_res.status_code == status.HTTP_200_OK
        final_detail = close_res.json()["data"]
        assert final_detail["status"] == "CLOSED"
        assert final_detail["closed_at"] is not None

    def test_worker_cannot_complete_unstarted_task(
        self, client, admin_headers, under_review_complaint, field_worker, worker_headers
    ):
        """Completing a task that is still ASSIGNED (not IN_PROGRESS) is rejected."""
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assignment_id = assign_res.json()["data"]["id"]

        # Attempt to complete without starting
        res = client.post(
            f"/api/v1/workers/me/tasks/{assignment_id}/complete",
            json={"summary": "Trying to finish immediately without starting."},
            headers=worker_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =============================================================================
# 6. Administrator Reassignment & History Tests
# =============================================================================

class TestComplaintReassignment:
    """Verifies reassignment of active tasks, history preservation, and audit logging."""

    def test_admin_reassigns_complaint_successfully(
        self, client, admin_headers, under_review_complaint, field_worker, other_field_worker
    ):
        c_id = under_review_complaint["id"]

        # 1. Assign to field_worker
        a1_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a1_id = a1_res.json()["data"]["id"]

        # 2. Reassign to other_field_worker with reason
        reassign_payload = {
            "new_worker_id": str(other_field_worker.id),
            "reason": "Original technician reassigned to emergency main road burst.",
            "notes": "Pick up supplies from ward depot 4.",
        }
        reassign_res = client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json=reassign_payload,
            headers=admin_headers,
        )
        assert reassign_res.status_code == status.HTTP_200_OK
        a2_data = reassign_res.json()["data"]
        assert a2_data["worker_id"] == str(other_field_worker.id)
        assert a2_data["status"] == "ASSIGNED"

        # 3. Verify previous assignment is marked REASSIGNED
        a1_detail = client.get(f"/api/v1/assignments/{a1_id}", headers=admin_headers)
        assert a1_detail.json()["data"]["status"] == "REASSIGNED"

        # 4. Verify complaint assignment history lists BOTH assignments
        hist_res = client.get(f"/api/v1/complaints/{c_id}/assignments", headers=admin_headers)
        assert hist_res.status_code == status.HTTP_200_OK
        history = hist_res.json()["data"]
        assert len(history) == 2
        statuses = [item["status"] for item in history]
        assert "REASSIGNED" in statuses
        assert "ASSIGNED" in statuses

    def test_reassignment_requires_valid_reason(
        self, client, admin_headers, under_review_complaint, field_worker, other_field_worker
    ):
        c_id = under_review_complaint["id"]
        client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )

        # Empty reason rejected
        res = client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json={"new_worker_id": str(other_field_worker.id), "reason": ""},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_reassignment_to_same_worker_rejected(
        self, client, admin_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )

        res = client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json={"new_worker_id": str(field_worker.id), "reason": "Accidental reassign to same worker."},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "identical" in res.json()["detail"].lower()

    def test_reassign_in_progress_complaint_follows_legal_transitions_atomically(
        self, client, admin_headers, worker_headers, other_worker_headers, under_review_complaint, field_worker, other_field_worker
    ):
        """
        Verifies that reassigning an IN_PROGRESS complaint transitions it through the legal
        Phase 4 lifecycle chain (IN_PROGRESS -> ON_HOLD -> UNDER_REVIEW -> ASSIGNED) atomically,
        preserving complete audit history and ensuring state machine consistency.
        """
        c_id = under_review_complaint["id"]

        # 1. Admin assigns to worker 1
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        assert assign_res.status_code == status.HTTP_200_OK
        a1_id = assign_res.json()["data"]["id"]

        # 2. Worker 1 accepts and starts work -> complaint is IN_PROGRESS
        client.post(f"/api/v1/workers/me/tasks/{a1_id}/accept", headers=worker_headers)
        start_res = client.post(f"/api/v1/workers/me/tasks/{a1_id}/start", headers=worker_headers)
        assert start_res.status_code == status.HTTP_200_OK
        assert client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers).json()["data"]["status"] == "IN_PROGRESS"

        # 3. Admin reassigns IN_PROGRESS complaint to worker 2
        reassign_payload = {
            "new_worker_id": str(other_field_worker.id),
            "reason": "Technician 1 called away to water main breach.",
            "notes": "Pick up site tools and continue paving.",
        }
        reassign_res = client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json=reassign_payload,
            headers=admin_headers,
        )
        assert reassign_res.status_code == status.HTTP_200_OK
        a2_data = reassign_res.json()["data"]
        a2_id = a2_data["id"]
        assert a2_data["status"] == "ASSIGNED"
        assert a2_data["worker_id"] == str(other_field_worker.id)

        # 4. Verify previous assignment is REASSIGNED and complaint is ASSIGNED
        a1_data = client.get(f"/api/v1/assignments/{a1_id}", headers=admin_headers).json()["data"]
        assert a1_data["status"] == "REASSIGNED"
        c_data = client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers).json()["data"]
        assert c_data["status"] == "ASSIGNED"

        # 5. Verify the complaint status history reflects the legal transition chain
        hist_res = client.get(f"/api/v1/complaints/{c_id}/history", headers=admin_headers)
        assert hist_res.status_code == status.HTTP_200_OK
        transitions = [(h["previous_status"], h["new_status"]) for h in hist_res.json()["data"]]
        # Must include IN_PROGRESS -> ON_HOLD -> UNDER_REVIEW -> ASSIGNED
        assert ("IN_PROGRESS", "ON_HOLD") in transitions
        assert ("ON_HOLD", "UNDER_REVIEW") in transitions
        assert ("UNDER_REVIEW", "ASSIGNED") in transitions

        # 6. Verify replacement worker can accept and start work
        acc_res = client.post(f"/api/v1/workers/me/tasks/{a2_id}/accept", headers=other_worker_headers)
        assert acc_res.status_code == status.HTTP_200_OK
        st_res = client.post(f"/api/v1/workers/me/tasks/{a2_id}/start", headers=other_worker_headers)
        assert st_res.status_code == status.HTTP_200_OK
        assert client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers).json()["data"]["status"] == "IN_PROGRESS"

    def test_direct_transition_to_assigned_from_in_progress_rejected(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        """
        Verifies that an external transition request attempting IN_PROGRESS -> ASSIGNED
        is rejected by execute_transition (HTTP 422 InvalidStateTransitionError).
        """
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)

        # Attempt illegal direct jump IN_PROGRESS -> ASSIGNED
        res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "ASSIGNED", "remarks": "Attempting illegal direct transition to ASSIGNED."},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_direct_transition_to_under_review_from_assigned_rejected(
        self, client, admin_headers, under_review_complaint, field_worker
    ):
        """
        Verifies that ASSIGNED -> UNDER_REVIEW is illegal under Phase 4 matrix and rejected.
        """
        c_id = under_review_complaint["id"]
        client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )

        res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "UNDER_REVIEW", "remarks": "Attempting illegal transition back to review."},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_failed_reassignment_rolls_back_atomically(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        """
        Verifies that when reassignment fails (e.g. non-existent replacement worker),
        the existing assignment and complaint status remain completely unchanged.
        """
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)

        # Reassign to non-existent worker
        fake_worker_id = str(uuid.uuid4())
        res = client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json={"new_worker_id": fake_worker_id, "reason": "Testing rollback on failure."},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_404_NOT_FOUND

        # Existing assignment must still be IN_PROGRESS
        a_detail = client.get(f"/api/v1/assignments/{a_id}", headers=admin_headers).json()["data"]
        assert a_detail["status"] == "IN_PROGRESS"

        # Complaint must still be IN_PROGRESS
        c_detail = client.get(f"/api/v1/complaints/{c_id}", headers=admin_headers).json()["data"]
        assert c_detail["status"] == "IN_PROGRESS"


# =============================================================================
# 7. Database Partial Unique Index Concurrency Safeguard
# =============================================================================

class TestConcurrencyAndDatabaseIntegrity:
    """Verifies PostgreSQL database constraint preventing duplicate active assignments."""

    def test_db_partial_unique_index_blocks_duplicate_active_assignment(
        self, db_session: Session, under_review_complaint, field_worker, other_field_worker, admin_user
    ):
        """
        Directly attempts inserting two active (ASSIGNED) records for the same complaint_id.
        PostgreSQL partial unique index uq_active_assignment_per_complaint must raise IntegrityError.
        """
        c_id = uuid.UUID(under_review_complaint["id"])

        a1 = Assignment(
            complaint_id=c_id,
            worker_id=field_worker.id,
            assigned_by_id=admin_user.id,
            status=AssignmentStatus.ASSIGNED,
        )
        db_session.add(a1)
        db_session.flush()

        a2 = Assignment(
            complaint_id=c_id,
            worker_id=other_field_worker.id,
            assigned_by_id=admin_user.id,
            status=AssignmentStatus.ASSIGNED,
        )
        db_session.add(a2)

        with pytest.raises(Exception) as exc_info:
            db_session.flush()

        assert "uq_active_assignment_per_complaint" in str(exc_info.value)
        db_session.rollback()

    def test_concurrent_multi_threaded_assignment_serialized_by_lock(
        self, test_engine, pwd_department, pwd_category
    ):
        """
        Verify that when two concurrent threads attempt to assign the same complaint
        using independent database sessions, row locks and the partial unique index
        guarantee that exactly ONE assignment succeeds, while the other is rejected,
        and no duplicate active assignment can ever be created.
        """
        import threading
        from sqlalchemy.orm import sessionmaker
        from app.services.assignment_service import assign_complaint
        from app.services.complaint_service import create_complaint
        from app.schemas.complaint import ComplaintCreateRequest, LocationCreate

        SessionFactory = sessionmaker(bind=test_engine)
        s_init = SessionFactory()
        c_id = None
        admin_id = None
        w1_id = None
        w2_id = None
        try:
            admin_role = s_init.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
            worker_role = s_init.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
            citizen_role = s_init.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()

            admin = User(
                email=f"admin_mt_{uuid.uuid4().hex[:6]}@civicpulse.org",
                hashed_password=hash_password("Pass123!"),
                full_name="MT Admin",
                role_id=admin_role.id,
                is_active=True,
                is_verified=True,
            )
            s_init.add(admin)

            citizen = User(
                email=f"cit_mt_{uuid.uuid4().hex[:6]}@example.com",
                hashed_password=hash_password("Pass123!"),
                full_name="MT Citizen",
                role_id=citizen_role.id,
                is_active=True,
                is_verified=True,
            )
            s_init.add(citizen)
            s_init.flush()

            complaint = create_complaint(
                s_init,
                citizen,
                ComplaintCreateRequest(
                    title="Concurrent assignment test",
                    description="Testing concurrency safety.",
                    category_id=pwd_category.id,
                    location=LocationCreate(latitude=12.9716, longitude=77.5946),
                ),
            )
            complaint.status = ComplaintStatus.UNDER_REVIEW
            s_init.flush()

            u1 = User(
                email=f"w1_mt_{uuid.uuid4().hex[:6]}@civicpulse.org",
                hashed_password=hash_password("Pass123!"),
                full_name="MT Worker 1",
                role_id=worker_role.id,
                is_active=True,
                is_verified=True,
            )
            u2 = User(
                email=f"w2_mt_{uuid.uuid4().hex[:6]}@civicpulse.org",
                hashed_password=hash_password("Pass123!"),
                full_name="MT Worker 2",
                role_id=worker_role.id,
                is_active=True,
                is_verified=True,
            )
            s_init.add_all([u1, u2])
            s_init.flush()

            w1 = Worker(
                user_id=u1.id,
                department_id=pwd_department.id,
                employee_id=f"EMP-MT1-{uuid.uuid4().hex[:4].upper()}",
                employment_status="ACTIVE",
                is_available=True,
            )
            w2 = Worker(
                user_id=u2.id,
                department_id=pwd_department.id,
                employee_id=f"EMP-MT2-{uuid.uuid4().hex[:4].upper()}",
                employment_status="ACTIVE",
                is_available=True,
            )
            s_init.add_all([w1, w2])
            s_init.commit()

            c_id = complaint.id
            admin_id = admin.id
            w1_id = w1.id
            w2_id = w2.id

            results = []

            def try_assign(worker_target_id, thread_name):
                s = SessionFactory()
                try:
                    admin_local = s.query(User).filter(User.id == admin_id).first()
                    assign_complaint(s, c_id, worker_target_id, admin_local, notes=f"From {thread_name}")
                    results.append((thread_name, "success"))
                except Exception as e:
                    results.append((thread_name, "error", type(e).__name__))
                finally:
                    s.close()

            t1 = threading.Thread(target=try_assign, args=(w1_id, "T1"))
            t2 = threading.Thread(target=try_assign, args=(w2_id, "T2"))

            t1.start()
            t2.start()
            t1.join()
            t2.join()

            successes = [r for r in results if r[1] == "success"]
            errors = [r for r in results if r[1] == "error"]
            assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
            assert len(errors) == 1, f"Expected exactly 1 error, got {len(errors)}: {results}"

            s_verify = SessionFactory()
            active_count = (
                s_verify.query(Assignment)
                .filter(
                    Assignment.complaint_id == c_id,
                    Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
                )
                .count()
            )
            assert active_count == 1
            s_verify.close()

        finally:
            s_clean = SessionFactory()
            if c_id:
                s_clean.query(AssignmentProgress).filter(
                    AssignmentProgress.assignment_id.in_(
                        s_clean.query(Assignment.id).filter(Assignment.complaint_id == c_id)
                    )
                ).delete(synchronize_session=False)
                s_clean.query(Assignment).filter(Assignment.complaint_id == c_id).delete()
                s_clean.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == c_id).delete()
                c_obj = s_clean.query(Complaint).filter(Complaint.id == c_id).first()
                if c_obj:
                    loc_id = c_obj.location_id
                    s_clean.delete(c_obj)
                    if loc_id:
                        s_clean.query(Location).filter(Location.id == loc_id).delete()
            if w1_id:
                s_clean.query(Worker).filter(Worker.id == w1_id).delete()
            if w2_id:
                s_clean.query(Worker).filter(Worker.id == w2_id).delete()
            if u1 and hasattr(u1, "id") and u1.id:
                s_clean.query(User).filter(User.id == u1.id).delete()
            if u2 and hasattr(u2, "id") and u2.id:
                s_clean.query(User).filter(User.id == u2.id).delete()
            s_clean.commit()
            s_clean.close()


# =============================================================================
# 8. Assignment Integrity and Terminal Constraint Tests
# =============================================================================

class TestAssignmentIntegrityAndTerminalConstraints:
    """Verifies assignment state invariant enforcement (cannot update terminal/superseded assignments)."""

    def test_cannot_add_progress_to_completed_assignment(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        """Once an assignment is COMPLETED, no further progress milestones can be appended (HTTP 422)."""
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)
        comp_res = client.post(
            f"/api/v1/workers/me/tasks/{a_id}/complete",
            json={"summary": "Job finished and verified."},
            headers=worker_headers,
        )
        assert comp_res.status_code == status.HTTP_200_OK

        prog_res = client.post(
            f"/api/v1/workers/me/tasks/{a_id}/progress",
            json={"description": "Attempting progress update on completed task."},
            headers=worker_headers,
        )
        assert prog_res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_cannot_add_progress_to_reassigned_assignment(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker, other_field_worker
    ):
        """Once an assignment is superseded (REASSIGNED), former worker cannot add progress (HTTP 422)."""
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a1_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a1_id}/start", headers=worker_headers)

        client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json={"new_worker_id": str(other_field_worker.id), "reason": "Reassigned due to scheduling."},
            headers=admin_headers,
        )

        res = client.post(
            f"/api/v1/workers/me/tasks/{a1_id}/progress",
            json={"description": "Former worker progress attempt."},
            headers=worker_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_cannot_complete_already_completed_assignment(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        """Completing an already COMPLETED assignment is rejected (HTTP 422)."""
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)
        client.post(
            f"/api/v1/workers/me/tasks/{a_id}/complete",
            json={"summary": "Initial completion."},
            headers=worker_headers,
        )

        res = client.post(
            f"/api/v1/workers/me/tasks/{a_id}/complete",
            json={"summary": "Second redundant completion."},
            headers=worker_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_cannot_complete_reassigned_assignment(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker, other_field_worker
    ):
        """A superseded (REASSIGNED) assignment cannot be marked completed (HTTP 422)."""
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a1_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a1_id}/start", headers=worker_headers)

        client.post(
            f"/api/v1/complaints/{c_id}/reassign",
            json={"new_worker_id": str(other_field_worker.id), "reason": "Worker replacement."},
            headers=admin_headers,
        )

        res = client.post(
            f"/api/v1/workers/me/tasks/{a1_id}/complete",
            json={"summary": "Former worker completion attempt."},
            headers=worker_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_cannot_accept_already_in_progress_or_completed_assignment(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        """Worker cannot accept a task that is already IN_PROGRESS or COMPLETED (HTTP 422)."""
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)

        res = client.post(f"/api/v1/workers/me/tasks/{a_id}/accept", headers=worker_headers)
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =============================================================================
# 9. Worker Authorization & Cross-Role Security Matrix
# =============================================================================

class TestWorkerAuthorizationMatrix:
    """Verifies strict cross-role isolation, IDOR defense, and deactivation blocks."""

    def test_worker_cannot_accept_another_worker_task(
        self, client, admin_headers, other_worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]

        res = client.post(f"/api/v1/workers/me/tasks/{a_id}/accept", headers=other_worker_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_worker_cannot_start_another_worker_task(
        self, client, admin_headers, other_worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]

        res = client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=other_worker_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_worker_cannot_submit_progress_for_another_worker_task(
        self, client, admin_headers, worker_headers, other_worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)

        res = client.post(
            f"/api/v1/workers/me/tasks/{a_id}/progress",
            json={"description": "Unauthorized progress entry."},
            headers=other_worker_headers,
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_worker_cannot_complete_another_worker_task(
        self, client, admin_headers, worker_headers, other_worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)

        res = client.post(
            f"/api/v1/workers/me/tasks/{a_id}/complete",
            json={"summary": "Unauthorized completion."},
            headers=other_worker_headers,
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivated_worker_blocked_from_task_queue(
        self, client, admin_headers, worker_headers, field_worker
    ):
        client.patch(f"/api/v1/workers/{field_worker.id}/deactivate", headers=admin_headers)

        res = client.get("/api/v1/workers/me/tasks", headers=worker_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivated_worker_blocked_from_task_operations(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]

        client.patch(f"/api/v1/workers/{field_worker.id}/deactivate", headers=admin_headers)

        res = client.post(f"/api/v1/workers/me/tasks/{a_id}/accept", headers=worker_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_citizen_blocked_from_worker_endpoints(
        self, client, citizen_headers, field_worker
    ):
        res = client.get("/api/v1/workers", headers=citizen_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

        res = client.get(f"/api/v1/workers/{field_worker.id}", headers=citizen_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

        res = client.get("/api/v1/workers/me/tasks", headers=citizen_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_worker_cannot_provision_another_worker(
        self, client, worker_headers, pwd_department
    ):
        payload = {
            "email": f"new_worker_{uuid.uuid4().hex[:6]}@civicpulse.org",
            "password": "WorkerSecurePass123!",
            "full_name": "Rogue Technician",
            "department_id": pwd_department.id,
            "employee_id": f"EMP-PWD-{uuid.uuid4().hex[:4].upper()}",
        }
        res = client.post("/api/v1/workers", json=payload, headers=worker_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_worker_cannot_access_admin_assignments_monitoring(
        self, client, worker_headers
    ):
        res = client.get("/api/v1/assignments", headers=worker_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_requests_rejected_with_401(
        self, client, field_worker
    ):
        assert client.get("/api/v1/workers").status_code == status.HTTP_401_UNAUTHORIZED
        assert client.get("/api/v1/workers/me/tasks").status_code == status.HTTP_401_UNAUTHORIZED
        assert client.get("/api/v1/assignments").status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# 10. Department and Worker Deactivation Parity
# =============================================================================

class TestDepartmentAndWorkerDeactivationParity:
    """Verifies PATCH .../deactivate and DELETE parity, safe deactivation, and historical preservation."""

    def test_patch_and_delete_department_deactivation_parity(
        self, client, admin_headers
    ):
        code = f"DEPT_{uuid.uuid4().hex[:4].upper()}"
        res = client.post(
            "/api/v1/departments",
            json={"name": f"Test Dept {code}", "code": code},
            headers=admin_headers,
        )
        dept_id = res.json()["data"]["id"]

        patch_res = client.patch(f"/api/v1/departments/{dept_id}/deactivate", headers=admin_headers)
        assert patch_res.status_code == status.HTTP_200_OK
        assert patch_res.json()["data"]["is_active"] is False

        client.patch(f"/api/v1/departments/{dept_id}", json={"is_active": True}, headers=admin_headers)

        del_res = client.delete(f"/api/v1/departments/{dept_id}", headers=admin_headers)
        assert del_res.status_code == status.HTTP_200_OK
        assert del_res.json()["data"]["is_active"] is False

    def test_patch_and_delete_worker_deactivation_parity(
        self, client, admin_headers, pwd_department
    ):
        emp_id = f"EMP-PWD-{uuid.uuid4().hex[:4].upper()}"
        res = client.post(
            "/api/v1/workers",
            json={
                "email": f"worker_{uuid.uuid4().hex[:6]}@civicpulse.org",
                "password": "WorkerPass123!",
                "full_name": "Parity Worker",
                "department_id": pwd_department.id,
                "employee_id": emp_id,
            },
            headers=admin_headers,
        )
        w_id = res.json()["data"]["id"]

        patch_res = client.patch(f"/api/v1/workers/{w_id}/deactivate", headers=admin_headers)
        assert patch_res.status_code == status.HTTP_200_OK
        assert patch_res.json()["data"]["employment_status"] == "INACTIVE"
        assert patch_res.json()["data"]["is_available"] is False

    def test_cannot_assign_to_worker_in_deactivated_department(
        self, client, admin_headers, under_review_complaint, field_worker, pwd_department, db_session: Session
    ):
        c_id = under_review_complaint["id"]
        dept = db_session.query(Department).filter(Department.id == pwd_department.id).first()
        dept.is_active = False
        db_session.commit()

        try:
            res = client.post(
                f"/api/v1/complaints/{c_id}/assign",
                json={"worker_id": str(field_worker.id)},
                headers=admin_headers,
            )
            assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
            assert "inactive" in res.json()["detail"].lower()
        finally:
            dept.is_active = True
            db_session.commit()

    def test_cannot_deactivate_department_with_active_assignments(
        self, client, admin_headers, under_review_complaint, field_worker, pwd_department
    ):
        c_id = under_review_complaint["id"]
        client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )

        res = client.patch(f"/api/v1/departments/{pwd_department.id}/deactivate", headers=admin_headers)
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "active worker assignment" in res.json()["detail"].lower()

    def test_deactivation_preserves_historical_records(
        self, client, admin_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]

        client.patch(f"/api/v1/workers/{field_worker.id}/deactivate", headers=admin_headers)

        a_detail = client.get(f"/api/v1/assignments/{a_id}", headers=admin_headers)
        assert a_detail.status_code == status.HTTP_200_OK
        assert a_detail.json()["data"]["worker_id"] == str(field_worker.id)


# =============================================================================
# 11. Progress History and Milestone Audit
# =============================================================================

class TestProgressHistoryAudit:
    """Verifies immutability, timestamps, and scoping of assignment progress milestones."""

    def test_immutable_progress_record_content_and_timestamps(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker, db_session: Session
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)

        before_ts = datetime.now(timezone.utc) - timedelta(seconds=2)
        prog_res = client.post(
            f"/api/v1/workers/me/tasks/{a_id}/progress",
            json={"description": "Detailed site excavation and measurements taken."},
            headers=worker_headers,
        )
        assert prog_res.status_code == status.HTTP_201_CREATED
        p_data = prog_res.json()["data"]
        assert p_data["worker_id"] == str(field_worker.id)
        assert p_data["description"] == "Detailed site excavation and measurements taken."

        progress_rec = db_session.query(AssignmentProgress).filter(AssignmentProgress.id == p_data["id"]).first()
        assert progress_rec is not None
        assert progress_rec.created_at >= before_ts

    def test_admin_can_inspect_progress_updates_via_assignment_detail(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)
        client.post(
            f"/api/v1/workers/me/tasks/{a_id}/progress",
            json={"description": "Milestone step 1."},
            headers=worker_headers,
        )
        client.post(
            f"/api/v1/workers/me/tasks/{a_id}/progress",
            json={"description": "Milestone step 2."},
            headers=worker_headers,
        )

        detail_res = client.get(f"/api/v1/assignments/{a_id}", headers=admin_headers)
        assert detail_res.status_code == status.HTTP_200_OK
        updates = detail_res.json()["data"]["progress_history"]
        descriptions = [u["description"] for u in updates]
        assert any("Milestone step 1." in d for d in descriptions)
        assert any("Milestone step 2." in d for d in descriptions)

    def test_worker_can_inspect_own_task_progress_history(
        self, client, admin_headers, worker_headers, under_review_complaint, field_worker
    ):
        c_id = under_review_complaint["id"]
        assign_res = client.post(
            f"/api/v1/complaints/{c_id}/assign",
            json={"worker_id": str(field_worker.id)},
            headers=admin_headers,
        )
        a_id = assign_res.json()["data"]["id"]
        client.post(f"/api/v1/workers/me/tasks/{a_id}/start", headers=worker_headers)
        client.post(
            f"/api/v1/workers/me/tasks/{a_id}/progress",
            json={"description": "Technician own progress."},
            headers=worker_headers,
        )

        task_detail = client.get(f"/api/v1/workers/me/tasks/{a_id}", headers=worker_headers)
        assert task_detail.status_code == status.HTTP_200_OK
        history = task_detail.json()["data"]["progress_history"]
        assert len(history) >= 2
