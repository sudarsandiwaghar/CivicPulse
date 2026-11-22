"""
CivicPulse — Database Connectivity & Preflight Diagnostic Utility

Secure, standalone Python diagnostic tool to verify PostgreSQL connectivity,
check required extensions (uuid-ossp, postgis), and report current Alembic
schema migration status without exposing credentials.

Usage:
    # 1. Using environment variables (local or remote Supabase)
    python scripts/verify_db_connection.py

    # 2. Testing against specific connection string
    DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require" python scripts/verify_db_connection.py
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure application root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine, inspect, text
from app.config import Settings, get_settings

EXPECTED_HEAD_REVISION = "b7c8d9e0f1a2"


def mask_database_url(url_str: str) -> str:
    """Mask password in database URL for safe logging."""
    try:
        parsed = urlparse(url_str)
        if parsed.password:
            masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
            return parsed._replace(netloc=masked_netloc).geturl()
        return url_str
    except Exception:
        return "<hidden-url>"


def run_database_preflight(custom_url: str | None = None, env_file: str | None = None) -> bool:
    """
    Execute comprehensive database diagnostic checks.
    Returns True if database is reachable and configured properly.
    """
    print("=" * 65)
    print("CivicPulse — Database Preflight & Diagnostic Check")
    print("=" * 65)

    # Always clear cached settings so CLI flags and env vars take immediate effect
    get_settings.cache_clear()

    try:
        if env_file:
            settings = Settings(_env_file=env_file)
        elif custom_url:
            settings = Settings(DATABASE_URL=custom_url)
        else:
            settings = get_settings()
    except ValueError as val_err:
        print(f"\n[FAIL] Configuration validation error: {val_err}", file=sys.stderr)
        return False

    raw_url = custom_url or settings.DATABASE_URL
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://"):
        raw_url = "postgresql+psycopg2://" + raw_url[len("postgresql://"):]

    masked_url = mask_database_url(raw_url)

    # Extract exact effective connection parameters directly from the sanitized URL
    parsed = urlparse(raw_url)
    target_host = parsed.hostname or settings.DB_HOST
    target_port = parsed.port or settings.DB_PORT
    target_db = parsed.path.lstrip("/").split("?")[0] if parsed.path else settings.DB_NAME
    target_user = parsed.username or settings.DB_USER
    qs = parse_qs(parsed.query) if parsed.query else {}
    target_ssl = qs.get("sslmode", [settings.DB_SSLMODE or "Default"])[0]

    print(f"\n[TARGET] Environment    : {settings.APP_ENV.upper()} (production={settings.IS_PRODUCTION})")
    print(f"         Connection URL : {masked_url}")
    print(f"         Database Host  : {target_host}")
    print(f"         Database Port  : {target_port}")
    print(f"         Database Name  : {target_db}")
    print(f"         Database User  : {target_user}")
    print(f"         SSL Mode       : {target_ssl}")
    print(f"         Pool Size      : {settings.DB_POOL_SIZE} (overflow: {settings.DB_MAX_OVERFLOW})")

    # Guard: Detect unreplaced template placeholders before opening network sockets
    placeholder_patterns = ["[", "]", "<", ">", "YOUR_PASSWORD", "YOUR-SUPABASE", "CHANGE_ME", "PROJECT-REF"]
    for pat in placeholder_patterns:
        if pat in raw_url:
            print(f"\n[FAIL] Incomplete database configuration:", file=sys.stderr)
            print(f"       Unreplaced template placeholder '{pat}' detected in connection target.", file=sys.stderr)
            print(f"       Please replace template placeholders with your real Supabase credentials.", file=sys.stderr)
            return False

    # Guard: Production environment cannot use localhost or loopback
    if settings.IS_PRODUCTION and target_host in ["localhost", "127.0.0.1", "::1"]:
        print(f"\n[FAIL] Production safety violation:", file=sys.stderr)
        print(f"       Production environment cannot connect to local database host '{target_host}'.", file=sys.stderr)
        return False

    # 1. Initialize SQLAlchemy Engine
    try:
        engine = create_engine(raw_url, pool_pre_ping=True)
    except Exception as exc:
        print(f"\n[FAIL] Engine initialization error: {exc}", file=sys.stderr)
        return False

    # 2. Test Live Connection & Query Execution
    print("\n--- 1. Connectivity Test ---")
    try:
        with engine.connect() as conn:
            ping_result = conn.execute(text("SELECT 1;")).scalar()
            if ping_result != 1:
                print(f"[FAIL] Unexpected ping result: {ping_result}", file=sys.stderr)
                return False
            print("[PASS] Connection established. 'SELECT 1;' returned successfully.")

            # Version check
            version_str = conn.execute(text("SELECT version();")).scalar()
            print(f"       PostgreSQL version: {version_str.split(',')[0] if version_str else 'Unknown'}")
    except Exception as exc:
        exc_str = str(exc)
        if "could not translate host name" in exc_str:
            print(f"[FAIL] DNS / Hostname translation failure for '{target_host}':", file=sys.stderr)
            print(f"       The host name could not be resolved. If this is a template (e.g. aws-0-[REGION]...),", file=sys.stderr)
            print(f"       ensure you have replaced the placeholder with your actual Supabase project region/host.", file=sys.stderr)
        else:
            print(f"[FAIL] Unable to connect to database: {exc}", file=sys.stderr)
        return False

    # 3. Check Required Extensions
    print("\n--- 2. Required Extensions Check ---")
    required_extensions = ["uuid-ossp", "postgis"]
    installed_extensions = {}
    try:
        with engine.connect() as conn:
            ext_rows = conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname IN ('uuid-ossp', 'postgis');")
            ).fetchall()
            for row in ext_rows:
                installed_extensions[row[0]] = row[1]

        all_extensions_installed = True
        for ext in required_extensions:
            if ext in installed_extensions:
                print(f"[PASS] Extension '{ext}' is INSTALLED (version: {installed_extensions[ext]}).")
            else:
                print(f"[WARN] Extension '{ext}' is NOT installed.", file=sys.stderr)
                all_extensions_installed = False

        if not all_extensions_installed:
            print(
                "\n[ACTION REQUIRED] In Supabase SQL Editor, execute:\n"
                "    CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";\n"
                "    CREATE EXTENSION IF NOT EXISTS postgis;",
                file=sys.stderr,
            )
    except Exception as exc:
        print(f"[WARN] Could not query pg_extension: {exc}", file=sys.stderr)

    # 4. Check Alembic Migration Status
    print("\n--- 3. Schema & Alembic Migration Status ---")
    try:
        insp = inspect(engine)
        table_names = insp.get_table_names()
        print(f"       Found {len(table_names)} tables in current schema.")

        if "alembic_version" in table_names:
            with engine.connect() as conn:
                current_rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            print(f"[PASS] Current Alembic schema version: {current_rev}")
            if current_rev == EXPECTED_HEAD_REVISION:
                print(f"[PASS] Database is up to date with target head ({EXPECTED_HEAD_REVISION}).")
            else:
                print(f"[INFO] Current revision ({current_rev}) does not match target head ({EXPECTED_HEAD_REVISION}).")
                print("       Apply pending migrations with: alembic upgrade head")
        else:
            print("[INFO] 'alembic_version' table not found. Fresh database detected.")
            print("       Run migrations to initialize schema: alembic upgrade head")
    except Exception as exc:
        print(f"[FAIL] Error checking schema tables: {exc}", file=sys.stderr)
        return False

    print("\n" + "=" * 65)
    print("[SUCCESS] Preflight diagnostics complete. Ready for operation.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CivicPulse Database Diagnostic")
    parser.add_argument("--url", type=str, default=None, help="Database connection URL")
    parser.add_argument("--env-file", type=str, default=None, help="Path to environment file (e.g. .env.production)")
    args = parser.parse_args()

    success = run_database_preflight(custom_url=args.url, env_file=args.env_file)
    sys.exit(0 if success else 1)
