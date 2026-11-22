"""
CivicPulse Category Schemas

Pydantic schemas for civic issue categories and department classifications.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryResponse(BaseModel):
    """
    Public response representation of a civic issue category.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="Unique integer identifier for category",
        examples=[1],
    )
    department_id: int = Field(
        ...,
        description="Managing municipal department ID",
        examples=[1],
    )
    department_name: str | None = Field(
        default=None,
        description="Name of managing municipal department",
        examples=["Public Works Department"],
    )
    name: str = Field(
        ...,
        description="Category headline title",
        examples=["Roads and Potholes"],
    )
    description: str | None = Field(
        default=None,
        description="Guidance on issues classified under this category",
        examples=["Issues related to damaged road surfaces, potholes, and broken dividers"],
    )
    is_active: bool = Field(
        ...,
        description="Whether citizens can file complaints under this category",
        examples=[True],
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp of category creation (UTC)",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of last category update (UTC)",
    )

    @field_validator("department_name", mode="before")
    @classmethod
    def resolve_department_name(cls, v: Any, info: Any) -> str | None:
        """Extract department name if department relationship object is passed."""
        if hasattr(v, "name"):
            return v.name
        return v
