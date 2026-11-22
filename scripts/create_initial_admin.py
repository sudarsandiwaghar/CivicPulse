"""
CivicPulse — Initial Administrator Provisioning Utility

Secure, standalone Python utility to create the initial municipal administrator
account for a new CivicPulse deployment without hardcoding credentials or
relying on database seeds.

Security design:
    - Never hardcodes passwords or credentials in script files.
    - Accepts credentials interactively via masked terminal input (getpass),
      or optionally via environment variables (INITIAL_ADMIN_EMAIL,
      INITIAL_ADMIN_PASSWORD, INITIAL_ADMIN_NAME) for headless automation.
    - Enforces strong password complexity requirements.
    - Utilizes application-standard bcrypt password hashing via passlib.
    - Idempotent: checks for existing administrator accounts to prevent duplicates.

Usage:
    Interactive mode:
        python scripts/create_initial_admin.py

    Automated / Headless mode:
        INITIAL_ADMIN_EMAIL="admin@city.gov" \
        INITIAL_ADMIN_PASSWORD="StrongSecurePassword123!" \
        INITIAL_ADMIN_NAME="Municipal Director" \
        python scripts/create_initial_admin.py
"""

import argparse
import getpass
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Ensure application root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.constants import UserRole
from app.core.security import hash_password
from app.db.session import get_engine, init_engine
from app.models.role import Role
from app.models.user import User


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


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate that the password satisfies minimum security complexity.
    Requirements:
        - At least 8 characters in length.
        - Contains at least one uppercase ASCII letter.
        - Contains at least one lowercase ASCII letter.
        - Contains at least one numeric digit (0-9).
        - Contains at least one special character.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_]", password):
        return False, "Password must contain at least one special character."
    return True, ""


def validate_email_format(email: str) -> bool:
    """Validate standard RFC 5322 email address format."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def create_initial_administrator(env_file: str | None = None) -> bool:
    """Prompt for administrator details and persist account securely."""
    print("=" * 65)
    print("CivicPulse — Initial Administrator Provisioning")
    print("=" * 65)

    if env_file:
        os.environ["ENV_FILE"] = env_file
    get_settings.cache_clear()
    settings = get_settings()

    raw_url = settings.DATABASE_URL
    parsed = urlparse(raw_url)
    target_host = parsed.hostname or settings.DB_HOST
    target_port = parsed.port or settings.DB_PORT
    target_db = parsed.path.lstrip("/").split("?")[0] if parsed.path else settings.DB_NAME

    print(f"\n[TARGET] Environment    : {settings.APP_ENV.upper()} (production={settings.IS_PRODUCTION})")
    print(f"         Database Host  : {target_host}")
    print(f"         Database Port  : {target_port}")
    print(f"         Database Name  : {target_db}")
    print(f"         Connection URL : {mask_database_url(raw_url)}")

    # Guard: Production environment cannot connect to local or test database
    if settings.IS_PRODUCTION and target_host in ["localhost", "127.0.0.1", "::1"]:
        print(f"\n[FAIL] Production safety violation:", file=sys.stderr)
        print(f"       Production environment cannot connect to local database host '{target_host}'.", file=sys.stderr)
        return False

    # 1. Read from environment or prompt interactively
    email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
    full_name = os.environ.get("INITIAL_ADMIN_NAME", "").strip()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD", "").strip()
    is_interactive = not (email and password and full_name)

    if is_interactive:
        print("\nEnter initial administrator credentials:\n")
        if not email:
            email = input("Administrator Email Address: ").strip()
        if not full_name:
            full_name = input("Administrator Full Name: ").strip()
        if not password:
            while True:
                password = getpass.getpass("Administrator Password: ").strip()
                valid, msg = validate_password_strength(password)
                if not valid:
                    print(f"Error: {msg}")
                    continue
                confirm = getpass.getpass("Confirm Password: ").strip()
                if password != confirm:
                    print("Error: Passwords do not match. Please re-enter.")
                    continue
                break
    else:
        valid, msg = validate_password_strength(password)
        if not valid:
            print(f"Error: Provided INITIAL_ADMIN_PASSWORD does not meet requirements: {msg}", file=sys.stderr)
            return False

    if not validate_email_format(email):
        print(f"Error: '{email}' is not a valid email address.", file=sys.stderr)
        return False

    if not full_name:
        print("Error: Administrator full name cannot be blank.", file=sys.stderr)
        return False

    # 2. Database connection & role resolution
    try:
        init_engine()
        engine = get_engine()
    except Exception as exc:
        print(f"Error connecting to database: {exc}", file=sys.stderr)
        return False

    with Session(engine) as db:
        admin_role = (
            db.query(Role)
            .filter(Role.name == UserRole.ADMINISTRATOR.value)
            .first()
        )
        if not admin_role:
            print(
                f"Error: '{UserRole.ADMINISTRATOR.value}' role not found in database. "
                "Ensure Alembic migrations have been applied: 'alembic upgrade head'",
                file=sys.stderr,
            )
            return False

        # 3. Check for existing account
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            if existing_user.role_id == admin_role.id:
                print(f"Notice: Administrator account '{email}' already exists. No changes made.")
                return True
            else:
                print(
                    f"Error: Account '{email}' exists with another role (Role ID: {existing_user.role_id}). "
                    "Use a dedicated administrator email address.",
                    file=sys.stderr,
                )
                return False

        # 4. Create and commit administrator account
        hashed_pw = hash_password(password)
        # Clear raw password from memory
        del password

        new_admin = User(
            email=email,
            hashed_password=hashed_pw,
            full_name=full_name,
            role_id=admin_role.id,
            is_active=True,
            is_verified=True,
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)

        print("\n[SUCCESS] Administrator account provisioned successfully.")
        print(f"  User ID : {new_admin.id}")
        print(f"  Email   : {new_admin.email}")
        print(f"  Name    : {new_admin.full_name}")
        print(f"  Role    : {UserRole.ADMINISTRATOR.value}")
        print(f"  Active  : {new_admin.is_active}")
        print(f"  Verified: {new_admin.is_verified}")
        print("\nStore your credentials in a secure municipal password vault.")
        print("=" * 65)
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CivicPulse Initial Administrator Provisioning")
    parser.add_argument("--env-file", type=str, default=None, help="Path to environment file (e.g. .env.production)")
    args = parser.parse_args()

    success = create_initial_administrator(env_file=args.env_file)
    sys.exit(0 if success else 1)
