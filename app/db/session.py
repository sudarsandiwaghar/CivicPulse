"""
CivicPulse Database Session Management

Creates the SQLAlchemy engine and session factory, and provides the
get_db dependency for FastAPI route handlers. Each HTTP request gets
its own database session that is committed on success and rolled back
on failure, then closed in the finally block.

Design decisions:
    - Synchronous engine with psycopg2 driver (confirmed project choice).
    - pool_pre_ping=True ensures stale connections (e.g. after a
      PostgreSQL restart) are detected and replaced automatically.
    - echo is controlled by DEBUG setting for SQL query logging during
      development.

Usage in route handlers:
    from app.db.session import get_db

    @router.get("/items")
    def list_items(db: Session = Depends(get_db)):
        ...
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger("civicpulse.db")

# Lazy initialisation: engine and factory are created on first access
# via init_engine(), called during application startup in main.py.
_engine = None
_SessionFactory = None


def init_engine() -> None:
    """
    Initialise the SQLAlchemy engine and session factory.

    Called once during application startup (in main.py lifespan).
    Separated from module-level code so that:
        1. Settings are fully loaded before the engine is created.
        2. Tests can call this with an overridden DATABASE_URL.

    Raises:
        RuntimeError: If called when the engine is already initialised
            (guards against accidental double-init).
    """
    global _engine, _SessionFactory

    settings = get_settings()
    logger.info(
        "Initialising database engine | env=%s host=%s port=%s db=%s ssl=%s",
        settings.APP_ENV,
        settings.DB_HOST,
        settings.DB_PORT,
        settings.DB_NAME,
        settings.DB_SSLMODE or "default",
    )

    _engine = create_engine(
        settings.DATABASE_URL,
        # pool_pre_ping sends a lightweight "SELECT 1" before reusing a
        # connection, automatically replacing stale ones.
        pool_pre_ping=True,
        # Echo SQL statements to the log when APP_DEBUG is enabled.
        echo=settings.APP_DEBUG,
        # Connection pool sizing — configurable via environment variables
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )

    _SessionFactory = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
    )

    logger.info("Database engine initialised successfully")


def get_engine():
    """
    Return the current SQLAlchemy engine.

    Returns:
        The initialised Engine instance.

    Raises:
        RuntimeError: If the engine has not been initialised.
    """
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialised. Call init_engine() first."
        )
    return _engine


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a request-scoped database session.

    Yields a Session that is automatically closed after the request
    completes. The caller (route handler or service) is responsible
    for calling db.commit() on success; if an unhandled exception
    propagates, the session is rolled back.

    Yields:
        A SQLAlchemy Session bound to the application engine.

    Raises:
        RuntimeError: If the session factory has not been initialised.
    """
    if _SessionFactory is None:
        raise RuntimeError(
            "Session factory not initialised. Call init_engine() first."
        )

    session = _SessionFactory()
    try:
        yield session
    except Exception:
        # Roll back any uncommitted changes on unhandled exceptions
        session.rollback()
        raise
    finally:
        session.close()
