"""
CivicPulse Application Configuration

Centralised, type-safe configuration management using pydantic-settings.
All settings are loaded from environment variables or a .env file at the
project root. Sensitive values (database credentials, JWT secrets) must
never be hardcoded or committed to version control.

Usage:
    from app.config import get_settings

    settings = get_settings()
    print(settings.DATABASE_URL)

The get_settings() function is cached via @lru_cache so the .env file
is read only once per application lifecycle.
"""

from functools import lru_cache
from typing import Any
from urllib.parse import parse_qs, urlparse
import json

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def check_for_unreplaced_placeholders(value: str | None, field_name: str) -> None:
    """
    Validate that connection strings or hosts do not contain unreplaced template placeholders.

    Raises:
        ValueError: If placeholder markers like '[', ']', '<', '>', or placeholder keywords are detected.
    """
    if not value:
        return
    placeholder_patterns = [
        "[", "]", "<", ">",
        "YOUR_PASSWORD", "YOUR-SUPABASE", "YOUR_DB_PASSWORD",
        "CHANGE_ME", "PROJECT-REF",
    ]
    for pattern in placeholder_patterns:
        if pattern in value:
            raise ValueError(
                f"Incomplete database configuration: Unreplaced template placeholder '{pattern}' "
                f"detected in {field_name}. Please configure actual database credentials instead of template placeholders."
            )


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables.

    Attributes are grouped by responsibility. Each group corresponds
    to a section in .env.example. Required secrets have empty-string
    defaults so the app starts without a .env for testing, but will
    fail safe when those values are actually used (e.g. JWT signing
    will raise on an empty key).
    """

    # ---- Application Identity & Environment ----------------------------------
    APP_NAME: str = "CivicPulse"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "Civic Issue Reporting, Monitoring & Intelligence Platform"
    )
    APP_ENV: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )  # "development", "staging", "production", "testing"
    APP_DEBUG: bool = False
    ENABLE_DOCS: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ENABLE_DOCS", "DOCS_ENABLED"),
    )  # Explicit override; auto-disabled in production when None

    @property
    def DEBUG(self) -> bool:
        """Alias for APP_DEBUG to maintain backward compatibility."""
        return self.APP_DEBUG

    @property
    def IS_PRODUCTION(self) -> bool:
        """Determine whether the application is running in production mode."""
        return self.APP_ENV.lower() == "production"

    @property
    def DOCS_ENABLED(self) -> bool:
        """
        Determine whether interactive API documentation (/docs, /redoc) is exposed.
        Defaults to True in development/testing and False in production.
        """
        if self.ENABLE_DOCS is not None:
            return self.ENABLE_DOCS
        return not self.IS_PRODUCTION

    # ---- API & CORS ----------------------------------------------------------
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] | str = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str] | Any:
        """Accept comma-separated origin strings or JSON arrays from environment variables."""
        if isinstance(v, str):
            val = v.strip()
            if val.startswith("[") and val.endswith("]"):
                try:
                    return json.loads(val)
                except Exception:
                    pass
            return [origin.strip() for origin in val.split(",") if origin.strip()]
        return v

    # ---- Database (PostgreSQL) -----------------------------------------------
    # Direct database connection URL override (supports full connection strings from
    # cloud platforms like Supabase / Render, and supports DATABASE_URL env var).
    DATABASE_URL_OVERRIDE: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL_OVERRIDE", "DATABASE_URL"),
    )

    # Individual components are kept separate so they can be overridden
    # independently (e.g. different host in CI vs production).
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "civicpulse"
    DB_PASSWORD: str = ""  # REQUIRED — set via .env or environment
    DB_NAME: str = "civicpulse"
    DB_POOL_SIZE: int = Field(
        default=10,
        validation_alias=AliasChoices("DB_POOL_SIZE", "POSTGRES_POOL_SIZE"),
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20,
        validation_alias=AliasChoices("DB_MAX_OVERFLOW", "POSTGRES_MAX_OVERFLOW"),
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        validation_alias=AliasChoices("DB_POOL_TIMEOUT", "POSTGRES_POOL_TIMEOUT"),
    )
    DB_SSLMODE: str | None = None  # e.g. "require", "verify-ca", "verify-full"

    @property
    def DATABASE_URL(self) -> str:
        """
        Constructs or returns the synchronous PostgreSQL connection string.

        If DATABASE_URL (or DATABASE_URL_OVERRIDE) is explicitly set in the
        environment, normalizes driver prefix to 'postgresql+psycopg2://' and returns it.
        Otherwise, constructs the URL safely from individual DB_* components.

        Returns:
            Full database URL in SQLAlchemy-compatible string format.
        """
        if self.DATABASE_URL_OVERRIDE:
            raw_url = self.DATABASE_URL_OVERRIDE.strip()
            if raw_url.startswith("postgres://"):
                raw_url = "postgresql+psycopg2://" + raw_url[len("postgres://"):]
            elif raw_url.startswith("postgresql://"):
                raw_url = "postgresql+psycopg2://" + raw_url[len("postgresql://"):]
            return raw_url

        from sqlalchemy import URL

        query_params = {}
        if self.DB_SSLMODE:
            query_params["sslmode"] = self.DB_SSLMODE

        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query=query_params or None,
        ).render_as_string(hide_password=False)

    # ---- JWT Authentication --------------------------------------------------
    JWT_SECRET_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )  # REQUIRED — set via .env or environment
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "ALGORITHM"),
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES"
        ),
    )
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        validation_alias=AliasChoices(
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS", "REFRESH_TOKEN_EXPIRE_DAYS"
        ),
    )

    # ---- File Uploads --------------------------------------------------------
    UPLOAD_DIR: str = Field(
        default="uploads",
        validation_alias=AliasChoices("UPLOAD_DIR", "CIVICPULSE_UPLOAD_DIR"),
    )
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: list[str] = [
        ".jpg", ".jpeg", ".png", ".gif",  # Images
        ".pdf", ".doc", ".docx",          # Documents
    ]

    @field_validator("UPLOAD_DIR", mode="after")
    @classmethod
    def sanitize_upload_dir(cls, v: str) -> str:
        """
        Validate and sanitize upload directory path.
        In containerized, PaaS, or non-root environments where /var/www is configured
        (e.g. copied from a VPS deployment template) but not writable or non-existent,
        safely reroute to a writable temporary scratch directory (/tmp/civicpulse/uploads).
        """
        if v and v.startswith("/var/www"):
            import os
            try:
                # If /var/www does not exist or is not writable by current user
                if not os.path.exists("/var/www") or not os.access("/var/www", os.W_OK):
                    return "/tmp/civicpulse/uploads"
            except Exception:
                return "/tmp/civicpulse/uploads"
        return v

    # ---- Rate Limiting -------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 60

    # ---- Logging -------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # ---- Cross-Environment Production Safeguards -----------------------------
    @model_validator(mode="after")
    def validate_production_environment_rules(self) -> "Settings":
        """
        Enforce critical cross-environment safety and configuration consistency rules:
        1. Reject unreplaced template placeholders in connection details.
        2. Synchronize individual DB_* attributes from DATABASE_URL_OVERRIDE when present.
        3. In production mode, prevent using test databases and prevent fallback to localhost.
        """
        # 1. Validate against unreplaced template placeholders
        if self.DATABASE_URL_OVERRIDE:
            check_for_unreplaced_placeholders(self.DATABASE_URL_OVERRIDE, "DATABASE_URL")
        check_for_unreplaced_placeholders(self.DB_HOST, "DB_HOST")
        check_for_unreplaced_placeholders(self.DB_USER, "DB_USER")
        check_for_unreplaced_placeholders(self.DB_PASSWORD, "DB_PASSWORD")

        # 2. Synchronize DB_* attributes from DATABASE_URL_OVERRIDE when provided
        if self.DATABASE_URL_OVERRIDE:
            parsed = urlparse(self.DATABASE_URL_OVERRIDE)
            if parsed.hostname:
                object.__setattr__(self, "DB_HOST", parsed.hostname)
            if parsed.port:
                object.__setattr__(self, "DB_PORT", parsed.port)
            if parsed.username:
                object.__setattr__(self, "DB_USER", parsed.username)
            if parsed.password:
                object.__setattr__(self, "DB_PASSWORD", parsed.password)
            db_name = parsed.path.lstrip("/").split("?")[0]
            if db_name:
                object.__setattr__(self, "DB_NAME", db_name)
            if parsed.query:
                qs = parse_qs(parsed.query)
                if "sslmode" in qs and qs["sslmode"]:
                    object.__setattr__(self, "DB_SSLMODE", qs["sslmode"][0])

        # 3. Cross-environment safety rules
        if self.IS_PRODUCTION:
            # Prevent using a test database in production
            if self.DB_NAME.lower().endswith("_test") or self.DB_NAME.lower() == "test":
                raise ValueError(
                    f"Production safety violation: Test database '{self.DB_NAME}' cannot be used in production mode."
                )

            # Prevent production from silently using localhost or loopback addresses
            if self.DB_HOST.lower() in ["localhost", "127.0.0.1", "::1"]:
                raise ValueError(
                    f"Production safety violation: Production environment cannot use localhost ({self.DB_HOST}). "
                    "A valid hosted database URL (e.g. Supabase) is required."
                )

        return self

    # ---- Pydantic Settings Configuration -------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # extra="ignore" allows the .env to contain keys this class
        # doesn't define (e.g. IDE-specific vars) without raising.
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    Uses @lru_cache so the .env file is parsed exactly once per
    process, avoiding repeated filesystem reads and environment
    variable lookups on every request.

    Dynamically resolves env_file:
    1. ENV_FILE environment variable override if specified.
    2. .env.production if APP_ENV / ENVIRONMENT is 'production' and .env.production exists.
    3. Defaults to .env for local development.

    Returns:
        The application Settings object.
    """
    import os

    env_file = os.getenv("ENV_FILE")
    if not env_file:
        app_env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").lower()
        if app_env == "production" and os.path.exists(".env.production"):
            env_file = ".env.production"
        else:
            env_file = ".env"

    return Settings(_env_file=env_file)
