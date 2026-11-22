"""
CivicPulse Configuration Regression Tests

Verifies application settings loading, environment variable isolation,
and SQLAlchemy database URL generation.
"""

from app.config import get_settings


class TestConfiguration:
    """Tests for application settings and configuration behavior."""

    def test_settings_load_successfully(self):
        """Settings should load without validation errors."""
        settings = get_settings()
        assert settings.APP_NAME == "CivicPulse"
        assert settings.APP_VERSION == "0.1.0"
        assert settings.API_V1_PREFIX == "/api/v1"

    def test_app_debug_resolution(self):
        """APP_DEBUG should resolve to a boolean and be mirrored by DEBUG property."""
        settings = get_settings()
        assert isinstance(settings.APP_DEBUG, bool)
        assert settings.DEBUG is settings.APP_DEBUG

    def test_database_url_generation(self):
        """DATABASE_URL should produce a valid PostgreSQL psycopg2 connection string."""
        settings = get_settings()
        url = settings.DATABASE_URL
        assert url.startswith("postgresql+psycopg2://")
        assert f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}" in url
        # Confirm credentials are not missing
        assert settings.DB_USER in url
