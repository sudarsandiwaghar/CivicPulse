"""
CivicPulse Complaint Schemas

Pydantic schemas for complaint creation, retrieval, filtering, lifecycle
transitions, administrator reviews, and status transition audit history.

Security design:
    - Citizens CANNOT submit arbitrary status, priority, citizen_id, or worker_id.
    - Strict boundary validation on latitude, longitude, and text lengths.
    - Clean separation between Citizen inputs and Administrator review payloads.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ComplaintStatus, PriorityLevel


# =============================================================================
# Location Schemas
# =============================================================================

class LocationCreate(BaseModel):
    """
    Geographical coordinates and address metadata for an issue location.
    """

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS84 latitude coordinate in decimal degrees",
        examples=[12.9716],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS84 longitude coordinate in decimal degrees",
        examples=[77.5946],
    )
    address_line: str | None = Field(
        default=None,
        max_length=255,
        description="Street name, building, or road segment",
        examples=["MG Road, Near Metro Station"],
    )
    area_name: str | None = Field(
        default=None,
        max_length=100,
        description="Locality, ward, or neighbourhood name",
        examples=["Indiranagar"],
    )
    city: str | None = Field(
        default="Default City",
        max_length=100,
        description="Municipal corporation or city name",
        examples=["Bengaluru"],
    )
    pincode: str | None = Field(
        default=None,
        max_length=20,
        description="Postal or ZIP code",
        examples=["560038"],
    )
    landmark: str | None = Field(
        default=None,
        max_length=255,
        description="Prominent physical landmark nearby",
        examples=["Opposite Empire Restaurant"],
    )


class LocationResponse(BaseModel):
    """
    Public representation of a verified complaint incident location.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique location UUID identifier")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    address_line: str | None = Field(default=None, description="Street address")
    area_name: str | None = Field(default=None, description="Locality or ward")
    city: str = Field(..., description="City name")
    pincode: str | None = Field(default=None, description="Postal code")
    landmark: str | None = Field(default=None, description="Nearby landmark")


# =============================================================================
# Complaint Status History Schemas
# =============================================================================

class ComplaintStatusHistoryResponse(BaseModel):
    """
    Historical record of an individual complaint lifecycle status transition.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique status transition UUID")
    complaint_id: uuid.UUID = Field(..., description="Associated complaint UUID")
    changed_by_id: uuid.UUID = Field(..., description="User UUID who authorized transition")
    changed_by_name: str | None = Field(default=None, description="Name of user who authorized transition")
    previous_status: ComplaintStatus | None = Field(default=None, description="Status prior to transition")
    new_status: ComplaintStatus = Field(..., description="New lifecycle status established")
    remarks: str | None = Field(default=None, description="Justification or administrative notes")
    created_at: datetime = Field(..., description="Timestamp of transition (UTC)")

    @field_validator("changed_by_name", mode="before")
    @classmethod
    def resolve_changed_by_name(cls, v: Any) -> str | None:
        """Extract full name from User model if relation was loaded."""
        if hasattr(v, "full_name"):
            return v.full_name
        return v


# =============================================================================
# Complaint Submission & Response Schemas
# =============================================================================

class ComplaintCreateRequest(BaseModel):
    """
    Payload for authenticated citizen complaint submission.

    Citizens can only supply core issue details and incident location.
    Server-side logic determines the complaint reference number, citizen ID,
    initial status (SUBMITTED), and default priority (MEDIUM).
    """

    title: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Concise summary title of the civic problem",
        examples=["Severe pothole on 100ft road causing traffic congestion"],
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Comprehensive problem description",
        examples=["A large deep pothole has formed in the middle lane near the metro pillar 45."],
    )
    category_id: int = Field(
        ...,
        description="Foreign key ID of the relevant civic issue category",
        examples=[1],
    )
    location: LocationCreate = Field(
        ...,
        description="Geographical coordinates and location details",
    )

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        """Strip extra whitespace from title."""
        cleaned = v.strip()
        if len(cleaned) < 5:
            raise ValueError("Title must contain at least 5 non-whitespace characters")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str) -> str:
        """Strip extra whitespace from description."""
        cleaned = v.strip()
        if len(cleaned) < 10:
            raise ValueError("Description must contain at least 10 non-whitespace characters")
        return cleaned


class ComplaintResponse(BaseModel):
    """
    Public safe profile response for a civic complaint entity.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique complaint UUID identifier")
    complaint_number: str = Field(..., description="Human-readable tracking code (e.g. CP-2026-10001)")
    citizen_id: uuid.UUID = Field(..., description="User UUID of reporting citizen")
    citizen_name: str | None = Field(default=None, description="Full name of reporting citizen")
    category_id: int = Field(..., description="Assigned issue category ID")
    category_name: str | None = Field(default=None, description="Name of assigned category")
    department_id: int | None = Field(default=None, description="Assigned municipal department ID")
    department_name: str | None = Field(default=None, description="Name of assigned municipal department")
    location: LocationResponse | None = Field(default=None, description="Incident location data")
    title: str = Field(..., description="Complaint summary title")
    description: str = Field(..., description="Detailed complaint description")
    status: ComplaintStatus = Field(..., description="Current complaint lifecycle status")
    priority: PriorityLevel = Field(..., description="Assigned operational priority level")
    resolved_at: datetime | None = Field(default=None, description="Resolution timestamp if resolved")
    closed_at: datetime | None = Field(default=None, description="Closure timestamp if verified closed")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    @field_validator("citizen_name", mode="before")
    @classmethod
    def resolve_citizen_name(cls, v: Any) -> str | None:
        """Extract citizen full name if citizen relationship is loaded."""
        if hasattr(v, "full_name"):
            return v.full_name
        return v

    @field_validator("category_name", mode="before")
    @classmethod
    def resolve_category_name(cls, v: Any) -> str | None:
        """Extract category name if category relationship is loaded."""
        if hasattr(v, "name"):
            return v.name
        return v

    @field_validator("department_name", mode="before")
    @classmethod
    def resolve_department_name(cls, v: Any) -> str | None:
        """Extract department name if department relationship is loaded."""
        if hasattr(v, "name"):
            return v.name
        return v


class ComplaintDetailResponse(ComplaintResponse):
    """
    Extended complaint detail response including recent status transitions.
    """

    status_history: list[ComplaintStatusHistoryResponse] = Field(
        default_factory=list,
        description="Chronological transition history for this complaint",
    )


# =============================================================================
# Lifecycle Transition & Review Schemas
# =============================================================================

class ComplaintTransitionRequest(BaseModel):
    """
    Payload for executing a lifecycle state transition.
    """

    new_status: ComplaintStatus = Field(
        ...,
        description="Requested target lifecycle status",
    )
    remarks: str | None = Field(
        default=None,
        max_length=1000,
        description="Reason or administrative justification for the transition",
    )
    original_complaint_id: uuid.UUID | None = Field(
        default=None,
        description="UUID of master complaint if transitioning to DUPLICATE",
    )


class ComplaintReviewRequest(BaseModel):
    """
    Payload for administrator-only complaint triage, review, and reclassification.
    """

    new_status: ComplaintStatus | None = Field(
        default=None,
        description="Target status (e.g. UNDER_REVIEW, REJECTED, DUPLICATE, ON_HOLD)",
    )
    category_id: int | None = Field(
        default=None,
        description="Updated category ID if reclassifying",
    )
    priority: PriorityLevel | None = Field(
        default=None,
        description="Updated operational priority level (LOW, MEDIUM, HIGH, CRITICAL)",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Recorded justification for priority adjustment, rejection, hold, or duplicate",
    )
    original_complaint_id: uuid.UUID | None = Field(
        default=None,
        description="Referenced original complaint UUID if marking as duplicate",
    )
