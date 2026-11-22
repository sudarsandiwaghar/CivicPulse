"""
CivicPulse Citizens API Router

Provides dedicated endpoints for citizen-facing features including the
personal civic reporting dashboard.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_citizen
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, StandardResponse
from app.schemas.dashboard import CitizenDashboardData
from app.services.dashboard_service import get_citizen_dashboard

router = APIRouter()


@router.get(
    "/me/dashboard",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="Retrieve citizen personal dashboard",
    description=(
        "Retrieves consolidated reporting metrics, status and priority breakdowns, "
        "and recent activity lists (recent submissions, recent updates, and action-required items) "
        "strictly scoped to the authenticated citizen."
    ),
    responses={
        200: {"description": "Citizen dashboard retrieved successfully", "model": StandardResponse},
        401: {"description": "Unauthorized: missing or invalid authentication token", "model": ErrorResponse},
        403: {"description": "Forbidden: user does not have CITIZEN role", "model": ErrorResponse},
    },
)
def get_my_dashboard(
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Endpoint for authenticated citizens to view their personal reporting dashboard.
    """
    dashboard_data = get_citizen_dashboard(db=db, citizen=current_user)
    return StandardResponse(
        success=True,
        message="Citizen dashboard retrieved successfully",
        data=dashboard_data,
    )
