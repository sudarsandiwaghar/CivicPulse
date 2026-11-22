"""
CivicPulse Departments API Router

Provides administrator-only endpoints for municipal department lifecycle management,
inspection, updates, and safe deactivation.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.department import Department
from app.models.user import User
from app.schemas.common import ErrorResponse, StandardResponse
from app.schemas.department import (
    DepartmentCreateRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
)
from app.services.department_service import (
    create_department,
    deactivate_department,
    get_department_by_id,
    list_departments,
    update_department,
)

router = APIRouter()


def _format_department(dept: Department) -> dict:
    """Format Department entity into response dict with linked counts."""
    return DepartmentResponse(
        id=dept.id,
        name=dept.name,
        code=dept.code,
        description=dept.description,
        contact_email=dept.contact_email,
        contact_phone=dept.contact_phone,
        is_active=dept.is_active,
        created_at=dept.created_at,
        updated_at=dept.updated_at,
        categories_count=len(dept.categories) if hasattr(dept, "categories") and dept.categories else 0,
        workers_count=len(dept.workers) if hasattr(dept, "workers") and dept.workers else 0,
    ).model_dump(mode="json")


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="List municipal departments (Administrator only)",
    description="Retrieves all registered municipal departments with optional active status filter.",
    responses={
        200: {"description": "Departments list retrieved", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
    },
)
def get_departments(
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Retrieve all municipal departments."""
    depts = list_departments(db=db, is_active=is_active)
    data = [_format_department(d) for d in depts]
    return StandardResponse(
        success=True,
        message="Departments retrieved successfully",
        data=data,
    )


@router.get(
    "/{department_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Get department details by ID (Administrator only)",
    description="Retrieves a specific department with category and worker metrics.",
    responses={
        200: {"description": "Department details retrieved", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Department not found", "model": ErrorResponse},
    },
)
def get_department(
    department_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Retrieve details for a single department."""
    dept = get_department_by_id(db=db, department_id=department_id)
    return StandardResponse(
        success=True,
        message="Department details retrieved successfully",
        data=_format_department(dept),
    )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
    summary="Create a new municipal department (Administrator only)",
    description="Registers a new municipal department with unique code and name validation.",
    responses={
        201: {"description": "Department successfully created", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden: requires ADMINISTRATOR role", "model": ErrorResponse},
        409: {"description": "Conflict: department name or code already exists", "model": ErrorResponse},
        422: {"description": "Validation error", "model": ErrorResponse},
    },
)
def create_new_department(
    payload: DepartmentCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Create a new department."""
    dept = create_department(db=db, data=payload)
    return StandardResponse(
        success=True,
        message="Department created successfully",
        data=_format_department(dept),
    )


@router.patch(
    "/{department_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Update department details (Administrator only)",
    description="Updates department attributes such as name, code, contact information, and active status.",
    responses={
        200: {"description": "Department updated successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Department not found", "model": ErrorResponse},
        409: {"description": "Conflict: new code or name already taken", "model": ErrorResponse},
    },
)
def update_existing_department(
    department_id: int,
    payload: DepartmentUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Update department details."""
    dept = update_department(db=db, department_id=department_id, data=payload)
    return StandardResponse(
        success=True,
        message="Department updated successfully",
        data=_format_department(dept),
    )


@router.patch(
    "/{department_id}/deactivate",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Deactivate department (Administrator only)",
    description="Sets department is_active to False safely without deleting historical records.",
    responses={
        200: {"description": "Department deactivated successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Department not found", "model": ErrorResponse},
    },
)
@router.delete(
    "/{department_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Soft-deactivate department (DELETE alias)",
    description="Soft-deactivates department by setting is_active=False.",
    responses={
        200: {"description": "Department deactivated successfully", "model": StandardResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Department not found", "model": ErrorResponse},
    },
)
def deactivate_existing_department(
    department_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """Deactivate a department."""
    dept = deactivate_department(db=db, department_id=department_id)
    return StandardResponse(
        success=True,
        message=f"Department '{dept.name}' deactivated successfully",
        data=_format_department(dept),
    )
