"""
CivicPulse Administrative Provisioning Utility

Provides secure, offline functions to seed or provision initial platform
administrators without exposing public registration endpoints or hardcoding
credentials in source code or migrations.

Security principles:
    - Never exposed via public HTTP REST routes.
    - Operates directly via database session.
    - Normalises email, enforces password length, and applies bcrypt hashing.
"""

import logging
from sqlalchemy.orm import Session

from app.core.constants import UserRole
from app.core.exceptions import EntityAlreadyExistsError
from app.core.security import hash_password
from app.models.user import User
from app.services.auth_service import get_role_by_name

logger = logging.getLogger("civicpulse.admin_provision")


def provision_administrator(
    db: Session,
    email: str,
    full_name: str,
    password: str,
    phone_number: str | None = None,
) -> User:
    """
    Securely provision an administrator account.

    Designed for operator execution via CLI or deployment scripts.
    Never callable from unauthenticated public APIs.

    Args:
        db: Active SQLAlchemy database session.
        email: Administrator email address.
        full_name: Administrator display name.
        password: Plaintext password (must be >= 8 characters).
        phone_number: Optional contact phone number.

    Returns:
        The created User entity with ADMINISTRATOR role.

    Raises:
        ValueError: If password is too short or too long.
        EntityAlreadyExistsError: If email is already registered.
    """
    cleaned_email = email.strip().lower()
    if len(password) < 8 or len(password) > 72:
        raise ValueError("Administrator password must be between 8 and 72 characters")

    existing = db.query(User).filter(User.email == cleaned_email).first()
    if existing:
        raise EntityAlreadyExistsError("User", "email", cleaned_email)

    admin_role = get_role_by_name(db, UserRole.ADMINISTRATOR.value)
    hashed_pw = hash_password(password)

    admin_user = User(
        role_id=admin_role.id,
        email=cleaned_email,
        hashed_password=hashed_pw,
        full_name=full_name.strip(),
        phone_number=phone_number,
        is_active=True,
        is_verified=True,
    )

    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    logger.info("Administrator account provisioned securely | id=%s email=%s", admin_user.id, admin_user.email)
    return admin_user
