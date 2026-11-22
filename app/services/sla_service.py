"""
CivicPulse SLA Service

Implements the business logic for Service Level Agreement (SLA) policy management,
dual-clock (Response and Resolution) tracking, pause accounting during ON_HOLD,
deterministic 4-tier policy precedence resolution, PostgreSQL advisory locking,
and append-only SLA cycle history snapshotting.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from app.core.constants import ComplaintStatus, PriorityLevel, UserRole
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
)
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_sla_history import ComplaintSLAHistory
from app.models.sla_policy import SLAPolicy
from app.models.user import User
from app.schemas.sla import (
    ComplaintSLADetailResponse,
    SLAEvaluationBatchResponse,
    SLAEvaluationFilterRequest,
    SLAEvaluationItemResult,
    SLAPolicyCreateRequest,
    SLAPolicyUpdateRequest,
)


# =============================================================================
# Concurrency & Policy Locking
# =============================================================================

def lock_policy_logical_key(
    db: Session,
    category_id: int | None,
    priority: PriorityLevel | str | None,
) -> None:
    """
    Acquire a PostgreSQL transaction-scoped advisory lock for the logical policy key.

    Locks are automatically released when the transaction ends (commit or rollback).
    This guarantees serialization of concurrent policy creation/updates for identical
    (category_id, priority) dimensions.
    """
    cat_val = category_id if category_id is not None else -1
    pri_val = priority.value if isinstance(priority, PriorityLevel) else (str(priority) if priority else "NONE")
    lock_key = f"sla_policy:{cat_val}:{pri_val}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key})


# =============================================================================
# Policy Resolution (Deterministic 4-Tier Precedence)
# =============================================================================

def resolve_sla_policy(
    db: Session,
    category_id: int | None,
    priority: PriorityLevel | None,
) -> SLAPolicy | None:
    """
    Resolve the active SLA policy for a given category and priority using 4-tier precedence:
        1. Exact category + priority match.
        2. Category-specific policy (category_id IS NOT NULL, priority IS NULL).
        3. Priority-specific policy (category_id IS NULL, priority IS NOT NULL).
        4. Global fallback policy (category_id IS NULL, priority IS NULL).

    Returns:
        The highest-precedence active SLAPolicy, or None if no matching policy exists.
    """
    # Fetch all potentially matching active policies
    clauses = [
        and_(SLAPolicy.category_id.is_(None), SLAPolicy.priority.is_(None)),
    ]
    if category_id is not None:
        clauses.append(and_(SLAPolicy.category_id == category_id, SLAPolicy.priority.is_(None)))
    if priority is not None:
        clauses.append(and_(SLAPolicy.category_id.is_(None), SLAPolicy.priority == priority))
    if category_id is not None and priority is not None:
        clauses.append(and_(SLAPolicy.category_id == category_id, SLAPolicy.priority == priority))

    policies = (
        db.query(SLAPolicy)
        .filter(
            SLAPolicy.is_active.is_(True),
            or_(*clauses),
        )
        .all()
    )

    if not policies:
        return None

    # Precedence ranking: lower number = higher precedence
    def rank(p: SLAPolicy) -> int:
        if p.category_id is not None and p.priority is not None:
            return 1
        if p.category_id is not None and p.priority is None:
            return 2
        if p.category_id is None and p.priority is not None:
            return 3
        return 4

    policies.sort(key=rank)
    return policies[0]


# =============================================================================
# Policy Management CRUD
# =============================================================================

def create_sla_policy(
    db: Session,
    data: SLAPolicyCreateRequest,
    commit: bool = True,
) -> SLAPolicy:
    """
    Create a new SLA policy with concurrency locking and logical duplicate rejection.
    """
    # 1. Acquire transaction-scoped advisory lock for the logical dimension key
    lock_policy_logical_key(db, data.category_id, data.priority)

    # 2. Check for duplicate logical policy
    existing_query = db.query(SLAPolicy)
    if data.category_id is not None:
        existing_query = existing_query.filter(SLAPolicy.category_id == data.category_id)
    else:
        existing_query = existing_query.filter(SLAPolicy.category_id.is_(None))

    if data.priority is not None:
        existing_query = existing_query.filter(SLAPolicy.priority == data.priority)
    else:
        existing_query = existing_query.filter(SLAPolicy.priority.is_(None))

    if existing_query.first():
        cat_desc = f"Category {data.category_id}" if data.category_id else "Global"
        pri_desc = f"Priority {data.priority.value}" if data.priority else "All Priorities"
        raise BusinessRuleViolationError(
            f"An SLA policy for {cat_desc} and {pri_desc} already exists"
        )

    # 3. Validate category existence if specified
    if data.category_id is not None:
        category = db.query(Category).filter(Category.id == data.category_id).first()
        if not category:
            raise EntityNotFoundError("Category", data.category_id)

    # 4. Create and persist policy
    policy = SLAPolicy(
        name=data.name,
        description=data.description,
        category_id=data.category_id,
        priority=data.priority,
        response_time_hours=data.response_time_hours,
        resolution_time_hours=data.resolution_time_hours,
        is_active=data.is_active,
    )
    db.add(policy)

    if commit:
        db.commit()
        db.refresh(policy)
    else:
        db.flush()
        db.refresh(policy)

    return policy


def list_sla_policies(
    db: Session,
    active_only: bool = False,
) -> list[SLAPolicy]:
    """
    List all SLA policies, optionally filtered by active status.
    """
    query = db.query(SLAPolicy)
    if active_only:
        query = query.filter(SLAPolicy.is_active.is_(True))
    return query.order_by(SLAPolicy.created_at.desc()).all()


def get_sla_policy_by_id(
    db: Session,
    policy_id: uuid.UUID,
) -> SLAPolicy:
    """
    Retrieve an SLA policy by UUID.
    """
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise EntityNotFoundError("SLAPolicy", policy_id)
    return policy


def update_sla_policy(
    db: Session,
    policy_id: uuid.UUID,
    data: SLAPolicyUpdateRequest,
    commit: bool = True,
    admin_user: User | None = None,
) -> SLAPolicy:
    """
    Update an existing SLA policy while locking the row and preserving historical SLA snapshots.
    Re-evaluates active complaints governed by this policy when targets change.
    """
    policy = (
        db.query(SLAPolicy)
        .filter(SLAPolicy.id == policy_id)
        .with_for_update()
        .first()
    )
    if not policy:
        raise EntityNotFoundError("SLAPolicy", policy_id)

    old_response = policy.response_time_hours
    old_resolution = policy.resolution_time_hours

    if data.name is not None:
        policy.name = data.name
    if data.description is not None:
        policy.description = data.description
    if data.response_time_hours is not None:
        policy.response_time_hours = data.response_time_hours
    if data.resolution_time_hours is not None:
        policy.resolution_time_hours = data.resolution_time_hours
    if data.is_active is not None:
        policy.is_active = data.is_active

    db.flush()

    # If targets changed, re-evaluate active complaints governed by this policy
    targets_changed = (
        (data.response_time_hours is not None and data.response_time_hours != old_response)
        or (data.resolution_time_hours is not None and data.resolution_time_hours != old_resolution)
    )

    if targets_changed:
        now_utc = datetime.now(timezone.utc)
        active_complaints = (
            db.query(Complaint)
            .filter(
                or_(
                    Complaint.response_sla_policy_id == policy.id,
                    Complaint.resolution_sla_policy_id == policy.id,
                ),
                Complaint.status.notin_([
                    ComplaintStatus.REJECTED,
                    ComplaintStatus.DUPLICATE,
                    ComplaintStatus.CLOSED,
                ]),
            )
            .with_for_update()
            .all()
        )
        for c in active_complaints:
            evaluate_complaint_sla(
                db,
                c,
                now_utc=now_utc,
                actor=admin_user,
                audit_reason=f"Policy '{policy.name}' target updated",
            )

    if commit:
        db.commit()
        db.refresh(policy)
    else:
        db.flush()
        db.refresh(policy)

    return policy


# =============================================================================
# Clock Evaluation & Escalation Calculations
# =============================================================================

def calculate_escalation_level(
    effective_elapsed_seconds: float | int | Decimal,
    target_seconds: float | int | Decimal,
    is_resolution: bool,
) -> int:
    """
    Determine the escalation level based on effective consumption percentage using precise Decimal comparison.

    Response clock:
        Level 0: elapsed percentage below 75% (< 0.75).
        Level 1: elapsed percentage >= 75% and < 100% (>= 0.75 and < 1.0).
        Level 2: elapsed percentage >= 100% (>= 1.0).

    Resolution clock:
        Level 0: elapsed percentage below 75% (< 0.75).
        Level 1: elapsed percentage >= 75% and < 100% (>= 0.75 and < 1.0).
        Level 2: elapsed percentage >= 100% and < 150% (>= 1.0 and < 1.5).
        Level 3: elapsed percentage >= 150% (>= 1.5).
    """
    if target_seconds <= 0:
        return 0

    elapsed_d = Decimal(str(effective_elapsed_seconds))
    target_d = Decimal(str(target_seconds))

    threshold_75 = target_d * Decimal("0.75")
    threshold_100 = target_d * Decimal("1.0")
    threshold_150 = target_d * Decimal("1.5")

    if not is_resolution:
        if elapsed_d < threshold_75:
            return 0
        elif elapsed_d < threshold_100:
            return 1
        else:
            return 2
    else:
        if elapsed_d < threshold_75:
            return 0
        elif elapsed_d < threshold_100:
            return 1
        elif elapsed_d < threshold_150:
            return 2
        else:
            return 3


def get_complaint_cycle_start(complaint: Complaint, db: Session | None = None) -> datetime:
    """
    Determine the start timestamp for the complaint's current SLA resolution cycle.
    For cycle 1, returns complaint.created_at.
    For cycle > 1 (reopened), returns the timestamp of the latest transition to REOPENED.
    """
    if complaint.sla_cycle_number <= 1:
        start_time = complaint.created_at
    else:
        start_time = None
        if db is not None:
            from app.models.status_history import ComplaintStatusHistory
            latest_reopen = (
                db.query(ComplaintStatusHistory)
                .filter(
                    ComplaintStatusHistory.complaint_id == complaint.id,
                    ComplaintStatusHistory.new_status == ComplaintStatus.REOPENED,
                )
                .order_by(ComplaintStatusHistory.created_at.desc())
                .first()
            )
            if latest_reopen:
                start_time = latest_reopen.created_at

        if start_time is None:
            for h in complaint.status_history:
                if h.new_status == ComplaintStatus.REOPENED:
                    start_time = h.created_at
                    break

        if start_time is None:
            start_time = complaint.created_at

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return start_time


def evaluate_complaint_sla(
    db: Session,
    complaint: Complaint,
    now_utc: datetime | None = None,
    actor: User | None = None,
    audit_reason: str | None = None,
) -> tuple[int, int, int, int]:
    """
    Perform synchronous evaluation of a complaint's dual SLA clocks and escalation levels.

    Guarantees:
        - Accurately accounts for accumulated and current active ON_HOLD pauses.
        - Does NOT mutate accumulated pause fields while complaint remains in ON_HOLD.
        - Completed response clock is never restarted, modified, or de-escalated.
        - Completed resolution clock for current cycle is never restarted or modified.
        - Idempotent: repeated evaluations at identical times do not mutate state.
        - Supports policy updates and dynamic de-escalation where policy changes for active clocks.
        - Records auditable status history entries when escalation levels change and actor is provided.

    Returns:
        tuple: (prev_resp_escalation, new_resp_escalation, prev_res_escalation, new_res_escalation)
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    prev_resp_esc = complaint.response_escalation_level
    prev_res_esc = complaint.resolution_escalation_level

    # 1. Resolve current active policy
    policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)

    # 2. Response Clock Evaluation
    if complaint.responded_at is not None:
        # Completed response clock: MUST REMAIN COMPLETED PERMANENTLY.
        # Do not modify deadline or escalation level once completed.
        pass
    else:
        # Active response clock
        if policy:
            complaint.response_sla_policy_id = policy.id
            resp_target_seconds = policy.response_time_hours * 3600
            created_at = complaint.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            # Active pause dynamically calculated without mutating DB pause field
            active_pause = 0
            if complaint.response_pause_started_at:
                p_start = complaint.response_pause_started_at
                if p_start.tzinfo is None:
                    p_start = p_start.replace(tzinfo=timezone.utc)
                active_pause = max(0, int((now_utc - p_start).total_seconds()))

            total_pause = complaint.response_pause_duration_seconds + active_pause
            complaint.response_deadline = created_at + timedelta(seconds=resp_target_seconds + total_pause)

            effective_elapsed = max(
                0,
                int((now_utc - created_at).total_seconds()) - total_pause,
            )
            complaint.response_escalation_level = calculate_escalation_level(
                effective_elapsed, resp_target_seconds, is_resolution=False
            )

    # 3. Resolution Clock Evaluation
    is_terminal = complaint.status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE, ComplaintStatus.CLOSED}
    if complaint.resolved_at is not None or is_terminal:
        # Completed resolution clock for current cycle:
        # Do not modify deadline or escalation level once resolved or closed.
        pass
    else:
        # Active resolution clock
        if policy:
            complaint.resolution_sla_policy_id = policy.id
            res_target_seconds = policy.resolution_time_hours * 3600
            cycle_start = get_complaint_cycle_start(complaint, db)

            active_pause = 0
            if complaint.resolution_pause_started_at:
                p_start = complaint.resolution_pause_started_at
                if p_start.tzinfo is None:
                    p_start = p_start.replace(tzinfo=timezone.utc)
                active_pause = max(0, int((now_utc - p_start).total_seconds()))

            total_pause = complaint.resolution_pause_duration_seconds + active_pause
            complaint.resolution_deadline = cycle_start + timedelta(seconds=res_target_seconds + total_pause)

            effective_elapsed = max(
                0,
                int((now_utc - cycle_start).total_seconds()) - total_pause,
            )
            complaint.resolution_escalation_level = calculate_escalation_level(
                effective_elapsed, res_target_seconds, is_resolution=True
            )

    complaint.last_sla_evaluated_at = now_utc

    # 4. Record audit history if escalation changed and actor is provided
    if actor is not None and (prev_resp_esc != complaint.response_escalation_level or prev_res_esc != complaint.resolution_escalation_level):
        from app.models.status_history import ComplaintStatusHistory
        history_entry = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_id=actor.id,
            previous_status=complaint.status,
            new_status=complaint.status,
            remarks=(
                f"SLA Escalation adjusted: Response [{prev_resp_esc} -> {complaint.response_escalation_level}], "
                f"Resolution [{prev_res_esc} -> {complaint.resolution_escalation_level}]. "
                f"Reason: {audit_reason or 'SLA Policy re-evaluation'}"
            ),
            created_at=now_utc,
        )
        db.add(history_entry)

    # 5. In-App Notification Dispatch when escalation level increases (Phase 6.4)
    if complaint.response_escalation_level > prev_resp_esc:
        from app.services.notification_service import notify_sla_escalation
        notify_sla_escalation(
            db=db,
            complaint=complaint,
            clock_type="response",
            prev_level=prev_resp_esc,
            new_level=complaint.response_escalation_level,
            actor=actor,
        )

    if complaint.resolution_escalation_level > prev_res_esc:
        from app.services.notification_service import notify_sla_escalation
        notify_sla_escalation(
            db=db,
            complaint=complaint,
            clock_type="resolution",
            prev_level=prev_res_esc,
            new_level=complaint.resolution_escalation_level,
            actor=actor,
        )

    return prev_resp_esc, complaint.response_escalation_level, prev_res_esc, complaint.resolution_escalation_level


# =============================================================================
# Lifecycle Hooks for Dual Clocks & History Snapshots
# =============================================================================

def on_complaint_created_sla_init(
    db: Session,
    complaint: Complaint,
    created_at: datetime,
) -> None:
    """
    Initialize dual SLA clocks and targets for a newly created complaint.
    """
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
    if policy:
        complaint.response_sla_policy_id = policy.id
        complaint.response_deadline = created_at + timedelta(hours=policy.response_time_hours)
        complaint.resolution_sla_policy_id = policy.id
        complaint.resolution_deadline = created_at + timedelta(hours=policy.resolution_time_hours)

    complaint.response_pause_duration_seconds = 0
    complaint.resolution_pause_duration_seconds = 0
    complaint.response_escalation_level = 0
    complaint.resolution_escalation_level = 0
    complaint.sla_cycle_number = 1
    complaint.last_sla_evaluated_at = created_at


def snapshot_sla_cycle_history(
    db: Session,
    complaint: Complaint,
    end_reason: str,
    ended_at: datetime,
) -> ComplaintSLAHistory | None:
    """
    Create an immutable snapshot of the current SLA cycle in complaint_sla_history.
    Idempotent: will not re-insert if a history record for (complaint_id, cycle_number) already exists.
    """
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=timezone.utc)

    # Check for existing history record for this cycle
    existing = (
        db.query(ComplaintSLAHistory)
        .filter(
            ComplaintSLAHistory.complaint_id == complaint.id,
            ComplaintSLAHistory.cycle_number == complaint.sla_cycle_number,
        )
        .first()
    )
    if existing:
        return existing

    policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
    cycle_start = get_complaint_cycle_start(complaint, db)

    # Calculate actual elapsed response seconds
    actual_resp_seconds = None
    resp_breached = None
    resp_target_seconds = None
    resp_policy = complaint.response_sla_policy or policy
    if complaint.responded_at:
        resp_at = complaint.responded_at
        if resp_at.tzinfo is None:
            resp_at = resp_at.replace(tzinfo=timezone.utc)
        created_at = complaint.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        actual_resp_seconds = max(
            0,
            int((resp_at - created_at).total_seconds()) - complaint.response_pause_duration_seconds,
        )
        if resp_policy:
            resp_target_seconds = resp_policy.response_time_hours * 3600
            resp_breached = actual_resp_seconds > resp_target_seconds

    # Calculate actual elapsed resolution seconds
    actual_res_seconds = None
    res_breached = None
    res_target_seconds = None
    res_policy = complaint.resolution_sla_policy or policy
    stop_time = complaint.resolved_at or ended_at
    if stop_time is not None:
        if stop_time.tzinfo is None:
            stop_time = stop_time.replace(tzinfo=timezone.utc)
        actual_res_seconds = max(
            0,
            int((stop_time - cycle_start).total_seconds()) - complaint.resolution_pause_duration_seconds,
        )
        if res_policy:
            res_target_seconds = res_policy.resolution_time_hours * 3600
            if complaint.resolved_at is not None:
                # Successfully resolved at RESOLVED_AWAITING_VERIFICATION
                res_breached = actual_res_seconds > res_target_seconds
            else:
                # Terminated prior to resolution (REJECTED, DUPLICATE).
                # Do NOT mark resolution SLA as successfully completed/met.
                # If elapsed time exceeded target before termination, it is marked as breached (True).
                # If terminated within target duration, it was NOT resolved; set None (never False).
                res_breached = True if actual_res_seconds > res_target_seconds else None

    policy_to_snapshot = res_policy or resp_policy or policy
    policy_snapshot = None
    if policy_to_snapshot:
        policy_snapshot = {
            "policy_id": str(policy_to_snapshot.id),
            "name": policy_to_snapshot.name,
            "response_time_hours": resp_policy.response_time_hours if resp_policy else policy_to_snapshot.response_time_hours,
            "resolution_time_hours": policy_to_snapshot.resolution_time_hours,
            "category_id": policy_to_snapshot.category_id,
            "priority": policy_to_snapshot.priority.value if policy_to_snapshot.priority else None,
        }

    history = ComplaintSLAHistory(
        complaint_id=complaint.id,
        cycle_number=complaint.sla_cycle_number,
        policy_id=policy_to_snapshot.id if policy_to_snapshot else None,
        policy_name=policy_to_snapshot.name if policy_to_snapshot else None,
        policy_snapshot=policy_snapshot,
        response_target_seconds=resp_target_seconds,
        resolution_target_seconds=res_target_seconds,
        actual_response_seconds=actual_resp_seconds,
        actual_resolution_seconds=actual_res_seconds,
        response_breached=resp_breached,
        resolution_breached=res_breached,
        response_escalation_level=complaint.response_escalation_level,
        resolution_escalation_level=complaint.resolution_escalation_level,
        cycle_started_at=cycle_start,
        cycle_ended_at=ended_at,
        end_reason=end_reason,
    )
    db.add(history)
    db.flush()
    return history


def on_complaint_status_transition_sla_update(
    db: Session,
    complaint: Complaint,
    previous_status: ComplaintStatus,
    new_status: ComplaintStatus,
    now_utc: datetime,
    actor: User | None = None,
) -> None:
    """
    Synchronously update dual clocks, pauses, and SLA cycle snapshots on complaint state machine transitions.

    Rules:
        - SUBMITTED -> UNDER_REVIEW: stops Response clock (responded_at = now_utc).
        - SUBMITTED -> REJECTED / DUPLICATE: stops Response clock and snapshots terminal cycle.
        - -> ON_HOLD: pauses active (uncompleted) clocks and records pause start timestamps.
        - ON_HOLD -> ...: resumes active clocks, accumulates pause duration, clears pause start timestamps,
                          and extends effective deadlines.
        - IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION: stops Resolution clock (resolved_at = now_utc).
        - -> CLOSED: snapshots completed SLA cycle with end_reason = "RESOLVED".
        - RESOLVED_AWAITING_VERIFICATION / CLOSED -> REOPENED:
            1. Snapshots previous cycle with end_reason = "REOPENED" (if not already snapshotted).
            2. Clears complaint.resolved_at = None for the new cycle.
            3. Increments cycle_number.
            4. Preserves completed response clock.
            5. Resets resolution pause/escalation counters and sets fresh resolution deadline.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # 1. Response clock completion: SUBMITTED -> UNDER_REVIEW
    if previous_status == ComplaintStatus.SUBMITTED and new_status == ComplaintStatus.UNDER_REVIEW:
        if complaint.responded_at is None:
            complaint.responded_at = now_utc
            policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
            if policy:
                resp_target_seconds = policy.response_time_hours * 3600
                created_at = complaint.created_at.replace(tzinfo=timezone.utc) if complaint.created_at.tzinfo is None else complaint.created_at
                effective_elapsed = max(0, int((now_utc - created_at).total_seconds()) - complaint.response_pause_duration_seconds)
                complaint.response_escalation_level = calculate_escalation_level(effective_elapsed, resp_target_seconds, is_resolution=False)

    # 2. Terminal transitions directly from SUBMITTED: stops response clock
    if previous_status == ComplaintStatus.SUBMITTED and new_status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
        if complaint.responded_at is None:
            complaint.responded_at = now_utc
            policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
            if policy:
                resp_target_seconds = policy.response_time_hours * 3600
                created_at = complaint.created_at.replace(tzinfo=timezone.utc) if complaint.created_at.tzinfo is None else complaint.created_at
                effective_elapsed = max(0, int((now_utc - created_at).total_seconds()) - complaint.response_pause_duration_seconds)
                complaint.response_escalation_level = calculate_escalation_level(effective_elapsed, resp_target_seconds, is_resolution=False)

    # 3. Entering ON_HOLD
    if new_status == ComplaintStatus.ON_HOLD:
        # Pause response clock only if active
        if complaint.responded_at is None and complaint.response_pause_started_at is None:
            complaint.response_pause_started_at = now_utc
        # Pause resolution clock only if active
        if complaint.resolved_at is None and complaint.resolution_pause_started_at is None:
            complaint.resolution_pause_started_at = now_utc

    # 4. Exiting ON_HOLD
    if previous_status == ComplaintStatus.ON_HOLD and new_status != ComplaintStatus.ON_HOLD:
        # Resume response clock if it was paused
        if complaint.response_pause_started_at is not None:
            p_start = complaint.response_pause_started_at
            if p_start.tzinfo is None:
                p_start = p_start.replace(tzinfo=timezone.utc)
            pause_sec = max(0, int((now_utc - p_start).total_seconds()))
            complaint.response_pause_duration_seconds += pause_sec
            complaint.response_pause_started_at = None
            if complaint.response_deadline is not None:
                complaint.response_deadline += timedelta(seconds=pause_sec)

        # Resume resolution clock if it was paused
        if complaint.resolution_pause_started_at is not None:
            p_start = complaint.resolution_pause_started_at
            if p_start.tzinfo is None:
                p_start = p_start.replace(tzinfo=timezone.utc)
            pause_sec = max(0, int((now_utc - p_start).total_seconds()))
            complaint.resolution_pause_duration_seconds += pause_sec
            complaint.resolution_pause_started_at = None
            if complaint.resolution_deadline is not None:
                complaint.resolution_deadline += timedelta(seconds=pause_sec)

    # 5. IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION: stops resolution clock
    if previous_status == ComplaintStatus.IN_PROGRESS and new_status == ComplaintStatus.RESOLVED_AWAITING_VERIFICATION:
        if complaint.resolved_at is None:
            complaint.resolved_at = now_utc
            policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
            if policy:
                res_target_seconds = policy.resolution_time_hours * 3600
                cycle_start = get_complaint_cycle_start(complaint, db)
                effective_elapsed = max(0, int((now_utc - cycle_start).total_seconds()) - complaint.resolution_pause_duration_seconds)
                complaint.resolution_escalation_level = calculate_escalation_level(effective_elapsed, res_target_seconds, is_resolution=True)

    # 6. Terminal states snapshotting
    if new_status == ComplaintStatus.CLOSED:
        snapshot_sla_cycle_history(db, complaint, end_reason="RESOLVED", ended_at=now_utc)
    elif new_status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
        snapshot_sla_cycle_history(db, complaint, end_reason=new_status.value, ended_at=now_utc)

    # 7. Reopening: start fresh resolution cycle
    if new_status == ComplaintStatus.REOPENED:
        # 1. Snapshot previous cycle if not yet snapshotted
        snapshot_sla_cycle_history(db, complaint, end_reason="REOPENED", ended_at=now_utc)

        # 2. Reset resolution clock state for the new cycle
        complaint.resolved_at = None
        complaint.sla_cycle_number += 1
        complaint.resolution_pause_duration_seconds = 0
        complaint.resolution_pause_started_at = None
        complaint.resolution_escalation_level = 0

        # 3. Preserve response clock (responded_at and response_pause_duration remain intact)

        # 4. Start new resolution deadline from reopening timestamp
        policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
        if policy:
            complaint.resolution_sla_policy_id = policy.id
            complaint.resolution_deadline = now_utc + timedelta(hours=policy.resolution_time_hours)
        else:
            complaint.resolution_sla_policy_id = None
            complaint.resolution_deadline = None

    # Evaluate SLA to update current escalation levels
    evaluate_complaint_sla(db, complaint, now_utc, actor=actor)


# =============================================================================
# Bounded On-Demand Batch SLA Evaluation Service
# =============================================================================

def evaluate_sla_batch(
    db: Session,
    filters: SLAEvaluationFilterRequest,
    admin_user: User | None = None,
) -> SLAEvaluationBatchResponse:
    """
    On-demand bounded batch evaluation of complaints with optional scoping filters.
    Bounded between 1 and 200 items per request to protect database throughput.
    """
    now_utc = datetime.now(timezone.utc)
    query = db.query(Complaint).with_for_update(of=Complaint)

    if filters.complaint_id is not None:
        query = query.filter(Complaint.id == filters.complaint_id)
    if filters.status is not None:
        query = query.filter(Complaint.status == filters.status)
    if filters.priority is not None:
        query = query.filter(Complaint.priority == filters.priority)
    if filters.category_id is not None:
        query = query.filter(Complaint.category_id == filters.category_id)
    if filters.department_id is not None:
        query = query.join(Complaint.category).filter(Category.department_id == filters.department_id)

    # By default, do not evaluate closed/rejected/duplicate unless specifically requested
    if filters.status is None and filters.complaint_id is None:
        query = query.filter(
            Complaint.status.notin_([ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE, ComplaintStatus.CLOSED])
        )

    # Bounded batch size
    batch_limit = min(max(1, filters.limit), 200)
    complaints = query.order_by(Complaint.created_at.asc()).limit(batch_limit).all()

    results: list[SLAEvaluationItemResult] = []
    escalated_count = 0

    for c in complaints:
        p_resp, n_resp, p_res, n_res = evaluate_complaint_sla(
            db,
            c,
            now_utc,
            actor=admin_user,
            audit_reason="Batch on-demand evaluation",
        )
        is_escalated = (n_resp > p_resp) or (n_res > p_res)
        if is_escalated:
            escalated_count += 1

        results.append(
            SLAEvaluationItemResult(
                complaint_id=c.id,
                complaint_number=c.complaint_number,
                previous_response_escalation=p_resp,
                new_response_escalation=n_resp,
                previous_resolution_escalation=p_res,
                new_resolution_escalation=n_res,
                evaluated_at=now_utc,
                escalated=is_escalated,
            )
        )

    db.commit()

    return SLAEvaluationBatchResponse(
        evaluated_count=len(results),
        escalated_count=escalated_count,
        results=results,
    )


# =============================================================================
# Complaint SLA Detail & History Retrieval
# =============================================================================

def get_complaint_sla_details(
    db: Session,
    complaint_id: uuid.UUID,
    user: User,
) -> ComplaintSLADetailResponse:
    """
    Retrieve comprehensive SLA status for a complaint. Enforces Administrator RBAC.
    """
    if user.role.name != UserRole.ADMINISTRATOR.value:
        raise AuthorizationError("Only administrators may access complaint SLA performance details")

    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    # Evaluate dynamically to present latest accurate status
    now_utc = datetime.now(timezone.utc)
    evaluate_complaint_sla(db, complaint, now_utc)
    db.commit()

    policy = resolve_sla_policy(db, complaint.category_id, complaint.priority)
    resp_breached = False
    if complaint.responded_at and complaint.response_deadline:
        resp_breached = complaint.responded_at > complaint.response_deadline
    elif complaint.status not in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE, ComplaintStatus.CLOSED}:
        if complaint.response_deadline and now_utc > complaint.response_deadline:
            resp_breached = True

    res_breached = False
    if complaint.resolved_at and complaint.resolution_deadline:
        res_breached = complaint.resolved_at > complaint.resolution_deadline
    elif complaint.status not in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE, ComplaintStatus.CLOSED}:
        if complaint.resolution_deadline and now_utc > complaint.resolution_deadline:
            res_breached = True
    elif complaint.status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
        history = (
            db.query(ComplaintSLAHistory)
            .filter(
                ComplaintSLAHistory.complaint_id == complaint.id,
                ComplaintSLAHistory.cycle_number == complaint.sla_cycle_number,
            )
            .first()
        )
        if history and history.resolution_breached is True:
            res_breached = True

    return ComplaintSLADetailResponse(
        complaint_id=complaint.id,
        complaint_number=complaint.complaint_number,
        status=complaint.status,
        priority=complaint.priority,
        category_id=complaint.category_id,
        created_at=complaint.created_at,
        sla_cycle_number=complaint.sla_cycle_number,
        response_sla_policy_id=complaint.response_sla_policy_id,
        response_deadline=complaint.response_deadline,
        responded_at=complaint.responded_at,
        response_pause_duration_seconds=complaint.response_pause_duration_seconds,
        response_pause_started_at=complaint.response_pause_started_at,
        response_escalation_level=complaint.response_escalation_level,
        response_breached=resp_breached,
        resolution_sla_policy_id=complaint.resolution_sla_policy_id,
        resolution_deadline=complaint.resolution_deadline,
        resolved_at=complaint.resolved_at,
        resolution_pause_duration_seconds=complaint.resolution_pause_duration_seconds,
        resolution_pause_started_at=complaint.resolution_pause_started_at,
        resolution_escalation_level=complaint.resolution_escalation_level,
        resolution_breached=res_breached,
        last_sla_evaluated_at=complaint.last_sla_evaluated_at,
    )


def get_complaint_sla_history_records(
    db: Session,
    complaint_id: uuid.UUID,
    user: User,
) -> list[ComplaintSLAHistory]:
    """
    Retrieve all immutable completed cycle history records for a complaint. Enforces Administrator RBAC.
    """
    if user.role.name != UserRole.ADMINISTRATOR.value:
        raise AuthorizationError("Only administrators may access complaint SLA cycle history")

    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    return (
        db.query(ComplaintSLAHistory)
        .filter(ComplaintSLAHistory.complaint_id == complaint_id)
        .order_by(ComplaintSLAHistory.cycle_number.asc())
        .all()
    )
