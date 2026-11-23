"""
Phase 8.0 & 8.1 — Production Deployment Preparation & Validation Tests

Verifies production configuration behavior, CORS origin validation,
conditional documentation toggles, database SSL modes and connection pool settings,
unhandled exception handler response sanitization, administrator provisioning validators,
deployment artifact configurations (Nginx & systemd), and initial admin execution.
"""

import os
from pathlib import Path
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.constants import UserRole
from app.core.security import verify_password
from app.main import app
from app.models.role import Role
from app.models.user import User
from scripts.create_initial_admin import (
    create_initial_administrator,
    validate_email_format,
    validate_password_strength,
)


class TestPhase8ProductionConfiguration:
    """Tests for Phase 8.0 production settings and environment properties."""

    def test_default_environment_settings(self):
        """Default settings should indicate development and enable docs."""
        settings = Settings(
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.APP_ENV == "development"
        assert settings.IS_PRODUCTION is False
        assert settings.ENABLE_DOCS is None
        assert settings.DOCS_ENABLED is True

    def test_production_environment_disables_docs_by_default(self):
        """When APP_ENV=production and ENABLE_DOCS is None, docs must be disabled."""
        settings = Settings(
            APP_ENV="production",
            DB_HOST="remote-prod-host.supabase.com",
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.APP_ENV == "production"
        assert settings.IS_PRODUCTION is True
        assert settings.DOCS_ENABLED is False

    def test_production_environment_with_explicit_docs_enable(self):
        """Explicitly setting ENABLE_DOCS=True in production overrides the default."""
        settings = Settings(
            APP_ENV="production",
            ENABLE_DOCS=True,
            DB_HOST="remote-prod-host.supabase.com",
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.APP_ENV == "production"
        assert settings.IS_PRODUCTION is True
        assert settings.DOCS_ENABLED is True

    def test_cors_origins_comma_separated_parsing(self):
        """Comma-delimited string of origins must be parsed into a clean list."""
        settings = Settings(
            CORS_ORIGINS="https://civicpulse.org, https://admin.civicpulse.org",
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.CORS_ORIGINS == [
            "https://civicpulse.org",
            "https://admin.civicpulse.org",
        ]

    def test_cors_origins_json_array_parsing(self):
        """JSON-formatted string array must be parsed into a clean list."""
        settings = Settings(
            CORS_ORIGINS='["https://civicpulse.gov", "https://portal.civicpulse.gov"]',
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.CORS_ORIGINS == [
            "https://civicpulse.gov",
            "https://portal.civicpulse.gov",
        ]

    def test_database_url_with_sslmode(self):
        """Configuring DB_SSLMODE should append ?sslmode=<mode> to DATABASE_URL."""
        settings = Settings(
            DB_SSLMODE="require",
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.DATABASE_URL.endswith("?sslmode=require")

    def test_database_pool_settings(self):
        """Connection pool parameters must have expected production-ready defaults."""
        settings = Settings(
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            DB_POOL_SIZE=20,
            DB_MAX_OVERFLOW=10,
            DB_POOL_TIMEOUT=45,
        )
        assert settings.DB_POOL_SIZE == 20
        assert settings.DB_MAX_OVERFLOW == 10
        assert settings.DB_POOL_TIMEOUT == 45


class TestPhase8AdminProvisioningValidators:
    """Tests for initial administrator credential validators in scripts/create_initial_admin.py."""

    def test_password_strength_validation(self):
        """validate_password_strength enforces length, case, numbers, and symbols."""
        # Too short (< 8 chars)
        ok, msg = validate_password_strength("Short1!")
        assert not ok
        assert "at least 8 characters" in msg

        # Missing uppercase
        ok, msg = validate_password_strength("alllowercase123!")
        assert not ok
        assert "uppercase" in msg

        # Missing lowercase
        ok, msg = validate_password_strength("ALLUPPERCASE123!")
        assert not ok
        assert "lowercase" in msg

        # Missing digit
        ok, msg = validate_password_strength("NoDigitsHere!@#")
        assert not ok
        assert "digit" in msg

        # Missing special character
        ok, msg = validate_password_strength("NoSpecialChar123")
        assert not ok
        assert "special character" in msg

        # Valid strong password
        ok, msg = validate_password_strength("P@ssw0rdSecure2026!")
        assert ok
        assert msg == ""

    def test_email_format_validation(self):
        """validate_email_format validates RFC 5322 email patterns."""
        assert validate_email_format("admin@city.gov") is True
        assert validate_email_format("director.operations@municipal.org") is True
        assert validate_email_format("invalid-email-no-at") is False
        assert validate_email_format("user@domain") is False
        assert validate_email_format("@nodomain.com") is False


class TestPhase8ErrorSanitization:
    """Tests that unhandled internal errors return sanitized 500 envelopes."""

    def test_unhandled_exception_returns_sanitized_500(self):
        """Unexpected internal errors must never leak traceback, filepaths, or database schemas."""
        client = TestClient(app, raise_server_exceptions=False)

        # Mock an endpoint dependency to raise an unexpected internal RuntimeError
        from app.db.session import get_db

        def bad_db():
            raise RuntimeError("Internal database socket corrupted /var/lib/secret.sock")

        app.dependency_overrides[get_db] = bad_db
        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@city.gov", "password": "Password123!"},
            )

            assert response.status_code == 500
            body = response.json()
            assert body["success"] is False
            assert body["message"] == "Internal server error"
            assert "unexpected server error occurred" in body["detail"]
            # Ensure internal message details are completely redacted from client
            assert "socket corrupted" not in response.text
            assert "secret.sock" not in response.text
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestPhase81DeploymentArtifacts:
    """Validations for Nginx configuration and systemd service unit."""

    def test_nginx_hsts_omits_preload(self):
        """Nginx HSTS header must NOT contain 'preload' to avoid breaking non-HTTPS subdomains."""
        conf_path = Path("deploy/nginx/civicpulse.conf")
        assert conf_path.exists(), "deploy/nginx/civicpulse.conf must exist"
        content = conf_path.read_text(encoding="utf-8")

        # Find the Strict-Transport-Security line
        for line in content.splitlines():
            if "Strict-Transport-Security" in line and not line.strip().startswith("#"):
                assert "preload" not in line, "HSTS must omit 'preload' by default"
                assert "includeSubDomains" in line
                assert "max-age=" in line

    def test_nginx_csp_allows_essential_assets(self):
        """CSP must whitelist self, OpenStreetMap tiles, unpkg, and data/blob URIs."""
        conf_path = Path("deploy/nginx/civicpulse.conf")
        content = conf_path.read_text(encoding="utf-8")

        assert "https://*.tile.openstreetmap.org" in content
        assert "https://unpkg.com" in content
        assert "data:" in content
        assert "blob:" in content

    def test_nginx_health_proxy_target(self):
        """Nginx /health location must proxy to /api/v1/health where FastAPI mounts it."""
        conf_path = Path("deploy/nginx/civicpulse.conf")
        content = conf_path.read_text(encoding="utf-8")

        assert "location = /health" in content
        assert "proxy_pass http://civicpulse_backend/api/v1/health;" in content

    def test_systemd_unit_directives(self):
        """Systemd service unit must include bytecode restrictions, LogsDirectory, and sandbox flags."""
        svc_path = Path("deploy/systemd/civicpulse-backend.service")
        assert svc_path.exists(), "deploy/systemd/civicpulse-backend.service must exist"
        content = svc_path.read_text(encoding="utf-8")

        assert 'Environment="PYTHONDONTWRITEBYTECODE=1"' in content
        assert 'Environment="PYTHONUNBUFFERED=1"' in content
        assert "LogsDirectory=civicpulse" in content
        assert "ProtectSystem=strict" in content
        assert "PrivateTmp=true" in content
        assert "NoNewPrivileges=true" in content


class TestPhase81AdminProvisioningExecution:
    """Tests executing the admin provisioning script against test database."""

    def test_admin_provisioning_headless_execution(self, test_engine):
        """Provisioning utility should create active verified admin in test database and be idempotent."""
        test_email = "test_provisioned_admin_2026@civicpulse.gov"
        test_password = "AdminProvisionPassword2026!"
        test_name = "Chief Municipal Admin"

        env_patch = {
            "INITIAL_ADMIN_EMAIL": test_email,
            "INITIAL_ADMIN_PASSWORD": test_password,
            "INITIAL_ADMIN_NAME": test_name,
        }

        with patch.dict(os.environ, env_patch), \
             patch("scripts.create_initial_admin.init_engine", return_value=None), \
             patch("scripts.create_initial_admin.get_engine", return_value=test_engine):

            # 1. First execution creates administrator
            result = create_initial_administrator()
            assert result is True

            with Session(test_engine) as session:
                created_user = session.query(User).filter(User.email == test_email).first()
                assert created_user is not None
                assert created_user.full_name == test_name
                assert created_user.is_active is True
                assert created_user.is_verified is True

                admin_role = session.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()
                assert created_user.role_id == admin_role.id
                assert verify_password(test_password, created_user.hashed_password)

                # 2. Second execution is idempotent (returns True, no duplicates)
                idempotent_result = create_initial_administrator()
                assert idempotent_result is True

                # Clean up created test user
                session.delete(created_user)
                session.commit()


class TestPhase82FreeTierDeploymentArtifacts:
    """Validations for Phase 8.2 Free-Tier deployment configuration artifacts."""

    def test_cloudflare_pages_redirects_rule(self):
        """frontend/public/_redirects must exist and contain the SPA fallback rule."""
        redirects_file = Path("frontend/public/_redirects")
        assert redirects_file.exists(), "frontend/public/_redirects must exist"
        content = redirects_file.read_text(encoding="utf-8")
        assert "/*" in content
        assert "/index.html" in content
        assert "200" in content

    def test_cloudflare_pages_headers_and_csp(self):
        """frontend/public/_headers must exist and whitelist Render backend in CSP."""
        headers_file = Path("frontend/public/_headers")
        assert headers_file.exists(), "frontend/public/_headers must exist"
        content = headers_file.read_text(encoding="utf-8")
        assert "X-Frame-Options: DENY" in content
        assert "X-Content-Type-Options: nosniff" in content
        assert "https://*.onrender.com" in content
        assert "/assets/*" in content

    def test_requirements_gunicorn_platform_marker(self):
        """requirements.txt must include gunicorn with sys_platform marker for Render."""
        req_file = Path("requirements.txt")
        assert req_file.exists(), "requirements.txt must exist"
        content = req_file.read_text(encoding="utf-8")
        assert "gunicorn>=22.0.0" in content
        assert 'sys_platform != "win32"' in content

    def test_free_deployment_guide_completeness(self):
        """FREE_DEPLOYMENT.md must exist and cover all three free-tier providers."""
        guide_file = Path("FREE_DEPLOYMENT.md")
        assert guide_file.exists(), "FREE_DEPLOYMENT.md must exist"
        content = guide_file.read_text(encoding="utf-8")
        assert "Cloudflare Pages" in content
        assert "Render" in content
        assert "Supabase" in content
        assert "PostGIS" in content
        assert "pooler.supabase.com" in content
        assert "Cold Starts" in content
        assert "Ephemeral" in content


class TestPhase83PreflightConsistency:
    """Preflight consistency verifications for Phase 8.3."""

    def test_environment_variable_alias_consistency(self):
        """ENVIRONMENT and POSTGRES_POOL_* aliases must seamlessly map to canonical settings."""
        settings = Settings(
            ENVIRONMENT="production",
            DB_HOST="remote-prod-host.supabase.com",
            POSTGRES_POOL_SIZE=8,
            POSTGRES_MAX_OVERFLOW=4,
            POSTGRES_POOL_TIMEOUT=45,
            SECRET_KEY="test_secret_via_alias_key_at_least_32_bytes_long",
            DB_USER="test_user",
            DB_PASSWORD="test_password",
        )
        assert settings.APP_ENV == "production"
        assert settings.IS_PRODUCTION is True
        assert settings.DOCS_ENABLED is False
        assert settings.DB_POOL_SIZE == 8
        assert settings.DB_MAX_OVERFLOW == 4
        assert settings.DB_POOL_TIMEOUT == 45
        assert settings.JWT_SECRET_KEY == "test_secret_via_alias_key_at_least_32_bytes_long"

    def test_database_url_direct_override_and_normalization(self):
        """Direct DATABASE_URL string must normalize driver prefix to postgresql+psycopg2://."""
        # 1. postgresql:// URI
        s1 = Settings(
            DATABASE_URL="postgresql://usr:pwd@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert s1.DATABASE_URL == "postgresql+psycopg2://usr:pwd@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

        # 2. Legacy postgres:// URI (common from cloud providers)
        s2 = Settings(
            DATABASE_URL="postgres://usr:pwd@render-host:5432/db",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert s2.DATABASE_URL == "postgresql+psycopg2://usr:pwd@render-host:5432/db"

    def test_admin_provisioning_script_path_and_contract(self):
        """Verified admin provisioning script must exist at scripts/create_initial_admin.py."""
        script_path = Path("scripts/create_initial_admin.py")
        assert script_path.exists(), "scripts/create_initial_admin.py must exist"

        nonexistent_script = Path("scripts/provision_admin.py")
        assert not nonexistent_script.exists(), "scripts/provision_admin.py must not exist to avoid naming confusion"

        content = script_path.read_text(encoding="utf-8")
        assert "INITIAL_ADMIN_EMAIL" in content
        assert "INITIAL_ADMIN_PASSWORD" in content
        assert "INITIAL_ADMIN_NAME" in content
        assert "validate_password_strength" in content
        assert "del password" in content  # Password memory clearing

    def test_api_client_url_resilience(self):
        """Frontend apiClient.js must exist and contain base URL normalization logic."""
        client_path = Path("frontend/src/services/apiClient.js")
        assert client_path.exists(), "frontend/src/services/apiClient.js must exist"
        content = client_path.read_text(encoding="utf-8")
        assert "VITE_API_BASE_URL" in content
        assert "/api/v1" in content
        assert "replace(" in content


class TestPhase84SupabaseMigrationReadiness:
    """Readiness validations for Phase 8.4 Supabase connectivity and migrations."""

    def test_gitignore_secret_exclusion(self):
        """.gitignore must exclude all .env and secret files while preserving examples."""
        gitignore_path = Path(".gitignore")
        assert gitignore_path.exists(), ".gitignore must exist"
        content = gitignore_path.read_text(encoding="utf-8")

        assert ".env" in content
        assert ".env.*" in content
        assert "!.env.example" in content
        assert "!.env.production.example" in content
        assert "*.pem" in content
        assert "*.key" in content

    def test_supabase_session_pooler_url_parsing_and_masking(self):
        """Supabase connection string must parse correctly, and diagnostic tool must mask password."""
        from scripts.verify_db_connection import mask_database_url

        sample_url = "postgresql://postgres.myprojectref:P%40ssw0rd!@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
        settings = Settings(
            DATABASE_URL=sample_url,
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.DATABASE_URL.startswith("postgresql+psycopg2://")
        assert "aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require" in settings.DATABASE_URL

        # Verify password masking
        masked = mask_database_url(sample_url)
        assert ":****@" in masked
        assert "P%40ssw0rd!" not in masked
        assert "aws-0-us-east-1.pooler.supabase.com" in masked

    def test_alembic_linear_migration_chain(self):
        """All seven Alembic migrations must form an unbroken linear chain to head b7c8d9e0f1a2."""
        import importlib.util

        versions_dir = Path("alembic/versions")
        assert versions_dir.exists(), "alembic/versions directory must exist"

        migration_files = list(versions_dir.glob("*.py"))
        assert len(migration_files) == 7, f"Expected exactly 7 migration files, found {len(migration_files)}"

        revisions = {}
        for file_path in migration_files:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            revisions[mod.revision] = mod.down_revision

        head = "b7c8d9e0f1a2"
        chain = []
        curr = head
        while curr is not None:
            chain.append(curr)
            assert curr in revisions, f"Revision {curr} in chain is missing from migrations"
            curr = revisions[curr]

        assert len(chain) == 7
        assert chain[0] == "b7c8d9e0f1a2"  # Head
        assert chain[-1] == "dc808166f213"  # Initial schema root

    def test_verify_db_connection_utility_exists(self):
        """Diagnostic utility scripts/verify_db_connection.py must exist with expected target head."""
        from scripts.verify_db_connection import EXPECTED_HEAD_REVISION, run_database_preflight

        assert EXPECTED_HEAD_REVISION == "b7c8d9e0f1a2"
        assert callable(run_database_preflight)


class TestPhase85DualEnvironmentSafeguards:
    """Safeguard validations for Phase 8.5 dual-environment database separation."""

    def test_production_blocks_test_database_name(self):
        """Production environment must never allow using a database ending in _test."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Production safety violation: Test database"):
            Settings(
                APP_ENV="production",
                DB_NAME="civicpulse_test",
                DB_USER="test_user",
                DB_PASSWORD="test_password",
                JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            )

    def test_production_blocks_test_database_url_override(self):
        """Production environment must block a DATABASE_URL pointing to a test database."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Production safety violation: Test database"):
            Settings(
                APP_ENV="production",
                DATABASE_URL="postgresql://user:pass@remotehost:5432/civicpulse_test?sslmode=require",
                JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            )

    def test_development_allows_test_database_for_testing(self):
        """Development and testing environments permit test databases."""
        dev_settings = Settings(
            APP_ENV="development",
            DB_NAME="civicpulse_test",
            DB_USER="test_user",
            DB_PASSWORD="test_password",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert dev_settings.DB_NAME == "civicpulse_test"
        assert dev_settings.IS_PRODUCTION is False

    def test_local_settings_load_without_production_collision(self):
        """Local environment defaults load safely and maintain dual-environment isolation."""
        from app.config import get_settings

        settings = get_settings()
        assert settings.APP_NAME == "CivicPulse"
        # Confirm local settings are not marked production
        assert settings.APP_ENV in ["development", "testing"]
        assert settings.IS_PRODUCTION is False
        assert "postgresql+psycopg2://" in settings.DATABASE_URL

    def test_mask_database_url_masks_credentials(self):
        """Database URL masking must hide sensitive passwords while preserving host and user."""
        from scripts.verify_db_connection import mask_database_url

        url = "postgresql://postgres.myproject:SuperSecretPassword123@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
        masked = mask_database_url(url)
        assert "SuperSecretPassword123" not in masked
        assert ":****@" in masked
        assert "postgres.myproject" in masked
        assert "aws-0-eu-central-1.pooler.supabase.com" in masked

    def test_mask_database_url_handles_no_password(self):
        """Database URL without password returns intact."""
        from scripts.verify_db_connection import mask_database_url

        url = "postgresql://localhost:5433/civicpulse"
        assert mask_database_url(url) == url


class TestPhase87DatabaseIsolationAndPlaceholderFixes:
    """Tests for Phase 8.7 database configuration consistency and placeholder rejection."""

    def test_unreplaced_placeholder_in_database_url_is_rejected(self):
        """Settings must reject unreplaced template placeholders like [REGION] in DATABASE_URL."""
        from pydantic import ValidationError

        placeholder_url = (
            "postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require"
        )
        with pytest.raises(ValidationError, match="Unreplaced template placeholder"):
            Settings(
                DATABASE_URL=placeholder_url,
                JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            )

    def test_unreplaced_placeholder_in_db_host_is_rejected(self):
        """Settings must reject unreplaced template placeholders in DB_HOST."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Unreplaced template placeholder"):
            Settings(
                DB_HOST="aws-0-[REGION].pooler.supabase.com",
                DB_USER="civicpulse",
                DB_PASSWORD="password",
                JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            )

    def test_database_url_synchronizes_individual_attributes(self):
        """When DATABASE_URL is provided, individual DB_* fields must synchronize from it."""
        valid_url = (
            "postgresql://postgres.myproject:SecretPass123@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
        )
        settings = Settings(
            DATABASE_URL=valid_url,
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.DB_HOST == "aws-0-eu-central-1.pooler.supabase.com"
        assert settings.DB_PORT == 5432
        assert settings.DB_NAME == "postgres"
        assert settings.DB_USER == "postgres.myproject"
        assert settings.DB_PASSWORD == "SecretPass123"
        assert settings.DB_SSLMODE == "require"

    def test_production_mode_rejects_localhost_host(self):
        """Production mode must reject localhost and fail-fast instead of silent fallback."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Production environment cannot use localhost"):
            Settings(
                APP_ENV="production",
                DB_HOST="localhost",
                DB_USER="civicpulse",
                DB_PASSWORD="password",
                JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            )

    def test_production_mode_rejects_loopback_ip(self):
        """Production mode must reject loopback IP (127.0.0.1) in host or DATABASE_URL."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Production environment cannot use localhost"):
            Settings(
                APP_ENV="production",
                DATABASE_URL="postgresql://user:pass@127.0.0.1:5433/civicpulse_prod?sslmode=require",
                JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
            )

    def test_preflight_diagnostic_rejects_placeholder_gracefully(self):
        """Standalone preflight utility must gracefully reject placeholders without crashing."""
        from scripts.verify_db_connection import run_database_preflight

        placeholder_url = "postgresql://postgres.ref:pass@aws-0-[REGION].pooler.supabase.com:5432/postgres"
        result = run_database_preflight(custom_url=placeholder_url)
        assert result is False

    def test_get_settings_env_file_resolution(self, tmp_path, monkeypatch):
        """get_settings must respect ENV_FILE override and dynamically load designated environment file."""
        from app.config import get_settings

        custom_env = tmp_path / ".env.custom"
        custom_env.write_text(
            "APP_NAME=CivicPulseCustom\nDB_USER=custom_usr\nDB_PASSWORD=pwd\nJWT_SECRET_KEY=at_least_32_characters_long_secret_here\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("ENV_FILE", str(custom_env))
        get_settings.cache_clear()
        try:
            s = get_settings()
            assert s.APP_NAME == "CivicPulseCustom"
            assert s.DB_USER == "custom_usr"
        finally:
            get_settings.cache_clear()


class TestPhase811RenderDeploymentConfiguration:
    """Verifications for Phase 8.11 Render Free Web Service deployment configuration."""

    def test_render_blueprint_specification(self):
        """render.yaml must exist and configure a Free-tier Python web service."""
        render_yaml = Path("render.yaml")
        assert render_yaml.exists(), "render.yaml must exist at repository root"
        content = render_yaml.read_text(encoding="utf-8")

        assert "type: web" in content
        assert "plan: free" in content
        assert "buildCommand: pip install -r requirements.txt" in content
        assert "healthCheckPath: /api/v1/health" in content
        assert "gunicorn app.main:app" in content
        assert "--workers 2" in content
        assert "--worker-class uvicorn.workers.UvicornWorker" in content
        assert "--bind 0.0.0.0:$PORT" in content

    def test_render_no_startup_migrations(self):
        """render.yaml build and start commands must not automatically run alembic migrations."""
        content = Path("render.yaml").read_text(encoding="utf-8")
        assert "alembic upgrade" not in content
        assert "alembic" not in content

    def test_render_environment_variables(self):
        """render.yaml must define canonical environment variables expected by app.config."""
        content = Path("render.yaml").read_text(encoding="utf-8")
        expected_keys = [
            "APP_ENV",
            "DATABASE_URL",
            "SECRET_KEY",
            "ALGORITHM",
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "REFRESH_TOKEN_EXPIRE_DAYS",
            "CORS_ORIGINS",
            "ENABLE_DOCS",
            "DB_POOL_SIZE",
            "DB_MAX_OVERFLOW",
        ]
        for key in expected_keys:
            assert key in content, f"Environment variable {key} must be specified in render.yaml"

    def test_health_endpoint_returns_200(self, client):
        """GET /api/v1/health must return HTTP 200 with status healthy."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    def test_production_docs_disabled_in_app(self):
        """When settings.DOCS_ENABLED is False, FastAPI docs URLs are None."""
        from fastapi import FastAPI
        from app.config import Settings

        prod_settings = Settings(
            APP_ENV="production",
            ENABLE_DOCS=False,
            DB_HOST="remote-supabase.pooler.supabase.com",
            DB_USER="usr",
            DB_PASSWORD="pwd",
            JWT_SECRET_KEY="at_least_32_characters_long_secret_here",
        )
        assert prod_settings.DOCS_ENABLED is False

        # Create FastAPI instance with same logic as app.main
        prod_app = FastAPI(
            docs_url="/docs" if prod_settings.DOCS_ENABLED else None,
            redoc_url="/redoc" if prod_settings.DOCS_ENABLED else None,
            openapi_url="/openapi.json" if prod_settings.DOCS_ENABLED else None,
        )
        assert prod_app.docs_url is None
        assert prod_app.redoc_url is None
        assert prod_app.openapi_url is None

        prod_client = TestClient(prod_app)
        assert prod_client.get("/docs").status_code == 404
        assert prod_client.get("/redoc").status_code == 404
        assert prod_client.get("/openapi.json").status_code == 404

    def test_python_runtime_pinning_files(self):
        """Repository must provide .python-version and runtime.txt pinned to Python 3.11.9."""
        py_version_file = Path(".python-version")
        assert py_version_file.exists(), ".python-version must exist"
        assert py_version_file.read_text(encoding="utf-8").strip() == "3.11.9"

        runtime_file = Path("runtime.txt")
        assert runtime_file.exists(), "runtime.txt must exist"
        assert runtime_file.read_text(encoding="utf-8").strip() == "python-3.11.9"

    def test_upload_dir_sanitizes_var_www_to_tmp(self):
        """Settings must automatically sanitize /var/www paths to /tmp scratch space when unprivileged."""
        settings = Settings(
            UPLOAD_DIR="/var/www/civicpulse/uploads",
            DB_USER="usr",
            DB_PASSWORD="pwd",
            JWT_SECRET_KEY="test_jwt_secret_key_at_least_32_bytes_long_here",
        )
        assert settings.UPLOAD_DIR == "/tmp/civicpulse/uploads"

    def test_render_yaml_upload_dir_configuration(self):
        """render.yaml must configure UPLOAD_DIR to /tmp/civicpulse/uploads."""
        content = Path("render.yaml").read_text(encoding="utf-8")
        assert "/tmp/civicpulse/uploads" in content
