"""
CivicPulse Admin SLA Management API Router

Provides administrator-only endpoints for SLA policy configuration, dual-clock inspection,
cycle history audit trails, and bounded on-demand SLA batch evaluations.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import StandardResponse
from app.schemas.sla import (
    ComplaintSLADetailResponse,
    ComplaintSLAHistoryResponse,
    SLAEvaluationBatchResponse,
    SLAEvaluationFilterRequest,
    SLAPolicyCreateRequest,
    SLAPolicyResponse,
    SLAPolicyUpdateRequest,
)
from app.services.sla_service import (
    create_sla_policy,
    evaluate_sla_batch,
    get_complaint_sla_details,
    get_complaint_sla_history_records,
    get_sla_policy_by_id,
    list_sla_policies,
    update_sla_policy,
)

router = APIRouter()


# =============================================================================
# Policy Management Endpoints
# =============================================================================

@router.get(
    "/policies",
    response_model=StandardResponse,
    summary="List SLA policies",
    description="Retrieve all configured SLA policies. Administrator access only.",
)
def get_policies(
    active_only: bool = Query(default=False, description="Filter for active policies only"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    policies = list_sla_policies(db=db, active_only=active_only)
    data = [SLAPolicyResponse.model_validate(p).model_dump(mode="json") for p in policies]
    return StandardResponse(
        message="SLA policies retrieved successfully",
        data=data,
    )


@router.post(
    "/policies",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SLA policy",
    description="Define a new SLA policy. Protected with database advisory locks to prevent duplicates.",
)
def create_policy(
    payload: SLAPolicyCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    policy = create_sla_policy(db=db, data=payload, commit=True)
    return StandardResponse(
        message="SLA policy created successfully",
        data=SLAPolicyResponse.model_validate(policy).model_dump(mode="json"),
    )


@router.patch(
    "/policies/{policy_id}",
    response_model=StandardResponse,
    summary="Update SLA policy",
    description="Update durations or active status of an existing SLA policy.",
)
def update_policy(
    policy_id: uuid.UUID,
    payload: SLAPolicyUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    policy = update_sla_policy(db=db, policy_id=policy_id, data=payload, commit=True, admin_user=admin)
    return StandardResponse(
        message="SLA policy updated successfully",
        data=SLAPolicyResponse.model_validate(policy).model_dump(mode="json"),
    )


# =============================================================================
# On-Demand Bounded SLA Evaluation
# =============================================================================

@router.post(
    "/evaluate",
    response_model=StandardResponse,
    summary="Evaluate SLA batch",
    description="Execute bounded on-demand SLA evaluation with optional filters. Bounded to at most 200 items.",
)
def evaluate_batch(
    payload: SLAEvaluationFilterRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    result = evaluate_sla_batch(db=db, filters=payload, admin_user=admin)
    return StandardResponse(
        message="SLA batch evaluation completed successfully",
        data=result.model_dump(mode="json"),
    )


# =============================================================================
# Complaint SLA Details & Cycle History
# =============================================================================

@router.get(
    "/complaints/{complaint_id}",
    response_model=StandardResponse,
    summary="Get complaint SLA details",
    description="Inspect live dual-clock SLA performance, deadlines, pauses, and escalation level.",
)
def get_complaint_sla(
    complaint_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    details = get_complaint_sla_details(db=db, complaint_id=complaint_id, user=admin)
    return StandardResponse(
        message="Complaint SLA details retrieved successfully",
        data=details.model_dump(mode="json"),
    )


@router.get(
    "/complaints/{complaint_id}/history",
    response_model=StandardResponse,
    summary="Get complaint SLA cycle history",
    description="Retrieve immutable history records capturing performance of completed SLA cycles.",
)
def get_complaint_history(
    complaint_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StandardResponse:
    history = get_complaint_sla_history_records(db=db, complaint_id=complaint_id, user=admin)
    data = [ComplaintSLAHistoryResponse.model_validate(h).model_dump(mode="json") for h in history]
    return StandardResponse(
        message="Complaint SLA history retrieved successfully",
        data=data,
    )
