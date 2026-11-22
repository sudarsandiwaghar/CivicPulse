"""
CivicPulse Field Worker Service

Implements business logic for field worker account provisioning, profile management,
availability tracking, and department association.
"""

import uuid
from sqlalchemy.orm import Session

from app.core.constants import UserRole
from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from app.core.security import hash_password
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.models.worker import Worker
from app.schemas.common import PaginationParams
from app.schemas.worker import WorkerCreateRequest, WorkerUpdateRequest


def create_worker(
    db: Session,
    data: WorkerCreateRequest,
) -> Worker:
    """
    Atomically provision a field worker: creates User account and Worker profile.

    Guarantees:
        - Email is unique in users.
        - Employee ID is unique in workers.
        - Assigned department exists and is active.
        - User role is bound to FIELD_WORKER.
        - Password is securely hashed using bcrypt.
        - User and Worker are persisted in a single transaction.
    """
    # 1. Normalize and validate email
    normalized_email = data.email.strip().lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise EntityAlreadyExistsError("User", "email", normalized_email)

    # 2. Check employee ID uniqueness
    employee_id = data.employee_id.strip().upper()
    existing_worker = db.query(Worker).filter(Worker.employee_id == employee_id).first()
    if existing_worker:
        raise EntityAlreadyExistsError("Worker", "employee_id", employee_id)

    # 3. Validate department existence and activity
    department = db.query(Department).filter(Department.id == data.department_id).first()
    if not department:
        raise EntityNotFoundError("Department", data.department_id)
    if not department.is_active:
        raise BusinessRuleViolationError(
            f"Department '{department.name}' is inactive and cannot receive new workers"
        )

    # 4. Resolve FIELD_WORKER role
    worker_role = db.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
    if not worker_role:
        raise EntityNotFoundError("Role", UserRole.FIELD_WORKER.value)

    # 5. Create base User account
    user = User(
        email=normalized_email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        phone_number=data.phone_number.strip() if data.phone_number else None,
        role_id=worker_role.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    # 6. Create Worker profile linked 1-to-1 with User
    worker = Worker(
        user_id=user.id,
        department_id=department.id,
        employee_id=employee_id,
        designation=data.designation.strip() if data.designation else None,
        is_available=True,
        employment_status="ACTIVE",
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def get_worker_by_id(db: Session, worker_id: uuid.UUID) -> Worker:
    """
    Retrieve single field worker profile by worker UUID.
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise EntityNotFoundError("Worker", worker_id)
    return worker


def get_worker_by_user_id(db: Session, user_id: uuid.UUID) -> Worker:
    """
    Retrieve worker profile associated with a User UUID.
    """
    worker = db.query(Worker).filter(Worker.user_id == user_id).first()
    if not worker:
        raise EntityNotFoundError("Worker profile for user", user_id)
    return worker


def list_workers(
    db: Session,
    department_id: int | None = None,
    is_available: bool | None = None,
    employment_status: str | None = None,
    pagination: PaginationParams | None = None,
) -> tuple[list[Worker], int]:
    """
    Retrieve paginated list of field workers with optional filtering.
    """
    query = db.query(Worker).join(Worker.user).join(Worker.department)

    if department_id is not None:
        query = query.filter(Worker.department_id == department_id)

    if is_available is not None:
        query = query.filter(Worker.is_available == is_available)

    if employment_status is not None:
        query = query.filter(Worker.employment_status == employment_status.strip().upper())

    total_items = query.count()

    if pagination:
        query = query.order_by(Worker.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    else:
        query = query.order_by(Worker.created_at.desc())

    return query.all(), total_items


def update_worker(
    db: Session,
    worker_id: uuid.UUID,
    data: WorkerUpdateRequest,
) -> Worker:
    """
    Update worker profile and personal details.
    """
    worker = get_worker_by_id(db, worker_id)

    if data.department_id is not None and data.department_id != worker.department_id:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise EntityNotFoundError("Department", data.department_id)
        if not dept.is_active:
            raise BusinessRuleViolationError(
                f"Cannot reassign worker to inactive department '{dept.name}'"
            )
        worker.department_id = dept.id

    if data.designation is not None:
        worker.designation = data.designation.strip() if data.designation else None

    if data.is_available is not None:
        worker.is_available = data.is_available

    if data.employment_status is not None:
        worker.employment_status = data.employment_status.strip().upper()
        if worker.employment_status != "ACTIVE":
            worker.is_available = False

    if data.full_name is not None and data.full_name.strip():
        worker.user.full_name = data.full_name.strip()

    if data.phone_number is not None:
        worker.user.phone_number = data.phone_number.strip() if data.phone_number else None

    db.commit()
    db.refresh(worker)
    return worker


def deactivate_worker(db: Session, worker_id: uuid.UUID) -> Worker:
    """
    Deactivate worker and base user account safely without deleting history.
    """
    worker = get_worker_by_id(db, worker_id)
    worker.is_available = False
    worker.employment_status = "INACTIVE"
    worker.user.is_active = False

    db.commit()
    db.refresh(worker)
    return worker
