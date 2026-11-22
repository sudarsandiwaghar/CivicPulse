"""
CivicPulse Constants and Enumerations

Defines application-wide enumerations and constant values used across
multiple modules. These ensure consistency between database models,
API schemas, and business logic.

Enumerations use Python's str + Enum pattern so their values serialise
directly to JSON-friendly strings (e.g. "SUBMITTED" rather than
"ComplaintStatus.SUBMITTED").
"""

from enum import Enum


# =============================================================================
# User Roles
# =============================================================================

class UserRole(str, Enum):
    """
    The three primary user categories in CivicPulse.

    CITIZEN       — Public users who submit and track complaints.
    ADMINISTRATOR — Platform administrators who manage complaints,
                    departments, categories, and worker assignments.
    FIELD_WORKER  — Field workers / resolution team members assigned
                    to investigate and resolve complaints.
    """
    CITIZEN = "CITIZEN"
    ADMINISTRATOR = "ADMINISTRATOR"
    FIELD_WORKER = "FIELD_WORKER"

    # Aliases for backward compatibility
    ADMIN = "ADMINISTRATOR"
    WORKER = "FIELD_WORKER"


# =============================================================================
# Assignment Status
# =============================================================================

class AssignmentStatus(str, Enum):
    """
    Status of a worker assignment to a complaint.

    ASSIGNED   — Worker assigned, pending start.
    IN_PROGRESS — Worker actively investigating/resolving.
    COMPLETED  — Work completed by assigned worker.
    REASSIGNED — Reassigned to another worker.
    """
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REASSIGNED = "REASSIGNED"


# =============================================================================
# Complaint Status Lifecycle
# =============================================================================

class ComplaintStatus(str, Enum):
    """
    All possible states in the complaint lifecycle.

    The valid transitions between states are enforced by
    COMPLAINT_STATUS_TRANSITIONS below, not by the enum itself.
    See the state machine diagram in ARCHITECTURE.md for a visual
    representation.

    Primary lifecycle:
        SUBMITTED → UNDER_REVIEW → ASSIGNED → IN_PROGRESS
        → RESOLVED_AWAITING_VERIFICATION → CLOSED

    Branching states:
        REJECTED   — Complaint deemed invalid or out of scope.
        DUPLICATE  — Merged with an existing complaint.
        ON_HOLD    — Temporarily paused (awaiting info, resources, etc.).
        REOPENED   — Citizen or admin reopened after resolution/closure.
    """
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED_AWAITING_VERIFICATION = "RESOLVED_AWAITING_VERIFICATION"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    ON_HOLD = "ON_HOLD"
    REOPENED = "REOPENED"


# Legal state transitions: maps each status to the set of statuses it
# may transition to. Any transition not listed here is invalid and must
# be rejected by the complaint service layer.
COMPLAINT_STATUS_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.SUBMITTED: {
        ComplaintStatus.UNDER_REVIEW,
        ComplaintStatus.REJECTED,
        ComplaintStatus.DUPLICATE,
    },
    ComplaintStatus.UNDER_REVIEW: {
        ComplaintStatus.ASSIGNED,
        ComplaintStatus.REJECTED,
        ComplaintStatus.DUPLICATE,
        ComplaintStatus.ON_HOLD,
    },
    ComplaintStatus.ASSIGNED: {
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.ON_HOLD,
    },
    ComplaintStatus.IN_PROGRESS: {
        ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        ComplaintStatus.ON_HOLD,
    },
    ComplaintStatus.RESOLVED_AWAITING_VERIFICATION: {
        ComplaintStatus.CLOSED,
        ComplaintStatus.REOPENED,
    },
    ComplaintStatus.CLOSED: {
        ComplaintStatus.REOPENED,
    },
    ComplaintStatus.ON_HOLD: {
        ComplaintStatus.UNDER_REVIEW,
        ComplaintStatus.IN_PROGRESS,
    },
    ComplaintStatus.REOPENED: {
        ComplaintStatus.UNDER_REVIEW,
    },
    # Terminal states with no outgoing transitions
    ComplaintStatus.REJECTED: set(),
    ComplaintStatus.DUPLICATE: set(),
}


# =============================================================================
# Complaint Priority Levels
# =============================================================================

class PriorityLevel(str, Enum):
    """
    Priority classification for complaints.

    Used by administrators and AI/ML models to triage complaints.
    AI-suggested priorities are stored as recommendations; only
    administrators can set the official priority.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =============================================================================
# Notification Types
# =============================================================================

class NotificationType(str, Enum):
    """
    Categories of in-app notifications.

    Each type maps to a specific event in the complaint lifecycle,
    enabling filtered notification retrieval and future notification
    preference controls.
    """
    STATUS_CHANGE = "STATUS_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"
    FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"
    FEEDBACK_REQUEST = "FEEDBACK_REQUEST"
    RESOLUTION_SUBMITTED = "RESOLUTION_SUBMITTED"
    COMPLAINT_REOPENED = "COMPLAINT_REOPENED"
    SLA_WARNING = "SLA_WARNING"
    SLA_BREACH = "SLA_BREACH"
    SYSTEM = "SYSTEM"


# =============================================================================
# Attachment Types
# =============================================================================

class AttachmentType(str, Enum):
    """
    Classifies the purpose of an uploaded file.

    COMPLAINT_EVIDENCE — Uploaded by the citizen with the initial report.
    RESOLUTION_EVIDENCE — Uploaded by the worker as proof of resolution.
    """
    COMPLAINT_EVIDENCE = "COMPLAINT_EVIDENCE"
    RESOLUTION_EVIDENCE = "RESOLUTION_EVIDENCE"
