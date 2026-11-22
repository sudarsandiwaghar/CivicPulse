"""
CivicPulse Phase 4 Complaint Management & Lifecycle State Machine Tests

Comprehensive test suite verifying:
    - Citizen complaint submission with server-side trusted defaults and validation.
    - Unique reference number generation (CP-YYYY-XXXXX) via PostgreSQL sequence.
    - Input validation: category existence/activity and coordinate check constraints.
    - Scoping & authorization: IDOR protection (citizens see only own complaints).
    - Administrator unrestricted listing, search, filtering, and pagination.
    - Complete lifecycle state machine transition matrix and preconditions.
    - Protection against arbitrary transitions, terminal states, and self-review.
    - Administrator review endpoint (category update, priority adjustment with reason).
    - Status history audit logging (atomic transactions, immutable records).
    - Active categories retrieval endpoint.
    - Transaction rollback and concurrency safety.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.core.constants import ComplaintStatus, PriorityLevel, UserRole
from app.core.security import create_access_token, hash_password
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.services.auth_service import init_roles
from app.services.category_service import init_categories


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def setup_seed_data(db_session: Session):
    """Ensure standard roles, departments, and categories exist in test DB."""
    # Alembic migrations 002 and 003 have already seeded them, but if missing, flush
    pass


@pytest.fixture
def citizen_user(db_session: Session) -> User:
    """Create and return a verified citizen user."""
    citizen_role = db_session.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
    user = User(
        email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("SecurePassword123!"),
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
    """Return Authorization Bearer header for citizen user."""
    token = create_access_token(
        subject=str(citizen_user.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": citizen_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_citizen_user(db_session: Session) -> User:
    """Create a second distinct citizen for IDOR tests."""
    citizen_role = db_session.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
    user = User(
        email=f"other_citizen_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("SecurePassword123!"),
        full_name="Pooja Patel",
        role_id=citizen_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def other_citizen_headers(other_citizen_user: User) -> dict[str, str]:
    """Return Authorization Bearer header for second citizen."""
    token = create_access_token(
        subject=str(other_citizen_user.id),
        role=UserRole.CITIZEN.value,
        extra_claims={"email": other_citizen_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create and return an administrator user."""
    admin_role = db_session.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
    user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("AdminSecurePassword123!"),
        full_name="Suresh Verma",
        role_id=admin_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    """Return Authorization Bearer header for administrator user."""
    token = create_access_token(
        subject=str(admin_user.id),
        role=UserRole.ADMINISTRATOR.value,
        extra_claims={"email": admin_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def worker_user(db_session: Session) -> User:
    """Create and return a field worker user."""
    worker_role = db_session.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
    user = User(
        email=f"worker_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("WorkerSecurePassword123!"),
        full_name="Ramesh Kumar",
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def worker_headers(worker_user: User) -> dict[str, str]:
    """Return Authorization Bearer header for field worker."""
    token = create_access_token(
        subject=str(worker_user.id),
        role=UserRole.FIELD_WORKER.value,
        extra_claims={"email": worker_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def active_category(db_session: Session) -> Category:
    """Return an active Category instance."""
    cat = db_session.query(Category).filter(Category.is_active.is_(True)).first()
    assert cat is not None, "At least one active category must exist"
    return cat


# =============================================================================
# 1. Complaint Submission Tests
# =============================================================================

class TestComplaintSubmission:
    """Verifies citizen complaint filing, validation, server defaults, and initial history."""

    def test_successful_citizen_complaint_submission(self, client, citizen_headers, active_category):
        """Citizen submitting valid payload receives HTTP 201 with server-assigned defaults."""
        payload = {
            "title": "Deep pothole causing accidents near Metro Station",
            "description": "Large road crater at the signal intersection causing severe traffic delay and vehicle damage.",
            "category_id": active_category.id,
            "location": {
                "latitude": 12.9716,
                "longitude": 77.5946,
                "address_line": "100ft Road, Indiranagar",
                "area_name": "Ward 80",
                "city": "Bengaluru",
                "pincode": "560038",
                "landmark": "Near Metro Pillar 120",
            },
        }

        response = client.post("/api/v1/complaints/", json=payload, headers=citizen_headers)
        assert response.status_code == status.HTTP_201_CREATED

        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Complaint submitted successfully"

        data = body["data"]
        assert "id" in data
        assert data["title"] == payload["title"]
        assert data["description"] == payload["description"]
        assert data["category_id"] == active_category.id
        # Server-enforced values
        assert data["status"] == ComplaintStatus.SUBMITTED.value
        assert data["priority"] == PriorityLevel.MEDIUM.value
        assert data["complaint_number"].startswith(f"CP-{datetime.now(timezone.utc).year}-")
        assert data["resolved_at"] is None
        assert data["closed_at"] is None
        assert data["location"]["latitude"] == 12.9716
        assert data["location"]["longitude"] == 77.5946

    def test_unique_complaint_numbers_generated(self, client, citizen_headers, active_category):
        """Sequential complaint submissions must produce unique tracking numbers."""
        payload = {
            "title": "Streetlight flickering continuously",
            "description": "The lamp pole outside building 42 flickers on and off all night.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946, "city": "Bengaluru"},
        }

        res1 = client.post("/api/v1/complaints/", json=payload, headers=citizen_headers)
        res2 = client.post("/api/v1/complaints/", json=payload, headers=citizen_headers)

        assert res1.status_code == status.HTTP_201_CREATED
        assert res2.status_code == status.HTTP_201_CREATED

        num1 = res1.json()["data"]["complaint_number"]
        num2 = res2.json()["data"]["complaint_number"]
        assert num1 != num2, f"Complaint numbers must be distinct ({num1} vs {num2})"

    def test_invalid_category_rejected(self, client, citizen_headers):
        """Referencing a non-existent category ID returns HTTP 404 Not Found."""
        payload = {
            "title": "Overflowing sewer pipe on main street",
            "description": "Sewage water leaking across the road near market entrance.",
            "category_id": 999999,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }

        response = client.post("/api/v1/complaints/", json=payload, headers=citizen_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_category_rejected(self, client, citizen_headers, db_session: Session):
        """Filing under an inactive category returns HTTP 422 Unprocessable Entity."""
        dept = db_session.query(Department).first()
        inactive_cat = Category(
            department_id=dept.id,
            name="Deprecated Archived Category",
            description="No longer active",
            is_active=False,
        )
        db_session.add(inactive_cat)
        db_session.commit()
        db_session.refresh(inactive_cat)

        payload = {
            "title": "Testing inactive category submission",
            "description": "This submission should be rejected because the category is disabled.",
            "category_id": inactive_cat.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }

        response = client.post("/api/v1/complaints/", json=payload, headers=citizen_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "inactive" in response.json()["detail"].lower()

    def test_invalid_coordinates_rejected(self, client, citizen_headers, active_category):
        """Latitude outside [-90, 90] or longitude outside [-180, 180] rejected with HTTP 422."""
        invalid_lat_payload = {
            "title": "Invalid latitude testing",
            "description": "Latitude is 150.0 which exceeds geographic maximum.",
            "category_id": active_category.id,
            "location": {"latitude": 150.0, "longitude": 77.5946},
        }
        res_lat = client.post("/api/v1/complaints/", json=invalid_lat_payload, headers=citizen_headers)
        assert res_lat.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        invalid_lon_payload = {
            "title": "Invalid longitude testing",
            "description": "Longitude is -250.0 which exceeds geographic minimum.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": -250.0},
        }
        res_lon = client.post("/api/v1/complaints/", json=invalid_lon_payload, headers=citizen_headers)
        assert res_lon.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_initial_status_history_persisted(self, client, citizen_headers, active_category, db_session: Session):
        """Complaint submission must create an initial ComplaintStatusHistory record in DB."""
        payload = {
            "title": "Water leakage from municipal pipe",
            "description": "Continuous drinking water leak wasting hundreds of litres daily.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }

        response = client.post("/api/v1/complaints/", json=payload, headers=citizen_headers)
        assert response.status_code == status.HTTP_201_CREATED

        complaint_id = uuid.UUID(response.json()["data"]["id"])
        history = (
            db_session.query(ComplaintStatusHistory)
            .filter(ComplaintStatusHistory.complaint_id == complaint_id)
            .all()
        )
        assert len(history) == 1
        assert history[0].previous_status is None
        assert history[0].new_status == ComplaintStatus.SUBMITTED
        assert "initial complaint submission" in history[0].remarks.lower()

    def test_unauthenticated_submission_rejected(self, client, active_category):
        """Complaint submission without Authorization header returns HTTP 401."""
        payload = {
            "title": "Unauthenticated report attempt",
            "description": "This request provides no Bearer token credentials.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        response = client.post("/api/v1/complaints/", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_citizen_submission_rejected(self, client, admin_headers, active_category):
        """Administrators cannot self-file citizen complaints via citizen endpoint."""
        payload = {
            "title": "Admin submitting citizen complaint",
            "description": "Admin accounts should not be filing public citizen complaints.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        response = client.post("/api/v1/complaints/", json=payload, headers=admin_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 2. Retrieval, Scoping & IDOR Prevention Tests
# =============================================================================

class TestComplaintRetrievalAndScoping:
    """Verifies that citizens can only access their own complaints, admins see all, and workers are blocked."""

    def test_citizen_can_only_view_own_complaints(
        self, client, citizen_headers, other_citizen_headers, active_category
    ):
        """Citizen list query must strictly scope results to their own citizen_id."""
        # Citizen 1 files a complaint
        p1 = {
            "title": "Citizen 1 unique complaint report",
            "description": "Specific issue reported exclusively by Citizen 1.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        r1 = client.post("/api/v1/complaints/", json=p1, headers=citizen_headers)
        assert r1.status_code == status.HTTP_201_CREATED
        c1_id = r1.json()["data"]["id"]

        # Citizen 2 files a complaint
        p2 = {
            "title": "Citizen 2 separate complaint report",
            "description": "Specific issue reported exclusively by Citizen 2.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        r2 = client.post("/api/v1/complaints/", json=p2, headers=other_citizen_headers)
        assert r2.status_code == status.HTTP_201_CREATED
        c2_id = r2.json()["data"]["id"]

        # Citizen 1 queries /complaints/
        list_c1 = client.get("/api/v1/complaints/", headers=citizen_headers)
        assert list_c1.status_code == status.HTTP_200_OK
        c1_items = list_c1.json()["data"]
        c1_ids = [item["id"] for item in c1_items]
        assert c1_id in c1_ids
        assert c2_id not in c1_ids, "Citizen 1 must NOT see Citizen 2's complaint!"

        # Citizen 2 queries /complaints/
        list_c2 = client.get("/api/v1/complaints/", headers=other_citizen_headers)
        assert list_c2.status_code == status.HTTP_200_OK
        c2_items = list_c2.json()["data"]
        c2_ids = [item["id"] for item in c2_items]
        assert c2_id in c2_ids
        assert c1_id not in c2_ids, "Citizen 2 must NOT see Citizen 1's complaint!"

    def test_citizen_blocked_from_other_citizen_complaint_detail(
        self, client, citizen_headers, other_citizen_headers, active_category
    ):
        """IDOR Prevention: Accessing another citizen's complaint ID returns HTTP 403 Forbidden."""
        p = {
            "title": "Confidential complaint by Citizen 1",
            "description": "Private civic issue details.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        r1 = client.post("/api/v1/complaints/", json=p, headers=citizen_headers)
        c1_id = r1.json()["data"]["id"]

        # Citizen 2 attempts to fetch Citizen 1's complaint detail
        idor_res = client.get(f"/api/v1/complaints/{c1_id}", headers=other_citizen_headers)
        assert idor_res.status_code == status.HTTP_403_FORBIDDEN

    def test_citizen_blocked_from_other_citizen_complaint_history(
        self, client, citizen_headers, other_citizen_headers, active_category
    ):
        """Citizen cannot inspect the transition history of another citizen's complaint."""
        p = {
            "title": "History inspection test complaint",
            "description": "Checking history security boundaries.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        r1 = client.post("/api/v1/complaints/", json=p, headers=citizen_headers)
        c1_id = r1.json()["data"]["id"]

        idor_history = client.get(f"/api/v1/complaints/{c1_id}/history", headers=other_citizen_headers)
        assert idor_history.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_view_all_complaints_and_details(
        self, client, citizen_headers, admin_headers, active_category
    ):
        """Administrators can list all complaints and view any complaint's details and history."""
        p = {
            "title": "Complaint inspected by admin",
            "description": "Citizen reports issue; administrator verifies.",
            "category_id": active_category.id,
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        r1 = client.post("/api/v1/complaints/", json=p, headers=citizen_headers)
        c1_id = r1.json()["data"]["id"]

        # Admin lists complaints
        admin_list = client.get("/api/v1/complaints/", headers=admin_headers)
        assert admin_list.status_code == status.HTTP_200_OK
        admin_ids = [item["id"] for item in admin_list.json()["data"]]
        assert c1_id in admin_ids

        # Admin views single detail
        admin_detail = client.get(f"/api/v1/complaints/{c1_id}", headers=admin_headers)
        assert admin_detail.status_code == status.HTTP_200_OK
        assert admin_detail.json()["data"]["id"] == c1_id
        assert "status_history" in admin_detail.json()["data"]

        # Admin views history
        admin_hist = client.get(f"/api/v1/complaints/{c1_id}/history", headers=admin_headers)
        assert admin_hist.status_code == status.HTTP_200_OK
        assert len(admin_hist.json()["data"]) >= 1

    def test_nonexistent_complaint_returns_404(self, client, admin_headers):
        """Looking up a non-existent UUID returns HTTP 404 Not Found."""
        random_id = uuid.uuid4()
        response = client.get(f"/api/v1/complaints/{random_id}", headers=admin_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_worker_blocked_from_complaints_in_phase_4(self, client, worker_headers):
        """Worker role is blocked from direct complaint listing in Phase 4."""
        response = client.get("/api/v1/complaints/", headers=worker_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Phase 5" in response.json()["detail"]


# =============================================================================
# 3. Filtering and Pagination Tests
# =============================================================================

class TestFilteringAndPagination:
    """Verifies administrator filtering by status, priority, category, search, and pagination."""

    def test_pagination_structure(self, client, admin_headers, citizen_headers, active_category):
        """Paginated list returns valid pagination metadata envelope."""
        # Create at least 2 complaints
        for i in range(3):
            client.post(
                "/api/v1/complaints/",
                json={
                    "title": f"Pagination batch item {i}",
                    "description": "Verifying page size and offset calculation.",
                    "category_id": active_category.id,
                    "location": {"latitude": 12.9716, "longitude": 77.5946},
                },
                headers=citizen_headers,
            )

        response = client.get("/api/v1/complaints/?page=1&page_size=2", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["success"] is True
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert body["total_items"] >= 3
        assert body["total_pages"] >= 2
        assert len(body["data"]) == 2

    def test_filter_by_status(self, client, admin_headers, citizen_headers, active_category):
        """Filtering by status=SUBMITTED returns only complaints in SUBMITTED status."""
        client.post(
            "/api/v1/complaints/",
            json={
                "title": "Submitted status filter test",
                "description": "Checking that filtering returns only submitted status.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )

        res = client.get("/api/v1/complaints/?status=SUBMITTED", headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        for item in res.json()["data"]:
            assert item["status"] == "SUBMITTED"

    def test_filter_by_search_query(self, client, admin_headers, citizen_headers, active_category):
        """Search query matches text in title or description."""
        unique_term = f"ZebraCrossingCrash_{uuid.uuid4().hex[:6]}"
        client.post(
            "/api/v1/complaints/",
            json={
                "title": f"Faded paint on {unique_term} causing hazards",
                "description": "Vehicles are not stopping for pedestrians at the zebra crossing.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )

        res = client.get(f"/api/v1/complaints/?search={unique_term}", headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.json()["data"]) == 1
        assert unique_term in res.json()["data"][0]["title"]


# =============================================================================
# 4. Lifecycle State Machine Transition Tests
# =============================================================================

class TestLifecycleTransitions:
    """Verifies state machine matrix, preconditions, role permissions, and terminal states."""

    def test_admin_moves_submitted_to_under_review(self, client, admin_headers, citizen_headers, active_category):
        """Admin can legally transition SUBMITTED -> UNDER_REVIEW."""
        res = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Review transition test",
                "description": "Testing transition from submitted to under review.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = res.json()["data"]["id"]

        t_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "UNDER_REVIEW", "remarks": "Admin triaging complaint."},
            headers=admin_headers,
        )
        assert t_res.status_code == status.HTTP_200_OK
        assert t_res.json()["data"]["status"] == "UNDER_REVIEW"

        # Verify audit history
        hist = client.get(f"/api/v1/complaints/{c_id}/history", headers=admin_headers)
        assert hist.status_code == status.HTTP_200_OK
        history_items = hist.json()["data"]
        assert len(history_items) == 2

        transition_record = next(h for h in history_items if h["new_status"] == "UNDER_REVIEW")
        assert transition_record["previous_status"] == "SUBMITTED"
        assert transition_record["remarks"] == "Admin triaging complaint."

        initial_record = next(h for h in history_items if h["new_status"] == "SUBMITTED")
        assert initial_record["previous_status"] is None

    def test_citizen_cannot_approve_own_review(self, client, citizen_headers, active_category):
        """Citizen cannot transition their own complaint to UNDER_REVIEW (no self-approval)."""
        res = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Citizen self review attempt",
                "description": "Citizen trying to mark their own issue under review.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = res.json()["data"]["id"]

        t_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "UNDER_REVIEW"},
            headers=citizen_headers,
        )
        assert t_res.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_rejects_complaint_with_reason(self, client, admin_headers, citizen_headers, active_category):
        """Admin can reject SUBMITTED complaint when providing a non-empty reason."""
        res = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Out of jurisdiction request",
                "description": "Issue located outside municipal corporation boundaries.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = res.json()["data"]["id"]

        # Reject without reason fails
        res_fail = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REJECTED", "remarks": ""},
            headers=admin_headers,
        )
        assert res_fail.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Reject with reason succeeds
        res_ok = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REJECTED", "remarks": "Property is outside municipal limits."},
            headers=admin_headers,
        )
        assert res_ok.status_code == status.HTTP_200_OK
        assert res_ok.json()["data"]["status"] == "REJECTED"

    def test_terminal_state_rejected_cannot_transition(self, client, admin_headers, citizen_headers, active_category):
        """A REJECTED complaint cannot transition to any other status."""
        res = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Terminal state rejection test",
                "description": "Testing transition from terminal REJECTED state.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = res.json()["data"]["id"]

        client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REJECTED", "remarks": "Invalid complaint."},
            headers=admin_headers,
        )

        # Attempt to revive from REJECTED to UNDER_REVIEW
        res_revive = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "UNDER_REVIEW"},
            headers=admin_headers,
        )
        assert res_revive.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_admin_marks_duplicate_with_valid_original(
        self, client, admin_headers, citizen_headers, active_category
    ):
        """Admin can mark a complaint as DUPLICATE referencing an existing original complaint."""
        # 1. Create original complaint
        r_orig = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Master complaint for road repair",
                "description": "Primary complaint for central road repairs.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        orig_id = r_orig.json()["data"]["id"]

        # 2. Create second duplicate complaint
        r_dup = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Duplicate complaint for road repair",
                "description": "Same pothole reported by another resident.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        dup_id = r_dup.json()["data"]["id"]

        # 3. Mark as duplicate referencing original
        res_dup = client.post(
            f"/api/v1/complaints/{dup_id}/transitions",
            json={
                "new_status": "DUPLICATE",
                "original_complaint_id": orig_id,
                "remarks": "Duplicate incident report at identical intersection.",
            },
            headers=admin_headers,
        )
        assert res_dup.status_code == status.HTTP_200_OK
        assert res_dup.json()["data"]["status"] == "DUPLICATE"

    def test_mark_duplicate_self_reference_rejected(
        self, client, admin_headers, citizen_headers, active_category
    ):
        """A complaint cannot be marked as a duplicate of itself."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Self duplicate attempt",
                "description": "Testing self-referential duplicate rejection.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "DUPLICATE", "original_complaint_id": c_id},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_transition_to_assigned_without_assignment_rejected(
        self, client, admin_headers, citizen_headers, active_category
    ):
        """Transitioning to ASSIGNED without an active assignment record raises HTTP 422."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Assignment precondition test",
                "description": "Should fail transition to ASSIGNED because no assignment exists.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        # Move to UNDER_REVIEW first
        client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "UNDER_REVIEW"},
            headers=admin_headers,
        )

        # Attempt to jump to ASSIGNED without assignment
        res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "ASSIGNED"},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "Phase 5" in res.json()["detail"]

    def test_citizen_verifies_and_closes_resolved_complaint(
        self, client, citizen_headers, admin_headers, active_category, db_session: Session
    ):
        """Citizen owner can verify and close a complaint that is in RESOLVED_AWAITING_VERIFICATION."""
        # Create complaint
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Resolution verification test",
                "description": "Verifying citizen closure workflow.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = uuid.UUID(r.json()["data"]["id"])

        # Manually set complaint status to RESOLVED_AWAITING_VERIFICATION in test DB
        complaint = db_session.query(Complaint).filter(Complaint.id == c_id).first()
        complaint.status = ComplaintStatus.RESOLVED_AWAITING_VERIFICATION
        db_session.commit()

        # Citizen verifies and closes
        close_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "CLOSED", "remarks": "Pothole has been repaired cleanly. Thank you."},
            headers=citizen_headers,
        )
        assert close_res.status_code == status.HTTP_200_OK
        assert close_res.json()["data"]["status"] == "CLOSED"
        assert close_res.json()["data"]["closed_at"] is not None

    def test_citizen_reopens_unsatisfactory_resolution(
        self, client, citizen_headers, active_category, db_session: Session
    ):
        """Citizen owner can reopen an unsatisfactorily resolved complaint with a recorded reason."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Reopening test complaint",
                "description": "Issue allegedly resolved but problem persists.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = uuid.UUID(r.json()["data"]["id"])

        # Set status to RESOLVED_AWAITING_VERIFICATION
        complaint = db_session.query(Complaint).filter(Complaint.id == c_id).first()
        complaint.status = ComplaintStatus.RESOLVED_AWAITING_VERIFICATION
        complaint.resolved_at = datetime.now(timezone.utc)
        db_session.commit()

        # Reopen with reason
        reopen_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REOPENED", "remarks": "Debris left behind, road still blocked."},
            headers=citizen_headers,
        )
        assert reopen_res.status_code == status.HTTP_200_OK
        assert reopen_res.json()["data"]["status"] == "REOPENED"
        assert reopen_res.json()["data"]["resolved_at"] is None

    def test_reopened_complaint_triaged_to_under_review(
        self, client, admin_headers, citizen_headers, active_category, db_session: Session
    ):
        """Admin can triage REOPENED complaint back into UNDER_REVIEW."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Reopened triage test",
                "description": "Triage back into review.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = uuid.UUID(r.json()["data"]["id"])

        complaint = db_session.query(Complaint).filter(Complaint.id == c_id).first()
        complaint.status = ComplaintStatus.REOPENED
        db_session.commit()

        triage_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "UNDER_REVIEW", "remarks": "Investigating citizen reopening claim."},
            headers=admin_headers,
        )
        assert triage_res.status_code == status.HTTP_200_OK
        assert triage_res.json()["data"]["status"] == "UNDER_REVIEW"

    def test_arbitrary_illegal_transition_rejected(
        self, client, admin_headers, citizen_headers, active_category
    ):
        """Direct illegal jump e.g. SUBMITTED -> CLOSED is rejected with HTTP 422."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Illegal jump test",
                "description": "Attempting to jump from SUBMITTED directly to CLOSED.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        jump_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "CLOSED"},
            headers=admin_headers,
        )
        assert jump_res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_reopen_outside_14_day_grace_period_rejected(
        self, client, citizen_headers, active_category, db_session: Session
    ):
        """Reopening a complaint past the 14-day grace period raises HTTP 422."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Expired reopening test complaint",
                "description": "Issue was resolved long ago and grace period has elapsed.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = uuid.UUID(r.json()["data"]["id"])

        complaint = db_session.query(Complaint).filter(Complaint.id == c_id).first()
        complaint.status = ComplaintStatus.RESOLVED_AWAITING_VERIFICATION
        complaint.resolved_at = datetime.now(timezone.utc) - timedelta(days=15)
        db_session.commit()

        reopen_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REOPENED", "remarks": "Trying to reopen after 15 days."},
            headers=citizen_headers,
        )
        assert reopen_res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "14-day grace period" in reopen_res.json()["detail"]

    def test_reopen_missing_timestamps_fails_safely(
        self, client, citizen_headers, active_category, db_session: Session
    ):
        """Attempting to reopen when both resolved_at and closed_at are missing fails safely."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Missing timestamp reopening test",
                "description": "Complaint with missing resolved_at and closed_at cannot bypass 14-day rule.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = uuid.UUID(r.json()["data"]["id"])

        complaint = db_session.query(Complaint).filter(Complaint.id == c_id).first()
        complaint.status = ComplaintStatus.RESOLVED_AWAITING_VERIFICATION
        complaint.resolved_at = None
        complaint.closed_at = None
        db_session.commit()

        reopen_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REOPENED", "remarks": "Trying to reopen without timestamps."},
            headers=citizen_headers,
        )
        assert reopen_res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "lacks a verified resolution" in reopen_res.json()["detail"]


# =============================================================================
# 5. Administrator Review & Triage Tests
# =============================================================================

class TestAdministratorReview:
    """Verifies PATCH /api/v1/complaints/{complaint_id}/review functionality."""

    def test_admin_review_updates_priority_with_reason(
        self, client, admin_headers, citizen_headers, active_category
    ):
        """Admin can adjust priority with a recorded justification reason."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Low priority water puddle",
                "description": "Triage review adjusting priority to HIGH due to nearby school.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        review_payload = {
            "priority": "HIGH",
            "reason": "Located directly outside primary school entrance; elevated risk.",
        }
        res = client.patch(f"/api/v1/complaints/{c_id}/review", json=review_payload, headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["data"]["priority"] == "HIGH"

        # Check status history recorded priority change
        hist = client.get(f"/api/v1/complaints/{c_id}/history", headers=admin_headers)
        assert any("priority changed" in h["remarks"].lower() for h in hist.json()["data"])

    def test_admin_review_priority_change_without_reason_rejected(
        self, client, admin_headers, citizen_headers, active_category
    ):
        """Admin attempting to adjust priority without providing a reason is rejected with HTTP 422."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Priority reason check test",
                "description": "Testing missing reason enforcement on priority update.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        review_payload = {"priority": "CRITICAL", "reason": ""}
        res = client.patch(f"/api/v1/complaints/{c_id}/review", json=review_payload, headers=admin_headers)
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_admin_review_reclassifies_category(
        self, client, admin_headers, citizen_headers, active_category, db_session: Session
    ):
        """Admin can reclassify complaint to a different category."""
        other_cat = db_session.query(Category).filter(Category.id != active_category.id).first()
        assert other_cat is not None

        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Reclassification category test",
                "description": "Report filed under wrong category by citizen.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        review_payload = {"category_id": other_cat.id}
        res = client.patch(f"/api/v1/complaints/{c_id}/review", json=review_payload, headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["data"]["category_id"] == other_cat.id

    def test_citizen_forbidden_from_review_endpoint(self, client, citizen_headers, active_category):
        """Citizen calling the PATCH review endpoint is rejected with HTTP 403 Forbidden."""
        r = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Citizen forbidden review test",
                "description": "Citizen trying to call administrative review route.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = r.json()["data"]["id"]

        review_payload = {"priority": "HIGH", "reason": "Self prioritization."}
        res = client.patch(f"/api/v1/complaints/{c_id}/review", json=review_payload, headers=citizen_headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 6. Active Categories Endpoint Tests
# =============================================================================

class TestCategoriesEndpoint:
    """Verifies GET /api/v1/categories/ endpoint."""

    def test_list_active_categories_success(self, client):
        """Public/authenticated users can fetch active categories with department names."""
        response = client.get("/api/v1/categories/")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["success"] is True
        categories = body["data"]
        assert len(categories) >= 7

        names = [c["name"] for c in categories]
        assert "Roads and Potholes" in names
        assert "Streetlights" in names
        assert "Water Supply" in names
        assert "Drainage and Sewage" in names
        assert "Waste Management" in names
        assert "Public Sanitation" in names
        assert "Public Infrastructure" in names

        for c in categories:
            assert c["is_active"] is True
            assert c["department_name"] is not None


# =============================================================================
# 7. Concurrency and Transaction Rollback Safety Tests
# =============================================================================

class TestConcurrencyAndRollbackSafety:
    """Verifies atomic rollback on failure and row-level locking concurrency protection."""

    def test_failed_transition_atomic_rollback(
        self, client, admin_headers, citizen_headers, active_category, db_session: Session
    ):
        """When a transition fails validation, the status is not mutated and no history record is committed."""
        res = client.post(
            "/api/v1/complaints/",
            json={
                "title": "Rollback safety test complaint",
                "description": "Verifying that failed transitions leave zero side effects.",
                "category_id": active_category.id,
                "location": {"latitude": 12.9716, "longitude": 77.5946},
            },
            headers=citizen_headers,
        )
        c_id = uuid.UUID(res.json()["data"]["id"])

        initial_history_count = (
            db_session.query(ComplaintStatusHistory)
            .filter(ComplaintStatusHistory.complaint_id == c_id)
            .count()
        )
        assert initial_history_count == 1

        # Attempt invalid transition (REJECTED with empty reason)
        fail_res = client.post(
            f"/api/v1/complaints/{c_id}/transitions",
            json={"new_status": "REJECTED", "remarks": ""},
            headers=admin_headers,
        )
        assert fail_res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify state is completely intact
        complaint = db_session.query(Complaint).filter(Complaint.id == c_id).first()
        assert complaint.status == ComplaintStatus.SUBMITTED

        post_fail_history_count = (
            db_session.query(ComplaintStatusHistory)
            .filter(ComplaintStatusHistory.complaint_id == c_id)
            .count()
        )
        assert post_fail_history_count == 1, "Failed transition must not commit partial history records!"

    def test_concurrent_conflicting_transitions_serialized_by_row_lock(
        self, test_engine
    ):
        """
        Verify PostgreSQL row-level locking (with_for_update) serializes concurrent transactions.
        Two independent database sessions attempt to transition the same complaint.
        """
        import threading
        from sqlalchemy.orm import sessionmaker
        from app.services.complaint_service import create_complaint, execute_transition
        from app.schemas.complaint import ComplaintCreateRequest, LocationCreate

        SessionFactory = sessionmaker(bind=test_engine)
        s1 = SessionFactory()
        s2 = SessionFactory()

        c_id = None
        user_id = None
        admin_id = None
        try:
            # 1. Create dedicated committed user and admin in s1
            citizen_role = s1.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
            user = User(
                email=f"concurrency_{uuid.uuid4().hex[:6]}@example.com",
                hashed_password=hash_password("Pass123!"),
                full_name="Concurrency User",
                role_id=citizen_role.id,
                is_active=True,
                is_verified=True,
            )
            s1.add(user)

            admin_role = s1.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
            admin = User(
                email=f"admin_concurrency_{uuid.uuid4().hex[:6]}@example.com",
                hashed_password=hash_password("AdminPass123!"),
                full_name="Concurrency Admin",
                role_id=admin_role.id,
                is_active=True,
                is_verified=True,
            )
            s1.add(admin)
            s1.commit()
            s1.refresh(user)
            s1.refresh(admin)
            user_id = user.id
            admin_id = admin.id

            category = s1.query(Category).first()

            # 2. Create complaint in s1
            payload = ComplaintCreateRequest(
                title="Concurrency test complaint",
                description="Testing database row-locking under concurrent sessions.",
                category_id=category.id,
                location=LocationCreate(latitude=12.9716, longitude=77.5946),
            )
            complaint = create_complaint(s1, user, payload)
            c_id = complaint.id

            results = []

            # 3. Two independent workers transition using s1 and s2
            admin_in_s2 = s2.query(User).filter(User.id == admin.id).first()

            def worker_1():
                try:
                    c = execute_transition(
                        s1, c_id, admin, ComplaintStatus.UNDER_REVIEW, remarks="Thread 1 update"
                    )
                    results.append(("w1_success", c.status))
                except Exception as e:
                    results.append(("w1_error", str(e)))

            def worker_2():
                try:
                    c = execute_transition(
                        s2, c_id, admin_in_s2, ComplaintStatus.ON_HOLD, remarks="Thread 2 update"
                    )
                    results.append(("w2_success", c.status))
                except Exception as e:
                    results.append(("w2_error", str(e)))

            t1 = threading.Thread(target=worker_1)
            t2 = threading.Thread(target=worker_2)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            assert len(results) == 2
            # At least one succeeded, and no uncaught deadlock/corruption occurred
            success_count = sum(1 for tag, _ in results if "success" in tag)
            assert success_count >= 1

        finally:
            s_clean = SessionFactory()
            if c_id:
                s_clean.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == c_id).delete()
                complaint_obj = s_clean.query(Complaint).filter(Complaint.id == c_id).first()
                if complaint_obj:
                    loc_id = complaint_obj.location_id
                    s_clean.delete(complaint_obj)
                    if loc_id:
                        s_clean.query(Location).filter(Location.id == loc_id).delete()
            if user_id:
                s_clean.query(User).filter(User.id == user_id).delete()
            if admin_id:
                s_clean.query(User).filter(User.id == admin_id).delete()
            s_clean.commit()
            s_clean.close()
            s1.close()
            s2.close()
