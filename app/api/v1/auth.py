"""
CivicPulse Authentication API Endpoints

Provides REST endpoints for citizen registration, user authentication (login),
and profile inspection (/me).

Routes:
    POST /api/v1/auth/register — Public citizen registration.
    POST /api/v1/auth/login    — Email & password authentication, returning signed JWT.
    GET  /api/v1/auth/me       — Retrieve current authenticated user profile.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.common import ErrorResponse, StandardResponse
from app.services.auth_service import (
    authenticate_user,
    generate_auth_token,
    register_citizen,
)

router = APIRouter()


# =============================================================================
# Registration
# =============================================================================

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
    summary="Register a new citizen account",
    description=(
        "Registers a new public citizen user account. "
        "The account is automatically assigned the CITIZEN role. "
        "Privileged roles (ADMINISTRATOR, FIELD_WORKER) cannot be self-registered."
    ),
    responses={
        201: {
            "description": "Citizen account successfully created",
            "model": StandardResponse,
        },
        409: {
            "description": "Conflict: email address already registered",
            "model": ErrorResponse,
        },
        422: {
            "description": "Validation error: invalid input or mismatched passwords",
            "model": ErrorResponse,
        },
    },
)
def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Public registration endpoint for citizens.

    Args:
        payload: Full name, email, password, and confirmation.
        db: Request-scoped database session.

    Returns:
        StandardResponse containing the created user profile (safe fields only).
    """
    new_user = register_citizen(db=db, request=payload)
    user_response = UserResponse.model_validate(new_user)

    return StandardResponse(
        success=True,
        message="Citizen registered successfully",
        data=user_response.model_dump(mode="json"),
    )


# =============================================================================
# Authentication (Login)
# =============================================================================

@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Authenticate user and obtain JWT access token",
    description=(
        "Authenticates a user via registered email and password. "
        "Upon successful verification, returns a signed JWT access bearer token "
        "containing user identity and authorization role claims."
    ),
    responses={
        200: {
            "description": "Authentication successful, token issued",
            "model": StandardResponse,
        },
        401: {
            "description": "Authentication failed: invalid credentials or inactive account",
            "model": ErrorResponse,
        },
        422: {
            "description": "Validation error: invalid email or missing password",
            "model": ErrorResponse,
        },
    },
)
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    User login endpoint.

    Args:
        payload: Email and password.
        db: Request-scoped database session.

    Returns:
        StandardResponse containing the signed JWT access token and user profile.
    """
    user = authenticate_user(db=db, request=payload)
    token_data = generate_auth_token(user=user)

    token_response = TokenResponse(
        access_token=token_data["access_token"],
        token_type=token_data["token_type"],
        expires_in=token_data["expires_in"],
        user=UserResponse.model_validate(user),
    )

    return StandardResponse(
        success=True,
        message="Login successful",
        data=token_response.model_dump(mode="json"),
    )


# =============================================================================
# Profile (/me)
# =============================================================================

@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Retrieve current user profile",
    description=(
        "Returns the authenticated user's safe profile information. "
        "Requires a valid Bearer access token in the Authorization header."
    ),
    responses={
        200: {
            "description": "User profile successfully retrieved",
            "model": StandardResponse,
        },
        401: {
            "description": "Unauthorized: missing, expired, or invalid token",
            "model": ErrorResponse,
        },
        403: {
            "description": "Forbidden: account is inactive",
            "model": ErrorResponse,
        },
    },
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Get profile of the currently authenticated user.

    Args:
        current_user: User instance validated from Bearer token.

    Returns:
        StandardResponse with the user's public profile data.
    """
    user_response = UserResponse.model_validate(current_user)

    return StandardResponse(
        success=True,
        message="User profile retrieved successfully",
        data=user_response.model_dump(mode="json"),
    )
