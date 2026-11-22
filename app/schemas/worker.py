"""
CivicPulse Field Worker Schemas

Pydantic schemas for field worker provisioning, profiles, management, and responses.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class WorkerCreateRequest(BaseModel):
    """Payload for administrator field worker account provisioning."""

    email: EmailStr = Field(
        ...,
        description="Worker login email address",
        examples=["ramesh.electrician@civicpulse.org"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Initial worker account password (8-72 characters for bcrypt boundary safety)",
        examples=["WorkerSecurePass123!"],
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full legal name of the field technician",
        examples=["Ramesh Kumar"],
    )
    department_id: int = Field(
        ...,
        description="Employing municipal department ID",
        examples=[2],
    )
    employee_id: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Unique employee badge or identification code",
        examples=["EMP-ELEC-042"],
    )
    designation: str | None = Field(
        default=None,
        max_length=100,
        description="Trade specialty or role title",
        examples=["Senior Lineman"],
    )
    phone_number: str | None = Field(
        default=None,
        max_length=50,
        description="Contact mobile number",
        examples=["+91-9876543210"],
    )

    @field_validator("employee_id")
    @classmethod
    def clean_employee_id(cls, v: str) -> str:
        emp = v.strip().upper()
        if len(emp) < 2:
            raise ValueError("Employee ID must contain at least 2 non-whitespace characters")
        return emp

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        name = v.strip()
        if len(name) < 2:
            raise ValueError("Full name must contain at least 2 non-whitespace characters")
        return name


class WorkerUpdateRequest(BaseModel):
    """Payload for administrator updates to a field worker profile."""

    department_id: int | None = Field(default=None, description="Reassign to another department")
    designation: str | None = Field(default=None, max_length=100)
    is_available: bool | None = Field(default=None, description="Field availability toggle")
    employment_status: str | None = Field(default=None, max_length=50, description="ACTIVE, ON_LEAVE, INACTIVE")
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone_number: str | None = Field(default=None, max_length=50)

    @field_validator("employment_status")
    @classmethod
    def clean_status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_statuses = {"ACTIVE", "ON_LEAVE", "INACTIVE"}
        status_upper = v.strip().upper()
        if status_upper not in valid_statuses:
            raise ValueError(f"Employment status must be one of: {', '.join(sorted(valid_statuses))}")
        return status_upper


class WorkerResponse(BaseModel):
    """Public representation of a field worker profile."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Worker profile UUID")
    user_id: uuid.UUID = Field(..., description="Base user account UUID")
    department_id: int = Field(..., description="Department ID")
    department_name: str | None = Field(default=None, description="Department name")
    employee_id: str = Field(..., description="Employee badge code")
    designation: str | None = Field(default=None, description="Role designation")
    is_available: bool = Field(..., description="Field availability status")
    employment_status: str = Field(..., description="Employment status (ACTIVE, ON_LEAVE, INACTIVE)")
    full_name: str | None = Field(default=None, description="Worker full name")
    email: str | None = Field(default=None, description="Worker email")
    phone_number: str | None = Field(default=None, description="Contact phone")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class WorkerDetailResponse(WorkerResponse):
    """Detailed worker profile response with task load summary."""

    active_tasks_count: int = Field(default=0, description="Number of active assigned tasks")
    completed_tasks_count: int = Field(default=0, description="Number of lifetime completed tasks")
