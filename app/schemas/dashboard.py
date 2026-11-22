"""
CivicPulse Citizen Dashboard Schemas

Pydantic schemas for the authenticated citizen dashboard endpoint, providing
consolidated metrics, breakdown counts, and recent activity feeds.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ComplaintStatus, PriorityLevel


class CitizenComplaintSummary(BaseModel):
    """
    Compact summary card for citizen dashboard activity lists.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique UUID identifier for the complaint")
    complaint_number: str = Field(..., description="Human-readable tracking code (e.g. CP-2026-10001)")
    title: str = Field(..., description="Short summary headline of civic problem")
    category_id: int = Field(..., description="Category identifier")
    category_name: str = Field(..., description="Display name of the category")
    status: ComplaintStatus = Field(..., description="Current lifecycle status")
    priority: PriorityLevel = Field(..., description="Assessed priority level")
    created_at: datetime = Field(..., description="Submission timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last modification timestamp (UTC)")
    resolved_at: datetime | None = Field(default=None, description="Resolution timestamp if available (UTC)")


class CitizenDashboardMetrics(BaseModel):
    """
    Consolidated metrics and category/status breakdowns for citizen reporting activity.
    """

    total_complaints: int = Field(0, description="Total complaints filed by authenticated citizen")
    active_complaints: int = Field(
        0,
        description="Non-terminal active complaints (SUBMITTED, UNDER_REVIEW, ASSIGNED, IN_PROGRESS, ON_HOLD, REOPENED)",
    )
    awaiting_verification: int = Field(
        0,
        description="Complaints in RESOLVED_AWAITING_VERIFICATION status awaiting citizen confirmation",
    )
    closed_complaints: int = Field(0, description="Complaints successfully verified and CLOSED")
    rejected_complaints: int = Field(0, description="Complaints in REJECTED status")
    duplicate_complaints: int = Field(0, description="Complaints in DUPLICATE status")
    action_required_count: int = Field(
        0,
        description="Action-required count matching RESOLVED_AWAITING_VERIFICATION",
    )
    status_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Complete breakdown across all 10 approved lifecycle statuses",
    )
    priority_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown across all 4 priority levels (LOW, MEDIUM, HIGH, CRITICAL)",
    )


class CitizenDashboardData(BaseModel):
    """
    Complete payload returned by GET /api/v1/citizens/me/dashboard.
    """

    metrics: CitizenDashboardMetrics = Field(..., description="Consolidated metrics and breakdowns")
    recent_submissions: list[CitizenComplaintSummary] = Field(
        default_factory=list,
        description="Latest 5 complaints ordered by creation timestamp descending",
    )
    recent_updates: list[CitizenComplaintSummary] = Field(
        default_factory=list,
        description="Latest 5 complaints ordered by update timestamp descending",
    )
    action_required: list[CitizenComplaintSummary] = Field(
        default_factory=list,
        description="Complaints in RESOLVED_AWAITING_VERIFICATION status awaiting citizen action (max 5)",
    )
