"""
CivicPulse Database Package

Provides database engine creation, session management, and the
declarative base class used by all ORM models.

Modules:
    base.py    — SQLAlchemy declarative base and shared metadata.
    session.py — Engine factory, session factory, and the get_db
                 dependency used for request-scoped sessions.
"""
