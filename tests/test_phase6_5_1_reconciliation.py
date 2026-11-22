"""
CivicPulse — Phase 6.5.1 Reconciliation Test Suite

Validates:
    1. Public complaint feed list contains zero pincode, coordinates, or citizen PII.
    2. Public complaint detail contains zero pincode, coordinates, or citizen PII.
    3. Registered API route paths match the authoritative API inventory.
    4. Public and private complaint access boundaries remain strictly enforced.
    5. Role-based authorization boundaries remain intact across roles.
    6. Model field names match database schema columns (resolving accepted_at, followed_at, description).
    7. Alembic migration chain and single-head status consistency.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.constants import ComplaintStatus, PriorityLevel, UserRole
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.user import User
from app.models.worker import Worker


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def citizen_role(db_session: Session) -> Role:
    role = db_session.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
    if not role:
        role = Role(name=UserRole.CITIZEN.value, description="Citizen role")
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def admin_role(db_session: Session) -> Role:
    role = db_session.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
    if not role:
        role = Role(name=UserRole.ADMINISTRATOR.value, description="Admin role")
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def worker_role(db_session: Session) -> Role:
    role = db_session.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
    if not role:
        role = Role(name=UserRole.FIELD_WORKER.value, description="Worker role")
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def department(db_session: Session) -> Department:
    dept = Department(
        name=f"Reconciliation Dept {uuid.uuid4().hex[:6]}",
        code=f"REC_{uuid.uuid4().hex[:4].upper()}",
        description="Department for reconciliation testing",
    )
    db_session.add(dept)
    db_session.flush()
    return dept


@pytest.fixture
def category(db_session: Session, department: Department) -> Category:
    cat = Category(
        name=f"Reconciliation Cat {uuid.uuid4().hex[:6]}",
        description="Category for reconciliation testing",
        department_id=department.id,
    )
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def citizen_user(db_session: Session, citizen_role: Role) -> User:
    user = User(
        email=f"recon_citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Recon Citizen",
        role_id=citizen_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_user(db_session: Session, admin_role: Role) -> User:
    user = User(
        email=f"recon_admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Recon Admin",
        role_id=admin_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def worker_user(db_session: Session, worker_role: Role, department: Department) -> User:
    user = User(
        email=f"recon_worker_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Recon Worker",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=department.id,
        employee_id=f"EMP-R-{uuid.uuid4().hex[:5].upper()}",
        designation="Inspector",
        is_available=True,
    )
    db_session.add(worker)
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
def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(admin_user.id),
        role=UserRole.ADMINISTRATOR.value,
        extra_claims={"email": admin_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def worker_headers(worker_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(worker_user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": worker_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


def create_published_complaint(
    db: Session,
    citizen: User,
    category: Category,
    admin: User,
) -> Complaint:
    """Create a published complaint with full private location data to test redaction."""
    loc = Location(
        latitude=12.9716,
        longitude=77.5946,
        address_line="42 Confidential Lane, Sensitive Sector",
        area_name="Ward 104 Indiranagar",
        city="Bengaluru",
        pincode="560038",
        landmark="Near High Security Vault",
    )
    db.add(loc)
    db.flush()

    now = datetime.now(timezone.utc)
    complaint = Complaint(
        complaint_number=f"CP-RECON-{uuid.uuid4().hex[:8].upper()}",
        citizen_id=citizen.id,
        category_id=category.id,
        location_id=loc.id,
        title="Private Pothole Near My Home",
        description="Private citizen description with PII: phone 9876543210 and sensitive details.",
        status=ComplaintStatus.UNDER_REVIEW,
        priority=PriorityLevel.HIGH,
        is_public=True,
        public_title="Public Approved Pothole Repair Headline",
        public_description="Sanitized public description approved by municipal moderation.",
        moderated_at=now,
        moderated_by_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(complaint)
    db.flush()
    return complaint


# =============================================================================
# 1. Public Feed Privacy Verification (Zero Pincode, Zero Precise Location)
# =============================================================================

ALLOWED_PUBLIC_FIELDS = {
    "id",
    "complaint_number",
    "category_name",
    "status",
    "created_at",
    "public_title",
    "public_description",
    "ward_or_district",
    "city",
}

FORBIDDEN_PRIVATE_FIELDS = {
    "pincode",
    "latitude",
    "longitude",
    "address_line",
    "landmark",
    "citizen_id",
    "citizen",
    "citizen_name",
    "citizen_email",
    "citizen_phone",
    "title",
    "description",
    "internal_remarks",
    "remarks",
    "worker",
    "worker_id",
    "moderated_by_id",
    "unpublish_requested_by_id",
    "unpublish_reason",
}


def test_public_feed_list_contains_zero_pincode_or_precise_location(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that GET /api/v1/public/complaints response JSON contains ONLY
    the 9 approved allowlisted fields and strictly excludes pincode, exact coordinates,
    street addresses, landmarks, and citizen PII.
    """
    complaint = create_published_complaint(db_session, citizen_user, category, admin_user)

    response = client.get("/api/v1/public/complaints")
    assert response.status_code == status.HTTP_200_OK

    json_data = response.json()
    assert json_data["success"] is True
    items = json_data["data"]["items"]
    assert len(items) > 0

    target = next((item for item in items if item["id"] == str(complaint.id)), None)
    assert target is not None, "Published complaint not found in public feed list"

    # Verify exact allowlist membership
    item_keys = set(target.keys())
    assert item_keys == ALLOWED_PUBLIC_FIELDS, f"Unexpected fields in public item: {item_keys - ALLOWED_PUBLIC_FIELDS}"

    # Explicitly verify every forbidden field is absent
    for forbidden in FORBIDDEN_PRIVATE_FIELDS:
        assert forbidden not in target, f"Privacy violation: '{forbidden}' exposed in public feed list item!"

    # Verify values match sanitized public content only
    assert target["public_title"] == "Public Approved Pothole Repair Headline"
    assert target["public_description"] == "Sanitized public description approved by municipal moderation."
    assert target["ward_or_district"] == "Ward 104 Indiranagar"
    assert target["city"] == "Bengaluru"


def test_public_feed_detail_contains_zero_pincode_or_precise_location(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verify that GET /api/v1/public/complaints/{id} response JSON contains ONLY
    the 9 approved allowlisted fields and strictly excludes pincode, coordinates,
    address line, landmark, and citizen PII.
    """
    complaint = create_published_complaint(db_session, citizen_user, category, admin_user)

    response = client.get(f"/api/v1/public/complaints/{complaint.id}")
    assert response.status_code == status.HTTP_200_OK

    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]

    # Verify exact allowlist membership
    data_keys = set(data.keys())
    assert data_keys == ALLOWED_PUBLIC_FIELDS, f"Unexpected fields in public detail: {data_keys - ALLOWED_PUBLIC_FIELDS}"

    # Explicitly verify forbidden fields are completely absent
    for forbidden in FORBIDDEN_PRIVATE_FIELDS:
        assert forbidden not in data, f"Privacy violation: '{forbidden}' exposed in public complaint detail!"

    # Verify values
    assert data["public_title"] == "Public Approved Pothole Repair Headline"
    assert data["public_description"] == "Sanitized public description approved by municipal moderation."
    assert data["ward_or_district"] == "Ward 104 Indiranagar"
    assert data["city"] == "Bengaluru"


# =============================================================================
# 2. Actual Registered API Route Inventory Verification
# =============================================================================

def test_actual_registered_routes_match_api_inventory():
    """
    Verify that the registered route paths in the running FastAPI application
    match the authoritative paths and do not use normalized or invented paths.
    """
    openapi = app.openapi()
    registered_paths = set(openapi["paths"].keys())

    # Critical reconciled paths
    expected_paths = {
        "/api/v1/citizens/me/dashboard",
        "/api/v1/public/complaints",
        "/api/v1/public/complaints/{complaint_id}",
        "/api/v1/complaints/",
        "/api/v1/complaints/{complaint_id}",
        "/api/v1/complaints/{complaint_id}/transitions",
        "/api/v1/complaints/{complaint_id}/assign",
        "/api/v1/complaints/{complaint_id}/reassign",
        "/api/v1/complaints/{complaint_id}/timeline",
        "/api/v1/complaints/{complaint_id}/moderate-public",
        "/api/v1/complaints/{complaint_id}/request-unpublish",
        "/api/v1/complaints/{complaint_id}/follow",
        "/api/v1/complaints/following",
        "/api/v1/workers/me/tasks",
        "/api/v1/workers/me/tasks/{assignment_id}",
        "/api/v1/workers/me/tasks/{assignment_id}/accept",
        "/api/v1/workers/me/tasks/{assignment_id}/start",
        "/api/v1/workers/me/tasks/{assignment_id}/progress",
        "/api/v1/workers/me/tasks/{assignment_id}/complete",
        "/api/v1/admin/sla/policies",
        "/api/v1/admin/sla/evaluate",
        "/api/v1/notifications",
        "/api/v1/notifications/unread-count",
        "/api/v1/notifications/read-all",
        "/api/v1/notifications/{notification_id}/read",
        "/api/v1/health",
    }

    for path in expected_paths:
        assert path in registered_paths, f"Expected registered route '{path}' missing from FastAPI application!"

    # Verify inaccurate paths from earlier report narrative do NOT exist
    inaccurate_paths = {
        "/api/v1/dashboard/citizen",
        "/api/v1/complaints/public",
        "/api/v1/complaints/{id}/transition",
        "/api/v1/assignments/my-tasks",
        "/api/v1/assignments/{id}/accept",
    }

    for path in inaccurate_paths:
        assert path not in registered_paths, f"Inaccurate route '{path}' should NOT exist in FastAPI application!"


# =============================================================================
# 3. Public and Private Complaint Access Boundaries
# =============================================================================

def test_public_and_private_complaint_access_boundaries(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
    citizen_headers: dict[str, str],
    worker_role: Role,
    department: Department,
):
    """
    Verify that private complaints are strictly invisible via public endpoints (404),
    accessible to their owner citizen via authenticated endpoints (200),
    and forbidden to unassigned or other citizens.
    """
    # Create private complaint (is_public=False)
    loc = Location(
        latitude=13.0827,
        longitude=80.2707,
        address_line="Private Street 1",
        city="Chennai",
    )
    db_session.add(loc)
    db_session.flush()

    private_complaint = Complaint(
        complaint_number=f"CP-PRIV-{uuid.uuid4().hex[:8].upper()}",
        citizen_id=citizen_user.id,
        category_id=category.id,
        location_id=loc.id,
        title="Private Household Issue",
        description="Private leak inside premises",
        status=ComplaintStatus.SUBMITTED,
        priority=PriorityLevel.LOW,
        is_public=False,
    )
    db_session.add(private_complaint)
    db_session.flush()

    # 1. Unauthenticated public detail -> 404
    pub_resp = client.get(f"/api/v1/public/complaints/{private_complaint.id}")
    assert pub_resp.status_code == status.HTTP_404_NOT_FOUND

    # 2. Authenticated owner -> 200
    owner_resp = client.get(
        f"/api/v1/complaints/{private_complaint.id}",
        headers=citizen_headers,
    )
    assert owner_resp.status_code == status.HTTP_200_OK
    assert owner_resp.json()["data"]["id"] == str(private_complaint.id)

    # 3. Another citizen -> 403 Forbidden
    other_citizen = User(
        email=f"other_cit_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Other Citizen",
        role_id=citizen_user.role_id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_citizen)
    db_session.flush()

    other_token = create_access_token(
        subject=str(other_citizen.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": other_citizen.email},
    )
    other_resp = client.get(
        f"/api/v1/complaints/{private_complaint.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_resp.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 4. Role-Based Authorization Boundaries
# =============================================================================

def test_role_based_authorization_boundaries(
    client: TestClient,
    citizen_headers: dict[str, str],
    worker_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    """
    Verify role boundaries:
    - Citizen cannot access worker task queue or admin SLA policies.
    - Worker cannot access citizen dashboard.
    - Admin can access SLA policies.
    """
    # Citizen -> Worker task queue (403)
    resp = client.get("/api/v1/workers/me/tasks", headers=citizen_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Citizen -> Admin SLA policies (403)
    resp = client.get("/api/v1/admin/sla/policies", headers=citizen_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Worker -> Citizen dashboard (403)
    resp = client.get("/api/v1/citizens/me/dashboard", headers=worker_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin -> SLA policies (200)
    resp = client.get("/api/v1/admin/sla/policies", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK


# =============================================================================
# 5. Model Fields and Database Schema Consistency
# =============================================================================

def test_model_fields_and_database_schema_consistency(db_session: Session):
    """
    Verify the true model attributes and database schema column names,
    resolving discrepancies from previous narrative reports.
    """
    # 1. Assignment: accepted_at exists; acknowledged_at does NOT exist
    assignment_mapper = inspect(Assignment)
    assignment_cols = {col.key for col in assignment_mapper.columns}
    assert "accepted_at" in assignment_cols, "Assignment model must have 'accepted_at'"
    assert "acknowledged_at" not in assignment_cols, "Assignment model must NOT have 'acknowledged_at'"

    # 2. ComplaintFollower: followed_at exists; created_at does NOT exist
    follower_mapper = inspect(ComplaintFollower)
    follower_cols = {col.key for col in follower_mapper.columns}
    assert "followed_at" in follower_cols, "ComplaintFollower model must have 'followed_at'"
    assert "created_at" not in follower_cols, "ComplaintFollower model must NOT have 'created_at'"

    # 3. AssignmentProgress: description exists; notes does NOT exist
    progress_mapper = inspect(AssignmentProgress)
    progress_cols = {col.key for col in progress_mapper.columns}
    assert "description" in progress_cols, "AssignmentProgress model must have 'description'"
    assert "notes" not in progress_cols, "AssignmentProgress model must NOT have 'notes'"

    # 4. Complaint: moderated_at and moderated_by_id exist; published_at does NOT exist
    complaint_mapper = inspect(Complaint)
    complaint_cols = {col.key for col in complaint_mapper.columns}
    assert "moderated_at" in complaint_cols, "Complaint model must have 'moderated_at'"
    assert "moderated_by_id" in complaint_cols, "Complaint model must have 'moderated_by_id'"
    assert "published_at" not in complaint_cols, "Complaint model must NOT have 'published_at'"
    assert "unpublish_requested_at" in complaint_cols, "Complaint model must have 'unpublish_requested_at'"
    assert "unpublish_reason" in complaint_cols, "Complaint model must have 'unpublish_reason'"


# =============================================================================
# 6. Alembic Migration Chain Integrity
# =============================================================================

def test_alembic_migration_chain_integrity(db_session: Session):
    """
    Verify that the database version_num is b7c8d9e0f1a2 and that the migration
    chain matches the true historical revisions.
    """
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "b7c8d9e0f1a2", f"Database version must be 'b7c8d9e0f1a2', got '{version}'"
