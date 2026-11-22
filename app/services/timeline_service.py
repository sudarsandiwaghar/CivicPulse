"""
CivicPulse Unified Complaint Timeline Service

Normalizes audit records from complaints, status history, assignments,
and progress updates into a consolidated chronological narrative.

Security & Authorization:
    - CITIZEN Author: Can view timeline; internal remarks and private dispatch notes are redacted.
    - Non-author CITIZEN: Blocked with 403 Forbidden.
    - FIELD WORKER: Only allowed if assigned to complaint; previously assigned workers
      have events bounded to their assignment duration.
    - ADMINISTRATOR: Unrestricted access to all public and internal events and remarks.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.constants import AssignmentStatus, ComplaintStatus, UserRole
from app.core.exceptions import AuthorizationError, EntityNotFoundError
from app.models.assignment import Assignment
from app.models.complaint import Complaint
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.models.worker import Worker
from app.schemas.timeline import TimelineEventType


def _ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime object is timezone-aware UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_complaint_timeline(
    db: Session,
    complaint_id: uuid.UUID,
    user: User,
) -> dict[str, Any]:
    """
    Retrieve and construct the unified chronological timeline for a complaint.

    Validates:
        1. Complaint existence (404 if missing).
        2. Role-based authorization and ownership scoping (403 if unauthorized).
        3. Redaction of internal administrative remarks and dispatch notes for citizens.
        4. Bounded timeline access for previously assigned workers.

    Args:
        db: Active database session.
        complaint_id: Target complaint UUID.
        user: Authenticated user making the request.

    Returns:
        Structured dictionary matching ComplaintTimelineData schema.
    """
    # 1. Retrieve complaint with eager relationships
    complaint = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.citizen),
            joinedload(Complaint.category),
            joinedload(Complaint.status_history),
            joinedload(Complaint.assignments).joinedload(Assignment.progress_updates),
            joinedload(Complaint.assignments).joinedload(Assignment.worker).joinedload(Worker.user),
            joinedload(Complaint.assignments).joinedload(Assignment.worker).joinedload(Worker.department),
        )
        .filter(Complaint.id == complaint_id)
        .first()
    )

    if not complaint:
        raise EntityNotFoundError("Complaint", complaint_id)

    user_role = user.role.name
    is_citizen = user_role == UserRole.CITIZEN.value
    is_admin = user_role == UserRole.ADMINISTRATOR.value
    is_worker = user_role == UserRole.FIELD_WORKER.value

    # 2. Authorization Scoping
    if is_citizen:
        if complaint.citizen_id != user.id:
            raise AuthorizationError("You do not have permission to access this complaint's timeline")

    worker_permitted_windows: list[tuple[datetime, datetime]] | None = None
    user_assignments: list[Assignment] = []
    if is_worker:
        user_assignments = [
            a for a in complaint.assignments if a.worker and a.worker.user_id == user.id
        ]
        if not user_assignments:
            raise AuthorizationError("You are not assigned to this complaint")

        # Sort all assignments chronologically to identify initial assignment
        all_complaint_assignments = sorted(
            complaint.assignments, key=lambda a: _ensure_utc(a.assigned_at)
        )
        initial_asgn_time = (
            _ensure_utc(all_complaint_assignments[0].assigned_at)
            if all_complaint_assignments
            else None
        )

        windows: list[tuple[datetime, datetime]] = []
        for a in user_assignments:
            # Determine window start:
            # Initial assignment spans from complaint inception to boundary.
            # Subsequent assignments span from assigned_at to boundary.
            is_initial = (
                initial_asgn_time is not None
                and _ensure_utc(a.assigned_at) == initial_asgn_time
            )
            if is_initial:
                start_time = _ensure_utc(complaint.created_at)
            else:
                start_time = _ensure_utc(a.assigned_at)

            # Determine window end:
            if a.status in {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}:
                # Active assignment: open-ended access
                end_time = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            elif a.status == AssignmentStatus.COMPLETED or a.completed_at is not None:
                # Completed assignment: must have verified completed_at
                if a.completed_at is not None:
                    end_time = _ensure_utc(a.completed_at)
                else:
                    raise AuthorizationError(
                        "Cannot reliably establish assignment boundary for historical access"
                    )
            elif a.status == AssignmentStatus.REASSIGNED:
                # Reassigned assignment: MUST be verified through an authentic reassignment
                # progress marker correlated with an administrative replacement assignment.
                replacement_assignments = [
                    r
                    for r in complaint.assignments
                    if r.id != a.id and _ensure_utc(r.assigned_at) >= _ensure_utc(a.assigned_at)
                ]
                if not replacement_assignments:
                    # No replacement assignment exists -> unverified reassignment
                    raise AuthorizationError(
                        "Cannot reliably establish assignment boundary for historical access"
                    )

                verified_reassign_times = []
                for p in a.progress_updates:
                    if p.description and p.description.startswith("Reassigned to "):
                        p_time = _ensure_utc(p.created_at)
                        for repl in replacement_assignments:
                            repl_time = _ensure_utc(repl.assigned_at)
                            if abs((p_time - repl_time).total_seconds()) <= 5.0:
                                verified_reassign_times.append(p_time)
                                break

                if verified_reassign_times:
                    end_time = max(verified_reassign_times)
                else:
                    # Unreliable or missing marker: do NOT fall back to activity timestamps
                    raise AuthorizationError(
                        "Cannot reliably establish assignment boundary for historical access"
                    )
            else:
                raise AuthorizationError(
                    "Cannot reliably establish assignment boundary for historical access"
                )

            windows.append((start_time, end_time))

        if not windows:
            raise AuthorizationError(
                "Cannot reliably establish assignment boundary for historical access"
            )

        worker_permitted_windows = windows

    # 3. Extract and normalize events
    events: list[dict[str, Any]] = []

    # Milestone 1: Complaint Submission
    sub_actor_name = "You" if is_citizen else (complaint.citizen.full_name if complaint.citizen else "Citizen")
    events.append(
        {
            "id": f"sub_{complaint.id}",
            "event_type": TimelineEventType.COMPLAINT_SUBMITTED.value,
            "title": "Complaint Submitted",
            "description": f"Complaint '{complaint.title}' was submitted.",
            "timestamp": _ensure_utc(complaint.created_at),
            "actor": {
                "id": complaint.citizen_id if is_admin else None,
                "role": UserRole.CITIZEN.value,
                "name": sub_actor_name,
            },
            "remarks": None,
            "metadata": {
                "complaint_number": complaint.complaint_number,
                "category": complaint.category.name if complaint.category else "Unknown",
                "priority": complaint.priority.value,
            },
        }
    )

    # Milestone 2: Status Transitions
    for h in complaint.status_history:
        # Avoid duplicate submission milestone
        if h.previous_status is None and h.new_status == ComplaintStatus.SUBMITTED:
            continue

        h_time = _ensure_utc(h.created_at)

        # Determine display title and safe description
        status_titles = {
            ComplaintStatus.UNDER_REVIEW: ("Complaint Under Review", "Complaint has been acknowledged and is under review by municipal administration."),
            ComplaintStatus.ASSIGNED: ("Complaint Assigned", "Complaint assigned to field response team."),
            ComplaintStatus.IN_PROGRESS: ("Work In Progress", "Field technician initiated investigation and remediation work."),
            ComplaintStatus.ON_HOLD: ("Complaint Placed On Hold", "Complaint temporarily placed on hold."),
            ComplaintStatus.RESOLVED_AWAITING_VERIFICATION: (
                "Resolution Submitted",
                "Field technician marked work as resolved. Awaiting citizen verification.",
            ),
            ComplaintStatus.CLOSED: ("Complaint Closed", "Complaint has been verified and successfully closed."),
            ComplaintStatus.REOPENED: ("Complaint Reopened", "Complaint has been reopened for further remediation."),
            ComplaintStatus.REJECTED: ("Complaint Rejected", "Complaint was reviewed and deemed ineligible or out of scope."),
            ComplaintStatus.DUPLICATE: ("Complaint Marked as Duplicate", "Complaint was identified as a duplicate of an existing report."),
        }

        title, desc = status_titles.get(
            h.new_status,
            (f"Status changed to {h.new_status.value}", f"Complaint status transitioned to {h.new_status.value}."),
        )

        event_type = TimelineEventType.STATUS_TRANSITION.value
        if h.new_status == ComplaintStatus.CLOSED:
            event_type = TimelineEventType.COMPLAINT_CLOSED.value
        elif h.new_status == ComplaintStatus.REOPENED:
            event_type = TimelineEventType.COMPLAINT_REOPENED.value

        # Actor formatting
        actor_role = h.changed_by.role.name if h.changed_by and h.changed_by.role else "SYSTEM"
        if is_citizen:
            if h.changed_by_id == user.id:
                actor_name = "You"
            elif actor_role == UserRole.ADMINISTRATOR.value:
                actor_name = "Administration"
            elif actor_role == UserRole.FIELD_WORKER.value:
                actor_name = "Field Technician"
            else:
                actor_name = "System"
            actor_id = None
        else:
            actor_name = h.changed_by.full_name if h.changed_by else "System"
            actor_id = h.changed_by_id if is_admin else None

        # Privacy Redaction for Remarks:
        # 1. Citizens must not see administrative remarks by default.
        # 2. REJECTED and DUPLICATE remarks must be redacted for citizens.
        # 3. Citizen-authored remarks may be shown only when the actor identity
        #    reliably proves that the remark was authored by the complaint owner.
        # 4. If authorship or visibility cannot be established reliably, return remarks = None.
        # 5. Administrators retain access to complete remarks.
        # 6. Worker visibility follows operational authorization rules.
        if is_citizen:
            if h.new_status in {ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE}:
                remarks = None
            elif (
                h.changed_by_id is not None
                and h.changed_by_id == user.id
                and user.id == complaint.citizen_id
            ):
                remarks = h.remarks
            else:
                remarks = None
        elif is_admin:
            remarks = h.remarks
        elif is_worker:
            if h.changed_by_id is not None and h.changed_by_id == user.id:
                # Worker authored this remark (e.g. resolution summary, work initiated note)
                remarks = h.remarks
            elif h.new_status == ComplaintStatus.ASSIGNED and h.remarks:
                # System dispatch remarks designating this field worker
                is_worker_dispatch = any(
                    a.worker
                    and (
                        (a.worker.employee_id and a.worker.employee_id in h.remarks)
                        or (
                            a.worker.user
                            and a.worker.user.full_name
                            and a.worker.user.full_name in h.remarks
                        )
                    )
                    for a in user_assignments
                )
                remarks = h.remarks if is_worker_dispatch else None
            else:
                # Redact all internal administrative deliberations, triage remarks,
                # hold notes, rejection notes, duplicate notes, and supervisor commentary
                remarks = None
        else:
            remarks = None

        events.append(
            {
                "id": f"stat_{h.id}",
                "event_type": event_type,
                "title": title,
                "description": desc,
                "timestamp": h_time,
                "actor": {
                    "id": actor_id,
                    "role": actor_role,
                    "name": actor_name,
                },
                "remarks": remarks,
                "metadata": {
                    "previous_status": h.previous_status.value if h.previous_status else None,
                    "new_status": h.new_status.value,
                },
            }
        )

    # Milestone 3: Assignments & Progress Milestones
    for a in complaint.assignments:
        # Assignment Created / Reassigned
        asgn_created_time = _ensure_utc(a.assigned_at)
        is_reassignment = a.status == AssignmentStatus.REASSIGNED or "Reassigned" in (a.notes or "")
        asgn_title = "Complaint Reassigned" if is_reassignment else "Technician Assigned"
        asgn_desc = (
            "Complaint reassigned to replacement field worker."
            if is_reassignment
            else f"Assigned to {a.worker.designation or 'field technician'} from {a.worker.department.name if a.worker and a.worker.department else 'department'}."
        )

        # Notes redaction: private dispatch instructions never exposed to citizens
        if is_citizen:
            asgn_notes = None
        elif is_admin:
            asgn_notes = a.notes
        elif is_worker:
            # Worker only sees dispatch notes if assigned to this specific assignment
            if a.worker and a.worker.user_id == user.id:
                asgn_notes = a.notes
            else:
                asgn_notes = None
        else:
            asgn_notes = None

        asgn_actor_name = "Administration" if is_citizen else (a.assigned_by.full_name if a.assigned_by else "Admin")
        events.append(
            {
                "id": f"asgn_create_{a.id}",
                "event_type": TimelineEventType.ASSIGNMENT_CREATED.value,
                "title": asgn_title,
                "description": asgn_desc,
                "timestamp": asgn_created_time,
                "actor": {
                    "id": a.assigned_by_id if is_admin else None,
                    "role": UserRole.ADMINISTRATOR.value,
                    "name": asgn_actor_name,
                },
                "remarks": asgn_notes,
                "metadata": {
                    "assignment_id": str(a.id) if (is_admin or is_worker) else None,
                    "assignment_status": a.status.value,
                },
            }
        )

        # Assignment Acknowledged
        if a.accepted_at:
            events.append(
                {
                    "id": f"asgn_accept_{a.id}",
                    "event_type": TimelineEventType.ASSIGNMENT_ACCEPTED.value,
                    "title": "Assignment Acknowledged",
                    "description": "Field technician acknowledged and accepted the assignment.",
                    "timestamp": _ensure_utc(a.accepted_at),
                    "actor": {
                        "id": a.worker.user_id if is_admin else None,
                        "role": UserRole.FIELD_WORKER.value,
                        "name": "Field Technician" if is_citizen else (a.worker.user.full_name if a.worker and a.worker.user else "Worker"),
                    },
                    "remarks": None,
                    "metadata": {},
                }
            )

        # Work Started
        if a.started_at:
            events.append(
                {
                    "id": f"asgn_start_{a.id}",
                    "event_type": TimelineEventType.WORK_STARTED.value,
                    "title": "Work Initiated On Site",
                    "description": "Field technician initiated investigation and remediation work on site.",
                    "timestamp": _ensure_utc(a.started_at),
                    "actor": {
                        "id": a.worker.user_id if is_admin else None,
                        "role": UserRole.FIELD_WORKER.value,
                        "name": "Field Technician" if is_citizen else (a.worker.user.full_name if a.worker and a.worker.user else "Worker"),
                    },
                    "remarks": None,
                    "metadata": {},
                }
            )

        # Progress Updates
        for p in a.progress_updates:
            prog_actor_name = "Field Technician" if is_citizen else (a.worker.user.full_name if a.worker and a.worker.user else "Worker")
            events.append(
                {
                    "id": f"prog_{p.id}",
                    "event_type": TimelineEventType.PROGRESS_UPDATE.value,
                    "title": "Field Progress Update",
                    "description": p.description,
                    "timestamp": _ensure_utc(p.created_at),
                    "actor": {
                        "id": p.worker_id if is_admin else None,
                        "role": UserRole.FIELD_WORKER.value,
                        "name": prog_actor_name,
                    },
                    "remarks": None,
                    "metadata": {},
                }
            )

        # Work Completed
        if a.completed_at:
            events.append(
                {
                    "id": f"asgn_comp_{a.id}",
                    "event_type": TimelineEventType.WORK_COMPLETED.value,
                    "title": "Field Work Completed",
                    "description": "Technician marked field assignment work as completed.",
                    "timestamp": _ensure_utc(a.completed_at),
                    "actor": {
                        "id": a.worker.user_id if is_admin else None,
                        "role": UserRole.FIELD_WORKER.value,
                        "name": "Field Technician" if is_citizen else (a.worker.user.full_name if a.worker and a.worker.user else "Worker"),
                    },
                    "remarks": None,
                    "metadata": {},
                }
            )

    # 4. Filter events for field worker by permitted access windows
    if is_worker and worker_permitted_windows is not None:
        events = [
            e
            for e in events
            if any(w_start <= e["timestamp"] <= w_end for w_start, w_end in worker_permitted_windows)
        ]

    # 5. Chronological Sort (ASC)
    events.sort(key=lambda e: e["timestamp"])

    return {
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "current_status": complaint.status,
        "events": events,
    }
