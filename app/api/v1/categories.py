"""
CivicPulse Categories API Router

Exposes endpoints for retrieving active civic complaint categories.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.category import CategoryResponse
from app.schemas.common import StandardResponse
from app.services.category_service import get_active_categories

router = APIRouter()


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
    summary="List active complaint categories",
    description="Returns all active civic issue categories with their managing department details.",
)
def list_categories(
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Retrieve active complaint categories for public and authenticated user selection.
    """
    categories = get_active_categories(db)
    category_list = [
        CategoryResponse(
            id=cat.id,
            department_id=cat.department_id,
            department_name=cat.department.name if cat.department else None,
            name=cat.name,
            description=cat.description,
            is_active=cat.is_active,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        ).model_dump(mode="json")
        for cat in categories
    ]

    return StandardResponse(
        success=True,
        message="Active categories retrieved successfully",
        data=category_list,
    )
