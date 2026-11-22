"""
CivicPulse Public Complaints API Router

Provides public, unauthenticated endpoints for civic complaints feed and detail views.
Enforces strict allowlist serialization to ensure zero citizen PII, zero exact coordinates,
and zero raw citizen description text are exposed to the public.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.constants import ComplaintStatus
from app.db.session import get_db
from app.schemas.common import StandardResponse
from app.schemas.public_complaint import (
    PublicComplaintDetail,
    PublicComplaintListResponseData,
)
from app.services.public_complaint_service import (
    get_public_complaint,
    list_public_complaints,
)

router = APIRouter()


@router.get(
    "/complaints",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="List published complaints feed",
    description="Retrieve paginated list of administrator-approved public civic complaints. No authentication required.",
)
def get_public_feed(
    category_id: int | None = Query(default=None, description="Filter by category ID"),
    status_filter: ComplaintStatus | None = Query(default=None, alias="status", description="Filter by complaint status"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=50, description="Items per page (max 50)"),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Publicly accessible list of moderated complaints.
    """
    items, total, total_pages = list_public_complaints(
        db=db,
        category_id=category_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return StandardResponse(
        success=True,
        message="Public complaints retrieved successfully",
        data=PublicComplaintListResponseData(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        ).model_dump(),
    )


@router.get(
    "/complaints/{complaint_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get published complaint detail",
    description="Retrieve details of a published civic complaint. Returns 404 for private complaints. No authentication required.",
)
def get_public_complaint_detail(
    complaint_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Publicly accessible detail view of a single moderated complaint.
    """
    item = get_public_complaint(db=db, complaint_id=complaint_id)
    return StandardResponse(
        success=True,
        message="Public complaint retrieved successfully",
        data=PublicComplaintDetail.model_validate(item).model_dump(),
    )
