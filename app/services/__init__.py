"""
CivicPulse Services Package

Exports application business logic and domain services.
"""

from app.services.assignment_service import (
    accept_assignment,
    add_assignment_progress,
    assign_complaint,
    complete_assignment,
    get_assignment_by_id,
    get_complaint_assignments,
    get_worker_task_by_id,
    get_worker_tasks,
    list_assignments,
    reassign_complaint,
    start_assignment,
)
from app.services.auth_service import (
    authenticate_user,
    generate_auth_token,
    get_role_by_name,
    init_roles,
    register_citizen,
)
from app.services.category_service import (
    get_active_categories,
    get_category_by_id,
    init_categories,
)
from app.services.complaint_service import (
    create_complaint,
    execute_transition,
    generate_complaint_number,
    get_complaint_by_id,
    get_complaint_history,
    list_complaints,
    review_complaint,
)
from app.services.department_service import (
    create_department,
    deactivate_department,
    get_department_by_id,
    list_departments,
    update_department,
)
from app.services.worker_service import (
    create_worker,
    deactivate_worker,
    get_worker_by_id,
    get_worker_by_user_id,
    list_workers,
    update_worker,
)

__all__ = [
    "init_roles",
    "get_role_by_name",
    "register_citizen",
    "authenticate_user",
    "generate_auth_token",
    "init_categories",
    "get_active_categories",
    "get_category_by_id",
    "generate_complaint_number",
    "create_complaint",
    "get_complaint_by_id",
    "get_complaint_history",
    "list_complaints",
    "execute_transition",
    "review_complaint",
    "list_departments",
    "get_department_by_id",
    "create_department",
    "update_department",
    "deactivate_department",
    "create_worker",
    "get_worker_by_id",
    "get_worker_by_user_id",
    "list_workers",
    "update_worker",
    "deactivate_worker",
    "assign_complaint",
    "accept_assignment",
    "start_assignment",
    "add_assignment_progress",
    "complete_assignment",
    "reassign_complaint",
    "get_worker_tasks",
    "get_worker_task_by_id",
    "list_assignments",
    "get_assignment_by_id",
    "get_complaint_assignments",
]
