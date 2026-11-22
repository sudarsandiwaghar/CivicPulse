"""
Alembic Environment Configuration for CivicPulse

Configures Alembic migration execution, binding dynamically to the
application settings without hardcoding credentials in alembic.ini.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.db.base import Base
import app.models  # Ensures all 13 models are registered in Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate detection
target_metadata = Base.metadata

# Retrieve database URL dynamically from environment configuration
# If a custom database URL is passed via -x db_url=..., use that (useful for test runs)
x_args = context.get_x_argument(as_dictionary=True)
custom_db_url = x_args.get("db_url")

if custom_db_url:
    # Check for unreplaced template placeholders in custom db_url
    for marker in ["[", "]", "<", ">", "YOUR_PASSWORD", "YOUR-SUPABASE", "CHANGE_ME"]:
        if marker in custom_db_url:
            raise ValueError(
                f"Alembic custom db_url contains unreplaced template placeholder '{marker}'. "
                "Please provide actual database credentials."
            )
    raw_url = custom_db_url.strip()
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgresql://"):]
    database_url = raw_url
else:
    database_url = get_settings().DATABASE_URL

# Escape '%' as '%%' for configparser to avoid interpolation errors with URL-encoded passwords
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates raw SQL scripts without establishing a live connection.
    """
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
