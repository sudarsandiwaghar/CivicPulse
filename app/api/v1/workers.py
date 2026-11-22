"""
CivicPulse Field Workers API Router

Provides endpoints for administrator worker provisioning and management,
as well as authenticated worker task inspection, acceptance, progress tracking,
and completion workflows.
"""

import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin, require_worker
from app.core.constants import AssignmentStatus, PriorityLevel
from app.db.session import get_db
from app.models.assignment import Assignment
from app.models.user import User
from app.models.worker import Worker
from app.schemas.assignment import (
    AssignmentProgressResponse,
    AssignmentResponse,
    WorkCompleteRequest,
    WorkProgressRequest,
    WorkerTaskDetailResponse,
    WorkerTaskResponse,
)
from app.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams, StandardResponse
from app.schemas.complaint import LocationResponse
from app.schemas.worker import (
    WorkerCreateRequest,
    WorkerDetailResponse,
    WorkerResponse,
    WorkerUpdateRequest,
)
from app.services.assignment_service import (
    accept_assignment,
    add_assignment_progress,
    complete_assignment,
    get_worker_task_by_id,
    get_worker_tasks,
    start_assignment,
)
from app.services.worker_service import (
    create_worker,
    deactivate_worker,
    get_worker_by_id,
    list_workers,
    update_worker,
)

router = APIRouter()


def _format_worker(worker: Worker, detailed: bool = False) -> dict[str, Any]:
    """Helper to convert Worker ORM entity into validated JSON response dict."""
    active_count = 0
    completed_count = 0
    if detailed and worker.assignments:
        for a in worker.assignments:
            if a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}:
                active_count += 1
            elif a.status == AssignmentStatus.COMPLETED:
                completed_count += 1

    resp = WorkerResponse(
        id=worker.id,
        user_id=worker.user_id,
        department_id=worker.department_id,
        department_name=worker.department.name if worker.department else None,
        employee_id=worker.employee_id,
        designation=worker.designation,
        is_available=worker.is_available,
        employment_status=worker.employment_status,
        full_name=worker.user.full_name if worker.user else None,
        email=worker.user.email if worker.user else None,
        phone_number=worker.user.phone_number if worker.user else None,
        created_at=worker.created_at,
        updated_at=worker.updated_at,
    ).model_dump(mode="json")

    if detailed:
        resp["active_tasks_count"] = active_count
        resp["completed_tasks_count"] = completed_count

    return resp


def _format_worker_task(a: Assignment, detailed: bool = False) -> dict[str, Any]:
    """Helper to convert Assignment into WorkerTaskResponse."""
    loc_data = None
    if a.complaint and a.complaint.location:
        loc_data = LocationResponse.model_validate(a.complaint.location).model_dump(mode="json")

    progress_history = []
    if detailed and a.progress_updates:
        for p in a.progress_updates:
            entry = AssignmentProgressResponse(
                id=p.id,
                assignment_id=p.assignment_id,
                worker_id=p.worker_id,
                worker_name=p.worker.user.full_name if p.worker and p.worker.user else None,
                description=p.description,
                created_at=p.created_at,
            )
            progress_history.append(entry.model_dump(mode="json"))

    resp = WorkerTaskResponse(
        assignment_id=a.id,
        complaint_id=a.complaint_id,
        complaint_number=a.complaint.complaint_number if a.complaint else "UNKNOWN",
        title=a.complaint.title if a.complaint else "Untitled",
        description=a.complaint.description if a.complaint else "",
        category_name=a.complaint.category.name if a.complaint and a.complaint.category else None,
        priority=a.complaint.priority if a.complaint else PriorityLevel.MEDIUM,
        complaint_status=a.complaint.status if a.complaint else "UNKNOWN",
        assignment_status=a.status,
        location=loc_data,
        assigned_at=a.assigned_at,
        accepted_at=a.accepted_at,
        started_at=a.started_at,
        completed_at=a.completed_at,
        notes=a.notes,
    ).model_dump(mode="json")

    if detailed:
        resp["citizen_name"] = a.complaint.citizen.full_name if a.complaint and a.complaint.citizen else None
        resp["progress_history"] = progress_history

    return resp


# =============================================================================
# 1. Administrator Worker Management
# =============================================================================

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
    summary="Provision a field worker account (Administrator only)",
    description="Atomically provisions a User account with FIELD_WORKER role and an associated Worker profile.",
    responses={
        201: {"description": "Worker successfully provisioned", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Department not found", "model": ErrorResponse},
        409: {"description": "Conflict: email or employee ID already exists", "model": ErrorResponse},
        422: {"description": "Validation or inactive department error", "model": ErrorResponse},
    },
)
def provision_worker(
    payload: WorkerCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Provision a new field technician account."""
    new_worker = create_worker(db=db, data=payload)
    return StandardResponse(
        success=True,
        message=f"Field worker '{new_worker.employee_id}' provisioned successfully",
        data=_format_worker(new_worker, detailed=True),
    )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=PaginatedResponse,
    summary="List field workers (Administrator only)",
    description="Retrieves a paginated list of field workers with optional department, availability, and employment status filters.",
    responses={
        200: {"description": "Workers list retrieved", "model": PaginatedResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
    },
)
def get_workers(
    department_id: int | None = Query(default=None, description="Filter by department ID"),
    is_available: bool | None = Query(default=None, description="Filter by availability status"),
    employment_status: str | None = Query(default=None, description="Filter by employment status (ACTIVE, ON_LEAVE, INACTIVE)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    """List field workers."""
    pagination = PaginationParams(page=page, page_size=page_size)
    workers, total_items = list_workers(
        db=db,
        department_id=department_id,
        is_available=is_available,
        employment_status=employment_status,
        pagination=pagination,
    )
    total_pages = math.ceil(total_items / pagination.page_size) if total_items > 0 else 0
    data = [_format_worker(w) for w in workers]

    return PaginatedResponse(
        success=True,
        message="Field workers retrieved successfully",
        data=data,
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


# =============================================================================
# 2. Worker Self Task Operations (/workers/me/tasks)
# NOTE: Must be defined BEFORE /workers/{worker_id} to avoid route masking
# =============================================================================

@router.get(
    "/me/tasks",
    status_code=status.HTTP_200_OK,
    response_model=PaginatedResponse,
    summary="Get assigned tasks for authenticated field worker",
    description="Retrieves tasks assigned strictly to the authenticated field technician.",
    responses={
        200: {"description": "Assigned tasks retrieved", "model": PaginatedResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires FIELD_WORKER role", "model": ErrorResponse},
    },
)
def get_my_tasks(
    status_filter: AssignmentStatus | None = Query(default=None, alias="status", description="Filter by assignment status"),
    priority_filter: PriorityLevel | None = Query(default=None, alias="priority", description="Filter by priority"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    """Worker task queue."""
    pagination = PaginationParams(page=page, page_size=page_size)
    tasks, total_items = get_worker_tasks(
        db=db,
        worker_user=current_user,
        status_filter=status_filter,
        priority_filter=priority_filter,
        pagination=pagination,
    )
    total_pages = math.ceil(total_items / pagination.page_size) if total_items > 0 else 0
    data = [_format_worker_task(t) for t in tasks]

    return PaginatedResponse(
        success=True,
        message="Assigned tasks retrieved successfully",
        data=data,
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get(
    "/me/tasks/{assignment_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get single assigned task detail (Field Worker only)",
    description="Retrieves full details of a specific assigned task with complete progress history.",
    responses={
        200: {"description": "Task detail retrieved", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: worker does not own this assignment", "model": ErrorResponse},
        404: {"description": "Task not found", "model": ErrorResponse},
    },
)
def get_my_task(
    assignment_id: uuid.UUID,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Worker single task detail."""
    task = get_worker_task_by_id(db=db, assignment_id=assignment_id, worker_user=current_user)
    return StandardResponse(
        success=True,
        message="Task detail retrieved successfully",
        data=_format_worker_task(task, detailed=True),
    )


@router.post(
    "/me/tasks/{assignment_id}/accept",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Accept assigned task (Field Worker only)",
    description="Technician acknowledges receipt of an assigned complaint task.",
    responses={
        200: {"description": "Task accepted successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: worker does not own task or is inactive", "model": ErrorResponse},
        404: {"description": "Task not found", "model": ErrorResponse},
        422: {"description": "Invalid assignment status", "model": ErrorResponse},
    },
)
def accept_task(
    assignment_id: uuid.UUID,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Worker task acceptance."""
    assignment = accept_assignment(db=db, assignment_id=assignment_id, worker_user=current_user)
    return StandardResponse(
        success=True,
        message="Task accepted successfully",
        data=_format_worker_task(assignment, detailed=True),
    )


@router.post(
    "/me/tasks/{assignment_id}/start",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Start work on assigned task (Field Worker only)",
    description="Technician initiates work on site, moving assignment and complaint to IN_PROGRESS.",
    responses={
        200: {"description": "Work started successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: worker does not own task or is inactive", "model": ErrorResponse},
        404: {"description": "Task not found", "model": ErrorResponse},
        422: {"description": "Invalid state transition or precondition failure", "model": ErrorResponse},
    },
)
def start_task(
    assignment_id: uuid.UUID,
    notes: str | None = Query(default=None, description="Optional dispatch remarks"),
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Worker initiates on-site investigation/work."""
    assignment, complaint = start_assignment(
        db=db,
        assignment_id=assignment_id,
        worker_user=current_user,
        notes=notes,
    )
    return StandardResponse(
        success=True,
        message="Work started successfully. Complaint is now IN_PROGRESS.",
        data=_format_worker_task(assignment, detailed=True),
    )


@router.post(
    "/me/tasks/{assignment_id}/progress",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
    summary="Record progress update for active task (Field Worker only)",
    description="Adds an immutable milestone or observation entry to the assignment progress audit log.",
    responses={
        201: {"description": "Progress update recorded", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: worker does not own task", "model": ErrorResponse},
        404: {"description": "Task not found", "model": ErrorResponse},
        422: {"description": "Invalid assignment status (must be IN_PROGRESS)", "model": ErrorResponse},
    },
)
def log_progress(
    assignment_id: uuid.UUID,
    payload: WorkProgressRequest,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Worker adds progress update."""
    progress = add_assignment_progress(
        db=db,
        assignment_id=assignment_id,
        worker_user=current_user,
        description=payload.description,
    )
    resp = AssignmentProgressResponse(
        id=progress.id,
        assignment_id=progress.assignment_id,
        worker_id=progress.worker_id,
        worker_name=current_user.full_name,
        description=progress.description,
        created_at=progress.created_at,
    ).model_dump(mode="json")

    return StandardResponse(
        success=True,
        message="Progress update recorded successfully",
        data=resp,
    )


@router.post(
    "/me/tasks/{assignment_id}/complete",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Submit work completion for verification (Field Worker only)",
    description="Technician finishes work, moving assignment to COMPLETED and complaint to RESOLVED_AWAITING_VERIFICATION.",
    responses={
        200: {"description": "Task completed successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Task not found", "model": ErrorResponse},
        422: {"description": "Invalid status or missing completion summary", "model": ErrorResponse},
    },
)
def complete_task(
    assignment_id: uuid.UUID,
    payload: WorkCompleteRequest,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Worker completes work on task."""
    assignment, complaint = complete_assignment(
        db=db,
        assignment_id=assignment_id,
        worker_user=current_user,
        summary=payload.summary,
    )
    return StandardResponse(
        success=True,
        message="Work completed. Complaint is now in RESOLVED_AWAITING_VERIFICATION.",
        data=_format_worker_task(assignment, detailed=True),
    )


# =============================================================================
# 3. Administrator Worker Inspection & Updates (/workers/{worker_id})
# =============================================================================

@router.get(
    "/{worker_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get worker details by ID (Administrator only)",
    description="Retrieves a specific field worker profile and task metrics.",
    responses={
        200: {"description": "Worker details retrieved", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Worker not found", "model": ErrorResponse},
    },
)
def get_worker(
    worker_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Get single worker details."""
    worker = get_worker_by_id(db=db, worker_id=worker_id)
    return StandardResponse(
        success=True,
        message="Worker details retrieved successfully",
        data=_format_worker(worker, detailed=True),
    )


@router.patch(
    "/{worker_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Update field worker profile (Administrator only)",
    description="Updates worker department, designation, availability, employment status, or name.",
    responses={
        200: {"description": "Worker profile updated", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Worker or Department not found", "model": ErrorResponse},
        422: {"description": "Invalid department or status", "model": ErrorResponse},
    },
)
def update_existing_worker(
    worker_id: uuid.UUID,
    payload: WorkerUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Update worker profile."""
    worker = update_worker(db=db, worker_id=worker_id, data=payload)
    return StandardResponse(
        success=True,
        message="Worker profile updated successfully",
        data=_format_worker(worker, detailed=True),
    )


@router.patch(
    "/{worker_id}/deactivate",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Deactivate worker account (Administrator only)",
    description="Sets worker availability to False, employment_status to INACTIVE, and deactivates base user account safely.",
    responses={
        200: {"description": "Worker deactivated successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Worker not found", "model": ErrorResponse},
    },
)
@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Soft-deactivate worker account (DELETE alias)",
    description="Sets worker availability to False, employment_status to INACTIVE, and deactivates base user account.",
    responses={
        200: {"description": "Worker deactivated successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Worker not found", "model": ErrorResponse},
    },
)
def deactivate_existing_worker(
    worker_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Deactivate worker account."""
    worker = deactivate_worker(db=db, worker_id=worker_id)
    return StandardResponse(
        success=True,
        message=f"Worker '{worker.employee_id}' deactivated successfully",
        data=_format_worker(worker, detailed=True),
    )
