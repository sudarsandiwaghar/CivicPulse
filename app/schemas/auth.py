"""
CivicPulse Authentication Schemas

Pydantic request and response models for user registration, authentication,
token distribution, and profile inspection.

Security features:
    - Normalises email to lowercase to prevent casing-based duplicate accounts.
    - Password confirmation check during registration.
    - Strict boundary on password length (8 to 72 characters) for bcrypt compatibility.
    - Never includes password hashes or sensitive internal database columns in responses.
    - Public registration schema NEVER accepts role inputs (always CITIZEN).
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# =============================================================================
# Request Schemas
# =============================================================================

class UserRegisterRequest(BaseModel):
    """
    Payload for public citizen registration.

    Public registration is strictly restricted to the CITIZEN role.
    Privileged roles (ADMINISTRATOR, FIELD_WORKER) cannot be requested.
    """

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Full legal or display name of the citizen",
        examples=["Priya Sharma"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address used as the unique login username",
        examples=["priya.sharma@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Password meeting security criteria (8 to 72 characters)",
        examples=["SecurePassw0rd!"],
    )
    password_confirm: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Password confirmation matching password",
        examples=["SecurePassw0rd!"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: Any) -> str:
        """Normalise email to trimmed lowercase to ensure uniqueness consistency."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Strip surrounding whitespace from name."""
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must contain at least 2 non-whitespace characters")
        return cleaned

    @model_validator(mode="after")
    def verify_password_match(self) -> "UserRegisterRequest":
        """Verify that password and password_confirm match identically."""
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self


class UserLoginRequest(BaseModel):
    """
    Payload for user email and password authentication.
    """

    email: EmailStr = Field(
        ...,
        description="Registered user email address",
        examples=["priya.sharma@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=72,
        description="Plaintext password for verification",
        examples=["SecurePassw0rd!"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: Any) -> str:
        """Normalise email to trimmed lowercase."""
        if isinstance(v, str):
            return v.strip().lower()
        return v


# =============================================================================
# Response Schemas
# =============================================================================

class UserResponse(BaseModel):
    """
    Public safe profile response for a platform user.

    Excludes password hashes, secret tokens, and internal security fields.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="Unique user UUID identifier",
    )
    email: str = Field(
        ...,
        description="User email address",
    )
    full_name: str = Field(
        ...,
        description="User display name",
    )
    phone_number: str | None = Field(
        default=None,
        description="Contact phone number if registered",
    )
    role: str = Field(
        ...,
        description="Assigned authorization role name (CITIZEN, ADMINISTRATOR, FIELD_WORKER)",
    )
    is_active: bool = Field(
        ...,
        description="Account operational active flag",
    )
    is_verified: bool = Field(
        ...,
        description="Citizen verification status flag",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp of account creation (UTC)",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of last account update (UTC)",
    )

    @field_validator("role", mode="before")
    @classmethod
    def extract_role_name(cls, v: Any) -> str:
        """Extract string role name from Role model instance or enum."""
        if hasattr(v, "name"):
            return v.name
        return str(v)


class TokenResponse(BaseModel):
    """
    Authentication token response containing signed JWT access token.
    """

    access_token: str = Field(
        ...,
        description="Signed JWT access bearer token",
    )
    token_type: str = Field(
        default="bearer",
        description="Authorization header token type",
    )
    expires_in: int = Field(
        ...,
        description="Token lifetime in seconds",
    )
    user: UserResponse = Field(
        ...,
        description="Authenticated user profile",
    )
