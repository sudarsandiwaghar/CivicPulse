"""
CivicPulse Phase 3 Authentication & Authorization Tests

Comprehensive test suite verifying:
    - Citizen self-registration (validation, duplicate prevention, hashing).
    - Email/password authentication and timing-safe error responses.
    - JWT token generation, signature validation, and expiration enforcement.
    - Protected /me profile endpoint (safe field inspection, exclusion of hashes).
    - Role-based access control (CITIZEN, ADMINISTRATOR, FIELD_WORKER).
    - Inactive user rejection.
    - Privilege escalation prevention.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_citizen, require_worker
from app.config import get_settings
from app.core.constants import UserRole
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import get_role_by_name, init_roles


# ---------------------------------------------------------------------------
# Test Route Setup for RBAC Verification
# ---------------------------------------------------------------------------

rbac_test_router = APIRouter(prefix="/api/v1/test-rbac", tags=["Test-RBAC"])


@rbac_test_router.get("/admin-only", dependencies=[Depends(require_admin)])
def admin_only_endpoint():
    """Protected endpoint accessible only to ADMINISTRATOR role."""
    return {"message": "Admin access granted"}


@rbac_test_router.get("/worker-only", dependencies=[Depends(require_worker)])
def worker_only_endpoint():
    """Protected endpoint accessible only to FIELD_WORKER role."""
    return {"message": "Worker access granted"}


@rbac_test_router.get("/citizen-only", dependencies=[Depends(require_citizen)])
def citizen_only_endpoint():
    """Protected endpoint accessible to CITIZEN role."""
    return {"message": "Citizen access granted"}


# Mount test router on app once for test module
app.include_router(rbac_test_router)


# ---------------------------------------------------------------------------
# Helper Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_roles(db_session: Session):
    """Ensure core roles exist in the test session."""
    return init_roles(db_session)


@pytest.fixture
def citizen_user(db_session: Session, test_roles):
    """Create a sample active citizen user."""
    role = get_role_by_name(db_session, UserRole.CITIZEN.value)
    user = User(
        role_id=role.id,
        email=f"citizen_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("CitizenPass123!"),
        full_name="Aarav Patel",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_user(db_session: Session, test_roles):
    """Create a sample active administrator user."""
    role = get_role_by_name(db_session, UserRole.ADMINISTRATOR.value)
    user = User(
        role_id=role.id,
        email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("AdminPass123!"),
        full_name="System Admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def worker_user(db_session: Session, test_roles):
    """Create a sample active field worker user."""
    role = get_role_by_name(db_session, UserRole.FIELD_WORKER.value)
    user = User(
        role_id=role.id,
        email=f"worker_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("WorkerPass123!"),
        full_name="Ramesh Kumar",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


# ---------------------------------------------------------------------------
# 1. Registration Tests
# ---------------------------------------------------------------------------

class TestRegistration:
    """Tests for POST /api/v1/auth/register."""

    def test_successful_citizen_registration(self, client, test_roles):
        """Citizen can register with valid payload, receiving HTTP 201 and safe profile."""
        email = f"priya_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "full_name": "Priya Sharma",
            "email": email,
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_201_CREATED

        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Citizen registered successfully"

        data = body["data"]
        assert data["email"] == email.lower()
        assert data["full_name"] == "Priya Sharma"
        assert data["role"] == UserRole.CITIZEN.value
        assert data["is_active"] is True
        assert data["is_verified"] is False
        assert "id" in data
        # CRITICAL: Verify password hash is never leaked in the response
        assert "hashed_password" not in data
        assert "password" not in data

    def test_duplicate_email_registration_rejected(self, client, citizen_user):
        """Attempting to register an already existing email returns HTTP 409 Conflict."""
        payload = {
            "full_name": "Another Citizen",
            "email": citizen_user.email,  # Existing email
            "password": "AnotherPassword123!",
            "password_confirm": "AnotherPassword123!",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_409_CONFLICT

        body = response.json()
        assert body["success"] is False
        assert "already exists" in body["detail"].lower()

    def test_duplicate_email_case_insensitivity(self, client, citizen_user):
        """Email duplicate check must be case-insensitive (e.g. UPPER vs lower)."""
        payload = {
            "full_name": "Case Citizen",
            "email": citizen_user.email.upper(),  # Uppercase variant
            "password": "AnotherPassword123!",
            "password_confirm": "AnotherPassword123!",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_invalid_email_format_rejected(self, client):
        """Malformed email returns HTTP 422 Unprocessable Entity."""
        payload = {
            "full_name": "Bad Email Citizen",
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "password_confirm": "ValidPassword123!",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_mismatched_password_confirmation_rejected(self, client):
        """Password confirmation mismatch returns HTTP 422."""
        payload = {
            "full_name": "Mismatch Citizen",
            "email": f"mismatch_{uuid.uuid4().hex[:6]}@example.com",
            "password": "PasswordOne123!",
            "password_confirm": "PasswordTwo456!",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_short_password_rejected(self, client):
        """Password shorter than 8 characters returns HTTP 422."""
        payload = {
            "full_name": "Short Pass",
            "email": f"short_{uuid.uuid4().hex[:6]}@example.com",
            "password": "short",
            "password_confirm": "short",
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_privileged_role_cannot_be_injected(self, client, test_roles):
        """Even if client attempts to pass 'role': 'ADMINISTRATOR', CITIZEN is assigned."""
        email = f"sneaky_{uuid.uuid4().hex[:6]}@example.com"
        payload = {
            "full_name": "Sneaky User",
            "email": email,
            "password": "ValidPassword123!",
            "password_confirm": "ValidPassword123!",
            "role": "ADMINISTRATOR",  # Attempted privilege escalation
        }

        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        # Must strictly be CITIZEN
        assert body["data"]["role"] == UserRole.CITIZEN.value


# ---------------------------------------------------------------------------
# 2. Login Tests
# ---------------------------------------------------------------------------

class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_successful_login(self, client, citizen_user):
        """Valid credentials return HTTP 200 with JWT access token and user profile."""
        payload = {
            "email": citizen_user.email,
            "password": "CitizenPass123!",
        }

        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "access_token" in data
        assert data["token_type"].lower() == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["email"] == citizen_user.email
        assert data["user"]["role"] == UserRole.CITIZEN.value
        # Verify no hash in token response
        assert "hashed_password" not in data["user"]

    def test_incorrect_password_rejected(self, client, citizen_user):
        """Wrong password returns HTTP 401 with generic message."""
        payload = {
            "email": citizen_user.email,
            "password": "WrongPassword999!",
        }

        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        body = response.json()
        assert body["success"] is False
        assert "invalid email or password" in body["detail"].lower()
        # Verify WWW-Authenticate header
        assert "WWW-Authenticate" in response.headers

    def test_nonexistent_email_rejected_with_identical_error(self, client):
        """Unknown account returns HTTP 401 with exact same generic error message (anti-enumeration)."""
        payload = {
            "email": f"ghost_{uuid.uuid4().hex[:8]}@example.com",
            "password": "AnyPassword123!",
        }

        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        body = response.json()
        assert body["success"] is False
        # Exact same message as wrong password to prevent account enumeration
        assert "invalid email or password" in body["detail"].lower()

    def test_inactive_user_login_rejected(self, client, db_session, test_roles):
        """Deactivated user account is rejected on login."""
        role = get_role_by_name(db_session, UserRole.CITIZEN.value)
        inactive_user = User(
            role_id=role.id,
            email=f"inactive_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("InactivePass123!"),
            full_name="Inactive User",
            is_active=False,  # Inactive
        )
        db_session.add(inactive_user)
        db_session.flush()

        payload = {
            "email": inactive_user.email,
            "password": "InactivePass123!",
        }

        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "inactive" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Token & Profile (/me) Tests
# ---------------------------------------------------------------------------

class TestUserProfileAndTokens:
    """Tests for GET /api/v1/auth/me and token validation."""

    def test_authenticated_me_endpoint_success(self, client, citizen_user):
        """Valid Bearer token accesses /me returning safe profile data."""
        # 1. Login to get token
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": citizen_user.email, "password": "CitizenPass123!"},
        )
        token = login_res.json()["data"]["access_token"]

        # 2. Access /me
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["success"] is True
        profile = body["data"]
        assert profile["id"] == str(citizen_user.id)
        assert profile["email"] == citizen_user.email
        assert profile["full_name"] == citizen_user.full_name
        assert profile["role"] == UserRole.CITIZEN.value
        assert "hashed_password" not in profile

    def test_missing_authorization_header_rejected(self, client):
        """Calling /me without Authorization header returns HTTP 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "credentials were not provided" in response.json()["detail"].lower()

    def test_invalid_bearer_token_rejected(self, client):
        """Malformed or tampered token returns HTTP 401."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in response.json()["detail"].lower()

    def test_expired_token_rejected(self, client, citizen_user):
        """Expired JWT token returns HTTP 401 with expiration detail."""
        settings = get_settings()
        # Generate token with exp in the past
        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        expired_payload = {
            "sub": str(citizen_user.id),
            "role": citizen_user.role.name,
            "email": citizen_user.email,
            "exp": past_time,
            "iat": past_time - timedelta(minutes=30),
            "type": "access",
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in response.json()["detail"].lower()

    def test_token_contains_valid_claims(self, citizen_user):
        """JWT access token contains required standard and domain claims."""
        token = create_access_token(
            subject=citizen_user.id,
            role=citizen_user.role.name,
            extra_claims={"email": citizen_user.email},
        )
        decoded = decode_token(token)

        assert decoded["sub"] == str(citizen_user.id)
        assert decoded["role"] == UserRole.CITIZEN.value
        assert decoded["email"] == citizen_user.email
        assert decoded["type"] == "access"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_inactive_user_token_access_rejected(self, client, db_session, citizen_user):
        """If user is deactivated after token issue, request is rejected on live DB check."""
        token = create_access_token(
            subject=citizen_user.id,
            role=citizen_user.role.name,
        )

        # Deactivate user in database
        citizen_user.is_active = False
        db_session.flush()

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Live DB check discovers inactive account -> 403 Forbidden
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "inactive" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Role-Based Access Control (RBAC) Tests
# ---------------------------------------------------------------------------

class TestRoleBasedAccessControl:
    """Verifies that require_roles, require_admin, require_worker, and require_citizen enforce RBAC."""

    def test_citizen_accesses_citizen_endpoint(self, client, citizen_user):
        """Citizen accesses citizen-protected endpoint successfully."""
        token = create_access_token(citizen_user.id, citizen_user.role.name)
        response = client.get(
            "/api/v1/test-rbac/citizen-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_citizen_blocked_from_admin_endpoint(self, client, citizen_user):
        """Citizen attempting admin-only endpoint is rejected with HTTP 403 Forbidden."""
        token = create_access_token(citizen_user.id, citizen_user.role.name)
        response = client.get(
            "/api/v1/test-rbac/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        body = response.json()
        assert body["success"] is False
        assert "not authorized" in body["detail"].lower()

    def test_citizen_blocked_from_worker_endpoint(self, client, citizen_user):
        """Citizen attempting worker-only endpoint is rejected with HTTP 403 Forbidden."""
        token = create_access_token(citizen_user.id, citizen_user.role.name)
        response = client.get(
            "/api/v1/test-rbac/worker-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_accesses_admin_endpoint(self, client, admin_user):
        """Administrator accesses admin-only endpoint successfully."""
        token = create_access_token(admin_user.id, admin_user.role.name)
        response = client.get(
            "/api/v1/test-rbac/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Admin access granted"

    def test_worker_accesses_worker_endpoint(self, client, worker_user):
        """Field worker accesses worker-only endpoint successfully."""
        token = create_access_token(worker_user.id, worker_user.role.name)
        response = client.get(
            "/api/v1/test-rbac/worker-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Worker access granted"

    def test_forged_role_in_token_rejected_by_database_check(self, client, db_session, citizen_user):
        """
        If a token is signed with role='ADMINISTRATOR' for a user who is actually a CITIZEN
        in the database, the database check rejects the forged role.
        """
        # Attacker signs token with role='ADMINISTRATOR'
        forged_token = create_access_token(
            subject=citizen_user.id,
            role=UserRole.ADMINISTRATOR.value,
        )

        response = client.get(
            "/api/v1/test-rbac/admin-only",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        # The dependency loads current_user from DB where current_user.role.name == CITIZEN
        # So require_admin rejects with 403 Forbidden!
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "not authorized" in response.json()["detail"].lower()



# ---------------------------------------------------------------------------
# 5. Administrative Account Security Tests
# ---------------------------------------------------------------------------

class TestAdminProvisioning:
    """Tests for secure administrator provisioning utility."""

    def test_provision_administrator_success(self, db_session, test_roles):
        """Operator can securely provision an administrator directly via database."""
        from app.core.admin_provision import provision_administrator

        admin_email = f"operator_admin_{uuid.uuid4().hex[:6]}@civicpulse.gov"
        admin = provision_administrator(
            db=db_session,
            email=admin_email,
            full_name="Lead Infrastructure Operator",
            password="AdminSecurePassword123!",
        )

        assert admin is not None
        assert admin.email == admin_email
        assert admin.role.name == UserRole.ADMINISTRATOR.value
        assert verify_password("AdminSecurePassword123!", admin.hashed_password)
        assert admin.is_active is True
        assert admin.is_verified is True

    def test_provision_administrator_duplicate_rejected(self, db_session, admin_user):
        """Provisioning with an existing email raises EntityAlreadyExistsError."""
        from app.core.admin_provision import provision_administrator
        from app.core.exceptions import EntityAlreadyExistsError

        with pytest.raises(EntityAlreadyExistsError):
            provision_administrator(
                db=db_session,
                email=admin_user.email,
                full_name="Duplicate Admin",
                password="AnotherPassword123!",
            )
