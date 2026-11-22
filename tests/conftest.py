"""
CivicPulse Test Configuration and Fixtures

Shared pytest fixtures providing:
    - Dedicated test database engine targeting `civicpulse_test`.
    - FastAPI TestClient with request-scoped database sessions bound to isolated
      savepoints that roll back completely after each test.
    - Guarantee that tests never touch or mutate the development database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.main import app


@pytest.fixture(scope="session")
def test_engine():
    """
    Session-scoped SQLAlchemy engine targeting the isolated civicpulse_test database.
    """
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
def db_session(test_engine):
    """
    Function-scoped database session using SQLAlchemy 2.0's savepoint transaction mode.
    Application commits within route handlers commit the savepoint, and outer rollback
    reverts all test changes completely.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    Provide a FastAPI TestClient whose database dependency (get_db) routes through
    the isolated test savepoint session.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
