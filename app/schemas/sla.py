"""
CivicPulse SLA Schemas

Pydantic schemas for SLA policy management, complaint SLA details,
cycle history audit records, and bounded on-demand SLA evaluations.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ComplaintStatus, PriorityLevel


# =============================================================================
# Policy Schemas
# =============================================================================

class SLAPolicyCreateRequest(BaseModel):
    """
    Administrator payload to create an SLA policy.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Descriptive policy name",
        examples=["Global Standard SLA", "Roads Critical SLA"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Policy notes or scope explanation",
    )
    category_id: int | None = Field(
        default=None,
        description="Category ID (null for global or priority-wide policies)",
    )
    priority: PriorityLevel | None = Field(
        default=None,
        description="Priority level (null for global or category-wide policies)",
    )
    response_time_hours: int = Field(
        ...,
        gt=0,
        le=8760,
        description="Target response time in positive integer hours",
        examples=[4],
    )
    resolution_time_hours: int = Field(
        ...,
        gt=0,
        le=8760,
        description="Target resolution time in positive integer hours",
        examples=[48],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the policy is active for SLA matching",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Policy name cannot be empty or whitespace only")
        return s


class SLAPolicyUpdateRequest(BaseModel):
    """
    Administrator payload to update an existing SLA policy.
    """
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated policy name",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Updated policy notes",
    )
    response_time_hours: int | None = Field(
        default=None,
        gt=0,
        le=8760,
        description="Updated target response time in positive integer hours",
    )
    resolution_time_hours: int | None = Field(
        default=None,
        gt=0,
        le=8760,
        description="Updated target resolution time in positive integer hours",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the policy is active",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Policy name cannot be empty or whitespace only")
            return s
        return v


class SLAPolicyResponse(BaseModel):
    """
    Serialized SLA Policy representation.
    """
    id: uuid.UUID
    name: str
    description: str | None = None
    category_id: int | None = None
    priority: PriorityLevel | None = None
    response_time_hours: int
    resolution_time_hours: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Complaint SLA Detail & History Schemas
# =============================================================================

class ComplaintSLADetailResponse(BaseModel):
    """
    Comprehensive SLA status and dual-clock tracking details for a complaint.
    """
    complaint_id: uuid.UUID
    complaint_number: str
    status: ComplaintStatus
    priority: PriorityLevel
    category_id: int
    created_at: datetime
    sla_cycle_number: int

    # Response clock
    response_sla_policy_id: uuid.UUID | None = None
    response_deadline: datetime | None = None
    responded_at: datetime | None = None
    response_pause_duration_seconds: int = 0
    response_pause_started_at: datetime | None = None
    response_escalation_level: int = 0
    response_breached: bool = False

    # Resolution clock
    resolution_sla_policy_id: uuid.UUID | None = None
    resolution_deadline: datetime | None = None
    resolved_at: datetime | None = None
    resolution_pause_duration_seconds: int = 0
    resolution_pause_started_at: datetime | None = None
    resolution_escalation_level: int = 0
    resolution_breached: bool = False

    last_sla_evaluated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ComplaintSLAHistoryResponse(BaseModel):
    """
    Immutable audit history record capturing the performance of a completed SLA cycle.
    """
    id: uuid.UUID
    complaint_id: uuid.UUID
    cycle_number: int
    policy_id: uuid.UUID | None = None
    policy_name: str | None = None
    policy_snapshot: dict[str, Any] | None = None
    response_target_seconds: int | None = None
    resolution_target_seconds: int | None = None
    actual_response_seconds: int | None = None
    actual_resolution_seconds: int | None = None
    response_breached: bool | None = None
    resolution_breached: bool | None = None
    response_escalation_level: int | None = None
    resolution_escalation_level: int | None = None
    cycle_started_at: datetime
    cycle_ended_at: datetime
    end_reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Bounded On-Demand SLA Evaluation Schemas
# =============================================================================

class SLAEvaluationFilterRequest(BaseModel):
    """
    Filter parameters for on-demand batch SLA evaluation.
    Enforces a strict upper bound limit on batch size to prevent database overload.
    """
    complaint_id: uuid.UUID | None = Field(
        default=None,
        description="Optionally evaluate a single complaint by UUID",
    )
    department_id: int | None = Field(
        default=None,
        description="Filter complaints by department ID",
    )
    category_id: int | None = Field(
        default=None,
        description="Filter complaints by category ID",
    )
    priority: PriorityLevel | None = Field(
        default=None,
        description="Filter complaints by priority level",
    )
    status: ComplaintStatus | None = Field(
        default=None,
        description="Filter complaints by lifecycle status",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum complaints to evaluate in one batch (bounded between 1 and 200)",
    )


class SLAEvaluationItemResult(BaseModel):
    """
    Outcome of evaluating a single complaint's SLA state.
    """
    complaint_id: uuid.UUID
    complaint_number: str
    previous_response_escalation: int
    new_response_escalation: int
    previous_resolution_escalation: int
    new_resolution_escalation: int
    evaluated_at: datetime
    escalated: bool


class SLAEvaluationBatchResponse(BaseModel):
    """
    Summary outcome of a bounded batch SLA evaluation run.
    """
    evaluated_count: int
    escalated_count: int
    results: list[SLAEvaluationItemResult]
