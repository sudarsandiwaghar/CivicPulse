"""
CivicPulse Public Complaint Schemas

Defines response structures for unauthenticated public complaint feeds
and discovery endpoints.

Privacy Invariants:
    - Exposes ONLY explicitly administrator-approved public content (public_title, public_description).
    - NEVER exposes original citizen complaint title or description.
    - NEVER exposes citizen PII (names, emails, phones, user IDs).
    - NEVER exposes exact coordinates (latitude, longitude) or street addresses.
    - Exposes only coarse locality/ward and city information when already recorded.
    - Exposes only public-safe status and category information.
    - NEVER serializes the raw Complaint ORM entity directly.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ComplaintStatus


class PublicComplaintItem(BaseModel):
    """
    Public-safe complaint summary item for feeds and listings.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique UUID identifier of the complaint")
    complaint_number: str = Field(..., description="Human-readable tracking code (e.g. CP-2026-10001)")
    category_name: str = Field(..., description="Issue classification category")
    status: ComplaintStatus = Field(..., description="Current complaint lifecycle status")
    created_at: datetime = Field(..., description="Timestamp when complaint was originally submitted (UTC)")
    public_title: str = Field(..., description="Administrator-approved headline for public display")
    public_description: str = Field(..., description="Administrator-approved description for public display")
    ward_or_district: str | None = Field(default=None, description="Coarse administrative ward or locality")
    city: str | None = Field(default=None, description="Municipality or metropolitan area")


class PublicComplaintDetail(PublicComplaintItem):
    """
    Detailed public view of a published complaint.
    """
    pass


class PublicComplaintListResponseData(BaseModel):
    """
    Structured pagination payload for public complaint feed.
    """

    total: int = Field(..., description="Total count of public complaints matching query")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items returned in this page")
    total_pages: int = Field(..., description="Total pages available")
    items: list[PublicComplaintItem] = Field(default_factory=list, description="List of public complaints")
