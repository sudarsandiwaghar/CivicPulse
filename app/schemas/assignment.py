"""
CivicPulse Assignment and Task Schemas

Pydantic schemas for complaint task assignment, reassignment, progress tracking,
work completion, and worker task management.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import AssignmentStatus, ComplaintStatus, PriorityLevel
from app.schemas.complaint import LocationResponse


# =============================================================================
# Assignment Action Payloads
# =============================================================================

class ComplaintAssignRequest(BaseModel):
    """Payload for administrator complaint assignment to a field worker."""

    worker_id: uuid.UUID = Field(
        ...,
        description="UUID of designated field worker",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Special instructions, priority directives, or equipment notes",
    )


class ComplaintReassignRequest(BaseModel):
    """Payload for administrator complaint reassignment to a replacement worker."""

    new_worker_id: uuid.UUID = Field(
        ...,
        description="UUID of new replacement field worker",
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Auditable justification for reassignment",
        examples=["Worker on sick leave; reassigning to available technician in same ward."],
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Instructions for replacement technician",
    )

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 5:
            raise ValueError("Reassignment reason must contain at least 5 non-whitespace characters")
        return cleaned


class WorkProgressRequest(BaseModel):
    """Payload for worker field progress update."""

    description: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Work progress update, milestone description, or on-site observations",
        examples=["Inspected damaged street light; replacement ballast and bulb ordered."],
    )

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 5:
            raise ValueError("Progress description must contain at least 5 non-whitespace characters")
        return cleaned


class WorkCompleteRequest(BaseModel):
    """Payload for worker completion submission."""

    summary: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Comprehensive summary of remediation actions taken",
        examples=["Replaced faulty 150W LED fixture and reconnected wiring. Streetlight fully functional."],
    )

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 10:
            raise ValueError("Completion summary must contain at least 10 non-whitespace characters")
        return cleaned


# =============================================================================
# Progress & Assignment Responses
# =============================================================================

class AssignmentProgressResponse(BaseModel):
    """Immutable audit entry for field work progress."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Progress record UUID")
    assignment_id: uuid.UUID = Field(..., description="Assignment UUID")
    worker_id: uuid.UUID = Field(..., description="Worker UUID")
    worker_name: str | None = Field(default=None, description="Name of reporting worker")
    description: str = Field(..., description="Progress update notes")
    created_at: datetime = Field(..., description="Timestamp of progress log (UTC)")


class AssignmentResponse(BaseModel):
    """Public representation of a task assignment record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Assignment UUID")
    complaint_id: uuid.UUID = Field(..., description="Assigned complaint UUID")
    complaint_number: str | None = Field(default=None, description="Complaint tracking reference code")
    complaint_title: str | None = Field(default=None, description="Complaint headline title")
    worker_id: uuid.UUID = Field(..., description="Assigned field worker UUID")
    worker_name: str | None = Field(default=None, description="Assigned worker name")
    worker_employee_id: str | None = Field(default=None, description="Worker badge ID")
    department_id: int | None = Field(default=None, description="Department ID")
    department_name: str | None = Field(default=None, description="Department name")
    assigned_by_id: uuid.UUID = Field(..., description="Administrator UUID who assigned worker")
    assigned_by_name: str | None = Field(default=None, description="Administrator name")
    status: AssignmentStatus = Field(..., description="Assignment operational status")
    assigned_at: datetime = Field(..., description="Assignment timestamp")
    accepted_at: datetime | None = Field(default=None, description="Worker acceptance timestamp")
    started_at: datetime | None = Field(default=None, description="Work initiation timestamp")
    completed_at: datetime | None = Field(default=None, description="Work completion timestamp")
    notes: str | None = Field(default=None, description="Assignment notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AssignmentDetailResponse(AssignmentResponse):
    """Detailed assignment representation including complete progress audit history."""

    progress_history: list[AssignmentProgressResponse] = Field(
        default_factory=list,
        description="Chronological progress history for this assignment",
    )


# =============================================================================
# Worker Task View Responses
# =============================================================================

class WorkerTaskResponse(BaseModel):
    """Worker task view representing an assigned complaint."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: uuid.UUID = Field(..., description="Assignment UUID")
    complaint_id: uuid.UUID = Field(..., description="Complaint UUID")
    complaint_number: str = Field(..., description="Complaint tracking number (e.g. CP-2026-10001)")
    title: str = Field(..., description="Complaint title")
    description: str = Field(..., description="Detailed issue description")
    category_name: str | None = Field(default=None, description="Category name")
    priority: PriorityLevel = Field(..., description="Operational priority level")
    complaint_status: ComplaintStatus = Field(..., description="Lifecycle status of complaint")
    assignment_status: AssignmentStatus = Field(..., description="Assignment status")
    location: LocationResponse | None = Field(default=None, description="Incident geographical location")
    assigned_at: datetime = Field(..., description="Assignment timestamp")
    accepted_at: datetime | None = Field(default=None, description="Acceptance timestamp")
    started_at: datetime | None = Field(default=None, description="Work start timestamp")
    completed_at: datetime | None = Field(default=None, description="Work completion timestamp")
    notes: str | None = Field(default=None, description="Administrator assignment instructions")


class WorkerTaskDetailResponse(WorkerTaskResponse):
    """Extended task detail for worker inspection."""

    citizen_name: str | None = Field(default=None, description="Reporting citizen name")
    progress_history: list[AssignmentProgressResponse] = Field(
        default_factory=list,
        description="All recorded progress updates for this task",
    )
