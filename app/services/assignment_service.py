"""
CivicPulse Assignment Service

Implements the business logic for complaint task assignment, worker acceptance,
work initiation, milestone progress tracking, completion verification, and reassignment.

Architecture & Safety:
    - Atomicity: State changes across complaints, assignments, and progress updates commit or rollback together.
    - PostgreSQL row-level locking (with_for_update) to eliminate race conditions during assignment and reassignment.
    - Centralized transition delegation: Always invokes execute_transition for complaint status updates.
    - Active assignment uniqueness: Enforced at both service layer and PostgreSQL partial unique index.
    - Strict eligibility validation: Worker active status, department matching, and complaint status preconditions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import (
    AssignmentStatus,
    ComplaintStatus,
    PriorityLevel,
    UserRole,
)
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.complaint import Complaint
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.models.worker import Worker
from app.schemas.common import PaginationParams
from app.services.complaint_service import execute_transition


# =============================================================================
# Helper Validations
# =============================================================================

def _validate_worker_eligibility(
    db: Session,
    worker_id: uuid.UUID,
    complaint: Complaint,
) -> Worker:
    """
    Validate that worker exists, is active, belongs to an active department,
    and has department coverage matching the complaint category.
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise EntityNotFoundError("Worker", worker_id)

    # 1. Base User account must be active and have FIELD_WORKER role
    if not worker.user or not worker.user.is_active:
        raise BusinessRuleViolationError(
            f"Worker '{worker.employee_id}' has an inactive user account"
        )
    if worker.user.role.name != UserRole.FIELD_WORKER.value:
        raise BusinessRuleViolationError(
            f"User associated with worker '{worker.employee_id}' does not have the FIELD_WORKER role"
        )

    # 2. Worker profile must be active and available
    if worker.employment_status != "ACTIVE":
        raise BusinessRuleViolationError(
            f"Worker '{worker.employee_id}' employment status is '{worker.employment_status}' (must be ACTIVE)"
        )
    if not worker.is_available:
        raise BusinessRuleViolationError(
            f"Worker '{worker.employee_id}' is currently marked unavailable"
        )

    # 3. Department must exist and be active
    if not worker.department or not worker.department.is_active:
        raise BusinessRuleViolationError(
            f"Worker's department '{worker.department.name if worker.department else 'Unknown'}' is inactive"
        )

    # 4. Department match: Complaint's category must belong to worker's department
    if complaint.category.department_id != worker.department_id:
        dept_name = worker.department.name
        cat_dept_name = complaint.category.department.name if complaint.category.department else "Unknown"
        raise BusinessRuleViolationError(
            f"Department mismatch: Complaint category '{complaint.category.name}' belongs to '{cat_dept_name}', "
            f"but worker belongs to '{dept_name}'"
        )

    return worker


# =============================================================================
# Primary Assignment
# =============================================================================

def assign_complaint(
    db: Session,
    complaint_id: uuid.UUID,
    worker_id: uuid.UUID,
    admin_user: User,
    notes: str | None = None,
) -> tuple[Assignment, Complaint]:
    """
    Assign an UNDER_REVIEW complaint to an eligible field worker.

    Transaction flow:
        1. Lock complaint row with with_for_update().
        2. Validate complaint status is strictly UNDER_REVIEW.
        3. Validate worker eligibility and category-department compatibility.
        4. Check for duplicate active assignments.
        5. Create Assignment record (status: ASSIGNED).
        6. Delegate lifecycle transition to execute_transition (UNDER_REVIEW -> ASSIGNED).
        7. Atomically commit.
    """
    if admin_user.role.name != UserRole.ADMINISTRATOR.value:
        raise AuthorizationError("Only administrators can assign complaints")

    # 1. Row-level lock on complaint
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .with_for_update()
        .first()
    )
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    # 2. Status precondition
    if complaint.status != ComplaintStatus.UNDER_REVIEW:
        raise BusinessRuleViolationError(
            f"Complaint must be in 'UNDER_REVIEW' status to be assigned. Current status is '{complaint.status.value}'"
        )

    # 3. Validate worker eligibility
    worker = _validate_worker_eligibility(db, worker_id, complaint)

    # 4. Check no active assignment already exists
    has_active = any(
        a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}
        for a in complaint.assignments
    )
    if has_active:
        raise BusinessRuleViolationError(
            "Complaint already has an active assignment. Use reassignment endpoint to change technicians."
        )

    now_utc = datetime.now(timezone.utc)

    # 5. Create Assignment record
    assignment = Assignment(
        complaint_id=complaint.id,
        worker_id=worker.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.ASSIGNED,
        assigned_at=now_utc,
        notes=notes.strip() if notes else None,
    )
    db.add(assignment)
    db.flush()
    db.expire(complaint, ["assignments"])

    # 6. Execute state machine transition (UNDER_REVIEW -> ASSIGNED)
    updated_complaint = execute_transition(
        db=db,
        complaint_id=complaint.id,
        user=admin_user,
        requested_status=ComplaintStatus.ASSIGNED,
        remarks=f"Assigned to {worker.user.full_name} ({worker.employee_id})",
        commit=False,
    )

    from app.services.notification_service import notify_assignment_dispatched
    notify_assignment_dispatched(db=db, complaint=updated_complaint, assignment=assignment, actor=admin_user)

    db.commit()
    db.refresh(assignment)
    db.refresh(updated_complaint)
    return assignment, updated_complaint


# =============================================================================
# Worker Task Actions (Accept, Start, Progress, Complete)
# =============================================================================

def accept_assignment(
    db: Session,
    assignment_id: uuid.UUID,
    worker_user: User,
) -> Assignment:
    """
    Worker acknowledges and accepts a dispatched assignment.
    """
    # 1. Row-level lock on complaint first (ensures consistent Complaint -> Assignment lock order)
    assignment_pre = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment_pre:
        raise EntityNotFoundError("Assignment", assignment_id)

    db.query(Complaint).filter(Complaint.id == assignment_pre.complaint_id).with_for_update().first()

    # 2. Row-level lock on assignment
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .with_for_update()
        .first()
    )

    # Verify worker ownership
    if assignment.worker.user_id != worker_user.id:
        raise AuthorizationError("You are not the designated worker for this assignment")

    # Verify worker is active
    if assignment.worker.employment_status != "ACTIVE" or not worker_user.is_active:
        raise AuthorizationError("Worker account or employment status is inactive")

    # Validate status
    if assignment.status != AssignmentStatus.ASSIGNED:
        raise BusinessRuleViolationError(
            f"Cannot accept assignment in '{assignment.status.value}' status"
        )

    # Idempotent: if already accepted, return
    if assignment.accepted_at is not None:
        return assignment

    now_utc = datetime.now(timezone.utc)
    assignment.accepted_at = now_utc

    progress = AssignmentProgress(
        assignment_id=assignment.id,
        worker_id=assignment.worker_id,
        description="Assignment accepted by technician",
        created_at=now_utc,
    )
    db.add(progress)

    from app.services.notification_service import notify_worker_activity
    notify_worker_activity(
        db=db,
        complaint=assignment.complaint,
        assignment=assignment,
        activity_type="ACCEPTED",
        actor=worker_user,
    )

    db.commit()
    db.refresh(assignment)
    return assignment


def start_assignment(
    db: Session,
    assignment_id: uuid.UUID,
    worker_user: User,
    notes: str | None = None,
) -> tuple[Assignment, Complaint]:
    """
    Worker initiates investigation or remediation work on site.

    Transitions:
        - Assignment: ASSIGNED -> IN_PROGRESS
        - Complaint: ASSIGNED -> IN_PROGRESS
    """
    # 1. Row-level lock on complaint first (ensures consistent Complaint -> Assignment lock order)
    assignment_pre = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment_pre:
        raise EntityNotFoundError("Assignment", assignment_id)

    db.query(Complaint).filter(Complaint.id == assignment_pre.complaint_id).with_for_update().first()

    # 2. Row-level lock on assignment
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .with_for_update()
        .first()
    )

    # Ownership and active status
    if assignment.worker.user_id != worker_user.id:
        raise AuthorizationError("You are not the designated worker for this assignment")
    if assignment.worker.employment_status != "ACTIVE" or not worker_user.is_active:
        raise AuthorizationError("Worker account or employment status is inactive")

    if assignment.status != AssignmentStatus.ASSIGNED:
        raise BusinessRuleViolationError(
            f"Cannot start work on assignment with status '{assignment.status.value}'"
        )

    now_utc = datetime.now(timezone.utc)
    if assignment.accepted_at is None:
        assignment.accepted_at = now_utc
    assignment.started_at = now_utc
    assignment.status = AssignmentStatus.IN_PROGRESS

    # Record progress milestone
    progress = AssignmentProgress(
        assignment_id=assignment.id,
        worker_id=assignment.worker_id,
        description=notes.strip() if notes else "Work initiated on site by technician",
        created_at=now_utc,
    )
    db.add(progress)
    db.flush()

    # Transition complaint ASSIGNED -> IN_PROGRESS via centralized transition service
    updated_complaint = execute_transition(
        db=db,
        complaint_id=assignment.complaint_id,
        user=worker_user,
        requested_status=ComplaintStatus.IN_PROGRESS,
        remarks=notes.strip() if notes else "Work initiated on site",
        commit=False,
    )

    from app.services.notification_service import notify_worker_activity
    notify_worker_activity(
        db=db,
        complaint=updated_complaint,
        assignment=assignment,
        activity_type="STARTED",
        actor=worker_user,
    )

    db.commit()
    db.refresh(assignment)
    return assignment, updated_complaint


def add_assignment_progress(
    db: Session,
    assignment_id: uuid.UUID,
    worker_user: User,
    description: str,
) -> AssignmentProgress:
    """
    Worker records an intermediate progress note or milestone update.
    """
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .with_for_update()
        .first()
    )
    if not assignment:
        raise EntityNotFoundError("Assignment", assignment_id)

    # Ownership and active status
    if assignment.worker.user_id != worker_user.id:
        raise AuthorizationError("You are not the designated worker for this assignment")
    if assignment.worker.employment_status != "ACTIVE" or not worker_user.is_active:
        raise AuthorizationError("Worker account or employment status is inactive")

    if assignment.status != AssignmentStatus.IN_PROGRESS:
        raise BusinessRuleViolationError(
            f"Progress updates can only be recorded when assignment is 'IN_PROGRESS'. Current status is '{assignment.status.value}'"
        )

    now_utc = datetime.now(timezone.utc)
    progress = AssignmentProgress(
        assignment_id=assignment.id,
        worker_id=assignment.worker_id,
        description=description.strip(),
        created_at=now_utc,
    )
    db.add(progress)
    db.flush()

    from app.services.notification_service import notify_worker_activity
    notify_worker_activity(
        db=db,
        complaint=assignment.complaint,
        assignment=assignment,
        activity_type="PROGRESS",
        progress=progress,
        actor=worker_user,
    )

    db.commit()
    db.refresh(progress)
    return progress


def complete_assignment(
    db: Session,
    assignment_id: uuid.UUID,
    worker_user: User,
    summary: str,
) -> tuple[Assignment, Complaint]:
    """
    Worker completes remediation and submits the task for verification.

    Transitions:
        - Assignment: IN_PROGRESS -> COMPLETED
        - Complaint: IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION
    """
    # 1. Row-level lock on complaint first (ensures consistent Complaint -> Assignment lock order)
    assignment_pre = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment_pre:
        raise EntityNotFoundError("Assignment", assignment_id)

    db.query(Complaint).filter(Complaint.id == assignment_pre.complaint_id).with_for_update().first()

    # 2. Row-level lock on assignment
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .with_for_update()
        .first()
    )

    # Ownership and active status
    if assignment.worker.user_id != worker_user.id:
        raise AuthorizationError("You are not the designated worker for this assignment")
    if assignment.worker.employment_status != "ACTIVE" or not worker_user.is_active:
        raise AuthorizationError("Worker account or employment status is inactive")

    if assignment.status != AssignmentStatus.IN_PROGRESS:
        raise BusinessRuleViolationError(
            f"Cannot complete assignment in '{assignment.status.value}' status (must be IN_PROGRESS)"
        )

    now_utc = datetime.now(timezone.utc)
    assignment.status = AssignmentStatus.COMPLETED
    assignment.completed_at = now_utc

    progress = AssignmentProgress(
        assignment_id=assignment.id,
        worker_id=assignment.worker_id,
        description=f"Work completed: {summary.strip()}",
        created_at=now_utc,
    )
    db.add(progress)
    db.flush()

    # Transition complaint IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION
    updated_complaint = execute_transition(
        db=db,
        complaint_id=assignment.complaint_id,
        user=worker_user,
        requested_status=ComplaintStatus.RESOLVED_AWAITING_VERIFICATION,
        remarks=summary.strip(),
    )

    db.refresh(assignment)
    return assignment, updated_complaint


# =============================================================================
# Administrator Reassignment
# =============================================================================

def reassign_complaint(
    db: Session,
    complaint_id: uuid.UUID,
    new_worker_id: uuid.UUID,
    admin_user: User,
    reason: str,
    notes: str | None = None,
) -> tuple[Assignment, Complaint]:
    """
    Reassign an ASSIGNED or IN_PROGRESS complaint to a replacement field worker.

    Guarantees:
        - Row lock serializes concurrent reassignment attempts.
        - Previous assignment marked REASSIGNED (never deleted).
        - New Assignment created in ASSIGNED state.
        - Complaint moved back to ASSIGNED if previously IN_PROGRESS.
        - Status history audit log preserved.
    """
    if admin_user.role.name != UserRole.ADMINISTRATOR.value:
        raise AuthorizationError("Only administrators can reassign complaints")

    # 1. Lock complaint row
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .with_for_update()
        .first()
    )
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    if complaint.status not in {ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS}:
        raise BusinessRuleViolationError(
            f"Complaint must be in 'ASSIGNED' or 'IN_PROGRESS' to reassign. Current status is '{complaint.status.value}'"
        )

    # 2. Find currently active assignment
    current_assignment = next(
        (
            a
            for a in complaint.assignments
            if a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}
        ),
        None,
    )
    if not current_assignment:
        raise BusinessRuleViolationError("Complaint does not have an active assignment to reassign")

    # 3. Validate new worker
    new_worker = _validate_worker_eligibility(db, new_worker_id, complaint)
    if new_worker.id == current_assignment.worker_id:
        raise BusinessRuleViolationError(
            "Replacement worker cannot be identical to the currently assigned worker"
        )

    now_utc = datetime.now(timezone.utc)

    # 4. Supersede current assignment
    current_assignment.status = AssignmentStatus.REASSIGNED
    reassign_note = f"Reassigned to {new_worker.user.full_name} ({new_worker.employee_id}). Reason: {reason.strip()}"
    old_progress = AssignmentProgress(
        assignment_id=current_assignment.id,
        worker_id=current_assignment.worker_id,
        description=reassign_note,
        created_at=now_utc,
    )
    db.add(old_progress)

    # 5. Create new assignment
    new_assignment = Assignment(
        complaint_id=complaint.id,
        worker_id=new_worker.id,
        assigned_by_id=admin_user.id,
        status=AssignmentStatus.ASSIGNED,
        assigned_at=now_utc,
        notes=notes.strip() if notes else f"Reassigned. Reason: {reason.strip()}",
    )
    db.add(new_assignment)
    db.flush()
    db.expire(complaint, ["assignments"])

    # 6. Update complaint status if was IN_PROGRESS
    if complaint.status == ComplaintStatus.IN_PROGRESS:
        # Strictly follow the approved Phase 4 lifecycle state machine transitions:
        # 1. IN_PROGRESS -> ON_HOLD: Work paused on site for technician reassignment
        execute_transition(
            db=db,
            complaint_id=complaint.id,
            user=admin_user,
            requested_status=ComplaintStatus.ON_HOLD,
            remarks=f"Work paused on site for technician reassignment. Reason: {reason.strip()}",
            commit=False,
        )
        # 2. ON_HOLD -> UNDER_REVIEW: Administrative review for technician replacement
        execute_transition(
            db=db,
            complaint_id=complaint.id,
            user=admin_user,
            requested_status=ComplaintStatus.UNDER_REVIEW,
            remarks=f"Administrative review for technician reassignment. Reason: {reason.strip()}",
            commit=False,
        )
        # 3. UNDER_REVIEW -> ASSIGNED: Reassigned to replacement technician
        updated_complaint = execute_transition(
            db=db,
            complaint_id=complaint.id,
            user=admin_user,
            requested_status=ComplaintStatus.ASSIGNED,
            remarks=reassign_note,
            commit=False,
        )
        from app.services.notification_service import notify_assignment_reassigned
        notify_assignment_reassigned(
            db=db,
            complaint=complaint,
            old_assignment=current_assignment,
            new_assignment=new_assignment,
            actor=admin_user,
        )

        db.commit()
        db.refresh(complaint)
    else:
        # If was already ASSIGNED, record reassignment in status history
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_id=admin_user.id,
            previous_status=ComplaintStatus.ASSIGNED,
            new_status=ComplaintStatus.ASSIGNED,
            remarks=reassign_note,
            created_at=now_utc,
        )
        db.add(history)

        from app.services.notification_service import notify_assignment_reassigned
        notify_assignment_reassigned(
            db=db,
            complaint=complaint,
            old_assignment=current_assignment,
            new_assignment=new_assignment,
            actor=admin_user,
        )

        db.commit()
        db.refresh(complaint)
        updated_complaint = complaint

    db.refresh(new_assignment)
    return new_assignment, updated_complaint


# =============================================================================
# Queries & Task Inspection
# =============================================================================

def get_worker_tasks(
    db: Session,
    worker_user: User,
    status_filter: AssignmentStatus | None = None,
    priority_filter: PriorityLevel | None = None,
    pagination: PaginationParams | None = None,
) -> tuple[list[Assignment], int]:
    """
    Retrieve tasks assigned to the authenticated field worker.
    """
    worker = db.query(Worker).filter(Worker.user_id == worker_user.id).first()
    if not worker:
        raise AuthorizationError("Authenticated user does not have a worker profile")
    if worker.employment_status != "ACTIVE" or not worker_user.is_active:
        raise AuthorizationError("Worker account or employment status is inactive")

    query = (
        db.query(Assignment)
        .join(Assignment.complaint)
        .filter(Assignment.worker_id == worker.id)
    )

    if status_filter is not None:
        query = query.filter(Assignment.status == status_filter)

    if priority_filter is not None:
        query = query.filter(Complaint.priority == priority_filter)

    total_items = query.count()

    if pagination:
        query = (
            query.order_by(Assignment.assigned_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    else:
        query = query.order_by(Assignment.assigned_at.desc())

    return query.all(), total_items


def get_worker_task_by_id(
    db: Session,
    assignment_id: uuid.UUID,
    worker_user: User,
) -> Assignment:
    """
    Retrieve single task for authenticated worker with IDOR ownership check.
    """
    worker = db.query(Worker).filter(Worker.user_id == worker_user.id).first()
    if not worker:
        raise AuthorizationError("Authenticated user does not have a worker profile")
    if worker.employment_status != "ACTIVE" or not worker_user.is_active:
        raise AuthorizationError("Worker account or employment status is inactive")

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise EntityNotFoundError("Task assignment", assignment_id)

    if assignment.worker_id != worker.id:
        raise AuthorizationError("You do not have permission to access this task")

    return assignment


def list_assignments(
    db: Session,
    filters: dict[str, Any],
    pagination: PaginationParams,
) -> tuple[list[Assignment], int]:
    """
    Administrator query for all assignments across the platform.
    """
    query = (
        db.query(Assignment)
        .join(Assignment.complaint)
        .join(Assignment.worker)
        .join(Worker.department)
    )

    if filters.get("department_id"):
        query = query.filter(Worker.department_id == filters["department_id"])

    if filters.get("worker_id"):
        query = query.filter(Assignment.worker_id == filters["worker_id"])

    if filters.get("complaint_id"):
        query = query.filter(Assignment.complaint_id == filters["complaint_id"])

    if filters.get("status"):
        query = query.filter(Assignment.status == filters["status"])

    total_items = query.count()
    items = (
        query.order_by(Assignment.assigned_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
        .all()
    )
    return items, total_items


def get_assignment_by_id(db: Session, assignment_id: uuid.UUID) -> Assignment:
    """
    Administrator lookup for single assignment.
    """
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .with_for_update()
        .first()
    )
    if not assignment:
        raise EntityNotFoundError("Assignment", assignment_id)
    return assignment


def get_complaint_assignments(db: Session, complaint_id: uuid.UUID) -> list[Assignment]:
    """
    Administrator lookup for all assignments associated with a complaint.
    """
    return (
        db.query(Assignment)
        .filter(Assignment.complaint_id == complaint_id)
        .order_by(Assignment.assigned_at.desc())
        .all()
    )
