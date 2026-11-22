"""
CivicPulse Security Module

Handles password hashing and JWT token management for the authentication
system. Uses Passlib with bcrypt for password hashing and PyJWT for
JSON Web Token encoding/decoding.

Design decisions:
    - Bcrypt is chosen for password hashing because it is purposefully
      slow and resistant to GPU-accelerated brute-force attacks.
    - JWT tokens carry only the user id and role in the payload;
      additional user data is loaded from the database per request
      to ensure freshness (e.g. if a user is deactivated).
    - Refresh tokens have a longer expiry and are used solely to
      obtain new access tokens without re-entering credentials.

Security notes:
    - JWT_SECRET_KEY must be a strong, randomly generated value.
    - Tokens are signed (HS256) but not encrypted; do not store
      sensitive data in the payload beyond user id and role.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config import get_settings

# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

# CryptContext manages hashing schemes. "bcrypt" is the default and only
# scheme; deprecated="auto" ensures that if we ever add a new scheme,
# passwords hashed with older schemes are automatically re-hashed on
# the next successful verification.
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The user's plain-text password.

    Returns:
        The bcrypt hash string (includes salt and algorithm metadata).
    """
    return password_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain_password: The password to verify.
        hashed_password: The stored hash to compare against.

    Returns:
        True if the password matches, False otherwise.
    """
    return password_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT Token Management
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str | int,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT access token.

    The token payload contains:
        sub  — user identifier (typically the user id)
        role — the user's role (CITIZEN, ADMIN, WORKER)
        exp  — expiration timestamp
        iat  — issued-at timestamp
        type — "access" to distinguish from refresh tokens

    Args:
        subject: The user identifier to embed as the "sub" claim.
        role: The user's role string.
        extra_claims: Optional additional claims to merge into the payload.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(subject: str | int) -> str:
    """
    Create a signed JWT refresh token.

    Refresh tokens have a longer expiry and carry only the user id.
    They are used exclusively to obtain new access tokens.

    Args:
        subject: The user identifier to embed as the "sub" claim.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Verifies the signature, expiration, and required claims.

    Args:
        token: The encoded JWT string.

    Returns:
        The decoded payload dictionary.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed or the
            signature is invalid.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
