"""
CivicPulse API Dependencies

FastAPI dependencies for authentication, token extraction, user retrieval,
and role-based access control (RBAC).

Security decisions:
    - Extracts Bearer token from HTTP Authorization header.
    - Decodes and verifies token signature and expiration against JWT_SECRET_KEY.
    - Retrieves the live User and Role records from the database to guarantee
      fresh authorization status (e.g. immediate revocation if account is deactivated).
    - Client-supplied claims are never trusted blindly without database confirmation.
"""

import uuid
from typing import Callable

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.constants import UserRole
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
# auto_error=False allows our custom exception handler to catch missing tokens
# and return the uniform CivicPulse ErrorResponse envelope.
bearer_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency to extract and validate the authenticated user from JWT token.

    Validates:
        1. Authorization header presence and Bearer scheme format.
        2. Token cryptographic signature and expiration time.
        3. Subject claim format (UUID).
        4. User record existence in database.
        5. User account active status.

    Args:
        credentials: Extracted HTTP Bearer credentials.
        db: Request-scoped database session.

    Returns:
        The verified, active User entity.

    Raises:
        AuthenticationError: If token is missing, expired, malformed, or user not found (HTTP 401).
        AuthorizationError: If user account is marked inactive (HTTP 403).
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication credentials were not provided")

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid authentication token")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Authentication token missing subject claim")

    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError):
        raise AuthenticationError("Malformed user identifier in authentication token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationError("Authenticated user account no longer exists")

    if not user.is_active:
        raise AuthorizationError("User account is inactive. Please contact support.")

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    FastAPI dependency to verify the authenticated user is currently active.

    Returns:
        The active User entity.
    """
    if not current_user.is_active:
        raise AuthorizationError("User account is inactive. Please contact support.")
    return current_user


def require_roles(*allowed_roles: UserRole | str) -> Callable[[User], User]:
    """
    Factory for role-based access control (RBAC) dependencies.

    Checks the authenticated user's role against the permitted roles.
    Always uses the database-stored role name.

    Usage:
        @router.get("/admin/dashboard", dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))])
        def admin_view(): ...

    Args:
        *allowed_roles: One or more allowed UserRole enums or string names.

    Returns:
        A dependency callable that checks authorization.
    """
    allowed_names = {
        r.value if hasattr(r, "value") else str(r) for r in allowed_roles
    }

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_name = current_user.role.name
        if user_role_name not in allowed_names:
            raise AuthorizationError(
                f"Role '{user_role_name}' is not authorized to access this resource"
            )
        return current_user

    return role_checker


# Convenient pre-configured role dependencies
require_citizen = require_roles(UserRole.CITIZEN)
require_admin = require_roles(UserRole.ADMINISTRATOR)
require_worker = require_roles(UserRole.FIELD_WORKER)
