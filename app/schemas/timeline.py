"""
CivicPulse Complaint Timeline Schemas

Pydantic schemas for the unified chronological complaint audit trail.
Normalizes records from complaints, status history, assignments, and progress.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ComplaintStatus


class TimelineEventType(str, Enum):
    """
    Standardized classification of timeline events.
    """

    COMPLAINT_SUBMITTED = "COMPLAINT_SUBMITTED"
    STATUS_TRANSITION = "STATUS_TRANSITION"
    ASSIGNMENT_CREATED = "ASSIGNMENT_CREATED"
    ASSIGNMENT_ACCEPTED = "ASSIGNMENT_ACCEPTED"
    WORK_STARTED = "WORK_STARTED"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    WORK_COMPLETED = "WORK_COMPLETED"
    COMPLAINT_CLOSED = "COMPLAINT_CLOSED"
    COMPLAINT_REOPENED = "COMPLAINT_REOPENED"


class TimelineActor(BaseModel):
    """
    Representation of the user or role responsible for a timeline milestone.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = Field(default=None, description="UUID identifier of actor (redacted for citizens)")
    role: str = Field(..., description="Role designation of the actor (CITIZEN, ADMINISTRATOR, FIELD_WORKER)")
    name: str = Field(..., description="Display-safe actor name or generic label")


class TimelineEvent(BaseModel):
    """
    Individual chronological milestone in the complaint lifecycle.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Deterministic or unique event identifier")
    event_type: str = Field(..., description="Standardized event classification")
    title: str = Field(..., description="Short human-readable event headline")
    description: str = Field(..., description="Detailed description of the event")
    timestamp: datetime = Field(..., description="UTC timestamp when the event occurred")
    actor: TimelineActor | None = Field(default=None, description="Actor who triggered or executed the event")
    remarks: str | None = Field(default=None, description="Display-safe notes or remarks (redacted if internal)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual event attributes")


class ComplaintTimelineData(BaseModel):
    """
    Complete timeline response payload for GET /api/v1/complaints/{id}/timeline.
    """

    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID = Field(..., description="Unique UUID identifier for the complaint")
    complaint_number: str = Field(..., description="Human-readable tracking code (e.g. CP-2026-10001)")
    current_status: ComplaintStatus = Field(..., description="Current complaint lifecycle status")
    events: list[TimelineEvent] = Field(default_factory=list, description="Chronologically sorted timeline milestones")
