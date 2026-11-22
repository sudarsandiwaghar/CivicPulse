"""
CivicPulse Custom Exception Hierarchy

Defines application-specific exceptions that map cleanly to HTTP error
responses. The FastAPI exception handlers in main.py catch these and
return structured JSON error bodies.

Design rationale:
    Rather than raising generic HTTPException everywhere (which scatters
    HTTP concerns into the service layer), services raise these domain
    exceptions. The API layer catches and translates them, keeping
    business logic decoupled from HTTP semantics.

Usage:
    from app.core.exceptions import EntityNotFoundError

    raise EntityNotFoundError("Complaint", complaint_id)
    # → {"detail": "Complaint with id '42' not found"}
"""

from typing import Any


class CivicPulseError(Exception):
    """
    Base exception for all CivicPulse application errors.

    All custom exceptions inherit from this class so they can be
    caught collectively when needed (e.g. in a top-level handler).

    Attributes:
        message: Human-readable error description.
    """

    def __init__(self, message: str = "An application error occurred"):
        self.message = message
        super().__init__(self.message)


# =============================================================================
# Authentication & Authorization Errors
# =============================================================================

class AuthenticationError(CivicPulseError):
    """
    Raised when authentication fails.

    Examples: invalid credentials, expired token, malformed token.
    Maps to HTTP 401 Unauthorized.
    """

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class AuthorizationError(CivicPulseError):
    """
    Raised when an authenticated user lacks permission for an action.

    Examples: citizen trying to access admin routes, worker trying
    to assign complaints. Maps to HTTP 403 Forbidden.
    """

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message)


# =============================================================================
# Entity Errors
# =============================================================================

class EntityNotFoundError(CivicPulseError):
    """
    Raised when a requested entity does not exist in the database.

    Maps to HTTP 404 Not Found.

    Args:
        entity_type: Name of the entity (e.g. "Complaint", "User").
        entity_id: The identifier that was looked up.
    """

    def __init__(self, entity_type: str, entity_id: Any):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(
            f"{entity_type} with id '{entity_id}' not found"
        )


class EntityAlreadyExistsError(CivicPulseError):
    """
    Raised when creating an entity that conflicts with an existing one.

    Examples: registering with a duplicate email, creating a category
    with an existing name. Maps to HTTP 409 Conflict.

    Args:
        entity_type: Name of the entity (e.g. "User").
        field: The field that caused the conflict (e.g. "email").
        value: The conflicting value.
    """

    def __init__(self, entity_type: str, field: str, value: Any):
        self.entity_type = entity_type
        self.field = field
        self.value = value
        super().__init__(
            f"{entity_type} with {field} '{value}' already exists"
        )


# =============================================================================
# Business Logic Errors
# =============================================================================

class InvalidStateTransitionError(CivicPulseError):
    """
    Raised when a complaint status transition violates the lifecycle.

    The valid transitions are defined in core.constants.
    COMPLAINT_STATUS_TRANSITIONS. Maps to HTTP 422 Unprocessable Entity.

    Args:
        current_status: The complaint's current status.
        requested_status: The status that was requested.
        reason: Optional detailed explanation of why the transition was rejected.
    """

    def __init__(
        self,
        current_status: str,
        requested_status: str,
        reason: str | None = None,
    ):
        self.current_status = current_status
        self.requested_status = requested_status
        self.reason = reason
        message = f"Cannot transition from '{current_status}' to '{requested_status}'"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class BusinessRuleViolationError(CivicPulseError):
    """
    Raised when an operation violates a domain business rule.

    A general-purpose exception for rules that don't fit a more
    specific exception class. Maps to HTTP 422 Unprocessable Entity.

    Args:
        rule: Short description of the violated rule.
    """

    def __init__(self, rule: str):
        self.rule = rule
        super().__init__(f"Business rule violation: {rule}")


# =============================================================================
# File / Upload Errors
# =============================================================================

class FileUploadError(CivicPulseError):
    """
    Raised when a file upload fails validation or storage.

    Examples: file too large, unsupported extension, storage write
    failure. Maps to HTTP 400 Bad Request.
    """

    def __init__(self, message: str = "File upload failed"):
        super().__init__(message)


# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimitExceededError(CivicPulseError):
    """
    Raised when a client exceeds the configured request rate limit.

    Maps to HTTP 429 Too Many Requests.
    """

    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message)
