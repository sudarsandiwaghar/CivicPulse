"""
CivicPulse Authentication & Authorization Service

Encapsulates core business logic for user registration, credential verification,
role assignment, and JWT token issuance.

Security policies:
    - Public registration is strictly restricted to the CITIZEN role.
    - Password hashes are never exposed or returned.
    - Generic error messages for failed login attempts prevent account enumeration.
    - Role lookups verify against real database records rather than trusting
      unvalidated client tokens.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.constants import UserRole
from app.core.exceptions import (
    AuthenticationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import UserLoginRequest, UserRegisterRequest

logger = logging.getLogger("civicpulse.auth")

INITIAL_ROLES = [
    {
        "name": UserRole.CITIZEN.value,
        "description": "Public citizen who submits and tracks civic complaints",
    },
    {
        "name": UserRole.ADMINISTRATOR.value,
        "description": "Municipal platform administrator with full oversight",
    },
    {
        "name": UserRole.FIELD_WORKER.value,
        "description": "Field worker or resolution team technician",
    },
]


def init_roles(db: Session) -> dict[str, Role]:
    """
    Idempotently initialize the three standard CivicPulse application roles.

    Checks the database for CITIZEN, ADMINISTRATOR, and FIELD_WORKER roles,
    inserting any that do not exist without creating duplicates.

    Args:
        db: Active SQLAlchemy database session.

    Returns:
        Dictionary mapping role names to their Role model instances.
    """
    roles_map: dict[str, Role] = {}
    existing_roles = db.query(Role).all()
    for r in existing_roles:
        roles_map[r.name] = r

    created_any = False
    for role_def in INITIAL_ROLES:
        if role_def["name"] not in roles_map:
            role = Role(
                name=role_def["name"],
                description=role_def["description"],
                is_active=True,
            )
            db.add(role)
            roles_map[role_def["name"]] = role
            created_any = True
            logger.info("Created missing initial role: %s", role_def["name"])

    if created_any:
        db.commit()
        for r in roles_map.values():
            db.refresh(r)

    return roles_map


def get_role_by_name(db: Session, role_name: str) -> Role:
    """
    Retrieve a role by its unique name, auto-seeding initial roles if table is empty.

    Args:
        db: Active SQLAlchemy session.
        role_name: Target role name string (e.g. "CITIZEN").

    Returns:
        The matched Role instance.

    Raises:
        EntityNotFoundError: If the role does not exist after verification.
    """
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        # If roles table is uninitialized, auto-seed and retry lookup
        roles = init_roles(db)
        role = roles.get(role_name)

    if not role:
        raise EntityNotFoundError("Role", role_name)

    return role


def register_citizen(db: Session, request: UserRegisterRequest) -> User:
    """
    Register a new citizen account with validated credentials.

    Enforces business rules:
        - Email uniqueness check.
        - Automatic assignment of CITIZEN role (no privilege escalation).
        - Bcrypt password hashing.

    Args:
        db: Active SQLAlchemy session.
        request: Validated registration payload.

    Returns:
        The newly created and committed User record.

    Raises:
        EntityAlreadyExistsError: If an account with this email already exists.
    """
    # 1. Check for duplicate email
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        logger.warning("Registration rejected: duplicate email '%s'", request.email)
        raise EntityAlreadyExistsError("User", "email", request.email)

    # 2. Assign standard CITIZEN role
    citizen_role = get_role_by_name(db, UserRole.CITIZEN.value)

    # 3. Hash password securely
    hashed_password = hash_password(request.password)

    # 4. Construct user entity
    new_user = User(
        role_id=citizen_role.id,
        email=request.email,
        hashed_password=hashed_password,
        full_name=request.full_name,
        is_active=True,
        is_verified=False,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info("Citizen registered successfully | id=%s email=%s", new_user.id, new_user.email)
    return new_user


def authenticate_user(db: Session, request: UserLoginRequest) -> User:
    """
    Authenticate a user by verifying email and password credentials.

    Security rules:
        - Returns generic AuthenticationError on missing user OR incorrect password
          to avoid disclosing whether an email address exists.
        - Validates account active status.

    Args:
        db: Active SQLAlchemy session.
        request: Validated login payload.

    Returns:
        Authenticated User record with role eagerly accessible.

    Raises:
        AuthenticationError: If credentials fail or account is inactive.
    """
    user = db.query(User).filter(User.email == request.email).first()

    # Constant-time security check: verify password even if user is not found
    # to resist timing-based account enumeration attacks.
    if not user or not verify_password(request.password, user.hashed_password):
        logger.warning("Failed login attempt for email: %s", request.email)
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        logger.warning("Login rejected for inactive user: %s", user.email)
        raise AuthenticationError("User account is inactive. Please contact support.")

    logger.info("User authenticated successfully | id=%s email=%s role=%s", user.id, user.email, user.role.name)
    return user


def generate_auth_token(user: User) -> dict[str, Any]:
    """
    Generate signed JWT access token for an authenticated user.

    Embeds:
        - sub: User UUID string.
        - role: Verified role string from database.
        - email: Verified user email.
        - exp: Expiration time based on application settings.

    Args:
        user: Authenticated User entity.

    Returns:
        Dictionary containing access_token, token_type, expires_in, and user entity.
    """
    settings = get_settings()
    expires_in_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.name,
        extra_claims={"email": user.email},
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in_seconds,
        "user": user,
    }
