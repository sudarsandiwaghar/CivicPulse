"""
CivicPulse Complaints API Router

Provides RESTful endpoints for citizen complaint submission, paginated listing,
detail inspection, status history tracking, lifecycle state machine transitions,
and administrator triage/review.

Security:
    - IDOR protection: Citizens can only access their authored complaints.
    - Role-Based Access Control: Admin review endpoints restricted to ADMINISTRATOR.
    - Server-side defaults: Client cannot supply arbitrary status, priority, or foreign identity.
    - PostgreSQL row-locking and atomic transactions on state transitions.
"""

import math
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin, require_citizen
from app.core.constants import ComplaintStatus, PriorityLevel
from app.db.session import get_db
from app.models.complaint import Complaint
from app.models.user import User
from app.schemas.assignment import (
    AssignmentResponse,
    ComplaintAssignRequest,
    ComplaintReassignRequest,
)
from app.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams, StandardResponse
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintDetailResponse,
    ComplaintResponse,
    ComplaintReviewRequest,
    ComplaintStatusHistoryResponse,
    ComplaintTransitionRequest,
    LocationResponse,
)
from app.schemas.follower import FollowActionResponse, FollowingListResponseData
from app.schemas.moderation import (
    ModeratePublicRequest,
    ModeratePublicResponse,
    UnpublishRequest,
    UnpublishResponse,
)
from app.services.assignment_service import (
    assign_complaint,
    get_complaint_assignments,
    reassign_complaint,
)
from app.services.complaint_service import (
    create_complaint,
    execute_transition,
    get_complaint_by_id,
    get_complaint_history,
    list_complaints,
    review_complaint,
)
from app.services.follower_service import (
    follow_complaint,
    list_followed_complaints,
    unfollow_complaint,
)
from app.services.public_complaint_service import (
    moderate_complaint_public,
    request_unpublish,
)
from app.services.timeline_service import get_complaint_timeline

router = APIRouter()


def _format_complaint(c: Complaint, include_history: bool = False) -> dict[str, Any]:
    """Helper to convert Complaint ORM instance into validated JSON-serializable dict."""
    loc_data = None
    if c.location:
        loc_data = LocationResponse.model_validate(c.location).model_dump(mode="json")

    history_data = []
    if include_history and c.status_history:
        for h in c.status_history:
            entry = ComplaintStatusHistoryResponse(
                id=h.id,
                complaint_id=h.complaint_id,
                changed_by_id=h.changed_by_id,
                changed_by_name=h.changed_by.full_name if h.changed_by else None,
                previous_status=h.previous_status,
                new_status=h.new_status,
                remarks=h.remarks,
                created_at=h.created_at,
            )
            history_data.append(entry.model_dump(mode="json"))

    resp = ComplaintResponse(
        id=c.id,
        complaint_number=c.complaint_number,
        citizen_id=c.citizen_id,
        citizen_name=c.citizen.full_name if c.citizen else None,
        category_id=c.category_id,
        category_name=c.category.name if c.category else None,
        location=loc_data,
        title=c.title,
        description=c.description,
        status=c.status,
        priority=c.priority,
        resolved_at=c.resolved_at,
        closed_at=c.closed_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    ).model_dump(mode="json")

    if include_history:
        resp["status_history"] = history_data

    return resp


# =============================================================================
# 1. Complaint Submission
# =============================================================================

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
    summary="Submit a new civic complaint",
    description=(
        "Registers a new civic complaint reported by an authenticated citizen. "
        "Server-side logic assigns initial status (SUBMITTED), default priority (MEDIUM), "
        "and generates a unique tracking reference code."
    ),
    responses={
        201: {"description": "Complaint successfully filed", "model": StandardResponse},
        400: {"description": "Validation error or invalid coordinates", "model": ErrorResponse},
        401: {"description": "Unauthorized: missing or invalid token", "model": ErrorResponse},
        403: {"description": "Forbidden: user is not a citizen", "model": ErrorResponse},
        404: {"description": "Category not found", "model": ErrorResponse},
        422: {"description": "Business rule violation or validation failure", "model": ErrorResponse},
    },
)
def submit_complaint(
    payload: ComplaintCreateRequest,
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Endpoint for authenticated citizens to file new civic complaints.
    """
    new_complaint = create_complaint(db=db, citizen=current_user, data=payload)
    return StandardResponse(
        success=True,
        message="Complaint submitted successfully",
        data=_format_complaint(new_complaint),
    )


# =============================================================================
# 2. Complaint Retrieval (Paginated)
# =============================================================================

@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=PaginatedResponse,
    summary="List complaints with pagination and filtering",
    description=(
        "Retrieves a paginated list of complaints. "
        "Citizens can retrieve only their own complaints. "
        "Administrators can access all complaints with filtering by status, priority, category, and date range."
    ),
    responses={
        200: {"description": "Paginated complaints list retrieved", "model": PaginatedResponse},
        401: {"description": "Unauthorized: missing or invalid token", "model": ErrorResponse},
        403: {"description": "Forbidden: worker or unauthorized access", "model": ErrorResponse},
    },
)
def get_complaints(
    status_filter: ComplaintStatus | None = Query(default=None, alias="status", description="Filter by status"),
    priority_filter: PriorityLevel | None = Query(default=None, alias="priority", description="Filter by priority"),
    category_id: int | None = Query(default=None, description="Filter by category ID"),
    complaint_number: str | None = Query(default=None, description="Filter by reference number"),
    search: str | None = Query(default=None, description="Search term in title, description, or code"),
    start_date: datetime | None = Query(default=None, description="Filter complaints created on or after UTC date"),
    end_date: datetime | None = Query(default=None, description="Filter complaints created on or before UTC date"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query(default="created_at", description="Field to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction (asc or desc)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    """
    Retrieve paginated complaints filtered by role and criteria.
    """
    filters = {
        "status": status_filter,
        "priority": priority_filter,
        "category_id": category_id,
        "complaint_number": complaint_number,
        "search": search,
        "start_date": start_date,
        "end_date": end_date,
    }
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    complaints, total_items = list_complaints(
        db=db,
        user=current_user,
        filters=filters,
        pagination=pagination,
    )

    data_items = [_format_complaint(c) for c in complaints]
    total_pages = math.ceil(total_items / pagination.page_size) if total_items > 0 else 0

    return PaginatedResponse(
        success=True,
        message="Complaints retrieved successfully",
        data=data_items,
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


# =============================================================================
# Followed Complaints Feed (Phase 6.2 - Must precede /{complaint_id})
# =============================================================================

@router.get(
    "/following",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get citizen's followed complaints feed",
    description="Retrieve paginated list of published complaints followed by the authenticated citizen.",
)
def get_followed_complaints(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=50, description="Items per page (max 50)"),
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Retrieve complaints followed by the current citizen.
    """
    items, total, total_pages = list_followed_complaints(
        db=db,
        citizen_user=current_user,
        page=page,
        page_size=page_size,
    )
    return StandardResponse(
        success=True,
        message="Followed complaints retrieved successfully",
        data=FollowingListResponseData(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        ).model_dump(),
    )


# =============================================================================
# 3. Single Complaint Retrieval
# =============================================================================

@router.get(
    "/{complaint_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get single complaint details",
    description=(
        "Retrieves detailed information for a specific complaint. "
        "Citizens can only view complaints they authored. "
        "Administrators can view any complaint."
    ),
    responses={
        200: {"description": "Complaint details found", "model": StandardResponse},
        401: {"description": "Unauthorized: missing or invalid token", "model": ErrorResponse},
        403: {"description": "Forbidden: citizen does not own this complaint", "model": ErrorResponse},
        404: {"description": "Complaint not found", "model": ErrorResponse},
    },
)
def get_complaint(
    complaint_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Retrieve full details for an individual complaint.
    """
    complaint = get_complaint_by_id(db=db, complaint_id=complaint_id, user=current_user)
    return StandardResponse(
        success=True,
        message="Complaint details retrieved successfully",
        data=_format_complaint(complaint, include_history=True),
    )


# =============================================================================
# 4. Status History Inspection
# =============================================================================

@router.get(
    "/{complaint_id}/history",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get complaint status transition history",
    description="Retrieves the chronological audit log of all status transitions for a complaint.",
    responses={
        200: {"description": "Status transition history", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Complaint not found", "model": ErrorResponse},
    },
)
def get_history(
    complaint_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Retrieve audit history entries for a specific complaint.
    """
    history_records = get_complaint_history(db=db, complaint_id=complaint_id, user=current_user)
    data = [
        ComplaintStatusHistoryResponse(
            id=h.id,
            complaint_id=h.complaint_id,
            changed_by_id=h.changed_by_id,
            changed_by_name=h.changed_by.full_name if h.changed_by else None,
            previous_status=h.previous_status,
            new_status=h.new_status,
            remarks=h.remarks,
            created_at=h.created_at,
        ).model_dump(mode="json")
        for h in history_records
    ]

    return StandardResponse(
        success=True,
        message="Complaint status history retrieved successfully",
        data=data,
    )


# =============================================================================
# 5. Administrator Review & Triage
# =============================================================================

@router.patch(
    "/{complaint_id}/review",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Administrator complaint review and triage",
    description=(
        "Allows administrators to review complaints, update status (UNDER_REVIEW, REJECTED, DUPLICATE, ON_HOLD), "
        "reclassify categories, and adjust operational priority with recorded reasons."
    ),
    responses={
        200: {"description": "Review action recorded successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Complaint or referenced category/duplicate not found", "model": ErrorResponse},
        422: {"description": "Invalid state transition or missing required reason", "model": ErrorResponse},
    },
)
def review(
    complaint_id: uuid.UUID,
    payload: ComplaintReviewRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Administrator review endpoint.
    """
    updated_complaint = review_complaint(
        db=db,
        complaint_id=complaint_id,
        admin_user=current_user,
        review=payload,
    )

    return StandardResponse(
        success=True,
        message="Complaint review processed successfully",
        data=_format_complaint(updated_complaint, include_history=True),
    )


# =============================================================================
# 6. Lifecycle Transitions
# =============================================================================

@router.post(
    "/{complaint_id}/transitions",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Execute complaint lifecycle state transition",
    description=(
        "Executes a validated status transition according to the lifecycle matrix. "
        "Citizens can verify and close or reopen resolved complaints. "
        "Administrators can move complaints through review stages."
    ),
    responses={
        200: {"description": "Status transition successful", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: role or ownership authority denied", "model": ErrorResponse},
        404: {"description": "Complaint not found", "model": ErrorResponse},
        422: {"description": "Invalid state transition or precondition failure", "model": ErrorResponse},
    },
)
def transition_status(
    complaint_id: uuid.UUID,
    payload: ComplaintTransitionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Execute a validated lifecycle state transition.
    """
    updated_complaint = execute_transition(
        db=db,
        complaint_id=complaint_id,
        user=current_user,
        requested_status=payload.new_status,
        remarks=payload.remarks,
        original_complaint_id=payload.original_complaint_id,
    )

    return StandardResponse(
        success=True,
        message=f"Complaint transitioned to '{updated_complaint.status.value}' successfully",
        data=_format_complaint(updated_complaint, include_history=True),
    )


# =============================================================================
# 7. Worker Assignment & Reassignment (Administrator Only)
# =============================================================================

@router.post(
    "/{complaint_id}/assign",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Assign complaint to field worker (Administrator only)",
    description=(
        "Assigns an UNDER_REVIEW complaint to an eligible field worker. "
        "Validates department-category compatibility, worker active status, "
        "creates an assignment record, and transitions complaint to ASSIGNED."
    ),
    responses={
        200: {"description": "Complaint assigned successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Complaint or Worker not found", "model": ErrorResponse},
        422: {"description": "Validation error or precondition failure", "model": ErrorResponse},
    },
)
def assign_complaint_to_worker(
    complaint_id: uuid.UUID,
    payload: ComplaintAssignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Administrator assigns complaint to worker."""
    assignment, complaint = assign_complaint(
        db=db,
        complaint_id=complaint_id,
        worker_id=payload.worker_id,
        admin_user=current_user,
        notes=payload.notes,
    )
    resp = AssignmentResponse(
        id=assignment.id,
        complaint_id=assignment.complaint_id,
        complaint_number=complaint.complaint_number,
        complaint_title=complaint.title,
        worker_id=assignment.worker_id,
        worker_name=assignment.worker.user.full_name if assignment.worker and assignment.worker.user else None,
        worker_employee_id=assignment.worker.employee_id if assignment.worker else None,
        department_id=assignment.worker.department_id if assignment.worker else None,
        department_name=assignment.worker.department.name if assignment.worker and assignment.worker.department else None,
        assigned_by_id=assignment.assigned_by_id,
        assigned_by_name=current_user.full_name,
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        accepted_at=assignment.accepted_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        notes=assignment.notes,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    ).model_dump(mode="json")

    return StandardResponse(
        success=True,
        message=f"Complaint assigned to worker '{assignment.worker.employee_id}' successfully",
        data=resp,
    )


@router.post(
    "/{complaint_id}/reassign",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Reassign complaint to replacement worker (Administrator only)",
    description=(
        "Reassigns an ASSIGNED or IN_PROGRESS complaint to another eligible field worker. "
        "Marks current assignment as REASSIGNED, creates a new assignment, and records audit reasons."
    ),
    responses={
        200: {"description": "Complaint reassigned successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Complaint or replacement worker not found", "model": ErrorResponse},
        422: {"description": "Validation error or invalid replacement worker", "model": ErrorResponse},
    },
)
def reassign_complaint_to_worker(
    complaint_id: uuid.UUID,
    payload: ComplaintReassignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Administrator reassigns complaint to replacement worker."""
    assignment, complaint = reassign_complaint(
        db=db,
        complaint_id=complaint_id,
        new_worker_id=payload.new_worker_id,
        admin_user=current_user,
        reason=payload.reason,
        notes=payload.notes,
    )
    resp = AssignmentResponse(
        id=assignment.id,
        complaint_id=assignment.complaint_id,
        complaint_number=complaint.complaint_number,
        complaint_title=complaint.title,
        worker_id=assignment.worker_id,
        worker_name=assignment.worker.user.full_name if assignment.worker and assignment.worker.user else None,
        worker_employee_id=assignment.worker.employee_id if assignment.worker else None,
        department_id=assignment.worker.department_id if assignment.worker else None,
        department_name=assignment.worker.department.name if assignment.worker and assignment.worker.department else None,
        assigned_by_id=assignment.assigned_by_id,
        assigned_by_name=current_user.full_name,
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        accepted_at=assignment.accepted_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        notes=assignment.notes,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    ).model_dump(mode="json")

    return StandardResponse(
        success=True,
        message=f"Complaint reassigned to worker '{assignment.worker.employee_id}' successfully",
        data=resp,
    )


@router.get(
    "/{complaint_id}/assignments",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get complaint assignment history (Administrator only)",
    description="Retrieves the chronological list of all assignments made for this complaint.",
    responses={
        200: {"description": "Assignment history retrieved", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Complaint not found", "model": ErrorResponse},
    },
)
def get_complaint_assignments_endpoint(
    complaint_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Administrator gets assignment history for a complaint."""
    # Ensure complaint exists
    get_complaint_by_id(db=db, complaint_id=complaint_id, user=current_user)
    assignments = get_complaint_assignments(db=db, complaint_id=complaint_id)
    data = [
        AssignmentResponse(
            id=a.id,
            complaint_id=a.complaint_id,
            complaint_number=a.complaint.complaint_number if a.complaint else None,
            complaint_title=a.complaint.title if a.complaint else None,
            worker_id=a.worker_id,
            worker_name=a.worker.user.full_name if a.worker and a.worker.user else None,
            worker_employee_id=a.worker.employee_id if a.worker else None,
            department_id=a.worker.department_id if a.worker else None,
            department_name=a.worker.department.name if a.worker and a.worker.department else None,
            assigned_by_id=a.assigned_by_id,
            assigned_by_name=a.assigned_by.full_name if a.assigned_by else None,
            status=a.status,
            assigned_at=a.assigned_at,
            accepted_at=a.accepted_at,
            started_at=a.started_at,
            completed_at=a.completed_at,
            notes=a.notes,
            created_at=a.created_at,
            updated_at=a.updated_at,
        ).model_dump(mode="json")
        for a in assignments
    ]
    return StandardResponse(
        success=True,
        message="Complaint assignment history retrieved successfully",
        data=data,
    )


# =============================================================================
# Unified Complaint Timeline (Phase 6.1)
# =============================================================================

@router.get(
    "/{complaint_id}/timeline",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get unified complaint timeline",
    description=(
        "Retrieves the chronological audit narrative of all milestones for this complaint, "
        "including submission, status transitions, technician assignments, field progress notes, "
        "and resolution/closure. Internal remarks are automatically redacted for citizens."
    ),
    responses={
        200: {"description": "Complaint timeline retrieved successfully", "model": StandardResponse},
        401: {"description": "Unauthorized: missing or invalid token", "model": ErrorResponse},
        403: {"description": "Forbidden: access restricted", "model": ErrorResponse},
        404: {"description": "Complaint not found", "model": ErrorResponse},
    },
)
def get_complaint_timeline_endpoint(
    complaint_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Retrieve unified chronological complaint audit timeline.
    Accessible to:
      - Author Citizen (internal remarks redacted)
      - Assigned Field Worker (active or bounded by assignment period)
      - Administrator (unrestricted)
    """
    timeline_data = get_complaint_timeline(db=db, complaint_id=complaint_id, user=current_user)
    return StandardResponse(
        success=True,
        message="Complaint timeline retrieved successfully",
        data=timeline_data,
    )


# =============================================================================
# Public Moderation & Community Following (Phase 6.2)
# =============================================================================

@router.post(
    "/{complaint_id}/moderate-public",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Moderate complaint public visibility",
    description="Administrator publishes, updates approved public content, or revokes publication.",
)
def moderate_public_endpoint(
    complaint_id: uuid.UUID,
    request: ModeratePublicRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Administrator endpoint for public content moderation.
    """
    res = moderate_complaint_public(
        db=db,
        complaint_id=complaint_id,
        admin_user=current_user,
        request=request,
    )
    return StandardResponse(
        success=True,
        message=res.message,
        data=res.model_dump(),
    )


@router.post(
    "/{complaint_id}/request-unpublish",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Request unpublishing of citizen complaint",
    description="Allows the complaint author to immediately unpublish their complaint from public feeds.",
)
def request_unpublish_endpoint(
    complaint_id: uuid.UUID,
    request: UnpublishRequest | None = None,
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Citizen endpoint for unpublishing their own complaint.
    """
    reason = request.reason if request else None
    res = request_unpublish(
        db=db,
        complaint_id=complaint_id,
        citizen_user=current_user,
        reason=reason,
    )
    return StandardResponse(
        success=True,
        message=res.message,
        data=res.model_dump(),
    )


@router.post(
    "/{complaint_id}/follow",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Follow a public complaint",
    description="Allows authenticated citizens to follow a public complaint for updates.",
)
def follow_complaint_endpoint(
    complaint_id: uuid.UUID,
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Citizen endpoint to subscribe/follow a public complaint.
    """
    res = follow_complaint(
        db=db,
        complaint_id=complaint_id,
        citizen_user=current_user,
    )
    return StandardResponse(
        success=True,
        message=res.message,
        data=res.model_dump(),
    )


@router.delete(
    "/{complaint_id}/follow",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Unfollow a complaint",
    description="Allows authenticated citizens to unfollow a complaint.",
)
def unfollow_complaint_endpoint(
    complaint_id: uuid.UUID,
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Citizen endpoint to unfollow a complaint.
    """
    res = unfollow_complaint(
        db=db,
        complaint_id=complaint_id,
        citizen_user=current_user,
    )
    return StandardResponse(
        success=True,
        message=res.message,
        data=res.model_dump(),
    )
