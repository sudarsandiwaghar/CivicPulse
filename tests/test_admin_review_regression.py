"""
CivicPulse Regression Tests — Admin Dashboard & Start Review Bug Fixes

Verifies:
1. Administrator Dashboard metrics and complaint filtering by priority:
   - Accepts both 'CRITICAL' and 'URGENT' priority query parameters without 422 error.
   - Correctly returns SUBMITTED complaints in the triage queue.
2. Start Review transition:
   - PATCH /api/v1/complaints/{complaint_id}/review transitions SUBMITTED -> UNDER_REVIEW.
   - Timeline audit record is created atomically with administrator attribution.
   - HTTP method correctness: POST is not allowed, PATCH is accepted.
3. Access Control & Authorization:
   - Unauthenticated requests are rejected with 401.
   - Citizen / non-admin requests are rejected with 403.
4. State Machine Invariants:
   - Invalid lifecycle transitions are rejected with 422.
"""

import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.constants import ComplaintStatus, PriorityLevel, UserRole
from app.core.security import create_access_token, hash_password
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.role import Role
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Fixture providing an active administrator user in test DB."""
    admin_role = db_session.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
    user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("AdminSecurePassword123!"),
        full_name="Municipal Admin",
        role_id=admin_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def citizen_user(db_session: Session) -> User:
    """Fixture providing an active citizen user in test DB."""
    citizen_role = db_session.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
    user = User(
        email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("CitizenSecure123!"),
        full_name="Citizen User",
        role_id=citizen_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def sample_category(db_session: Session) -> Category:
    """Fixture providing an active category in test DB."""
    cat = db_session.query(Category).filter(Category.is_active == True).first()
    if not cat:
        cat = Category(name="Public Roads", description="Road repairs", is_active=True)
        db_session.add(cat)
        db_session.flush()
    return cat


@pytest.fixture
def submitted_complaint(db_session: Session, citizen_user: User, sample_category: Category) -> Complaint:
    """Fixture providing a SUBMITTED complaint in test DB."""
    complaint = Complaint(
        complaint_number=f"CP-2026-{uuid.uuid4().int % 90000 + 10000}",
        citizen_id=citizen_user.id,
        category_id=sample_category.id,
        title="Pothole on Main Avenue",
        description="Dangerous road hazard requiring prompt municipal inspection.",
        status=ComplaintStatus.SUBMITTED,
        priority=PriorityLevel.CRITICAL,
    )
    db_session.add(complaint)
    db_session.flush()
    return complaint


# =============================================================================
# 1. Admin Dashboard Priority Query Regression Tests
# =============================================================================

def test_admin_list_complaints_accepts_urgent_priority(
    client: TestClient,
    admin_user: User,
    submitted_complaint: Complaint,
):
    """
    Regression Test:
    Verify GET /api/v1/complaints/?priority=URGENT succeeds (HTTP 200)
    and maps transparently to CRITICAL priority, preventing the 422 Dashboard Error.
    """
    token = create_access_token(admin_user.id, UserRole.ADMINISTRATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/complaints/?priority=URGENT", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["total_items"] >= 1
    # Check that our submitted_complaint is present
    ids = [item["id"] for item in data["data"]]
    assert str(submitted_complaint.id) in ids


def test_admin_list_complaints_accepts_critical_priority(
    client: TestClient,
    admin_user: User,
    submitted_complaint: Complaint,
):
    """
    Verify GET /api/v1/complaints/?priority=CRITICAL succeeds (HTTP 200).
    """
    token = create_access_token(admin_user.id, UserRole.ADMINISTRATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/complaints/?priority=CRITICAL", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["total_items"] >= 1


def test_admin_dashboard_triage_queue_submitted_count(
    client: TestClient,
    admin_user: User,
    submitted_complaint: Complaint,
):
    """
    Verify querying status=SUBMITTED returns the correct pending triage count.
    """
    token = create_access_token(admin_user.id, UserRole.ADMINISTRATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/complaints/?status=SUBMITTED", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_items"] >= 1
    assert any(c["id"] == str(submitted_complaint.id) for c in data["data"])


# =============================================================================
# 2. Start Review Transition (PATCH vs POST) Regression Tests
# =============================================================================

def test_start_review_patch_succeeds_and_transitions_status(
    client: TestClient,
    admin_user: User,
    submitted_complaint: Complaint,
    db_session: Session,
):
    """
    Regression Test:
    Verify PATCH /api/v1/complaints/{id}/review transitions SUBMITTED to UNDER_REVIEW
    and records an audit timeline entry.
    """
    token = create_access_token(admin_user.id, UserRole.ADMINISTRATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "new_status": "UNDER_REVIEW",
        "reason": "Administrator initiated formal complaint review and verification.",
    }

    response = client.patch(f"/api/v1/complaints/{submitted_complaint.id}/review", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["data"]["status"] == ComplaintStatus.UNDER_REVIEW.value

    # Verify database state
    db_session.refresh(submitted_complaint)
    assert submitted_complaint.status == ComplaintStatus.UNDER_REVIEW

    # Verify status history audit entry
    history_entries = (
        db_session.query(ComplaintStatusHistory)
        .filter(ComplaintStatusHistory.complaint_id == submitted_complaint.id)
        .order_by(ComplaintStatusHistory.created_at.desc())
        .all()
    )
    assert len(history_entries) >= 1
    latest = history_entries[0]
    assert latest.previous_status == ComplaintStatus.SUBMITTED
    assert latest.new_status == ComplaintStatus.UNDER_REVIEW
    assert latest.changed_by_id == admin_user.id


def test_start_review_post_returns_405_method_not_allowed(
    client: TestClient,
    admin_user: User,
    submitted_complaint: Complaint,
):
    """
    Regression Test:
    Verify calling POST on the review endpoint yields 405 Method Not Allowed,
    confirming why the frontend must use PATCH.
    """
    token = create_access_token(admin_user.id, UserRole.ADMINISTRATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "new_status": "UNDER_REVIEW",
        "reason": "Administrator initiated formal complaint review.",
    }

    response = client.post(f"/api/v1/complaints/{submitted_complaint.id}/review", json=payload, headers=headers)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# =============================================================================
# 3. Access Control & Authorization Tests
# =============================================================================

def test_start_review_unauthorized_for_citizen(
    client: TestClient,
    citizen_user: User,
    submitted_complaint: Complaint,
):
    """
    Verify citizens cannot call the administrator review endpoint (HTTP 403).
    """
    token = create_access_token(citizen_user.id, UserRole.CITIZEN.value)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "new_status": "UNDER_REVIEW",
        "reason": "Citizen attempt.",
    }

    response = client.patch(f"/api/v1/complaints/{submitted_complaint.id}/review", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_start_review_unauthenticated(
    client: TestClient,
    submitted_complaint: Complaint,
):
    """
    Verify unauthenticated calls are rejected with HTTP 401.
    """
    payload = {
        "new_status": "UNDER_REVIEW",
        "reason": "No token.",
    }

    response = client.patch(f"/api/v1/complaints/{submitted_complaint.id}/review", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# 4. State Machine & Validation Invariants
# =============================================================================

def test_start_review_invalid_transition_rejected(
    client: TestClient,
    admin_user: User,
    submitted_complaint: Complaint,
):
    """
    Verify illegal state transition (e.g. SUBMITTED -> CLOSED) is rejected with 422.
    """
    token = create_access_token(admin_user.id, UserRole.ADMINISTRATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "new_status": "CLOSED",
        "reason": "Premature closure attempt.",
    }

    response = client.patch(f"/api/v1/complaints/{submitted_complaint.id}/review", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
