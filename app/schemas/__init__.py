"""
CivicPulse Pydantic Schemas Package

Exports shared and domain-specific Pydantic schemas for API validation
and JSON serialisation.
"""

from app.schemas.assignment import (
    AssignmentDetailResponse,
    AssignmentProgressResponse,
    AssignmentResponse,
    ComplaintAssignRequest,
    ComplaintReassignRequest,
    WorkCompleteRequest,
    WorkProgressRequest,
    WorkerTaskDetailResponse,
    WorkerTaskResponse,
)
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.category import CategoryResponse
from app.schemas.common import (
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
    StandardResponse,
)
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintDetailResponse,
    ComplaintResponse,
    ComplaintReviewRequest,
    ComplaintStatusHistoryResponse,
    ComplaintTransitionRequest,
    LocationCreate,
    LocationResponse,
)
from app.schemas.dashboard import (
    CitizenComplaintSummary,
    CitizenDashboardData,
    CitizenDashboardMetrics,
)
from app.schemas.department import (
    DepartmentCreateRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
)
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.schemas.timeline import (
    ComplaintTimelineData,
    TimelineActor,
    TimelineEvent,
    TimelineEventType,
)
from app.schemas.worker import (
    WorkerCreateRequest,
    WorkerDetailResponse,
    WorkerResponse,
    WorkerUpdateRequest,
)

__all__ = [
    "StandardResponse",
    "ErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserResponse",
    "TokenResponse",
    "CategoryResponse",
    "LocationCreate",
    "LocationResponse",
    "ComplaintCreateRequest",
    "ComplaintResponse",
    "ComplaintDetailResponse",
    "ComplaintStatusHistoryResponse",
    "ComplaintReviewRequest",
    "ComplaintTransitionRequest",
    "DepartmentCreateRequest",
    "DepartmentUpdateRequest",
    "DepartmentResponse",
    "WorkerCreateRequest",
    "WorkerUpdateRequest",
    "WorkerResponse",
    "WorkerDetailResponse",
    "ComplaintAssignRequest",
    "ComplaintReassignRequest",
    "WorkProgressRequest",
    "WorkCompleteRequest",
    "AssignmentProgressResponse",
    "AssignmentResponse",
    "AssignmentDetailResponse",
    "WorkerTaskResponse",
    "WorkerTaskDetailResponse",
    "CitizenComplaintSummary",
    "CitizenDashboardMetrics",
    "CitizenDashboardData",
    "TimelineEventType",
    "TimelineActor",
    "TimelineEvent",
    "ComplaintTimelineData",
    "NotificationResponse",
    "NotificationListResponse",
    "UnreadCountResponse",
]
