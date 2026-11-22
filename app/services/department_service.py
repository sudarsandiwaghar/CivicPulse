"""
CivicPulse Department Service

Implements business logic for municipal department management, validation,
and lifecycle operations.
"""

from sqlalchemy.orm import Session

from app.core.constants import AssignmentStatus
from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from app.models.assignment import Assignment
from app.models.department import Department
from app.models.worker import Worker
from app.schemas.department import DepartmentCreateRequest, DepartmentUpdateRequest


def list_departments(
    db: Session,
    is_active: bool | None = None,
) -> list[Department]:
    """
    Retrieve all municipal departments, optionally filtered by activity status.
    """
    query = db.query(Department)
    if is_active is not None:
        query = query.filter(Department.is_active == is_active)
    return query.order_by(Department.name.asc()).all()


def get_department_by_id(db: Session, department_id: int) -> Department:
    """
    Retrieve single department by ID.
    """
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise EntityNotFoundError("Department", department_id)
    return dept


def create_department(
    db: Session,
    data: DepartmentCreateRequest,
) -> Department:
    """
    Create a new municipal department with unique code and name validation.
    """
    code = data.code.strip().upper()
    existing_code = db.query(Department).filter(Department.code == code).first()
    if existing_code:
        raise EntityAlreadyExistsError("Department", "code", code)

    existing_name = db.query(Department).filter(Department.name == data.name.strip()).first()
    if existing_name:
        raise EntityAlreadyExistsError("Department", "name", data.name.strip())

    department = Department(
        name=data.name.strip(),
        code=code,
        description=data.description.strip() if data.description else None,
        contact_email=str(data.contact_email) if data.contact_email else None,
        contact_phone=data.contact_phone.strip() if data.contact_phone else None,
        is_active=data.is_active,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def update_department(
    db: Session,
    department_id: int,
    data: DepartmentUpdateRequest,
) -> Department:
    """
    Update department details, ensuring code and name uniqueness if modified.
    """
    department = get_department_by_id(db, department_id)

    if data.code is not None:
        new_code = data.code.strip().upper()
        if new_code != department.code:
            existing = db.query(Department).filter(Department.code == new_code).first()
            if existing:
                raise EntityAlreadyExistsError("Department", "code", new_code)
            department.code = new_code

    if data.name is not None:
        new_name = data.name.strip()
        if new_name != department.name:
            existing = db.query(Department).filter(Department.name == new_name).first()
            if existing:
                raise EntityAlreadyExistsError("Department", "name", new_name)
            department.name = new_name

    if data.description is not None:
        department.description = data.description.strip() if data.description else None

    if data.contact_email is not None:
        department.contact_email = str(data.contact_email) if data.contact_email else None

    if data.contact_phone is not None:
        department.contact_phone = data.contact_phone.strip() if data.contact_phone else None

    if data.is_active is not None:
        department.is_active = data.is_active

    db.commit()
    db.refresh(department)
    return department


def deactivate_department(db: Session, department_id: int) -> Department:
    """
    Deactivate a municipal department safely without deleting historical records.
    Rejects deactivation if there are active worker assignments currently ongoing.
    """
    department = get_department_by_id(db, department_id)
    if not department.is_active:
        return department

    # Block deactivation if there are active worker assignments in this department
    active_assignments = (
        db.query(Assignment)
        .join(Worker, Assignment.worker_id == Worker.id)
        .filter(
            Worker.department_id == department_id,
            Assignment.status.in_([
                AssignmentStatus.ASSIGNED,
                AssignmentStatus.IN_PROGRESS,
            ]),
        )
        .count()
    )
    if active_assignments > 0:
        raise BusinessRuleViolationError(
            f"Cannot deactivate department '{department.name}': {active_assignments} active worker assignment(s) currently ongoing"
        )

    department.is_active = False
    db.commit()
    db.refresh(department)
    return department
