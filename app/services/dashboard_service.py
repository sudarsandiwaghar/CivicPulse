"""
CivicPulse Citizen Dashboard Service

Provides high-efficiency SQL aggregation and activity feed queries
for the authenticated citizen dashboard.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.constants import ComplaintStatus, PriorityLevel
from app.models.complaint import Complaint
from app.models.user import User


def _format_summary(c: Complaint) -> dict[str, Any]:
    """
    Format a Complaint ORM instance into a summary dictionary.
    """
    return {
        "id": c.id,
        "complaint_number": c.complaint_number,
        "title": c.title,
        "category_id": c.category_id,
        "category_name": c.category.name if c.category else "Unknown",
        "status": c.status,
        "priority": c.priority,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "resolved_at": c.resolved_at,
    }


def get_citizen_dashboard(db: Session, citizen: User) -> dict[str, Any]:
    """
    Calculate consolidated metrics and retrieve recent activity feeds
    strictly scoped to the authenticated citizen.

    SQL Strategy:
        - Single-query PostgreSQL conditional aggregation (`func.count().filter(...)`)
          computes all status and priority breakdowns and metric totals in one pass.
        - Three indexed queries capped at 5 records retrieve activity lists:
            1. recent_submissions (created_at DESC)
            2. recent_updates (updated_at DESC)
            3. action_required (RESOLVED_AWAITING_VERIFICATION, resolved_at DESC)
        - Joined loading on Category avoids N+1 queries.

    Args:
        db: Request-scoped database session.
        citizen: Authenticated citizen User record.

    Returns:
        Structured dictionary matching CitizenDashboardData schema.
    """
    citizen_id = citizen.id

    # 1. Single-query conditional aggregation across all statuses and priorities
    agg_stmt = (
        select(
            func.count().label("total"),
            func.count()
            .filter(
                Complaint.status.in_(
                    [
                        ComplaintStatus.SUBMITTED,
                        ComplaintStatus.UNDER_REVIEW,
                        ComplaintStatus.ASSIGNED,
                        ComplaintStatus.IN_PROGRESS,
                        ComplaintStatus.ON_HOLD,
                        ComplaintStatus.REOPENED,
                    ]
                )
            )
            .label("active"),
            func.count()
            .filter(Complaint.status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION)
            .label("awaiting_verification"),
            func.count().filter(Complaint.status == ComplaintStatus.CLOSED).label("closed"),
            func.count().filter(Complaint.status == ComplaintStatus.REJECTED).label("rejected"),
            func.count().filter(Complaint.status == ComplaintStatus.DUPLICATE).label("duplicate"),
            # Status breakdown
            func.count().filter(Complaint.status == ComplaintStatus.SUBMITTED).label("status_submitted"),
            func.count().filter(Complaint.status == ComplaintStatus.UNDER_REVIEW).label("status_under_review"),
            func.count().filter(Complaint.status == ComplaintStatus.ASSIGNED).label("status_assigned"),
            func.count().filter(Complaint.status == ComplaintStatus.IN_PROGRESS).label("status_in_progress"),
            func.count().filter(Complaint.status == ComplaintStatus.ON_HOLD).label("status_on_hold"),
            func.count()
            .filter(Complaint.status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION)
            .label("status_resolved_awaiting_verification"),
            func.count().filter(Complaint.status == ComplaintStatus.CLOSED).label("status_closed"),
            func.count().filter(Complaint.status == ComplaintStatus.REOPENED).label("status_reopened"),
            func.count().filter(Complaint.status == ComplaintStatus.REJECTED).label("status_rejected"),
            func.count().filter(Complaint.status == ComplaintStatus.DUPLICATE).label("status_duplicate"),
            # Priority breakdown
            func.count().filter(Complaint.priority == PriorityLevel.LOW).label("priority_low"),
            func.count().filter(Complaint.priority == PriorityLevel.MEDIUM).label("priority_medium"),
            func.count().filter(Complaint.priority == PriorityLevel.HIGH).label("priority_high"),
            func.count().filter(Complaint.priority == PriorityLevel.CRITICAL).label("priority_critical"),
        )
        .where(Complaint.citizen_id == citizen_id)
    )

    agg_result = db.execute(agg_stmt).one()

    # Build exhaustive status breakdown covering all 10 approved statuses
    status_breakdown = {
        ComplaintStatus.SUBMITTED.value: int(agg_result.status_submitted or 0),
        ComplaintStatus.UNDER_REVIEW.value: int(agg_result.status_under_review or 0),
        ComplaintStatus.ASSIGNED.value: int(agg_result.status_assigned or 0),
        ComplaintStatus.IN_PROGRESS.value: int(agg_result.status_in_progress or 0),
        ComplaintStatus.ON_HOLD.value: int(agg_result.status_on_hold or 0),
        ComplaintStatus.RESOLVED_AWAITING_VERIFICATION.value: int(agg_result.status_resolved_awaiting_verification or 0),
        ComplaintStatus.CLOSED.value: int(agg_result.status_closed or 0),
        ComplaintStatus.REOPENED.value: int(agg_result.status_reopened or 0),
        ComplaintStatus.REJECTED.value: int(agg_result.status_rejected or 0),
        ComplaintStatus.DUPLICATE.value: int(agg_result.status_duplicate or 0),
    }

    # Build exhaustive priority breakdown covering all 4 priority levels
    priority_breakdown = {
        PriorityLevel.LOW.value: int(agg_result.priority_low or 0),
        PriorityLevel.MEDIUM.value: int(agg_result.priority_medium or 0),
        PriorityLevel.HIGH.value: int(agg_result.priority_high or 0),
        PriorityLevel.CRITICAL.value: int(agg_result.priority_critical or 0),
    }

    metrics = {
        "total_complaints": int(agg_result.total or 0),
        "active_complaints": int(agg_result.active or 0),
        "awaiting_verification": int(agg_result.awaiting_verification or 0),
        "closed_complaints": int(agg_result.closed or 0),
        "rejected_complaints": int(agg_result.rejected or 0),
        "duplicate_complaints": int(agg_result.duplicate or 0),
        "action_required_count": int(agg_result.awaiting_verification or 0),
        "status_breakdown": status_breakdown,
        "priority_breakdown": priority_breakdown,
    }

    # 2. Activity list: Recent submissions (latest 5 ordered by created_at DESC)
    recent_submissions_query = (
        db.query(Complaint)
        .options(joinedload(Complaint.category))
        .filter(Complaint.citizen_id == citizen_id)
        .order_by(Complaint.created_at.desc())
        .limit(5)
        .all()
    )

    # 3. Activity list: Recent updates (latest 5 ordered by updated_at DESC)
    recent_updates_query = (
        db.query(Complaint)
        .options(joinedload(Complaint.category))
        .filter(Complaint.citizen_id == citizen_id)
        .order_by(Complaint.updated_at.desc())
        .limit(5)
        .all()
    )

    # 4. Activity list: Action required (RESOLVED_AWAITING_VERIFICATION, latest 5)
    action_required_query = (
        db.query(Complaint)
        .options(joinedload(Complaint.category))
        .filter(
            Complaint.citizen_id == citizen_id,
            Complaint.status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        )
        .order_by(
            Complaint.resolved_at.desc().nullslast(),
            Complaint.updated_at.desc(),
        )
        .limit(5)
        .all()
    )

    return {
        "metrics": metrics,
        "recent_submissions": [_format_summary(c) for c in recent_submissions_query],
        "recent_updates": [_format_summary(c) for c in recent_updates_query],
        "action_required": [_format_summary(c) for c in action_required_query],
    }
