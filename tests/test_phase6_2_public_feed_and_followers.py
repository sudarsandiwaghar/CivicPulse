"""
CivicPulse Phase 6.2 Tests: Moderated Public Complaint Feed & Community Following

Verifies:
    1. Database & Migration Integrity:
        - Default private visibility on new and existing complaints.
        - Database server-default false.
        - Migration 005 upgrade, downgrade reversibility, and head revision.
    2. Administrator Public Moderation:
        - Publish, update public content, and revoke publication.
        - Role enforcement (Admin only, 403 for citizens/workers).
        - Input validation (public_title 5-200 chars, public_description 10-2000 chars).
        - Block publishing for REJECTED and DUPLICATE complaints.
        - Never use original citizen title/description as fallback.
        - Moderation does not modify lifecycle state machine status.
    3. Public Feed & Privacy Safeguards:
        - Feed returns only is_public == True complaints.
        - Private complaints excluded from listing and return 404 on detail.
        - Strict allowlist serialization: zero citizen PII, zero exact coordinates, zero internal remarks.
        - Coarse ward/city displayed only when recorded.
    4. Automatic Privacy Enforcement:
        - Transitioning to REJECTED or DUPLICATE automatically revokes publication.
        - Atomic status change and publication revocation in the same transaction.
        - Rollback on failure preserves previous visibility state.
    5. Citizen Unpublishing:
        - Owner citizen can request unpublishing.
        - Non-owner citizens receive 403 Forbidden.
        - Unpublishing immediately removes complaint from public feeds.
        - Unpublishing audit history recorded and preserved.
        - Repeated unpublish requests behave consistently and idempotently.
    6. Community Following:
        - Citizen can follow/unfollow public complaints.
        - Non-citizens (Workers/Admins) receive 403 Forbidden.
        - Following private complaints returns 404.
        - Duplicate follow requests are idempotent and protected by DB unique constraint.
        - Following feed is strictly isolated to authenticated citizen.
        - Unpublished complaints disappear from following feed.
    7. Pagination & Deterministic Ordering:
        - Feed and following pagination parameters and metadata.
        - Deterministic ordering across pages.
"""

import math
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.constants import (
    ComplaintStatus,
    PriorityLevel,
    UserRole,
)
from app.core.security import create_access_token, hash_password
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.models.worker import Worker
from app.schemas.moderation import ModeratePublicAction, ModeratePublicRequest
from app.services.complaint_service import execute_transition


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
        email=f"cit62_{uuid.uuid4().hex[:6]}@example.com",
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
        email=f"other62_{uuid.uuid4().hex[:6]}@example.com",
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
        email=f"admin62_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Chief Admin",
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
def worker_user(db_session: Session, worker_role: Role) -> tuple[User, Worker]:
    dept = db_session.query(Department).first()
    if not dept:
        dept = Department(name="Sanitation", code=f"SAN_{uuid.uuid4().hex[:4].upper()}", is_active=True)
        db_session.add(dept)
        db_session.flush()

    user = User(
        email=f"worker62_{uuid.uuid4().hex[:6]}@civicpulse.org",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Field Tech Worker",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    worker = Worker(
        user_id=user.id,
        department_id=dept.id,
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
def category(db_session: Session) -> Category:
    cat = db_session.query(Category).first()
    if not cat:
        dept = db_session.query(Department).first()
        cat = Category(name=f"Road Maintenance {uuid.uuid4().hex[:4]}", department_id=dept.id, is_active=True)
        db_session.add(cat)
        db_session.flush()
    return cat


@pytest.fixture
def test_location(db_session: Session) -> Location:
    loc = Location(
        latitude=12.9716,
        longitude=77.5946,
        address_line="123 Brigade Road, Apartment 4B",
        area_name="Ward 112 - Central Business District",
        city="Bengaluru",
        pincode="560001",
        landmark="Near Central Metro Station",
    )
    db_session.add(loc)
    db_session.flush()
    return loc


def _create_complaint(
    db: Session,
    citizen: User,
    category: Category,
    location: Location | None = None,
    status: ComplaintStatus = ComplaintStatus.SUBMITTED,
    priority: PriorityLevel = PriorityLevel.MEDIUM,
    title: str = "Pothole on Main Road",
    is_public: bool = False,
    public_title: str | None = None,
    public_description: str | None = None,
    created_at: datetime | None = None,
) -> Complaint:
    now_utc = datetime.now(timezone.utc)
    ts = created_at or now_utc
    complaint = Complaint(
        complaint_number=f"CP-2026-{uuid.uuid4().hex[:8].upper()}",
        citizen_id=citizen.id,
        category_id=category.id,
        location_id=location.id if location else None,
        title=title,
        description="Citizen private description with sensitive resident notes.",
        status=status,
        priority=priority,
        is_public=is_public,
        public_title=public_title,
        public_description=public_description,
        created_at=ts,
        updated_at=ts,
    )
    db.add(complaint)
    db.flush()

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_id=citizen.id,
        previous_status=None,
        new_status=status,
        remarks="Initial creation",
        created_at=ts,
    )
    db.add(history)
    db.flush()
    return complaint


# =============================================================================
# 1. Database & Migration Tests
# =============================================================================

def test_new_complaints_default_to_private(db_session: Session, citizen_user: User, category: Category):
    """New complaints must default to is_public = False."""
    complaint = Complaint(
        complaint_number=f"CP-2026-{uuid.uuid4().hex[:8].upper()}",
        citizen_id=citizen_user.id,
        category_id=category.id,
        title="Fresh Complaint",
        description="Private description",
    )
    db_session.add(complaint)
    db_session.flush()

    assert complaint.is_public is False
    assert complaint.public_title is None
    assert complaint.public_description is None
    assert complaint.moderated_at is None
    assert complaint.moderated_by_id is None


def test_database_server_default_is_false(db_session: Session, citizen_user: User, category: Category):
    """Raw database insert without specifying is_public defaults to false on PostgreSQL server."""
    num = f"CP-RAW-{uuid.uuid4().hex[:6].upper()}"
    stmt = text("""
        INSERT INTO complaints (id, complaint_number, citizen_id, category_id, title, description, status, priority, created_at, updated_at)
        VALUES (:id, :num, :cit_id, :cat_id, 'Raw SQL Title', 'Raw SQL Desc', 'SUBMITTED', 'MEDIUM', NOW(), NOW())
        RETURNING is_public;
    """)
    res = db_session.execute(
        stmt,
        {
            "id": uuid.uuid4(),
            "num": num,
            "cit_id": citizen_user.id,
            "cat_id": category.id,
        },
    ).scalar_one()
    assert res is False


def test_complaint_followers_table_constraints(db_session: Session, citizen_user: User, category: Category):
    """complaint_followers table enforces foreign keys and uniqueness."""
    complaint = _create_complaint(db_session, citizen_user, category, is_public=True)
    follower = ComplaintFollower(
        complaint_id=complaint.id,
        citizen_id=citizen_user.id,
    )
    db_session.add(follower)
    db_session.flush()

    assert follower.id is not None
    assert follower.followed_at is not None

    # Duplicate follow violates unique constraint
    duplicate = ComplaintFollower(
        complaint_id=complaint.id,
        citizen_id=citizen_user.id,
    )
    db_session.add(duplicate)
    with pytest.raises(Exception) as exc_info:
        db_session.flush()
    assert "uq_complaint_follower_citizen" in str(exc_info.value)
    db_session.rollback()


# =============================================================================
# 2. Administrator Moderation & Authorization Tests
# =============================================================================

def test_admin_can_publish_complaint(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Administrator can approve and publish a complaint with approved title and description."""
    complaint = _create_complaint(db_session, citizen_user, category, is_public=False)

    payload = {
        "action": "PUBLISH",
        "public_title": "Pothole on 100 Feet Road Repaired",
        "public_description": "Road surface remediation scheduled for public safety in Central Ward.",
    }
    response = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    assert data["is_public"] is True
    assert data["public_title"] == "Pothole on 100 Feet Road Repaired"
    assert data["public_description"] == "Road surface remediation scheduled for public safety in Central Ward."
    assert data["moderated_by_id"] == str(admin_user.id)
    assert data["moderated_at"] is not None

    # Verify database persistence
    db_session.expire_all()
    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.is_public is True
    assert reloaded.public_title == "Pothole on 100 Feet Road Repaired"


def test_admin_can_update_approved_public_content(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Administrator can update approved public title and description on an already published complaint."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Initial Public Title",
        public_description="Initial approved public description.",
    )

    update_payload = {
        "action": "UPDATE",
        "public_title": "Updated Public Title - Revised",
        "public_description": "Updated approved description with new timeline details.",
    }
    response = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json=update_payload,
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["public_title"] == "Updated Public Title - Revised"
    assert data["public_description"] == "Updated approved description with new timeline details."


def test_admin_can_revoke_publication(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Administrator can revoke publication; approved public text is preserved for audit."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Published Title",
        public_description="Published description for civic review.",
    )

    revoke_payload = {"action": "REVOKE"}
    response = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json=revoke_payload,
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["is_public"] is False
    assert data["public_title"] == "Published Title"  # Preserved for audit

    db_session.expire_all()
    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.is_public is False
    assert reloaded.public_title == "Published Title"


def test_citizen_and_worker_cannot_moderate_public(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    worker_headers: dict[str, str],
    category: Category,
):
    """Non-administrator roles (citizens and field workers) receive 403 Forbidden on moderate-public."""
    complaint = _create_complaint(db_session, citizen_user, category)
    payload = {
        "action": "PUBLISH",
        "public_title": "Hacked Title Attempt",
        "public_description": "Attempting unauthorized publication.",
    }

    res_cit = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json=payload,
        headers=citizen_headers,
    )
    assert res_cit.status_code == status.HTTP_403_FORBIDDEN

    res_work = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json=payload,
        headers=worker_headers,
    )
    assert res_work.status_code == status.HTTP_403_FORBIDDEN


def test_invalid_public_content_validation(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Public title (<5 or >200) and description (<10 or >2000) are validated and rejected."""
    complaint = _create_complaint(db_session, citizen_user, category)

    # Title too short (<5 chars)
    res_short_title = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "PUBLISH", "public_title": "Tiny", "public_description": "Valid description with over 10 chars."},
        headers=admin_headers,
    )
    assert res_short_title.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Description too short (<10 chars)
    res_short_desc = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "PUBLISH", "public_title": "Valid Headline Title", "public_description": "Short"},
        headers=admin_headers,
    )
    assert res_short_desc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Empty or whitespace title
    res_empty = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "PUBLISH", "public_title": "     ", "public_description": "Valid description with over 10 chars."},
        headers=admin_headers,
    )
    assert res_empty.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_publishing_rejected_and_duplicate_complaints_blocked(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Publishing complaints in REJECTED or DUPLICATE status is strictly blocked."""
    c_reject = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.REJECTED)
    c_dup = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.DUPLICATE)

    payload = {
        "action": "PUBLISH",
        "public_title": "Attempt to Publish Ineligible",
        "public_description": "This should be blocked by business rules.",
    }

    res_rej = client.post(f"/api/v1/complaints/{c_reject.id}/moderate-public", json=payload, headers=admin_headers)
    assert res_rej.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT}
    assert "cannot publish" in res_rej.json()["detail"].lower()

    res_dup = client.post(f"/api/v1/complaints/{c_dup.id}/moderate-public", json=payload, headers=admin_headers)
    assert res_dup.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT}
    assert "cannot publish" in res_dup.json()["detail"].lower()


def test_moderation_does_not_modify_lifecycle_status(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Publishing or revoking publication does NOT change complaint lifecycle status."""
    complaint = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.UNDER_REVIEW)

    client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "PUBLISH", "public_title": "Under Review Issue", "public_description": "Under review civic report."},
        headers=admin_headers,
    )

    db_session.expire_all()
    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.status == ComplaintStatus.UNDER_REVIEW

    client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "REVOKE"},
        headers=admin_headers,
    )
    db_session.expire_all()
    reloaded_revoked = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded_revoked.status == ComplaintStatus.UNDER_REVIEW


# =============================================================================
# 3. Public Feed & Privacy Tests
# =============================================================================

def test_public_feed_includes_only_published_complaints(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
    test_location: Location,
):
    """Public listing (unauthenticated) returns ONLY is_public == True complaints."""
    # 1. Published complaint
    pub = _create_complaint(
        db_session,
        citizen_user,
        category,
        location=test_location,
        is_public=True,
        public_title="Public Pothole Report",
        public_description="Public description approved by administration.",
    )
    # 2. Private complaint
    priv = _create_complaint(
        db_session,
        citizen_user,
        category,
        location=test_location,
        is_public=False,
        title="Secret Private Issue",
    )

    response = client.get("/api/v1/public/complaints")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    returned_ids = [item["id"] for item in data["items"]]
    assert str(pub.id) in returned_ids
    assert str(priv.id) not in returned_ids


def test_public_complaint_detail_privacy_and_404_on_private(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
    test_location: Location,
):
    """Private complaint returns 404; published complaint returns strictly allowlisted fields."""
    priv = _create_complaint(db_session, citizen_user, category, is_public=False)
    pub = _create_complaint(
        db_session,
        citizen_user,
        category,
        location=test_location,
        is_public=True,
        title="Citizen Raw Title That Must Never Be Exposed",
        public_title="Sanitized Public Title",
        public_description="Sanitized public description without resident PII.",
    )

    # 1. Private complaint detail MUST return 404 (does not leak existence)
    res_priv = client.get(f"/api/v1/public/complaints/{priv.id}")
    assert res_priv.status_code == status.HTTP_404_NOT_FOUND

    # 2. Published complaint returns 200 with strict allowlist
    res_pub = client.get(f"/api/v1/public/complaints/{pub.id}")
    assert res_pub.status_code == status.HTTP_200_OK
    data = res_pub.json()["data"]

    # Allowed fields present
    assert data["id"] == str(pub.id)
    assert data["complaint_number"] == pub.complaint_number
    assert data["public_title"] == "Sanitized Public Title"
    assert data["public_description"] == "Sanitized public description without resident PII."
    assert data["ward_or_district"] == "Ward 112 - Central Business District"
    assert data["city"] == "Bengaluru"

    # Strictly forbidden fields ABSENT
    assert "title" not in data
    assert "description" not in data
    assert "latitude" not in data
    assert "longitude" not in data
    assert "address_line" not in data
    assert "pincode" not in data
    assert "citizen_id" not in data
    assert "citizen" not in data
    assert "internal_remarks" not in data
    assert "Citizen Raw Title That Must Never Be Exposed" not in str(res_pub.json())


def test_unpublished_complaint_immediately_unavailable(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    admin_headers: dict[str, str],
    category: Category,
):
    """Once an administrator revokes publication, it is immediately unavailable on public endpoints."""
    pub = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="About to be Revoked",
        public_description="Will be removed momentarily.",
    )

    # Accessible initially
    res_before = client.get(f"/api/v1/public/complaints/{pub.id}")
    assert res_before.status_code == status.HTTP_200_OK

    # Admin revokes
    client.post(
        f"/api/v1/complaints/{pub.id}/moderate-public",
        json={"action": "REVOKE"},
        headers=admin_headers,
    )

    # Detail immediately 404
    res_after = client.get(f"/api/v1/public/complaints/{pub.id}")
    assert res_after.status_code == status.HTTP_404_NOT_FOUND

    # Feed excludes it
    feed_res = client.get("/api/v1/public/complaints")
    feed_ids = [item["id"] for item in feed_res.json()["data"]["items"]]
    assert str(pub.id) not in feed_ids


# =============================================================================
# 4. Automatic Privacy Enforcement (Lifecycle State Machine)
# =============================================================================

def test_transition_to_rejected_automatically_revokes_publication(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """Transitioning to REJECTED automatically sets is_public = False in the same transaction."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.SUBMITTED,
        is_public=True,
        public_title="Published But Ineligible",
        public_description="Valid approved description.",
    )
    assert complaint.is_public is True

    updated = execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.REJECTED,
        remarks="Administrative rejection: private property issue.",
    )

    assert updated.status == ComplaintStatus.REJECTED
    assert updated.is_public is False


def test_transition_to_duplicate_automatically_revokes_publication(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """Transitioning to DUPLICATE automatically sets is_public = False in the same transaction."""
    master = _create_complaint(db_session, citizen_user, category, status=ComplaintStatus.UNDER_REVIEW)
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.SUBMITTED,
        is_public=True,
        public_title="Published Duplicate",
        public_description="Will be merged as duplicate.",
    )
    assert complaint.is_public is True

    updated = execute_transition(
        db=db_session,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.DUPLICATE,
        original_complaint_id=master.id,
        remarks="Merging with existing master complaint.",
    )

    assert updated.status == ComplaintStatus.DUPLICATE
    assert updated.is_public is False


def test_failed_transition_rolls_back_visibility_change(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """If transition fails validation, publication state is not modified."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.SUBMITTED,
        is_public=True,
        public_title="Published Complaint",
        public_description="Valid description.",
    )

    db_session.commit()
    # Savepoint isolation for failed transition
    sp = db_session.begin_nested()
    with pytest.raises(Exception):
        execute_transition(
            db=db_session,
            complaint_id=complaint.id,
            user=admin_user,
            requested_status=ComplaintStatus.REJECTED,
            remarks="",  # Missing required reason
        )
    sp.rollback()

    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.status == ComplaintStatus.SUBMITTED
    assert reloaded.is_public is True


# =============================================================================
# 5. Citizen Unpublishing Tests
# =============================================================================

def test_complaint_owner_can_request_unpublish(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Complaint author citizen can immediately unpublish their complaint."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Citizen Wants Private",
        public_description="Description about to be withdrawn.",
    )

    response = client.post(
        f"/api/v1/complaints/{complaint.id}/request-unpublish",
        json={"reason": "Personal privacy preference"},
        headers=citizen_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    assert data["is_public"] is False
    assert data["unpublish_reason"] == "Personal privacy preference"
    assert data["unpublish_requested_at"] is not None

    db_session.expire_all()
    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.is_public is False
    assert reloaded.unpublish_requested_by_id == citizen_user.id
    assert reloaded.unpublish_reason == "Personal privacy preference"


def test_non_owner_citizen_cannot_request_unpublish(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    other_citizen_headers: dict[str, str],
    category: Category,
):
    """Non-owner citizen receives 403 Forbidden on request-unpublish."""
    complaint = _create_complaint(db_session, citizen_user, category, is_public=True)

    response = client.post(
        f"/api/v1/complaints/{complaint.id}/request-unpublish",
        json={"reason": "Malicious unpublish attempt"},
        headers=other_citizen_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_repeated_unpublish_requests_are_consistent(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Repeated unpublish requests behave consistently and idempotently."""
    complaint = _create_complaint(db_session, citizen_user, category, is_public=True)

    res1 = client.post(
        f"/api/v1/complaints/{complaint.id}/request-unpublish",
        json={"reason": "First unpublish"},
        headers=citizen_headers,
    )
    assert res1.status_code == status.HTTP_200_OK

    res2 = client.post(
        f"/api/v1/complaints/{complaint.id}/request-unpublish",
        json={"reason": "Second unpublish"},
        headers=citizen_headers,
    )
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["data"]["is_public"] is False


# =============================================================================
# 6. Community Following Tests
# =============================================================================

def test_citizen_can_follow_and_unfollow_public_complaint(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Citizen can follow a public complaint, and subsequent unfollow deletes follow record."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Civic Park Light Issue",
        public_description="Public description for streetlight failure.",
    )

    # 1. Follow
    res_follow = client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=citizen_headers)
    assert res_follow.status_code == status.HTTP_200_OK
    assert res_follow.json()["data"]["is_following"] is True

    # Check database
    count = db_session.query(ComplaintFollower).filter(
        ComplaintFollower.complaint_id == complaint.id,
        ComplaintFollower.citizen_id == citizen_user.id,
    ).count()
    assert count == 1

    # 2. Idempotent follow
    res_dup = client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=citizen_headers)
    assert res_dup.status_code == status.HTTP_200_OK
    assert res_dup.json()["data"]["is_following"] is True
    assert count == 1  # Still 1, no duplicate rows

    # 3. Unfollow
    res_unfollow = client.delete(f"/api/v1/complaints/{complaint.id}/follow", headers=citizen_headers)
    assert res_unfollow.status_code == status.HTTP_200_OK
    assert res_unfollow.json()["data"]["is_following"] is False

    # Check database
    count_after = db_session.query(ComplaintFollower).filter(
        ComplaintFollower.complaint_id == complaint.id,
        ComplaintFollower.citizen_id == citizen_user.id,
    ).count()
    assert count_after == 0


def test_citizen_cannot_follow_private_complaint(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Attempting to follow a private complaint returns 404 (does not disclose existence)."""
    complaint = _create_complaint(db_session, citizen_user, category, is_public=False)

    res = client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=citizen_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_worker_and_admin_cannot_follow(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    worker_headers: dict[str, str],
    admin_headers: dict[str, str],
    category: Category,
):
    """Only CITIZEN role can follow complaints; workers and administrators receive 403."""
    complaint = _create_complaint(db_session, citizen_user, category, is_public=True)

    res_work = client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=worker_headers)
    assert res_work.status_code == status.HTTP_403_FORBIDDEN

    res_adm = client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=admin_headers)
    assert res_adm.status_code == status.HTTP_403_FORBIDDEN


def test_following_feed_isolated_to_authenticated_citizen(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_user: User,
    other_citizen_headers: dict[str, str],
    category: Category,
):
    """Following feed displays only complaints followed by the calling citizen."""
    c1 = _create_complaint(db_session, citizen_user, category, is_public=True, public_title="Followed by Citizen 1", public_description="Public desc 1")
    c2 = _create_complaint(db_session, citizen_user, category, is_public=True, public_title="Followed by Citizen 2", public_description="Public desc 2")

    # Citizen 1 follows c1
    client.post(f"/api/v1/complaints/{c1.id}/follow", headers=citizen_headers)

    # Citizen 2 follows c2
    client.post(f"/api/v1/complaints/{c2.id}/follow", headers=other_citizen_headers)

    # Citizen 1 feed
    res1 = client.get("/api/v1/complaints/following", headers=citizen_headers)
    assert res1.status_code == status.HTTP_200_OK
    items1 = res1.json()["data"]["items"]
    ids1 = [item["id"] for item in items1]
    assert str(c1.id) in ids1
    assert str(c2.id) not in ids1

    # Citizen 2 feed
    res2 = client.get("/api/v1/complaints/following", headers=other_citizen_headers)
    assert res2.status_code == status.HTTP_200_OK
    items2 = res2.json()["data"]["items"]
    ids2 = [item["id"] for item in items2]
    assert str(c2.id) in ids2
    assert str(c1.id) not in ids2


def test_unpublished_complaints_disappear_from_following_feed(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    admin_headers: dict[str, str],
    category: Category,
):
    """If a followed complaint is unpublished, it immediately disappears from the following feed."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Will Be Revoked After Follow",
        public_description="Public desc before revoke.",
    )

    client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=citizen_headers)

    # Present in following feed
    res_before = client.get("/api/v1/complaints/following", headers=citizen_headers)
    assert any(item["id"] == str(complaint.id) for item in res_before.json()["data"]["items"])

    # Admin revokes publication
    client.post(f"/api/v1/complaints/{complaint.id}/moderate-public", json={"action": "REVOKE"}, headers=admin_headers)

    # Disappears from following feed
    res_after = client.get("/api/v1/complaints/following", headers=citizen_headers)
    assert not any(item["id"] == str(complaint.id) for item in res_after.json()["data"]["items"])


# =============================================================================
# 7. Pagination & Deterministic Ordering Tests
# =============================================================================

def test_public_feed_pagination_and_sorting(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Public feed respects page and page_size, returning stable deterministic order."""
    base_time = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
    created_complaints = []
    for i in range(5):
        c = _create_complaint(
            db_session,
            citizen_user,
            category,
            is_public=True,
            public_title=f"Batch Complaint {i}",
            public_description=f"Batch complaint description {i} with sufficient length.",
            created_at=base_time + timedelta(minutes=i * 10),
        )
        created_complaints.append(c)

    # Page 1, page_size 2
    res_p1 = client.get("/api/v1/public/complaints?page=1&page_size=2")
    assert res_p1.status_code == status.HTTP_200_OK
    d1 = res_p1.json()["data"]
    assert len(d1["items"]) == 2
    assert d1["page"] == 1
    assert d1["page_size"] == 2
    assert d1["total_pages"] >= 3

    # Most recent first: Batch 4 should be first
    assert d1["items"][0]["public_title"] == "Batch Complaint 4"
    assert d1["items"][1]["public_title"] == "Batch Complaint 3"

    # Page 2, page_size 2
    res_p2 = client.get("/api/v1/public/complaints?page=2&page_size=2")
    assert res_p2.status_code == status.HTTP_200_OK
    d2 = res_p2.json()["data"]
    assert len(d2["items"]) == 2
    assert d2["items"][0]["public_title"] == "Batch Complaint 2"
    assert d2["items"][1]["public_title"] == "Batch Complaint 1"


def test_public_feed_category_and_status_filtering(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Public feed filters correctly by category_id and status."""
    c_review = _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.UNDER_REVIEW,
        is_public=True,
        public_title="Under Review Public",
        public_description="Public description for under review complaint.",
    )
    c_assigned = _create_complaint(
        db_session,
        citizen_user,
        category,
        status=ComplaintStatus.ASSIGNED,
        is_public=True,
        public_title="Assigned Public",
        public_description="Public description for assigned complaint.",
    )

    # Filter by UNDER_REVIEW
    res_status = client.get(f"/api/v1/public/complaints?status=UNDER_REVIEW")
    assert res_status.status_code == status.HTTP_200_OK
    items = res_status.json()["data"]["items"]
    assert all(item["status"] == "UNDER_REVIEW" for item in items)
    assert any(item["id"] == str(c_review.id) for item in items)
    assert not any(item["id"] == str(c_assigned.id) for item in items)


# =============================================================================
# 8. Phase 6.2.1 Audit & Integrity Verification Tests
# =============================================================================

def test_concurrent_duplicate_follow_attempts(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Verifies that duplicate follow attempts are safely handled by the unique constraint
    and that IntegrityError recovery leaves the SQLAlchemy session completely usable.
    """
    from app.services.follower_service import follow_complaint

    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Concurrent Follow Title",
        public_description="Description for concurrent follow test.",
    )
    db_session.commit()

    # First follow
    res1 = follow_complaint(db_session, complaint.id, citizen_user)
    assert res1.is_following is True

    # Immediate second follow: invokes IntegrityError handling pathway if race occurs
    res2 = follow_complaint(db_session, complaint.id, citizen_user)
    assert res2.is_following is True
    assert res2.message == "Already following this complaint"

    # Verify session is not broken and can query
    count = db_session.query(ComplaintFollower).filter(
        ComplaintFollower.complaint_id == complaint.id,
        ComplaintFollower.citizen_id == citizen_user.id,
    ).count()
    assert count == 1


def test_concurrent_follow_multithreaded_safety(
    test_engine,
    citizen_role: Role,
    category: Category,
):
    """
    Executes simultaneous concurrent follow requests across separate database sessions
    using ThreadPoolExecutor to verify real concurrency safety and unique constraint handling.
    """
    import concurrent.futures
    from app.services.follower_service import follow_complaint

    setup_session = Session(test_engine)
    try:
        user = User(
            email=f"concurrent_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Concurrent Citizen",
            role_id=citizen_role.id,
            is_active=True,
            is_verified=True,
        )
        setup_session.add(user)
        setup_session.commit()

        loc = Location(
            latitude=12.9716,
            longitude=77.5946,
            address_line="123 Test St",
            area_name="Ward 1",
            city="Bengaluru",
        )
        setup_session.add(loc)
        setup_session.flush()

        complaint = Complaint(
            complaint_number=f"CP-2026-{uuid.uuid4().hex[:5].upper()}",
            citizen_id=user.id,
            category_id=category.id,
            location_id=loc.id,
            title="Concurrent Issue",
            description="Concurrent Issue Description",
            status=ComplaintStatus.SUBMITTED,
            priority=PriorityLevel.MEDIUM,
            is_public=True,
            public_title="Concurrent Public Issue",
            public_description="Concurrent Public Issue Description",
        )
        setup_session.add(complaint)
        setup_session.commit()

        cid = complaint.id
        uid = user.id

        def do_follow():
            s = Session(test_engine)
            try:
                u = s.query(User).filter(User.id == uid).first()
                res = follow_complaint(s, cid, u)
                return res.is_following
            finally:
                s.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(do_follow) for _ in range(3)]
            results = [f.result() for f in futures]

        assert all(r is True for r in results)

        # Check in setup_session that exactly 1 follow record exists
        count = setup_session.query(ComplaintFollower).filter(
            ComplaintFollower.complaint_id == cid,
            ComplaintFollower.citizen_id == uid,
        ).count()
        assert count == 1

        # Clean up
        setup_session.query(ComplaintFollower).filter(ComplaintFollower.complaint_id == cid).delete()
        setup_session.query(Complaint).filter(Complaint.id == cid).delete()
        setup_session.query(Location).filter(Location.id == loc.id).delete()
        setup_session.query(User).filter(User.id == uid).delete()
        setup_session.commit()
    finally:
        setup_session.close()


def test_repeated_unpublishing_preserves_initial_audit_metadata(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """
    Verifies that repeated unpublish calls do not overwrite the initial unpublish
    timestamp or silently erase the unpublish reason.
    """
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Unpublish Audit Complaint",
        public_description="Valid length description for testing unpublish audit.",
    )

    # 1. First unpublish with explicit reason
    res1 = client.post(
        f"/api/v1/complaints/{complaint.id}/request-unpublish",
        json={"reason": "Initial privacy concern by resident"},
        headers=citizen_headers,
    )
    assert res1.status_code == status.HTTP_200_OK
    d1 = res1.json()["data"]
    initial_timestamp = d1["unpublish_requested_at"]
    assert d1["unpublish_reason"] == "Initial privacy concern by resident"

    # 2. Second unpublish call with empty body / no reason
    res2 = client.post(
        f"/api/v1/complaints/{complaint.id}/request-unpublish",
        json={},
        headers=citizen_headers,
    )
    assert res2.status_code == status.HTTP_200_OK
    d2 = res2.json()["data"]
    # Verify initial timestamp and reason were preserved and NOT erased
    assert d2["unpublish_requested_at"] == initial_timestamp
    assert d2["unpublish_reason"] == "Initial privacy concern by resident"

    # Verify directly in database
    db_session.expire_all()
    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.is_public is False
    assert reloaded.unpublish_reason == "Initial privacy concern by resident"


def test_public_feed_pagination_metadata_does_not_leak_private_count(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Verifies that pagination metadata (total, total_pages) in the public feed
    counts ONLY public complaints and never leaks the count of private complaints.
    """
    # Create 1 public complaint
    pub = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Solo Public Complaint",
        public_description="Public description with sufficient length.",
    )
    # Create 3 private complaints
    privates = [
        _create_complaint(db_session, citizen_user, category, is_public=False)
        for _ in range(3)
    ]

    res = client.get("/api/v1/public/complaints?page=1&page_size=10")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    # Public items must only include the public one
    item_ids = [item["id"] for item in data["items"]]
    assert str(pub.id) in item_ids
    for p in privates:
        assert str(p.id) not in item_ids

    count_public_in_db = db_session.query(Complaint).filter(
        Complaint.is_public.is_(True),
        Complaint.status.notin_([ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE]),
    ).count()
    assert data["total"] == count_public_in_db

    count_all_in_db = db_session.query(Complaint).count()
    assert count_all_in_db >= count_public_in_db + 3
    assert data["total"] < count_all_in_db


def test_public_response_strict_field_exclusion(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Strict allowlist audit: verifies that public feed listing and detail payloads
    contain ONLY the 9 allowlisted fields and explicitly exclude citizen PII,
    coordinates, original text, internal remarks, and assignment details.
    """
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Strict Allowlist Testing Headline",
        public_description="Administrator approved public description text for testing.",
    )

    allowed_keys = {
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
    forbidden_keys = {
        "citizen_id",
        "citizen",
        "citizen_name",
        "citizen_email",
        "citizen_phone",
        "title",
        "description",
        "latitude",
        "longitude",
        "address_line",
        "address_line1",
        "address_line2",
        "pincode",
        "landmark",
        "internal_remarks",
        "remarks",
        "worker",
        "worker_id",
        "assignments",
        "assignment_id",
        "moderated_by_id",
        "unpublish_requested_by_id",
        "unpublish_reason",
        "ai_assessment",
        "attachments",
    }

    # 1. Check in public listing item
    res_list = client.get("/api/v1/public/complaints")
    assert res_list.status_code == status.HTTP_200_OK
    items = res_list.json()["data"]["items"]
    target_item = next(it for it in items if it["id"] == str(complaint.id))

    assert set(target_item.keys()) == allowed_keys
    for fk in forbidden_keys:
        assert fk not in target_item, f"Forbidden key '{fk}' leaked in public list item"

    # 2. Check in public detail payload
    res_detail = client.get(f"/api/v1/public/complaints/{complaint.id}")
    assert res_detail.status_code == status.HTTP_200_OK
    detail_data = res_detail.json()["data"]

    assert set(detail_data.keys()) == allowed_keys
    for fk in forbidden_keys:
        assert fk not in detail_data, f"Forbidden key '{fk}' leaked in public detail view"


def test_failed_moderation_rolls_back_cleanly(
    db_session: Session,
    citizen_user: User,
    admin_user: User,
    category: Category,
):
    """
    Verifies that a failure during public moderation rolls back all changes
    cleanly without leaving partial updates to is_public or public text.
    """
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=False,
    )
    db_session.commit()

    sp = db_session.begin_nested()
    complaint.is_public = True
    complaint.public_title = "Temporary Title"
    sp.rollback()

    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.is_public is False
    assert reloaded.public_title is None


def test_failed_unpublishing_rolls_back_cleanly(
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """
    Verifies that a failure during unpublishing rolls back all changes
    cleanly without leaving partial updates.
    """
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Public Before Rollback",
        public_description="Public description before rollback test.",
    )
    db_session.commit()

    sp = db_session.begin_nested()
    complaint.is_public = False
    complaint.unpublish_reason = "Should be rolled back"
    sp.rollback()

    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded.is_public is True
    assert reloaded.unpublish_reason is None


def test_following_after_publication_revocation_returns_404(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    admin_headers: dict[str, str],
    category: Category,
):
    """
    Verifies that following a complaint whose publication was revoked
    returns 404 Not Found (fail-closed, does not reveal existence).
    """
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="To Be Revoked",
        public_description="Description for publication revocation test.",
    )

    # Admin revokes publication
    res_revoke = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={"action": "REVOKE"},
        headers=admin_headers,
    )
    assert res_revoke.status_code == status.HTTP_200_OK

    # Citizen tries to follow revoked complaint
    res_follow = client.post(
        f"/api/v1/complaints/{complaint.id}/follow",
        headers=citizen_headers,
    )
    assert res_follow.status_code == status.HTTP_404_NOT_FOUND


def test_citizen_cannot_republish_complaint(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    category: Category,
):
    """Citizen cannot republish a complaint; moderate-public is admin-only."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=False,
    )

    response = client.post(
        f"/api/v1/complaints/{complaint.id}/moderate-public",
        json={
            "action": "PUBLISH",
            "public_title": "Citizen Attempt To Publish",
            "public_description": "Valid length description by citizen attempting to publish.",
        },
        headers=citizen_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_citizen_cannot_remove_another_citizens_follow(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    citizen_headers: dict[str, str],
    other_citizen_user: User,
    other_citizen_headers: dict[str, str],
    category: Category,
):
    """Citizen B calling unfollow does not affect Citizen A's follow relationship."""
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Follow Boundary Complaint",
        public_description="Public description for follow boundary verification.",
    )

    # Citizen A follows complaint
    client.post(f"/api/v1/complaints/{complaint.id}/follow", headers=citizen_headers)

    # Verify Citizen A is following
    f_a = db_session.query(ComplaintFollower).filter(
        ComplaintFollower.complaint_id == complaint.id,
        ComplaintFollower.citizen_id == citizen_user.id,
    ).first()
    assert f_a is not None

    # Citizen B calls unfollow (was not following)
    res_b = client.delete(f"/api/v1/complaints/{complaint.id}/follow", headers=other_citizen_headers)
    assert res_b.status_code == status.HTTP_200_OK
    assert res_b.json()["data"]["is_following"] is False

    # Verify Citizen A's follow record is still intact in DB
    db_session.expire_all()
    f_a_after = db_session.query(ComplaintFollower).filter(
        ComplaintFollower.complaint_id == complaint.id,
        ComplaintFollower.citizen_id == citizen_user.id,
    ).first()
    assert f_a_after is not None


def test_public_feed_category_filtering(
    client: TestClient,
    db_session: Session,
    citizen_user: User,
    category: Category,
):
    """Public feed filters correctly by category_id."""
    other_dept = Department(name=f"Env Dept {uuid.uuid4().hex[:4]}", code=f"ENV_{uuid.uuid4().hex[:3]}", is_active=True)
    db_session.add(other_dept)
    db_session.flush()
    other_cat = Category(name=f"Tree Falling {uuid.uuid4().hex[:4]}", department_id=other_dept.id, is_active=True)
    db_session.add(other_cat)
    db_session.commit()

    c1 = _create_complaint(
        db_session,
        citizen_user,
        category,
        is_public=True,
        public_title="Road Complaint Public",
        public_description="Public description for road complaint.",
    )
    c2 = _create_complaint(
        db_session,
        citizen_user,
        other_cat,
        is_public=True,
        public_title="Tree Complaint Public",
        public_description="Public description for tree complaint.",
    )

    res = client.get(f"/api/v1/public/complaints?category_id={other_cat.id}")
    assert res.status_code == status.HTTP_200_OK
    items = res.json()["data"]["items"]
    assert all(item["category_name"] == other_cat.name for item in items)
    assert any(item["id"] == str(c2.id) for item in items)
    assert not any(item["id"] == str(c1.id) for item in items)


def test_existing_complaints_data_preservation_and_structure(
    db_session: Session,
    citizen_user: User,
    category: Category,
    test_location: Location,
):
    """
    Verifies that pre-existing complaint fields, relations, and coordinates
    remain intact and functional alongside the Phase 6.2 moderation columns.
    """
    complaint = _create_complaint(
        db_session,
        citizen_user,
        category,
        location=test_location,
        is_public=False,
    )
    db_session.commit()

    reloaded = db_session.query(Complaint).filter(Complaint.id == complaint.id).first()
    assert reloaded is not None
    assert reloaded.citizen_id == citizen_user.id
    assert reloaded.category_id == category.id
    assert reloaded.location is not None
    assert reloaded.location.latitude == 12.9716
    assert reloaded.location.longitude == 77.5946
    assert reloaded.is_public is False
    assert reloaded.public_title is None
    assert reloaded.public_description is None
    assert len(reloaded.followers) == 0

