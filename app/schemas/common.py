"""
CivicPulse Common Schemas

Shared Pydantic models used across multiple API endpoints for
consistent request/response structures. These include:

    - StandardResponse: Uniform envelope for all API success responses.
    - ErrorResponse: Uniform envelope for all API error responses.
    - PaginationParams: Query parameters for paginated list endpoints.
    - PaginatedResponse: Wrapper adding pagination metadata to list results.

Design rationale:
    Using a consistent response envelope ensures that the future
    frontend can rely on a predictable JSON structure, simplifying
    error handling, loading states, and pagination logic.

Usage:
    @router.get("/items", response_model=StandardResponse)
    def list_items():
        return StandardResponse(
            message="Items retrieved successfully",
            data=[...],
        )
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

# TypeVar for generic paginated responses
T = TypeVar("T")


class StandardResponse(BaseModel):
    """
    Uniform success response envelope for all API endpoints.

    Attributes:
        success: Always True for successful responses.
        message: Human-readable description of the result.
        data: The response payload (entity, list, or None).
    """
    success: bool = True
    message: str = "Operation completed successfully"
    data: Any = None


class ErrorResponse(BaseModel):
    """
    Uniform error response envelope.

    Returned by exception handlers for all application errors.
    The 'detail' field may be a string or a list of validation
    error objects (for Pydantic validation failures).

    Attributes:
        success: Always False for error responses.
        message: Short error category (e.g. "Not Found").
        detail: Detailed error description or validation errors.
    """
    success: bool = False
    message: str = "An error occurred"
    detail: Any = None


class PaginationParams(BaseModel):
    """
    Query parameters for paginated list endpoints.

    Provides sensible defaults and enforces upper bounds to prevent
    clients from requesting excessively large pages.

    Attributes:
        page: 1-based page number (default 1).
        page_size: Number of items per page (default 20, max 100).
        sort_by: Column name to sort by (default "created_at").
        sort_order: "asc" or "desc" (default "desc" — newest first).
    """
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page (max 100)",
    )
    sort_by: str = Field(
        default="created_at",
        description="Column name to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort direction: 'asc' or 'desc'",
    )

    @property
    def offset(self) -> int:
        """Calculate the SQL OFFSET from page number and page size."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """
    Response envelope for paginated list endpoints.

    Wraps the data items with pagination metadata so the frontend
    can render pagination controls without additional API calls.

    Attributes:
        success: Always True.
        message: Description of the result.
        data: List of items for the current page.
        page: Current page number.
        page_size: Items per page.
        total_items: Total number of matching items across all pages.
        total_pages: Computed total number of pages.
    """
    success: bool = True
    message: str = "Data retrieved successfully"
    data: list[Any] = Field(default_factory=list)
    page: int
    page_size: int
    total_items: int
    total_pages: int
