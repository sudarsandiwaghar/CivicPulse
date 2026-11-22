"""
CivicPulse Application-Wide Dependencies

Shared FastAPI dependencies that are used across the entire application,
not specific to any single API version.

Currently provides:
    - Database session dependency (re-exported from db.session for
      convenience, so route handlers can import from one place).

Design note:
    This module re-exports get_db rather than duplicating it, ensuring
    a single source of truth for session lifecycle management.
"""

from app.db.session import get_db  # noqa: F401 — re-exported for convenience

# Additional application-wide dependencies (e.g. settings injection,
# file storage clients) will be added here as needed.
