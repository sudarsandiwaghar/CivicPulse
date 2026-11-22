"""
CivicPulse API v1 Router

Aggregates all v1 route modules into a single APIRouter that is
mounted on the FastAPI application in main.py. Each domain module
(auth, users, complaints, etc.) defines its own router which is
included here with an appropriate prefix and tag.

Phase 1 provides only the health-check endpoint. Domain routers
will be included as they are implemented in subsequent phases.
"""

from fastapi import APIRouter

from app.schemas.common import StandardResponse

# Master v1 router — all domain routers are included onto this
router = APIRouter()


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get(
    "/health",
    response_model=StandardResponse,
    tags=["System"],
    summary="Health check",
    description=(
        "Returns the current health status of the CivicPulse API. "
        "Use this endpoint for monitoring, load balancer health probes, "
        "and verifying that the service is running."
    ),
    responses={
        200: {
            "description": "Service is healthy and operational",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "CivicPulse API is running",
                        "data": {"status": "healthy", "version": "0.1.0"},
                    }
                }
            },
        }
    },
)
def health_check() -> StandardResponse:
    """
    Health check endpoint for CivicPulse API.

    Returns a simple status response confirming the service is
    operational. Does not require authentication.

    Returns:
        StandardResponse with health status and application version.
    """
    from app.config import get_settings

    settings = get_settings()
    return StandardResponse(
        message="CivicPulse API is running",
        data={
            "status": "healthy",
            "version": settings.APP_VERSION,
        },
    )


# =============================================================================
# Domain Router Inclusions
# =============================================================================

from app.api.v1.admin_sla import router as admin_sla_router
from app.api.v1.assignments import router as assignments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.citizens import router as citizens_router
from app.api.v1.complaints import router as complaints_router
from app.api.v1.departments import router as departments_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.public import router as public_router
from app.api.v1.workers import router as workers_router

router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(categories_router, prefix="/categories", tags=["Categories"])
router.include_router(citizens_router, prefix="/citizens", tags=["Citizens"])
router.include_router(complaints_router, prefix="/complaints", tags=["Complaints"])
router.include_router(departments_router, prefix="/departments", tags=["Departments"])
router.include_router(workers_router, prefix="/workers", tags=["Field Workers"])
router.include_router(assignments_router, prefix="/assignments", tags=["Assignments"])
router.include_router(public_router, prefix="/public", tags=["Public Feed"])
router.include_router(admin_sla_router, prefix="/admin/sla", tags=["Admin SLA"])
router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
