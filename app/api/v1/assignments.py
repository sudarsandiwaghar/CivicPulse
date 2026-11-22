"""
CivicPulse Assignments API Router

Provides administrator-only endpoints for platform-wide assignment monitoring,
inspection, and complete progress history audit tracking.
"""

import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.constants import AssignmentStatus
from app.db.session import get_db
from app.models.assignment import Assignment
from app.models.user import User
from app.schemas.assignment import (
    AssignmentDetailResponse,
    AssignmentProgressResponse,
    AssignmentResponse,
)
from app.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams, StandardResponse
from app.services.assignment_service import get_assignment_by_id, list_assignments

router = APIRouter()


def _format_assignment(a: Assignment, detailed: bool = False) -> dict[str, Any]:
    """Format Assignment ORM instance into response schema dict."""
    progress_list = []
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
            progress_list.append(entry.model_dump(mode="json"))

    resp = AssignmentResponse(
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

    if detailed:
        resp["progress_history"] = progress_list

    return resp


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=PaginatedResponse,
    summary="List assignments (Administrator only)",
    description="Retrieves a paginated list of complaint assignments with filters by department, worker, complaint, and status.",
    responses={
        200: {"description": "Assignments list retrieved", "model": PaginatedResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
    },
)
def get_all_assignments(
    department_id: int | None = Query(default=None, description="Filter by department ID"),
    worker_id: uuid.UUID | None = Query(default=None, description="Filter by worker UUID"),
    complaint_id: uuid.UUID | None = Query(default=None, description="Filter by complaint UUID"),
    status_filter: AssignmentStatus | None = Query(default=None, alias="status", description="Filter by assignment status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    """Administrator assignment query endpoint."""
    pagination = PaginationParams(page=page, page_size=page_size)
    filters = {
        "department_id": department_id,
        "worker_id": worker_id,
        "complaint_id": complaint_id,
        "status": status_filter,
    }
    assignments, total_items = list_assignments(db=db, filters=filters, pagination=pagination)
    total_pages = math.ceil(total_items / pagination.page_size) if total_items > 0 else 0
    data = [_format_assignment(a) for a in assignments]

    return PaginatedResponse(
        success=True,
        message="Assignments retrieved successfully",
        data=data,
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get(
    "/{assignment_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get assignment details (Administrator only)",
    description="Retrieves full assignment details including complete milestone progress audit history.",
    responses={
        200: {"description": "Assignment details retrieved", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        404: {"description": "Assignment not found", "model": ErrorResponse},
    },
)
def get_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Get single assignment details."""
    assignment = get_assignment_by_id(db=db, assignment_id=assignment_id)
    return StandardResponse(
        success=True,
        message="Assignment details retrieved successfully",
        data=_format_assignment(assignment, detailed=True),
    )
