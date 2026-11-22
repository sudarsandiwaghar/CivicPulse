"""
CivicPulse Category Service

Handles civic issue classification categories and responsible municipal departments.
Provides idempotent data seeding and safe category lookups.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.models.category import Category
from app.models.department import Department

INITIAL_DEPARTMENTS = [
    {
        "code": "PWD",
        "name": "Public Works Department",
        "description": "Roads, bridges, footpaths, and civil infrastructure",
        "contact_email": "pwd@civicpulse.org",
        "contact_phone": "1800-111-001",
    },
    {
        "code": "ELECTRICAL",
        "name": "Electrical & Lighting Department",
        "description": "Streetlights, poles, and public electrical fixtures",
        "contact_email": "electrical@civicpulse.org",
        "contact_phone": "1800-111-002",
    },
    {
        "code": "WATER_SEWAGE",
        "name": "Water Supply & Sewerage Board",
        "description": "Water supply pipes, quality, drainage, and sewage networks",
        "contact_email": "water@civicpulse.org",
        "contact_phone": "1800-111-003",
    },
    {
        "code": "WASTE_MGMT",
        "name": "Solid Waste Management Department",
        "description": "Garbage collection, waste dumping, and street sanitation",
        "contact_email": "waste@civicpulse.org",
        "contact_phone": "1800-111-004",
    },
    {
        "code": "HEALTH_SANITATION",
        "name": "Public Health & Sanitation Department",
        "description": "Public hygiene, pest control, and public sanitation facilities",
        "contact_email": "health@civicpulse.org",
        "contact_phone": "1800-111-005",
    },
]

INITIAL_CATEGORIES = [
    {
        "dept_code": "PWD",
        "name": "Roads and Potholes",
        "description": "Issues related to damaged road surfaces, potholes, and broken dividers",
    },
    {
        "dept_code": "PWD",
        "name": "Public Infrastructure",
        "description": "Maintenance of public parks, footpaths, bridges, and government buildings",
    },
    {
        "dept_code": "ELECTRICAL",
        "name": "Streetlights",
        "description": "Non-functioning street lights, exposed wiring, or damaged lamp poles",
    },
    {
        "dept_code": "WATER_SEWAGE",
        "name": "Water Supply",
        "description": "Drinking water contamination, pipe bursts, low water pressure, or supply disruption",
    },
    {
        "dept_code": "WATER_SEWAGE",
        "name": "Drainage and Sewage",
        "description": "Overflowing gutters, clogged drains, manhole damage, and sewage leaks",
    },
    {
        "dept_code": "WASTE_MGMT",
        "name": "Waste Management",
        "description": "Uncollected household garbage, overflow of public dustbins, and illegal dumping",
    },
    {
        "dept_code": "HEALTH_SANITATION",
        "name": "Public Sanitation",
        "description": "Public toilet cleanliness, stagnating water pools, and vector breeding spots",
    },
]


def init_categories(db: Session) -> None:
    """
    Idempotently seeds standard departments and categories into the database.
    """
    dept_map: dict[str, Department] = {}

    for d_data in INITIAL_DEPARTMENTS:
        dept = db.query(Department).filter(Department.code == d_data["code"]).first()
        if not dept:
            dept = Department(
                code=d_data["code"],
                name=d_data["name"],
                description=d_data["description"],
                contact_email=d_data["contact_email"],
                contact_phone=d_data["contact_phone"],
                is_active=True,
            )
            db.add(dept)
            db.flush()
        dept_map[d_data["code"]] = dept

    for c_data in INITIAL_CATEGORIES:
        category = db.query(Category).filter(Category.name == c_data["name"]).first()
        if not category:
            dept = dept_map.get(c_data["dept_code"])
            if dept:
                category = Category(
                    department_id=dept.id,
                    name=c_data["name"],
                    description=c_data["description"],
                    is_active=True,
                )
                db.add(category)

    db.commit()


def get_active_categories(db: Session) -> list[Category]:
    """
    Retrieve all active complaint categories with joined department data.

    Returns:
        List of Category ORM instances.
    """
    return (
        db.query(Category)
        .join(Category.department)
        .filter(Category.is_active.is_(True))
        .order_by(Category.id.asc())
        .all()
    )


def get_category_by_id(db: Session, category_id: int) -> Category:
    """
    Retrieve a category by integer primary key or raise EntityNotFoundError.

    Args:
        db: Active database session.
        category_id: Category identifier.

    Returns:
        The matched Category instance.

    Raises:
        EntityNotFoundError: If no category exists with that ID.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise EntityNotFoundError("Category", category_id)
    return category
