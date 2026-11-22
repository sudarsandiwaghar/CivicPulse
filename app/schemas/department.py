"""
CivicPulse Department Schemas

Pydantic schemas for municipal department management, validation, and responses.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class DepartmentCreateRequest(BaseModel):
    """Payload for administrator department creation."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Official municipal department name",
        examples=["Public Works Department"],
    )
    code: str = Field(
        ...,
        min_length=2,
        max_length=20,
        description="Unique uppercase departmental identifier code",
        examples=["PWD"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Operational mandate and responsibility summary",
        examples=["Roads, bridges, footpaths, and civil infrastructure"],
    )
    contact_email: EmailStr | None = Field(
        default=None,
        description="Departmental contact or support email",
        examples=["pwd@civicpulse.org"],
    )
    contact_phone: str | None = Field(
        default=None,
        max_length=50,
        description="Helpdesk or dispatch phone number",
        examples=["1800-111-001"],
    )
    is_active: bool = Field(
        default=True,
        description="Operational activity status",
    )

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        code = v.strip().upper()
        if not code.replace("_", "").isalnum():
            raise ValueError("Department code must be alphanumeric (underscores allowed)")
        return code

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        name = v.strip()
        if len(name) < 2:
            raise ValueError("Department name must be at least 2 non-whitespace characters")
        return name


class DepartmentUpdateRequest(BaseModel):
    """Payload for administrator department updates."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    code: str | None = Field(default=None, min_length=2, max_length=20)
    description: str | None = Field(default=None, max_length=1000)
    contact_email: EmailStr | None = Field(default=None)
    contact_phone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = Field(default=None)

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        code = v.strip().upper()
        if not code.replace("_", "").isalnum():
            raise ValueError("Department code must be alphanumeric (underscores allowed)")
        return code

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        name = v.strip()
        if len(name) < 2:
            raise ValueError("Department name must be at least 2 non-whitespace characters")
        return name


class DepartmentResponse(BaseModel):
    """Public representation of a municipal department."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique department ID")
    name: str = Field(..., description="Department name")
    code: str = Field(..., description="Department code (e.g. PWD)")
    description: str | None = Field(default=None, description="Department description")
    contact_email: str | None = Field(default=None, description="Contact email")
    contact_phone: str | None = Field(default=None, description="Contact phone")
    is_active: bool = Field(..., description="Active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    categories_count: int | None = Field(default=None, description="Number of linked categories")
    workers_count: int | None = Field(default=None, description="Number of linked field workers")
