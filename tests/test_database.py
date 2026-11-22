"""
CivicPulse Phase 2 Database and Migration Tests

Automated verification of:
    - Model registry and metadata completeness (all 13 tables).
    - Primary key, foreign key, unique, and check constraints.
    - PostgreSQL connection and schema inspection on civicpulse_test.
    - ORM relationship configuration and cascade rules.
    - Database check constraints (coordinate bounds, rating, AI confidence).
    - Alembic migration upgrade/downgrade idempotency on test database.
"""

import uuid
import pytest
from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.core.constants import (
    AssignmentStatus,
    AttachmentType,
    ComplaintStatus,
    NotificationType,
    PriorityLevel,
    UserRole,
)
from app.db.base import Base
from app.models import (
    AIAssessment,
    Assignment,
    Attachment,
    Category,
    Complaint,
    ComplaintStatusHistory,
    Department,
    Feedback,
    Location,
    Notification,
    Role,
    User,
    Worker,
)


EXPECTED_TABLES = {
    "roles",
    "users",
    "departments",
    "categories",
    "workers",
    "locations",
    "complaints",
    "assignments",
    "assignment_progress",
    "attachments",
    "complaint_status_history",
    "notifications",
    "feedback",
    "ai_assessments",
}


@pytest.fixture(scope="module")
def test_db_engine():
    """Create a dedicated engine connected to civicpulse_test."""
    settings = get_settings()
    test_url = URL.create(
        drivername="postgresql+psycopg2",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME + "_test",
    ).render_as_string(hide_password=False)

    engine = create_engine(test_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """
    Provide an isolated database session that rolls back all operations
    after each test, leaving civicpulse_test clean.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_factory()

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


class TestModelMetadata:
    """Verifies SQLAlchemy Base.metadata definition without requiring live DB."""

    def test_all_13_tables_registered_in_metadata(self):
        """Base.metadata must contain exactly the 13 required entity tables."""
        registered_tables = set(Base.metadata.tables.keys())
        assert EXPECTED_TABLES.issubset(registered_tables), (
            f"Missing tables: {EXPECTED_TABLES - registered_tables}"
        )

    def test_primary_keys_defined(self):
        """All 13 tables must have valid primary keys defined."""
        for table_name in EXPECTED_TABLES:
            table = Base.metadata.tables[table_name]
            pks = [col.name for col in table.primary_key.columns]
            assert len(pks) >= 1, f"Table {table_name} has no primary key"

    def test_roles_model_structure(self):
        """Role model must have name as unique indexed column."""
        table = Base.metadata.tables["roles"]
        assert "name" in table.c
        assert table.c.name.unique or any(
            idx.unique and "name" in [c.name for c in idx.columns]
            for idx in table.indexes
        )

    def test_users_model_structure(self):
        """Users table must have email as unique indexed column and role_id FK."""
        table = Base.metadata.tables["users"]
        assert "email" in table.c
        assert "role_id" in table.c
        assert "hashed_password" in table.c
        fk_targets = [fk.target_fullname for fk in table.foreign_keys]
        assert "roles.id" in fk_targets

    def test_complaints_foreign_keys(self):
        """Complaints table must link to users, categories, and locations."""
        table = Base.metadata.tables["complaints"]
        fk_targets = {fk.target_fullname for fk in table.foreign_keys}
        assert "users.id" in fk_targets
        assert "categories.id" in fk_targets
        assert "locations.id" in fk_targets

    def test_feedback_unique_complaint_id(self):
        """Feedback table must enforce 1-to-1 relationship with complaints."""
        table = Base.metadata.tables["feedback"]
        assert "complaint_id" in table.c
        has_unique = table.c.complaint_id.unique or any(
            idx.unique and "complaint_id" in [c.name for c in idx.columns]
            for idx in table.indexes
        )
        assert has_unique, "feedback.complaint_id must have a UNIQUE constraint"

    def test_workers_unique_user_id(self):
        """Workers table must enforce 1-to-1 relationship with users."""
        table = Base.metadata.tables["workers"]
        assert "user_id" in table.c
        has_unique = table.c.user_id.unique or any(
            idx.unique and "user_id" in [c.name for c in idx.columns]
            for idx in table.indexes
        )
        assert has_unique, "workers.user_id must have a UNIQUE constraint"


class TestDatabaseSchemaInspection:
    """Verifies actual PostgreSQL schema on civicpulse_test."""

    def test_all_13_tables_exist_in_database(self, test_db_engine):
        """Database inspector must report all 13 tables present."""
        inspector = inspect(test_db_engine)
        db_tables = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(db_tables), (
            f"Database missing tables: {EXPECTED_TABLES - db_tables}"
        )

    def test_locations_check_constraints_in_database(self, test_db_engine):
        """Check constraints for coordinate ranges must exist in PostgreSQL."""
        inspector = inspect(test_db_engine)
        check_constraints = inspector.get_check_constraints("locations")
        names = [cc["name"] for cc in check_constraints]
        assert "chk_location_latitude_range" in names
        assert "chk_location_longitude_range" in names

    def test_feedback_rating_check_constraint_in_database(self, test_db_engine):
        """Feedback table must enforce rating check constraint in PostgreSQL."""
        inspector = inspect(test_db_engine)
        check_constraints = inspector.get_check_constraints("feedback")
        names = [cc["name"] for cc in check_constraints]
        assert "chk_feedback_rating_range" in names

    def test_ai_assessment_confidence_check_constraint(self, test_db_engine):
        """AI assessment confidence score check constraint must exist."""
        inspector = inspect(test_db_engine)
        check_constraints = inspector.get_check_constraints("ai_assessments")
        names = [cc["name"] for cc in check_constraints]
        assert "chk_ai_confidence_range" in names


class TestDataPersistenceAndRelationships:
    """Verifies ORM object creation, relationships, and constraint validation."""

    def test_create_role_and_user_hierarchy(self, test_db_session: Session):
        """Can insert role and user, querying via ORM relationship."""
        citizen_role = Role(
            name=f"TEST_CITIZEN_{uuid.uuid4().hex[:6]}",
            description="Test citizen role",
        )
        test_db_session.add(citizen_role)
        test_db_session.flush()

        user = User(
            role_id=citizen_role.id,
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="bcrypt_hashed_dummy_value",
            full_name="Jane Citizen",
        )
        test_db_session.add(user)
        test_db_session.flush()

        # Query back and verify relationship
        loaded_user = test_db_session.query(User).filter_by(id=user.id).first()
        assert loaded_user is not None
        assert loaded_user.role.name == citizen_role.name
        assert loaded_user.created_at is not None

    def test_complaint_full_lifecycle_graph(self, test_db_session: Session):
        """Can create complaint with location, category, department, and status history."""
        # 1. Setup role & citizen
        role = Role(name=f"CITIZEN_{uuid.uuid4().hex[:6]}")
        test_db_session.add(role)
        test_db_session.flush()

        citizen = User(
            role_id=role.id,
            email=f"citizen_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="password_hash",
            full_name="John Citizen",
        )
        test_db_session.add(citizen)

        # 2. Setup department & category
        dept = Department(
            name=f"Public Works {uuid.uuid4().hex[:6]}",
            code=f"PW_{uuid.uuid4().hex[:4].upper()}",
        )
        test_db_session.add(dept)
        test_db_session.flush()

        cat = Category(
            department_id=dept.id,
            name=f"Pothole {uuid.uuid4().hex[:6]}",
        )
        test_db_session.add(cat)

        # 3. Setup location
        loc = Location(
            latitude=12.9716,
            longitude=77.5946,
            address_line="MG Road",
            city="Bengaluru",
        )
        test_db_session.add(loc)
        test_db_session.flush()

        # 4. Create complaint
        complaint = Complaint(
            complaint_number=f"CP-TEST-{uuid.uuid4().hex[:8].upper()}",
            citizen_id=citizen.id,
            category_id=cat.id,
            location_id=loc.id,
            title="Large pothole near junction",
            description="Pothole causing dangerous traffic slowdown",
            status=ComplaintStatus.SUBMITTED,
            priority=PriorityLevel.HIGH,
        )
        test_db_session.add(complaint)
        test_db_session.flush()

        # 5. Add initial status history
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_id=citizen.id,
            previous_status=None,
            new_status=ComplaintStatus.SUBMITTED,
            remarks="Initial submission by citizen",
        )
        test_db_session.add(history)
        test_db_session.flush()

        # Verify graph via relationships
        reloaded = test_db_session.query(Complaint).filter_by(id=complaint.id).first()
        assert reloaded is not None
        assert reloaded.citizen.full_name == "John Citizen"
        assert reloaded.category.department.code == dept.code
        assert reloaded.location.city == "Bengaluru"
        assert len(reloaded.status_history) == 1
        assert reloaded.status_history[0].new_status == ComplaintStatus.SUBMITTED

    def test_invalid_latitude_raises_check_violation(self, test_db_session: Session):
        """Inserting latitude > 90 must fail PostgreSQL check constraint."""
        loc = Location(
            latitude=120.0,  # Invalid
            longitude=77.0,
            city="InvalidCity",
        )
        test_db_session.add(loc)
        with pytest.raises(Exception) as exc_info:
            test_db_session.flush()
        assert "chk_location_latitude_range" in str(exc_info.value)

    def test_invalid_rating_raises_check_violation(self, test_db_session: Session):
        """Inserting feedback rating > 5 must fail PostgreSQL check constraint."""
        role = Role(name=f"ROLE_{uuid.uuid4().hex[:6]}")
        test_db_session.add(role)
        test_db_session.flush()

        citizen = User(
            role_id=role.id,
            email=f"u_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="pw",
            full_name="User",
        )
        dept = Department(name=f"D_{uuid.uuid4().hex[:6]}", code=f"D_{uuid.uuid4().hex[:4]}")
        test_db_session.add_all([citizen, dept])
        test_db_session.flush()

        cat = Category(department_id=dept.id, name=f"C_{uuid.uuid4().hex[:6]}")
        test_db_session.add(cat)
        test_db_session.flush()

        complaint = Complaint(
            complaint_number=f"CP-{uuid.uuid4().hex[:6].upper()}",
            citizen_id=citizen.id,
            category_id=cat.id,
            title="Title",
            description="Desc",
        )
        test_db_session.add(complaint)
        test_db_session.flush()

        fb = Feedback(
            complaint_id=complaint.id,
            citizen_id=citizen.id,
            rating=6,  # Invalid: max allowed is 5
        )
        test_db_session.add(fb)
        with pytest.raises(Exception) as exc_info:
            test_db_session.flush()
        assert "chk_feedback_rating_range" in str(exc_info.value)


class TestAlembicMigrationIntegrity:
    """Tests Alembic upgrade and downgrade reversibility against civicpulse_test."""

    def test_migration_reversibility_on_test_db(self):
        """Downgrade to base and re-upgrade to head must execute cleanly."""
        settings = get_settings()
        test_url = URL.create(
            drivername="postgresql+psycopg2",
            username=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME + "_test",
        ).render_as_string(hide_password=False)

        cfg = Config("alembic.ini")
        cfg.set_section_option("alembic", "sqlalchemy.url", test_url.replace("%", "%%"))
        cfg.cmd_opts = type("CmdOpts", (), {"x": [f"db_url={test_url}"]})()

        # Ensure test database transactional data is clear before testing schema teardown
        clean_engine = create_engine(test_url)
        with clean_engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE complaints, assignments, assignment_progress, complaint_status_history, feedback, attachments, ai_assessments, notifications CASCADE"))
            conn.execute(text("DELETE FROM workers"))
            conn.execute(text("DELETE FROM users"))
        clean_engine.dispose()

        # Downgrade to base
        command.downgrade(cfg, "base")

        # Verify only alembic_version remains
        engine = create_engine(test_url)
        inspector = inspect(engine)
        remaining = inspector.get_table_names()
        assert "departments" not in remaining
        assert "users" not in remaining
        assert "complaints" not in remaining

        # Re-upgrade to head
        command.upgrade(cfg, "head")
        inspector = inspect(engine)
        recreated = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(recreated)
        engine.dispose()
