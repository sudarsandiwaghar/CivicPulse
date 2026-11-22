# CivicPulse — Changelog

All notable changes to the CivicPulse project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [0.8.11] — 2026-11-22

### Verified & Prepared (Phase 8.11 — Render Free Backend Deployment Preparation & Blueprint Specification)

- **Pre-Deployment Runtime & Dependency Audit**:
  - Confirmed Python 3.11.9 runtime compatibility.
  - Confirmed `gunicorn>=22.0.0; sys_platform != "win32"` in `requirements.txt` installs Gunicorn on Linux while keeping local Windows development clean.
  - Confirmed `uvicorn[standard]>=0.54.0` provides the ASGI `uvicorn.workers.UvicornWorker` class.
- **Render Web Service Configuration & Blueprint (`render.yaml`)**:
  - Created root-level Render Blueprint `render.yaml` configuring `type: web`, `plan: free`, `runtime: python`.
  - Set build command to `pip install -r requirements.txt` (excluding automated migrations per project requirements).
  - Configured memory-conscious start command: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`.
  - Set health check path to `/api/v1/health`.
  - Defined canonical environment variables (`APP_ENV`, `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`, `ENABLE_DOCS`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `UPLOAD_DIR`, `LOG_LEVEL`).
- **Production Safeguards Verified**:
  - Confirmed `/api/v1/health` returns HTTP 200 with operational status.
  - Confirmed `/docs`, `/redoc`, and `/openapi.json` return HTTP 404 when `APP_ENV=production` or `ENABLE_DOCS=false`.
  - Confirmed production configuration enforces non-localhost database host (rejects `localhost`, `127.0.0.1`, `::1`).
  - Updated `FREE_DEPLOYMENT.md` to remove automated migrations during build.
- **Test Suite Results**:
  - Added 5 new automated tests in `tests/test_phase8_production.py` for Render configuration, blueprint validity, health endpoint, and docs toggle (45/45 passing).

---

## [0.8.10] — 2026-11-22

### Verified & Completed (Phase 8.10 — Secure Production Administrator Provisioning)

- **Role Compatibility Resolution**:
  - Queried active hosted `roles` table on Supabase: confirmed three canonical roles `CITIZEN` (ID 1), `ADMINISTRATOR` (ID 2), `FIELD_WORKER` (ID 3).
  - Reconciled with `app/core/constants.py` (`UserRole.ADMINISTRATOR`), seed migration `5c60c8914494`, and `require_admin` dependency.
  - Resolved that `ADMIN` is an enum alias mapping to `"ADMINISTRATOR"` and `STAFF` is an informal conceptual name not used in the database (`FIELD_WORKER` is the canonical role).
- **Provisioning Utility Verification (`scripts/create_initial_admin.py`)**:
  - Confirmed script creates users with exact `Role.name == UserRole.ADMINISTRATOR.value` (`"ADMINISTRATOR"`).
  - Confirmed password complexity validation (min 8 chars, uppercase, lowercase, digit, special char) and bcrypt hashing (`app.core.security.hash_password`).
  - Added target database preflight display with password masking and loopback/localhost rejection guard for production.
  - Added `--env-file` parameter support for explicit environment file selection.
- **Production Administrator Provisioned on Supabase**:
  - Connected to Supabase Session Pooler (`aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres`) via `.env.production`.
  - Provisioned administrator account `admin@civicpulse.gov` (`Municipal Administrator`).
  - Verified exactly 1 user exists in hosted `users` table with `is_active=True`, `is_verified=True`, role `ADMINISTRATOR` (Role ID: 2).
- **Authentication & Authorization Verified**:
  - Verified bcrypt password hash format (`$2b$`) and verification via Passlib.
  - Verified `authenticate_user` succeeds for valid credentials and rejects invalid credentials with `AuthenticationError`.
  - Verified JWT access token generation and claims decoding (`sub` UUID, `role: ADMINISTRATOR`).
  - Verified `require_admin` route dependency approves administrator access.
- **Local Database Preservation**:
  - Confirmed local development database (`localhost:5433/civicpulse`) remains at 0 users and 18 tables.
  - Confirmed local test database (`civicpulse_test`) remains at 0 users.
  - All 40 Phase 8 production tests passing.

---

## [0.8.9] — 2026-11-22

### Verified & Completed (Phase 8.9 — Actual Supabase Connection, Hosted Schema Initialization & Verification)

- **Supabase Cloud Database Connectivity Established**:
  - Connected securely to Supabase PostgreSQL Session Pooler (`aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres`) with TLS (`sslmode=require`).
  - Confirmed target server version: PostgreSQL 17.12 on aarch64-unknown-linux-gnu.
- **Geospatial & UUID Extensions Initialized**:
  - Confirmed extension `uuid-ossp` (version 1.1) installed.
  - Enabled extension `postgis` (version 3.3.7) via direct SQL initialization.
- **Hosted Schema Initialized via Alembic**:
  - Executed complete Alembic migration sequence (`001` through `007`) targeting head revision `b7c8d9e0f1a2`:
    - `001_initial_schema` (`dc808166f213`)
    - `002_seed_initial_roles` (`5c60c8914494`)
    - `003_seed_departments_categories_and_seq` (`7f3a8b2c4d1e`)
    - `004_assignment_enhancements_and_progress` (`8d2e4f6a1c3b`)
    - `005_public_visibility_and_followers` (`9e1f2a3b4c5d`)
    - `006_sla_management_and_escalation` (`a4b5c6d7e8f9`)
    - `007_notification_event_keys` (`b7c8d9e0f1a2`)
  - Verified 18 application tables created + `spatial_ref_sys` (19 tables total).
  - Verified initial seed data on Supabase: 3 roles, 5 departments, 7 categories.
- **Dual-Database Environment Isolation Preserved**:
  - Verified local development PostgreSQL 18.7 database (`localhost:5433/civicpulse`) remains at `b7c8d9e0f1a2` with 18 tables, completely untouched.
  - Local test database (`localhost:5433/civicpulse_test`) remains intact.
  - All 40 unit and preflight tests in `tests/test_phase8_production.py` passing cleanly.
- **Dynamic Environment Resolution (`app/config.py`)**:
  - Enhanced `get_settings()` with intelligent multi-tier environment file resolution: respects `ENV_FILE` if set, loads `.env.production` when `APP_ENV=production` and `.env.production` exists, and safely defaults to `.env` for local development.
- **Table Count Discrepancy Resolved**:
  - Confirmed and documented the exact 18 application tables: `ai_assessments`, `alembic_version`, `assignment_progress`, `assignments`, `attachments`, `categories`, `complaint_followers`, `complaint_sla_history`, `complaint_status_history`, `complaints`, `departments`, `feedback`, `locations`, `notifications`, `roles`, `sla_policies`, `users`, `workers`.

---

## [0.8.8] — 2026-11-22

### Verified & Documented (Phase 8.8 — Supabase Hosted PostgreSQL Connection & Initial Migration Preflight)

- **Source of Truth Alembic Migration Chain Audit**:
  - Parsed all 7 actual migration files (`001_initial_schema.py` through `007_notification_event_keys.py`) directly from the filesystem.
  - Confirmed unbroken linear chain: `dc808166f213` &rarr; `5c60c8914494` &rarr; `7f3a8b2c4d1e` &rarr; `8d2e4f6a1c3b` &rarr; `9e1f2a3b4c5d` &rarr; `a4b5c6d7e8f9` &rarr; `b7c8d9e0f1a2 (head)`.
  - Confirmed seed data structure: initial roles/permissions (002), departments/categories/sequence (003), progress tracking (004), followers (005), SLA policies (006), notification event keys (007).
- **Security & Secret File Verification**:
  - Verified `.gitignore` blocks `.env`, `.env.*`, `*.env.local`, `*.pem`, `*.key` with zero leaks.
  - Re-verified safe password masking in `scripts/verify_db_connection.py`.
- **Preflight Isolation & Stop Condition Compliance**:
  - Preserved local development database `localhost:5433/civicpulse` (18 tables, revision `b7c8d9e0f1a2`) and test database `civicpulse_test`.
  - Strictly observed stop condition: did not invent credentials, did not execute migrations against an unidentified database, and did not deploy to Render or Cloudflare.
- **Runbook Enhancement (`FREE_DEPLOYMENT.md`)**:
  - Updated Section 9 with detailed PowerShell and `.env.production` commands for running migrations and diagnostics on Supabase Session Pooler.

---

## [0.8.7] — 2026-11-22

### Fixed & Verified (Phase 8.7 — Database Environment Isolation Fix + Frontend Completion)

- **Database Configuration Consistency & Parameter Synchronization (`app/config.py`)**:
  - Implemented automatic attribute synchronization in `@model_validator(mode="after")`: when `DATABASE_URL` is set, individual fields (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE`) are dynamically updated from the parsed URL.
  - Resolved root cause of diagnostic inconsistency where host showed `localhost` while psycopg2 connected to the remote/placeholder URL.
- **Template Placeholder Rejection (`check_for_unreplaced_placeholders`)**:
  - Added programmatic detection for unreplaced placeholders (`[`, `]`, `<`, `>`, `[REGION]`, `[PROJECT-REF]`, `[PASSWORD]`, `CHANGE_ME`).
  - Rejects incomplete connection strings immediately with a clear, descriptive `ValueError`, preventing failed DNS lookups (`could not translate host name`).
- **Production Mode Localhost Guard**:
  - Added strict production validator blocking `APP_ENV=production` from connecting to `localhost`, `127.0.0.1`, or `::1`, preventing any silent fallback to local databases in production.
- **Diagnostic Tool Upgrade (`scripts/verify_db_connection.py`)**:
  - Displays effective connection parameters extracted directly from the engine URL (Host, Port, Database, User, SSL mode).
  - Clears cached settings on invocation and provides descriptive DNS resolution failure guidance.
- **Alembic Environment Safety (`alembic/env.py`)**:
  - Added placeholder validation and driver prefix normalization for custom `-x db_url=...` overrides.
- **Frontend Verification & Health Audit**:
  - Verified Citizen, Administrator, and Field Worker portals against FastAPI endpoints.
  - Verified 100% JavaScript ES6+ / JSX architecture, in-memory JWT authentication, 0 localStorage tokens, and approved design palette.
  - Verified clean Vite build in 266ms, 0 lint errors, and 408/408 backend tests passing.

---

## [0.8.6] — 2026-11-22

### Validated & Configured (Phase 8.6 — Hosted Supabase Database Initialization)

- **Diagnostic CLI Enhancements (`scripts/verify_db_connection.py`)**:
  - Enhanced standalone preflight utility with support for `--url` (direct connection string) and `--env-file` (e.g., `.env.production`) flags.
  - Isolated engine creation (`create_engine(..., pool_pre_ping=True)`) preventing side-effects or mutation of the global application engine singleton.
  - Verified robust password masking (`:****@`) for all connection string variants.
- **Local Database Environment Preservation**:
  - Verified local PostgreSQL 18.7 instance on `localhost:5433` remains completely untouched with 18 tables and Alembic revision `b7c8d9e0f1a2`.
  - Zero development or test records copied, dropped, or modified.
- **Automated Verification Suite (`tests/test_phase8_production.py`)**:
  - Added unit tests verifying password masking and parameter parsing (33/33 tests passing in file; 400 tests passing project-wide).
- **Hosted Migration Preflight Readiness**:
  - Verified Alembic dynamic configuration (`alembic/env.py`) ready to execute `alembic upgrade head` upon injection of the hosted Supabase Session Pooler `DATABASE_URL`.

---

## [0.8.5] — 2026-11-21

### Validated & Configured (Phase 8.5 — Dual-Environment Database Setup & Free Cloud Deployment Preparation)

- **Dual-Environment Database Safeguards (`app/config.py`)**:
  - Implemented `@model_validator(mode="after")` enforcing strict separation between local development and production environments.
  - Added programmatic guards preventing production mode (`APP_ENV=production`) from booting against test databases (blocking databases named `*_test` or `test` via `DB_NAME` or `DATABASE_URL`).
  - Guaranteed zero silent fallbacks from failed remote production database connections to local instances.
- **Dual-Environment Architecture in Runbook (`FREE_DEPLOYMENT.md`)**:
  - Restructured runbook into a complete dual-environment guide: Section 2 detailing local PostgreSQL 18 setup on `localhost:5433` (`civicpulse` and `civicpulse_test`), and Sections 3–10 detailing hosted Supabase, Render, and Cloudflare Pages setup.
  - Added unified migration reference (Section 9) detailing local and hosted migration commands.
- **Automated Dual-Environment Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase85DualEnvironmentSafeguards` with 4 new tests validating test-database production blocking, development environment permission, and local settings isolation (31/31 tests passing in file).

---

## [0.8.4] — 2026-11-21

### Validated & Prepared (Phase 8.4 — Supabase Database Connection & Migration Readiness)

- **Production Database Secret Protection (`.gitignore`)**:
  - Hardened `.gitignore` to comprehensively block `.env`, `.env.*`, `*.pem`, `*.key`, and `*.env.local` while strictly preserving tracking for `.env.example` and `.env.production.example`. Verified via `git check-ignore`.
- **Database Preflight & Diagnostic Tooling (`scripts/verify_db_connection.py`)**:
  - Implemented standalone preflight diagnostic utility that verifies live PostgreSQL connection via `SELECT 1;`, inspects installed extensions (`uuid-ossp`, `postgis`), verifies Alembic schema migration versions against target head (`b7c8d9e0f1a2`), and masks sensitive credentials in output logs (`:****@`).
- **Alembic Linear Migration Chain Verification**:
  - Verified all seven migrations form an unbroken, non-branching linear chain from root (`dc808166f213`) to head (`b7c8d9e0f1a2`).
  - Confirmed all migrations use standard PostgreSQL types (`UUID`, `Float`, `DateTime(timezone=True)`), check constraints, and plpgsql triggers (`prevent_sla_history_mutation()`), fully supported on Supabase PostgreSQL.
- **Supabase Session Pooler & SSL Compatibility**:
  - Verified that Supabase Session Pooler connection strings (Port 5432, `aws-0-[region].pooler.supabase.com`, `sslmode=require`) are correctly parsed by SQLAlchemy and psycopg2.
- **Automated Verification Suite (`tests/test_phase8_production.py`)**:
  - Added 4 new tests in `TestPhase84SupabaseMigrationReadiness` validating gitignore secret rules, Supabase URL parsing and password masking, unbroken 7-migration linear chain, and preflight diagnostic contracts (27/27 tests passing in file).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

## [0.8.2] — 2026-11-21

### Added & Validated (Phase 8.2 — Free-Tier Demonstration Deployment Preparation)

- **Cloudflare Pages SPA Configuration (`frontend/public/`)**:
  - Added `_redirects` (`/* /index.html 200`) enabling seamless React Router v7 deep linking across all pages (`/login`, `/citizen/report`, `/admin/map`, etc.) on Cloudflare Pages.
  - Added `_headers` establishing production security headers and configuring Content Security Policy (`connect-src 'self' https://*.onrender.com;`) allowing the static frontend to communicate with Render backend APIs while keeping other origins restricted.
  - Added 1-year immutable caching rules for `/assets/*` fingerprint chunks.
- **Render Backend Web Service Compatibility (`requirements.txt`)**:
  - Added `gunicorn>=22.0.0; sys_platform != "win32"` to `requirements.txt` using PEP 508 environment markers. Render's Linux environment automatically installs Gunicorn, while Windows local development environments completely ignore it with zero installation errors.
  - Documented Render dynamic `$PORT` binding (`gunicorn ... --bind 0.0.0.0:$PORT` and `uvicorn ... --host 0.0.0.0 --port $PORT`).
  - Documented automatic migration execution during Render build phase (`pip install -r requirements.txt && alembic upgrade head`).
  - Documented Render free-tier cold-start behaviors (50–90 second spin-up after 15 minutes of inactivity) and ephemeral local disk limitations.
- **Supabase Managed PostgreSQL & PostGIS Integration**:
  - Verified compatibility with Alembic migrations 001–007 and existing SQLAlchemy models.
  - Resolved Render IPv4 networking limitation with Supabase by mandating the Supavisor Connection Pooler (`aws-0-[region].pooler.supabase.com` on Port 5432 Session Mode), avoiding IPv6-only direct connection failures.
  - Documented free-tier database limits (500 MB capacity, 7-day inactivity pausing policy, and manual backup export options).
- **Comprehensive Free-Tier Deployment Runbook (`FREE_DEPLOYMENT.md`)**:
  - Authored complete, step-by-step dashboard configuration guide covering Supabase setup, Render service creation and environment variables, administrator provisioning, and Cloudflare Pages git integration.
  - Preserved existing VPS deployment guide (`DEPLOYMENT.md`) intact.
- **Automated Validation Suite (`tests/test_phase8_production.py`)**:
  - Added 4 new automated unit tests validating `_redirects`, `_headers`, Gunicorn PEP 508 environment marker in `requirements.txt`, and `FREE_DEPLOYMENT.md` completeness (19/19 passed in test file).

---

---

## [0.8.1] — 2026-11-21

### Validated & Hardened (Phase 8.1 — Deployment Runbook Validation & Launch Preparation)

- **Deployment Runbook Hardening (`DEPLOYMENT.md`)**:
  - **Certbot Bootstrap Chicken-and-Egg Prevention**: Clarified certificate acquisition using Certbot standalone mode prior to enabling HTTPS Nginx configuration, preventing `nginx -t` startup crashes on non-existent `.pem` files.
  - **Data Loss Prevention in Database Restoration**: Added strict preconditions: automated pre-restoration safety snapshot, archive integrity verification (`pg_restore --list`), peer authentication execution (`sudo -u postgres`), and public schema permission checks.
  - **Alembic Downgrade Risk & Destructive Migration Documentation**: Documented that migrations 004, 005, 006, and 007 drop tables and columns (`assignment_progress`, `complaint_followers`, `complaint_sla_history`, `event_key`); prohibited routine downgrades and established code-only rollbacks or database restoration as safe alternatives.
- **Nginx Reverse Proxy Hardening (`deploy/nginx/civicpulse.conf`)**:
  - **HSTS Preload Removal**: Removed `preload` from `Strict-Transport-Security` header to prevent unintended irreversible domain-wide HSTS lockouts on municipal subdomains.
  - **Health Check Routing Fix**: Corrected Nginx `/health` proxy target to `/api/v1/health` where FastAPI mounts the health endpoint, ensuring external uptime probes succeed with HTTP 200.
  - **Static Asset Security Header Inheritance**: Preserved `X-Content-Type-Options: nosniff` and `Strict-Transport-Security` on `/assets/` and `/uploads/` locations.
  - **Upload Directory Script Execution Defense**: Moved executable script blocking to top-level regex rule, avoiding nested alias location parsing issues in Nginx.
  - **Trailing Slash Handling**: Added explicit handling for `/api/v1` without trailing slash.
- **Systemd Daemon Hardening (`deploy/systemd/civicpulse-backend.service`)**:
  - Added `Environment="PYTHONDONTWRITEBYTECODE=1"` and `Environment="PYTHONUNBUFFERED=1"` to prevent bytecode compilation attempts in read-only filesystems under `ProtectSystem=strict`.
  - Added `LogsDirectory=civicpulse` for automatic creation of `/var/log/civicpulse` with correct permissions.
- **Automated Validation Suite (`tests/test_phase8_production.py`)**:
  - Added unit and integration tests verifying Nginx HSTS policy, CSP allowlist, health proxy routing, systemd security directives, and headless initial admin provisioning on fresh test databases with full idempotency verification (15/15 passed).

---

---

## [0.8.0] — 2026-11-21

### Added & Hardened (Phase 8.0 — Production Deployment Preparation)

- **Environment-Aware Configuration (`app/config.py`)**:
  - Introduced `APP_ENV` (`development`, `staging`, `production`) with `IS_PRODUCTION` boolean helper property.
  - Introduced configurable `ENABLE_DOCS` setting and `DOCS_ENABLED` property that automatically disables `/docs`, `/redoc`, and `/openapi.json` in production environments while maintaining them in development.
  - Added dynamic, resilient `CORS_ORIGINS` validator supporting both comma-delimited strings and JSON array strings.
  - Added configurable SQLAlchemy database connection pool settings: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, and `DB_SSLMODE`.
  - Updated `DATABASE_URL` property to automatically append `?sslmode=<mode>` for secure managed database cluster connections.
- **Backend Application Hardening (`app/main.py` & `app/db/session.py`)**:
  - Wired conditional Swagger UI, ReDoc, and OpenAPI endpoints based on `settings.DOCS_ENABLED`.
  - Replaced hardcoded localhost CORS with dynamic `allow_origins=settings.CORS_ORIGINS`.
  - Added global unhandled exception handler (`@app.exception_handler(Exception)`) logging sanitized tracebacks server-side and returning uniform HTTP 500 error envelopes without internal code path or database schema leakage.
  - Updated SQLAlchemy engine initialization in `app/db/session.py` to utilize environment-configured connection pool parameters.
- **Initial Administrator Account Provisioning (`scripts/create_initial_admin.py`)**:
  - Implemented standalone Python CLI utility to safely provision the initial municipal administrator account without storing passwords in seeds or code.
  - Supports interactive masked terminal input via `getpass` as well as headless CI/CD environment variable automation (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`).
  - Enforces strong password complexity validation (min 8 chars, uppercase, lowercase, digit, special symbol).
  - Implements idempotent account checks preventing unintended overwrites.
- **Production Deployment Packaging**:
  - Created `.env.production.example` root template with comprehensive comments and placeholder values.
  - Created `frontend/.env.production.example` template with relative `/api/v1` API base URL and optional municipal coordinate center parameters.
  - Created `requirements-prod.txt` extending base dependencies with `gunicorn>=22.0.0` for Linux ASGI worker process management.
  - Authored production Nginx reverse proxy configuration (`deploy/nginx/civicpulse.conf`) featuring TLS 1.2/1.3, HTTP/2, HSTS, CSP, X-Frame-Options, SPA routing (`try_files`), immutable asset caching (`/assets/`), and buffered API proxying with 15MB file upload support.
  - Authored hardened systemd service unit (`deploy/systemd/civicpulse-backend.service`) executing Gunicorn with 4 Uvicorn workers under unprivileged user `civicpulse` with `ProtectSystem=strict` and sandboxed private temporary files.
- **Comprehensive Production Deployment Guide (`DEPLOYMENT.md`)**:
  - Authored complete, production-ready operational runbook covering system architecture, VPS sizing for small/medium/large municipalities, server provisioning and UFW firewall hardening, PostgreSQL 16+ / PostGIS setup, Alembic migrations, administrator provisioning, systemd backend management, frontend compilation and Nginx reverse proxy hosting, automated Certbot SSL renewal, nightly database and upload backup/restoration runbooks, and zero-downtime deployment/rollback procedures.
- **Quality & Constraint Verification**:
  - Frontend production build (`npm run build`) verified clean in 470ms.
  - Frontend linter (`npm run lint`) verified with 0 errors.
  - Strict compliance verified: zero `.sh`, `.ps1`, or `.bat` script files; 100% pure JavaScript ES6+ / JSX; strictly in-memory JWT authentication (zero `localStorage`/`sessionStorage` tokens); zero changes to database models or Alembic migrations.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.9.1] — 2026-11-21

### Verified & Audited (Phase 7.9.1 — Browser-Based Acceptance Verification, Test Data Cleanup & Release Sign-Off)

- **Live Asset & Server Delivery Verification**:
  - Probed live FastAPI backend at `http://127.0.0.1:8000/api/v1/health` (verified HTTP 200 OK with `healthy` status).
  - Probed live Vite preview server at `http://127.0.0.1:5173/` and verified delivery of HTML shell and preloaded modules.
  - Verified all 53 compiled frontend JavaScript chunk assets (`dist/assets/*.js`) delivered with HTTP 200 OK and valid MIME types, with zero 404 missing chunks.
- **Test Data Audit & Cleanup**:
  - Audited PostgreSQL development database (`civicpulse`): confirmed 0 complaints existed and all seed departments and categories remained intact.
  - Safely deleted Phase 7.9 temporary test data (worker `EMP-TEST-001` and user accounts `worker@civicpulse.org`, `admin@civicpulse.org`, `citizen@example.com`) via `scratch/cleanup_phase7_9_test_data.py`.
  - Confirmed development database users table returned to pristine state (0 users).
- **Environment & Browser Testing Status**:
  - Documented Chrome DevTools protocol limitation resulting from Windows host Chrome user session isolation preventing remote debugging attachment.
  - Accurately recorded live browser driving as `BLOCKED` due to host Chrome environment boundaries, and viewports as `NOT TESTED` for live browser automation, while verifying static responsive styling and media query structure (`<= 900px`).
- **Regression Suite Sign-Off**:
  - Frontend production build (`npm run build`) verified clean in 550ms.
  - Frontend linter (`npm run lint`) verified with 0 errors and 24 non-blocking React compiler effect warnings.
  - 100% pure JavaScript ES6+ / JSX compliance re-verified (0 TypeScript files).
  - Pure in-memory JWT handling re-verified (0 localStorage/sessionStorage tokens).
  - Full backend test suite passing (`369/369` tests across 12 files).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.9] — 2026-11-21

### Added & Verified (Phase 7.9 — End-to-End User Journeys, Acceptance Testing & Release Readiness)

- **Comprehensive Multi-Role Acceptance Testing**:
  - **Citizen Journey**: Executed end-to-end registration, authentication, personal dashboard retrieval, category selection, coordinate validation (invalid lat > 90 rejected with HTTP 422), complaint creation with deliberate coordinates (`CP-2026-10044`), directory retrieval, complaint dossier, status audit trail, and unified timeline.
  - **Administrator Journey**: Verified admin authentication, complaint review and triage (`UNDER_REVIEW`, priority adjustment to `HIGH`), rejection of ineligible/inactive worker assignments, active worker dispatch (`ASSIGNED`), SLA policies directory, dual-clock complaint SLA details, explicitly confirmed on-demand SLA batch evaluation (`POST /admin/sla/evaluate`), and public moderation publishing.
  - **Field Worker Journey**: Verified worker authentication, assigned task queue (`/workers/me/tasks`), task detail inspection, assignment acknowledgment (`accepted_at`), work start (`IN_PROGRESS`), progress update recording (`HTTP 201`), and work completion (`COMPLETED`), successfully triggering complaint transition to `RESOLVED_AWAITING_VERIFICATION`.
  - **Complete Cross-Role Resolution Lifecycle**: Validated citizen verification and closure (`CLOSED`), as well as citizen reopen validation within the 14-day resolution window (`REOPENED`).
  - **Negative & Security Tests**: Verified strict role-based access control (citizens blocked from worker and admin routes with HTTP 403; workers blocked from admin routes with HTTP 403), unauthenticated access rejected (HTTP 401), invalid JWT tokens rejected (HTTP 401), and public feed privacy invariants verified (zero PII, emails, or phone numbers leaked).
  - **Community & Notifications**: Authenticated citizen following and unfollowing of public complaints, followed feed listing, and notification retrieval with single and bulk mark-as-read operations.
- **Frontend Bundle Optimization & Code Splitting**:
  - Implemented route-level dynamic code splitting using `React.lazy()` and `Suspense` in `AppRoutes.jsx`.
  - Reduced initial bundle size from **759.53 kB** to **289.88 kB** (89.82 kB gzip), achieving a **61.8% initial load size reduction**.
  - Isolated Leaflet and page chunk dependencies into dynamic async chunks loaded strictly on demand.
  - Fixed `STATUS_COLORS` import path in `ComplaintMapMarker.jsx`.
- **Quality & Regression Results**:
  - Frontend: Clean Vite production build in 238ms; 0 linter errors (`oxlint`); 100% pure JavaScript ES6+ / JSX compliance.
  - In-memory JWT handling strictly verified with 0 `localStorage` or `sessionStorage` persistence.
  - Backend: 369 / 369 tests passing across all 12 test files (`pytest tests/`).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.8] — 2026-11-21

### Added & Audited (Phase 7.8 — Full-System Integration, Security, Accessibility & Production Readiness Audit)

- **API & Client Integration Fixes**:
  - `categoryService.js`: Added `getCategories()` alias matching caller signatures across administrative modals, complaint triage, public moderation, and SLA policy creation.
  - `CitizenComplaintMapPage.jsx` & `AdminComplaintMapPage.jsx`: Rectified paginated payload unwrapping to support backend `res.data` array structure.
- **Geospatial & Map Configuration**:
  - Eliminated hardcoded Bengaluru coordinates and default city assumptions; configured neutral national overview (`[20.5937, 78.9629]`, zoom 5) with optional `VITE_MUNICIPAL_*` environment overrides.
  - Required deliberate citizen incident location selection; unpinned initial state prevents unintentional default location reporting.
  - `AdminComplaintMapPage.jsx`: Added explicit dataset sample indicators distinguishing the visible map subset (up to 100) from total matching platform complaints.
- **Security & Authorization Hardening**:
  - Implemented `ConfirmationDialog` before executing on-demand SLA batch evaluations, warning of backend state mutations and clarifying the non-daemon execution model.
  - Verified in-memory JWT authentication storage without `localStorage` or `sessionStorage` persistence.
  - Confirmed all external navigation links include `target="_blank" rel="noopener noreferrer"` preventing reverse tabnabbing.
  - Verified 0 `console.log` statements throughout frontend source code.
- **Accessibility & Focus Management**:
  - Added `Escape` key keyboard dismissal and explicit `aria-label="Close dialog"` across `ConfirmationDialog`, `AssignmentModal`, `TriageActionModal`, and `PublicModerationModal`.
  - Confirmed input labels, helper text, and error messages use semantic `aria-invalid` and `aria-describedby` associations.
- **Code Quality & Build Optimization**:
  - Extracted `AuthContext` to `AuthContextObject.js` resolving React Fast Refresh warnings.
  - Cleaned unused imports in `AdminComplaintsPage.jsx` and `MapLegend.jsx`.
  - Achieved clean production build (`vite build` in 692ms) and 0 linter errors (`oxlint`).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.7] — 2026-11-21

### Added & Integrated (Phase 7.7 — Maps, Geolocation & Location-Based Complaint Visualization)

- **Map Library & Design System**:
  - Integrated Leaflet 1.9.4 and OpenStreetMap standard cartographic tiles without proprietary API keys.
  - Custom SVG DivIcon pin factories (`createStatusIcon`, `createPickerIcon`) color-coded to each complaint lifecycle state.
  - Interactive map container, responsive grid, popup card templates, and visual status legend.
  - Strict WGS84 coordinate bounds validator (`isValidCoordinate`) verifying `[-90, 90]` latitude and `[-180, 180]` longitude.
- **Citizen Incident Location Pinpointing (`LocationPicker.jsx`, `CitizenReportPage.jsx`)**:
  - Embedded interactive Leaflet map picker inside the complaint filing workflow.
  - Draggable pinpoint marker with real-time coordinate synchronization to latitude/longitude inputs.
  - Native browser GPS detection via `navigator.geolocation.getCurrentPosition` with comprehensive error handling (permission denied, timeout, unavailable).
  - Reset to municipal city center action.
- **Citizen Complaint Map (`CitizenComplaintMapPage.jsx`)**:
  - Dedicated authenticated citizen view at `/citizen/map` rendering all submitted complaints geographically.
  - Status filter dropdown and real-time search input.
  - Interactive popup cards with reference codes, categories, status badges, and direct links to `/citizen/complaints/:id`.
  - Responsive incident feed sidebar highlighting individual complaint pins on click.
- **Administrator Geographic Intelligence Dashboard (`AdminComplaintMapPage.jsx`)**:
  - Citywide geospatial complaint visualization at `/admin/map` supporting municipal operations.
  - Multi-faceted filter toolbar: Status, Priority, Category, Ward/Area, and full-text search.
  - Dynamic Ward Hotspots breakdown ranking municipal areas by incident count with one-click ward filtering.
  - Pinpoint Inspector drawer providing granular metadata and direct access to `/admin/complaints/:id`.
  - High-level geospatial telemetry cards: Total complaints, Mapped pins, Critical/High count, and Primary hotspot ward.
- **Field Worker Incident Location & Navigation (`WorkerTaskDetailPage.jsx`)**:
  - Embedded Leaflet map in the "Incident Location & Field Access" work order view.
  - Direct external navigation link (`https://maps.google.com/?q=${lat},${lng}`) allowing field technicians to navigate to the exact incident site.
- **Strict Privacy Invariant Verification**:
  - Re-verified public complaint schemas (`/api/v1/public/complaints`) ensuring exact coordinates (`latitude`, `longitude`) and residential addresses are strictly redacted to protect citizen privacy.
- **Navigation & Routing**:
  - Added "Complaints Map" (`/citizen/map`) to citizen navigation.
  - Added "Geographic Map" (`/admin/map`) to administrator navigation.
  - Registered protected routes in `AppRoutes.jsx` under `CITIZEN` and `ADMINISTRATOR` RBAC guards.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.6] — 2026-11-21

### Added & Integrated (Phase 7.6 — SLA Monitoring, Policy Management & Notification Center)

- **Dedicated API Service Layers**:
  - `slaService.js`: Full integration with SLA policy listing (`GET /api/v1/admin/sla/policies`), policy creation (`POST /api/v1/admin/sla/policies`), policy update (`PATCH /api/v1/admin/sla/policies/{id}`), bounded on-demand batch evaluation (`POST /api/v1/admin/sla/evaluate`), complaint SLA details (`GET /api/v1/admin/sla/complaints/{id}`), and completed cycle history (`GET /api/v1/admin/sla/complaints/{id}/history`).
  - `notificationService.js`: Cross-role in-app notification client supporting paginated inbox retrieval (`GET /api/v1/notifications`), unread badge counter (`GET /api/v1/notifications/unread-count`), individual read mutation (`PATCH /api/v1/notifications/{id}/read`), and bulk read mutation (`POST /api/v1/notifications/read-all`).
- **Administrator SLA Monitoring Dashboard (`AdminSLADashboardPage.jsx`)**:
  - Live dual-clock oversight distinctly separating Response SLA (initial triage) and Resolution SLA (field remediation) without fabricated metrics.
  - Interactive overview cards showing real counts of cases within target, approaching warning threshold (75%), and breached (&ge;100%).
  - Bounded on-demand batch evaluation trigger allowing administrators to evaluate up to 100 active complaints dynamically.
  - Dedicated watch queues: Response Watch (pending triage), Resolution Watch (active remediation), Escalated & Overdue (Level &ge; 1), and Paused Cases (frozen in `ON_HOLD`).
  - Server-side and client-side filtering by lifecycle status, priority, category, and escalation severity.
- **SLA Policy Management (`AdminSLAPoliciesPage.jsx`)**:
  - Complete policy directory displaying configured response and resolution target hours, scope, and activation status.
  - Precedence rule guidance illustrating resolution hierarchy: (Category + Priority) > Category Specific > Priority Specific > Global Default.
  - Create SLA Policy modal with positive duration validation and database conflict handling.
  - Edit SLA Policy modal supporting target duration updates and activation toggling.
- **Role-Aware Notification Center (`NotificationsPage.jsx`, `NotificationBell.jsx`, `NotificationItem.jsx`)**:
  - `NotificationBell.jsx`: Reusable header bell with live unread counter badge and automatic refresh on window focus.
  - `NotificationItem.jsx`: Distinct visual styling and semantic icons across 9 event types (`STATUS_CHANGE`, `ASSIGNMENT`, `RESOLUTION_SUBMITTED`, `COMPLAINT_REOPENED`, `SLA_WARNING`, `SLA_BREACH`, etc.) with role-aware target routing.
  - `NotificationsPage.jsx`: Centralized in-app inbox supporting Citizens, Field Workers, and Administrators with Unread Only filter, pagination, and "Mark All as Read" action.
- **Navigation & Routing**:
  - Corrected worker sidebar navigation from `/citizen/notifications` to the shared `/notifications` route.
  - Configured protected `/notifications` route accessible to all authenticated roles.
  - Added SLA Monitoring (`/admin/sla`) and SLA Policies (`/admin/sla/policies`) to administrator navigation.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.5] — 2026-11-21

### Added & Integrated (Phase 7.5 — Administrator Portal: Dashboard, Complaint Triage, Workforce & Department Management)

- **Administrative API Services**:
  - `departmentService.js`: Full CRUD lifecycle integration with `GET /api/v1/departments/`, `GET /api/v1/departments/{id}`, `POST /api/v1/departments/`, `PATCH /api/v1/departments/{id}`, and `PATCH /api/v1/departments/{id}/deactivate`.
  - `adminService.js`: Comprehensive administrative operations integrating complaint triage (`listComplaints`, `getComplaint`, `reviewComplaint`, `transitionComplaint`, `getComplaintTimeline`), assignments (`assignComplaint`, `reassignComplaint`, `getComplaintAssignments`, `listAllAssignments`), workforce management (`listWorkers`, `getWorker`, `createWorker`, `updateWorker`, `deactivateWorker`), public content moderation (`moderatePublic`), complaint SLA inspection (`getComplaintSLA`), and platform-wide dashboard metric aggregation (`getDashboardMetrics`).
- **Administrative Modals & Operational Controls**:
  - `AssignmentModal.jsx`: Modal dialog for initial field worker dispatch and technician reassignment with department-matched worker selection, availability filtering, and mandatory reason enforcement on reassignment.
  - `TriageActionModal.jsx`: Dialog supporting formal administrative state transitions, complaint rejection with mandatory justification, duplicate tagging with original complaint UUID verification, priority level adjustments, and category reclassifications.
  - `PublicModerationModal.jsx`: Modal for publishing complaints to the community feed, modifying approved public headlines and narratives (enforcing 5–200 title / 10–2000 description character limits), or revoking public visibility.
- **Administrator Dashboard (`AdminDashboardPage.jsx`)**:
  - Live operational metrics: Total Complaints, Pending Initial Triage, Under Review, Dispatched (Assigned), In Progress, Awaiting Citizen Verification, Closed, and Rejected / Duplicates.
  - "Complaints Requiring Immediate Attention" section surfacing high-priority and urgent complaints needing review or reassignment.
  - "Recent Inflow & Triage Queue" offering quick triage transitions directly from the dashboard overview.
- **Complaint Management & Triage Center (`AdminComplaintsPage.jsx`)**:
  - 8 lifecycle status tabs: All, Pending Triage, Under Review, Dispatched, In Progress, Awaiting Verification, Closed & Resolved, and Rejected / Duplicate.
  - Server-side pagination, category filter dropdown, priority filter dropdown, and keyword search.
- **Complaint Dossier & Audit View (`AdminComplaintDetailPage.jsx`)**:
  - Comprehensive inspection view with complaint specification, reporting citizen details, locality, and GPS coordinates with external map link.
  - Tabbed operational history: Chronological Milestone Timeline (`ComplaintTimeline`), Immutable Status Transitions Audit Table, and Field Technician Assignments History.
  - Dual-clock SLA performance card detailing response and resolution deadlines, pause durations, escalation levels, and breach statuses.
  - Public feed visibility card with direct moderation triggers.
- **Municipal Workforce Management (`AdminWorkersPage.jsx`)**:
  - Workforce roster listing all field technicians with employee badge IDs, department assignments, contact info, employment status (`ACTIVE`, `ON_LEAVE`, `INACTIVE`), and dispatch readiness indicators.
  - Provision Field Worker modal creating an authenticated user account with `FIELD_WORKER` role and linked worker profile.
  - Edit Field Worker modal and deactivation confirmation dialog.
- **Municipal Departments Directory (`AdminDepartmentsPage.jsx`)**:
  - Department management table displaying unique uppercase codes, names, contact channels, linked categories count, linked technician count, and active status.
  - Create Department modal with alphanumeric code validation, Edit modal, and deactivation dialog.
- **Public Feed Moderation Directory (`AdminModerationPage.jsx`)**:
  - Moderation queue listing published and unlisted complaints with quick publish, update, and revoke controls.
- **Navigation & Route Protection**:
  - Updated `Sidebar.jsx` with full administrator navigation links.
  - Configured `AppRoutes.jsx` with all `/admin/*` routes strictly guarded under `allowedRoles={["ADMINISTRATOR"]}`.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.4] — 2026-11-21

### Added & Integrated (Phase 7.4 — Field Worker Portal: Dashboard, Assigned Tasks & Resolution Workflow)

- **Field Worker Service Layer (`workerService.js`)**:
  - Full API integration with `GET /api/v1/workers/me/tasks`, `GET /api/v1/workers/me/tasks/{assignment_id}`, `POST /api/v1/workers/me/tasks/{assignment_id}/accept`, `POST /api/v1/workers/me/tasks/{assignment_id}/start`, `POST /api/v1/workers/me/tasks/{assignment_id}/progress`, and `POST /api/v1/workers/me/tasks/{assignment_id}/complete`.
  - Added `getDashboardMetrics()` helper aggregating live task statistics (Total Assigned, Pending Acceptance, In Progress, Completed) from real backend responses.
- **Field Worker Operations Dashboard (`WorkerDashboardPage.jsx`)**:
  - Replaced static placeholder `WorkerLandingPage.jsx` with an operational dashboard for technicians.
  - Live metric StatCards derived from actual assigned tasks without fabricated data.
  - "Tasks Requiring Immediate Attention" section highlighting urgent/high-priority tasks and work orders awaiting acceptance.
  - "Recent Dispatch Activity" queue displaying the latest assignments with quick action triggers.
- **Assigned Work Orders Queue (`WorkerTasksPage.jsx`)**:
  - Dedicated task management view supporting category tabs: "All Tasks", "Awaiting Acceptance", "In Progress", and "Completed".
  - Priority filter dropdown (All, Urgent, High, Medium, Low) and keyword search (tracking number, title, locality).
  - Server-side pagination controls synchronizing with backend query parameters (`page`, `page_size`, `total_pages`).
- **Work Order Dossier & Lifecycle Actions (`WorkerTaskDetailPage.jsx`)**:
  - Detailed task inspection view displaying incident title, full description, administrator dispatch instructions, and authorized field location data (street address, landmark, ward/district, GPS coordinates with an external navigation link).
  - Chronological progress audit history displaying technician observation updates.
  - State-aware workflow actions:
    - **Accept Task**: Acknowledges assignment receipt with modal confirmation.
    - **Start Work**: Initiates work on site with optional dispatch remarks, transitioning assignment and complaint to `IN_PROGRESS`.
    - **Log Progress Milestone**: Interactive modal with character length validation (min 5, max 2000 chars) logging updates to the audit trail.
    - **Complete Work Order**: Form modal with remediation summary validation (min 10, max 2000 chars) that transitions assignment to `COMPLETED` and complaint to `RESOLVED_AWAITING_VERIFICATION` for citizen review.
- **Field Worker Component & Navigation Updates**:
  - `WorkerTaskCard.jsx` & `WorkerTaskCard.css`: Reusable task card with distinct border indicators for action-required, in-progress, and completed states.
  - `Sidebar.jsx`: Updated `FIELD_WORKER` navigation links: Overview (`/worker`), My Tasks (`/worker/tasks`), In Progress (`/worker/tasks/in-progress`), Completed Tasks (`/worker/tasks/completed`), and Notifications (`/citizen/notifications`).
  - `AppRoutes.jsx`: Registered all worker routes protected by `FIELD_WORKER` role gate.
- **Security & Architectural Compliance**:
  - All worker routes strictly guarded by `allowedRoles={["FIELD_WORKER"]}`.
  - Tasks strictly scoped to the designated technician at both API layer (IDOR protection) and frontend presentation.
  - Zero modifications to backend Python code, database schemas, or Alembic migrations.
  - 100% pure ES6+ JavaScript and React JSX source code; zero TypeScript.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.3] — 2026-11-21

### Added & Integrated (Phase 7.3 — JavaScript Frontend Audit, Public Complaint Feed & Community Following)

- **JavaScript Frontend Audit & Invariant Verification**:
  - Full source-level audit confirming 100% JavaScript (ES6+) and React JSX implementation with zero TypeScript remnants or configurations.
  - In-memory JWT handling rigorously verified; no tokens stored in `localStorage` or `sessionStorage`.
  - Vite build verified clean (`dist/assets/index-*.js`, `dist/assets/index-*.css`) with zero compilation errors.
- **Dedicated Public & Follower Frontend Services**:
  - `publicComplaintService.js`: Integrated with `GET /api/v1/public/complaints` (unauthenticated feed), `GET /api/v1/public/complaints/{id}` (unauthenticated detail), `POST /api/v1/complaints/{id}/follow` (authenticated citizen follow), `DELETE /api/v1/complaints/{id}/follow` (authenticated citizen unfollow), and `GET /api/v1/complaints/following` (citizen followed feed).
- **Public Complaint Feed Interface**:
  - `PublicFeedPage.jsx` (`/public-feed`): Public community bulletin displaying administrator-moderated complaints with category and status dropdown filtering, backend pagination, responsive card grid, and clear loading/empty/error states.
  - `PublicComplaintCard.jsx`: Dedicated public card strictly projecting approved public fields (`public_title`, `public_description`, `complaint_number`, `category_name`, `status`, `ward_or_district`, `city`, `created_at`) with zero PII, zero exact coordinates, and zero private address exposure.
- **Public Complaint Detail & Community Following**:
  - `PublicComplaintDetailPage.jsx` (`/public-feed/:id`): Unauthenticated detail dossier displaying public sanitized description, coarse ward/city locality, and dynamic Follow/Unfollow action.
  - Interactive authentication gate: Prompts unauthenticated visitors to sign in or register before following issues, while authenticated citizens toggle follows with instant feedback and duplicate protection.
  - Safe 404 handling: Safely treats non-public or missing complaints without leaking private record existence.
- **Citizen Following Dashboard View**:
  - `CitizenFollowingPage.jsx` (`/citizen/following`): Authenticated portal view displaying all public issues followed by the citizen, with pagination and one-click unfollow capability.
- **Navigation Integration**:
  - `PublicNavbar.jsx` & `PublicFooter.jsx`: Added public navigation links to `/public-feed`.
  - `Sidebar.jsx`: Added **Following** navigation item (`/citizen/following`) to the Citizen Portal.
- **Strict Privacy Invariant Compliance**:
  - All public views consume strictly the public allowlist schemas (`PublicComplaintItem` and `PublicComplaintDetail`), ensuring zero leakage of citizen names, contact information, exact GPS coordinates, street addresses, or internal administrative notes.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.2] — 2026-11-21

### Added & Integrated (Phase 7.2 — Citizen Dashboard, Complaint Submission & Tracking)

- **Dedicated Citizen Frontend Services**:
  - `citizenService.ts`: Integrated with `GET /api/v1/citizens/me/dashboard` returning real metrics (`CitizenDashboardData`).
  - `categoryService.ts`: Integrated with `GET /api/v1/categories/` dynamically loading active categories.
  - `complaintService.ts`: Full integration with `POST /api/v1/complaints/`, `GET /api/v1/complaints/` (paginated), `GET /api/v1/complaints/{id}`, `GET /api/v1/complaints/{id}/history`, `GET /api/v1/complaints/{id}/timeline`, and `POST /api/v1/complaints/{id}/transitions`.
- **Citizen Navigation Architecture**:
  - Configured 6-item citizen sidebar: Overview (`/citizen`), My Complaints (`/citizen/complaints`), Report an Issue (`/citizen/report`), Complaint Tracking (`/citizen/track`), Notifications (`/citizen/notifications`), and Profile (`/citizen/profile`).
- **Personalized Citizen Dashboard**:
  - `CitizenDashboardPage.tsx`: Live StatCards (Total Filed, Active Resolution, Awaiting Verification, Verified Closed), Action-Required Section highlighting complaints in `RESOLVED_AWAITING_VERIFICATION`, Recent Submissions feed, and Recent Updates feed with live reload capability.
- **Complaint Submission Interface**:
  - `CitizenReportPage.tsx`: Dynamic category selection, validated title (5–200 chars), description (10–2000 chars), location coordinates with HTML5 geolocation detection, street address, ward/area, city, pincode, and landmark inputs.
  - Client-side validation, backend 422 error alerts, duplicate submission defense, and success screen displaying tracking reference code.
- **My Complaints Listing**:
  - `CitizenComplaintsPage.tsx`: Paginated complaint table with search filtering (tracking code, keywords), status dropdown (10 lifecycle statuses), priority filtering, and direct links to detail dossiers.
- **Complaint Dossier & Unified Timeline**:
  - `CitizenComplaintDetailPage.tsx`: Complete complaint specification view, location card with coordinates, chronological timeline (`ComplaintTimeline.tsx`), and status audit history tab (`ComplaintStatusHistory`).
  - `ComplaintStatusTracker.tsx`: Visual milestone stepper showing complaint journey through municipal resolution.
- **Citizen Lifecycle Actions**:
  - Integrated `ConfirmationDialog.tsx` for citizen verification:
    - **Verify & Close**: Transitions `RESOLVED_AWAITING_VERIFICATION` complaints to `CLOSED`.
    - **Reopen**: Permits reopening with mandatory recorded justification (`remarks`) within the approved 14-day grace period.
- **Complaint Tracking & Profile Pages**:
  - `CitizenTrackPage.tsx`: Quick reference code search lookup.
  - `CitizenProfilePage.tsx`: Displays authenticated user details (`full_name`, `email`, `phone_number`, role, creation date).
  - `CitizenNotificationsPage.tsx`: In-app notification hub placeholder.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.7.1] — 2026-11-21

### Added & Established (Phase 7.1 — Frontend Foundation, UI Design System & Authentication)

- **Frontend Foundation & Build Pipeline**:
  - Initialized Vite + React 19 + TypeScript + React Router v7 frontend foundation under `frontend/`.
  - Configured strict TypeScript with `verbatimModuleSyntax` and zero build warnings (`npm --prefix frontend run build` passing in 264ms).
  - Configured native browser Fetch API client (`apiClient.ts`) with automatic token attachment and 401 unauthorized interceptor.
- **Official CivicPulse Color System & Design Tokens**:
  - Implemented exact palette: Primary Teal (`#087F8C`), Soft Teal (`#49A0AB`), Dark Navy (`#142F4F`), Background Light Blue Grey (`#F4F8FA`), Cards White (`#FFFFFF`), Active Navigation Pale Teal (`#D9EFEC`), Borders Light Grey Blue (`#EAF1F3`).
  - Defined design tokens in `frontend/src/styles/variables.css` and base reset in `frontend/src/styles/global.css`.
  - Added semantic badge styling for all 9 complaint lifecycle statuses.
- **Reusable Component Library**:
  - Implemented `Button`, `Input` (with show/hide password toggle), `Card`, `StatCard`, `StatusBadge`, `Alert`, `Table`, `Pagination`, `UserProfileMenu`, `TopHeader`, `Sidebar`, `PublicNavbar`, `PublicFooter`, and `Spinner`.
- **Application Shells & Layouts**:
  - `PublicLayout`: Responsive top navigation bar, public page container, and footer.
  - `AuthenticatedLayout`: Left sidebar with role-filtered links, `#D9EFEC` active state indicator, mobile drawer, and top header with user profile menu.
- **Authentication State & Secure In-Memory Token Management**:
  - Implemented `AuthContext` holding JWT access tokens strictly in memory — zero usage of `localStorage` or `sessionStorage` to eliminate XSS token persistence risks.
  - Automatic session cleanup and role-sensitive redirect on unauthorized responses.
- **Authentication Pages**:
  - `LoginPage` (`/login`): Clean SaaS login card with email & password validation, toggle visibility, and role-based redirect upon sign-in.
  - `RegisterPage` (`/register`): Citizen registration interface aligned with backend `UserRegisterRequest` schema (`full_name`, `email`, `password`, `password_confirm`) with client validation and success confirmation.
- **Role-Based Access Control & Portal Foundations**:
  - Created `ProtectedRoute` route guard enforcing authentication and role whitelist.
  - Foundation portal landing pages: `CitizenLandingPage` (`/citizen`), `AdminLandingPage` (`/admin`), and `WorkerLandingPage` (`/worker`).
  - Implemented `UnauthorizedPage` (403) with role display and return navigation, and `NotFoundPage` (404).
- **Backend CORS Configuration**:
  - Configured FastAPI `CORSMiddleware` in `app/main.py` with explicit allowed origins (`http://localhost:5173`), avoiding wildcard origins.
- **ORM Model Count Reconciled**:
  - Reconciled 16 active business models + 1 AI assessment model (`AIAssessment` mapped to `ai_assessments`) = 17 registered ORM models in SQLAlchemy metadata.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.5.1] — 2026-11-20

### Reconciled & Audited (Phase 6.5.1 — Final API Contract, Database Schema & Privacy Reconciliation)

- **Public Feed Privacy Verification**:
  - Reconciled and verified that `pincode` was never included in `PublicComplaintItem` or `map_complaint_to_public_item`.
  - Reconfirmed that public responses strictly contain only the 9 approved allowlisted fields (`id`, `complaint_number`, `category_name`, `status`, `created_at`, `public_title`, `public_description`, `ward_or_district`, `city`).
  - Added JSON serialization tests verifying zero leakage of `pincode`, exact GPS coordinates, street addresses, landmarks, or citizen PII.
- **Alembic Migration History Reconciled**:
  - Reconciled true historical migration revisions: `dc808166f213` -> `5c60c8914494` -> `7f3a8b2c4d1e` -> `8d2e4f6a1c3b` -> `9e1f2a3b4c5d` -> `a4b5c6d7e8f9` -> `b7c8d9e0f1a2`.
  - Confirmed both `civicpulse` and `civicpulse_test` databases are at head `b7c8d9e0f1a2`.
- **Authoritative Registered API Route Inventory**:
  - Generated complete 53-endpoint inventory directly from FastAPI application routers.
  - Reconciled exact route paths: `GET /api/v1/citizens/me/dashboard`, `GET /api/v1/public/complaints`, `POST /api/v1/complaints/{complaint_id}/transitions`, etc.
- **Model Fields & PostgreSQL Schema 1:1 Parity**:
  - Reconciled true column names: `Assignment.accepted_at` (not `acknowledged_at`), `ComplaintFollower.followed_at` (not `created_at`), `AssignmentProgress.description` (not `notes`), and `Complaint.moderated_at` (not `published_at`).
  - Confirmed exact 1:1 column parity across all 15 ORM models with PostgreSQL 18 tables.
- **Index Verification**:
  - Verified that all foreign keys on active business models have supporting B-tree indexes.
- **Test Metrics Expansion**:
  - Added `tests/test_phase6_5_1_reconciliation.py` with 7 targeted tests.
  - Full project test suite expanded to 369 passing tests across 12 test files (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.5] — 2026-11-20

### Audited, Hardened & Optimized (Phase 6.5 — Final Integration, Security, Privacy, Database Integrity & Performance Audit)

- **Specific Verification A — Notification Conflict Arbiter**:
  - Verified `create_notifications` uses SQLAlchemy `ON CONFLICT` explicitly targeting `index_elements=["recipient_id", "event_key"]` with `index_where=text("event_key IS NOT NULL")`.
  - Confirmed perfect alignment with partial unique index `uq_notifications_recipient_event_key`, preventing PostgreSQL 42P10 syntax errors.
- **Specific Verification B — Outer Transaction Rollback Integrity**:
  - Proved that outer transaction rollbacks on raw database connections revert both originating business mutations and dispatched notifications without leaving partial state.
- **Specific Verification C — Reassignment Timeline Integrity & Anti-Spoofing**:
  - Confirmed atomic timestamp correlation during reassignment serialized under complaint row-level lock (`with_for_update`).
  - Proved replacement assignment's `assigned_at` acts as an immutable boundary; synthetic worker progress notes cannot forge or manipulate timeline access cutoff.
- **Specific Verification D — Public Unpublish Audit Preservation**:
  - Audited complaint-level unpublish audit fields (`unpublish_requested_at`, `unpublish_requested_by_id`, `unpublish_reason`).
  - Proved initial unpublish audit metadata is immutable during unpublish state; citizen republishing is strictly blocked.
- **Performance & Query Optimization** (`app/services/timeline_service.py`):
  - Added eager joinedloading for `Assignment.worker.user` and `Assignment.worker.department`, eliminating secondary lazy-loading queries during timeline construction.
  - Verified dashboard conditional aggregation query performance and bounded notification inbox pagination.
- **Code Modernization & Warning Elimination**:
  - Replaced 6 occurrences of deprecated `status.HTTP_422_UNPROCESSABLE_ENTITY` with `status.HTTP_422_UNPROCESSABLE_CONTENT` across test suites.
  - Eliminated all project-level warnings (0 project warnings).
- **Test Metrics Expansion**:
  - Added `tests/test_phase6_5_final_audit.py` with 20 comprehensive audit tests.
  - Full project test suite expanded to 362 passing tests across 11 test files (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.4.1] — 2026-11-20

### Fixed & Hardened (Phase 6.4.1 — Notification Event Classification, Transaction Integrity & Final Security Audit)

- **SLA Notification Event Classification** (`app/core/constants.py`, `app/services/notification_service.py`):
  - Added `SLA_WARNING`, `SLA_BREACH`, and `FEEDBACK_REQUEST` to canonical `NotificationType` enum.
  - Updated `notify_sla_escalation` to classify Level 1 warning escalations as `NotificationType.SLA_WARNING` and Level 2/3 breach escalations as `NotificationType.SLA_BREACH`.
  - Zero database migration required due to non-native PostgreSQL `VARCHAR(50)` column definition.
- **Transaction Atomicity & Rollback Integrity** (`tests/test_phase6_4_notifications.py`):
  - Verified atomic persistence of business entities and dispatched notifications in identical transactions.
  - Proved that transaction rollbacks revert both business updates and their dispatched notifications.
  - Verified that notification creation and dispatch helpers never independently commit the caller's session.
- **Multi-Threaded Concurrent Idempotency & Conflict Arbiter Matching** (`tests/test_phase6_4_notifications.py`):
  - Executed multithreaded test using 5 simultaneous threads with independent SQLAlchemy sessions and connections inserting identical `(recipient_id, event_key)`. Exactly 1 row persisted with 0 constraint violation errors.
  - Verified different recipients can independently receive notifications sharing the same logical `event_key`.
  - Verified PostgreSQL catalog metadata for `uq_notifications_recipient_event_key` and confirmed that inserts without `WHERE event_key IS NOT NULL` fail with `42P10`.
- **SLA Event Integration & Lifecycle Boundaries** (`tests/test_phase6_4_notifications.py`):
  - Confirmed zero notifications generated for evaluations or reads without genuine escalation level increases.
  - Confirmed terminated complaints (`REJECTED`, `DUPLICATE`) never evaluate resolution SLA or dispatch resolution escalation notifications.
  - Verified compliance with deterministic cycle-aware event key format: `sla:{complaint_id}:cycle:{sla_cycle_number}:{clock_type}:level:{level}`.
- **Privacy Hardening & REST API Security** (`tests/test_phase6_4_notifications.py`):
  - Verified comprehensive redaction across follower notifications (zero leakage of coordinates, addresses, citizen emails, internal remarks, or progress notes).
  - Verified that reassigned workers receive strictly reassignment notices and zero subsequent milestone progress updates.
  - Hardened and verified cross-user and cross-role IDOR defense (`404 Not Found`).
  - Verified mark-all-read user scoping and idempotent read timestamp preservation.
- **Test Metrics Expansion**:
  - Expanded `tests/test_phase6_4_notifications.py` from 46 to 62 tests.
  - Full project test suite expanded to 342 passing tests across 10 test files (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.4] — 2026-11-20

### Added (Phase 6.4 — In-App Notifications & Event Integration)

- **Database Migration 007** (`alembic/versions/b7c8d9e0f1a2_007_notification_event_keys.py`):
  - Added nullable `event_key` column (`String(255)`) to `notifications` table.
  - Added check constraint `ck_notifications_event_key_not_empty` enforcing `event_key IS NULL OR length(trim(event_key)) > 0`.
  - Created PostgreSQL partial unique index `uq_notifications_recipient_event_key` on `(recipient_id, event_key) WHERE event_key IS NOT NULL`.
  - Reversibility verified on `civicpulse_test` via downgrade to `a4b5c6d7e8f9` and re-upgrade to `b7c8d9e0f1a2`.
- **Centralized Notification Service** (`app/services/notification_service.py`):
  - Idempotent multi-recipient creation using PostgreSQL `ON CONFLICT (recipient_id, event_key) WHERE event_key IS NOT NULL DO NOTHING`.
  - Atomic transaction participation: executes within the caller's active database transaction without standalone commits.
  - Automatic recipient list deduplication per dispatch call.
  - Strict follower privacy filtering via `_get_public_follower_ids`: strictly returns empty list when `complaint.is_public == False`.
  - Actor exclusion enforcement: actors performing actions never receive echo notifications (with explicit exception for citizen complaint submission confirmation).
  - Cycle-aware deterministic SLA event keys: `sla:{complaint_id}:cycle:{sla_cycle_number}:{clock_type}:level:{level}`.
- **Service Layer Event Integration**:
  - `complaint_service.py`: Automated notification dispatch on complaint submission and status transitions (`UNDER_REVIEW`, `ON_HOLD`, `RESOLVED_AWAITING_VERIFICATION`, `CLOSED`, `REOPENED`, `REJECTED`, `DUPLICATE`).
  - `assignment_service.py`: Automated dispatch on worker assignment dispatch, worker acceptance (`ACCEPTED`), work start (`STARTED`), milestone progress updates (`PROGRESS`), and reassignment.
  - `sla_service.py`: Automated dispatch for Response (Level 1 warning, Level 2 breach) and Resolution (Level 1 warning, Level 2 breach, Level 3 critical breach) strictly when escalation level genuinely increases (`new_level > prev_level`). Delivered strictly to owner and active worker; never broadcast to followers.
- **Authenticated REST API Endpoints** (`app/api/v1/notifications.py`):
  - `GET /api/v1/notifications`: Paginated user inbox with optional `unread_only` filtering.
  - `GET /api/v1/notifications/unread-count`: Badge counter returning unread count.
  - `PATCH /api/v1/notifications/{notification_id}/read`: Individual read state update with strict IDOR protection (`404 Not Found` for other users' notifications).
  - `POST /api/v1/notifications/read-all`: Batch read mark for all unread notifications belonging to the authenticated user.
  - Declared fixed sub-paths before dynamic UUID path parameter to prevent FastAPI routing collisions.
- **Dedicated Test Suite** (`tests/test_phase6_4_notifications.py`):
  - 46 comprehensive tests covering migration constraints, service idempotency, complaint lifecycle dispatch, worker milestone events, SLA escalations, follower privacy, actor exclusion, and REST API security.
  - Total project test suite expanded to 326 passing tests across 10 test files (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.3.2] — 2026-11-20

### Fixed & Hardened (Phase 6.3.2 — Final Resolution SLA Semantics, Precision & Verification)

- **Resolution SLA Clock Stop Condition Exclusivity** (`app/services/sla_service.py`):
  - Enforced that the resolution SLA completion event is exclusively `IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION`.
  - Moving from `RESOLVED_AWAITING_VERIFICATION` to `CLOSED` does not re-stop or alter `resolved_at`; cycle snapshots preserve the original worker completion timestamp for calculating `actual_resolution_seconds`.
- **Handling of Terminated (Rejected & Duplicate) Complaints** (`app/services/sla_service.py`):
  - When complaints terminate via `REJECTED` or `DUPLICATE` prior to resolution, `complaint.resolved_at` remains strictly `None` (no fabricated resolution timestamp).
  - Preserved actual elapsed seconds to termination in `actual_resolution_seconds`.
  - Resolution SLA is never marked as successfully completed (`resolution_breached` evaluates to `True` if target was exceeded, or `None` if terminated within target duration; never `False`).
  - Active resolution escalation is permanently frozen on `REJECTED`, `DUPLICATE`, and `CLOSED` complaints, preventing active escalation in background or batch evaluations.
  - Hardened `get_complaint_sla_details` to prevent terminated complaints from retroactively reporting `resolution_breached=True` merely because wall-clock time passed after termination.
- **Exact Decimal Precision for Escalation Comparisons** (`app/services/sla_service.py`):
  - Replaced 6-decimal rounding with exact `Decimal` precision comparison without rounding.
  - Threshold comparisons (`target_d * Decimal("0.75")`, `target_d * Decimal("1.0")`, `target_d * Decimal("1.5")`) ensure values immediately below a boundary (e.g. 74.999996%) strictly remain in the lower escalation level without premature rounding promotion.
- **Dedicated Test Suite Expanded** (`tests/test_phase6_3_sla_management.py`):
  - Added tests 68–74 covering `RESOLVED -> CLOSED` timestamp preservation, rejection/duplicate non-completion, termination escalation freezing, reopening resolution timestamp accuracy, exact Decimal threshold boundaries, and admin detail consistency.
  - Dedicated Phase 6.3 suite expanded from 67 to 74 passing tests (100% pass rate).
  - Full backend test suite expanded from 273 to 280 passing tests across 9 test files.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.3.1] — 2026-11-20

### Fixed & Hardened (Phase 6.3.1 — SLA Lifecycle Corrections, Escalation Boundary Fixes & Final Verification)

- **Response SLA Clock Semantics** (`app/services/sla_service.py`):
  - Enforced that the response SLA clock starts strictly at `complaint.created_at` and stops strictly when the complaint transitions from `SUBMITTED` to `UNDER_REVIEW` (or earlier terminal `REJECTED`/`DUPLICATE`).
  - Worker assignment, acceptance, progress updates, and reassignments never stop or restart the response clock.
  - Completed response clock remains permanently frozen across subsequent lifecycle changes and reopenings.
- **Resolution SLA Clock & Reopening Lifecycle** (`app/services/complaint_service.py`, `app/services/sla_service.py`):
  - Corrected citizen transition authorization in `execute_transition` to permit reopening from `CLOSED` within the 14-day grace period.
  - Preserved `complaint.resolved_at` when entering `REOPENED` so `snapshot_sla_cycle_history` accurately logs the cycle 1 resolution timestamp before starting cycle 2.
  - Reopening increments `sla_cycle_number`, resets resolution pause duration and pause start timestamps, resets resolution escalation level, resolves the active policy for the complaint, and sets a fresh resolution deadline.
  - Cycle snapshots record `end_reason="REOPENED"` and capture physical elapsed seconds.
- **Deterministic Escalation Boundary Calculation** (`app/services/sla_service.py`):
  - Implemented exact ratio calculation with 6-decimal precision: `round(effective_elapsed_seconds / target_seconds, 6)`.
  - Guaranteed boundary levels:
    - Response: Level 0 (< 75%), Level 1 (>= 75% and < 100%), Level 2 (>= 100%).
    - Resolution: Level 0 (< 75%), Level 1 (>= 75% and < 100%), Level 2 (>= 100% and < 150%), Level 3 (>= 150%).
- **Policy Updates & Historical Immutability** (`app/services/sla_service.py`, `app/api/v1/admin_sla.py`):
  - Policy updates never modify completed cycles or completed response/resolution clocks.
  - When target durations change on active complaints, escalation levels are recalculated and audit records are created in `ComplaintStatusHistory` attributing the change to the authenticated administrator.
- **Dedicated Test Suite Expanded** (`tests/test_phase6_3_sla_management.py`):
  - Added 7 targeted tests covering response clock non-termination on worker acceptance, boundary percentages (74.99%, 75%, 99.99%, 100%, 149.99%, 150%), reopen from `CLOSED`, resolution snapshot accuracy, concurrent snapshot idempotency, rollback atomicity, and policy update audit logging.
  - Suite expanded from 60 to 67 tests (100% pass rate). Total project test suite expanded to 273/273 passing tests.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.3] — 2026-11-20

### Added (Phase 6.3 — SLA Management, Dual Clocks & Intelligent Escalation)

- **Database Migration & Schema Extensions** (`alembic/versions/a4b5c6d7e8f9_006_sla_management_and_escalation.py`, `app/models/sla_policy.py`, `app/models/complaint_sla_history.py`, `app/models/complaint.py`):
  - Created Alembic migration `006_sla_management_and_escalation` (revision: `a4b5c6d7e8f9`, parent: `9e1f2a3b4c5d`).
  - Created `sla_policies` table with 4 partial unique indexes (`uq_sla_policy_category_priority`, `uq_sla_policy_category_only`, `uq_sla_policy_priority_only`, `uq_sla_policy_global`) guaranteeing uniqueness for nullable dimensions.
  - Extended `complaints` table with dual-clock SLA fields (`response_sla_policy_id`, `response_deadline`, `responded_at`, `response_pause_duration_seconds`, `response_pause_started_at`, `response_escalation_level`, `resolution_sla_policy_id`, `resolution_deadline`, `resolution_pause_duration_seconds`, `resolution_pause_started_at`, `resolution_escalation_level`, `sla_cycle_number`, `last_sla_evaluated_at`).
  - Added database check constraints for nonnegative durations (`response_pause_duration_seconds >= 0`, `resolution_pause_duration_seconds >= 0`), valid escalation levels (0–2 for response, 0–3 for resolution), and valid cycle numbers (`sla_cycle_number >= 1`).
  - Created `complaint_sla_history` table with composite unique constraint `uq_complaint_sla_history_cycle (complaint_id, cycle_number)`.
  - Created PostgreSQL database trigger `trg_prevent_sla_history_mutation` calling `prevent_sla_history_mutation()` to block `UPDATE` and `DELETE` at the database level.
- **Dual SLA Clock Semantics & Lifecycle Hooks** (`app/services/sla_service.py`, `app/services/complaint_service.py`):
  - Independent **Response Clock**: Starts at `created_at`, stops on `SUBMITTED -> UNDER_REVIEW` (or terminal `REJECTED`/`DUPLICATE`). Does not restart on assignment, reassignment, or reopening.
  - Independent **Resolution Clock**: Starts at `created_at` (cycle 1) or reopen timestamp (cycle > 1), stops on `IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION`. Restarts with fresh resolution deadline on reopening.
  - Integrated hooks into `create_complaint`, `execute_transition`, and `review_complaint`.
- **ON_HOLD Pause Accounting** (`app/services/sla_service.py`):
  - Transitions to `ON_HOLD` pause active (uncompleted) clocks and record separate pause start timestamps without overwriting accumulated durations.
  - Transitions out of `ON_HOLD` accumulate elapsed pause seconds, clear pause start timestamps, and extend effective deadlines.
  - Dynamic pause calculation during evaluations computes active pause without double-counting or mutating database fields while in `ON_HOLD`.
- **Deterministic 4-Tier Policy Precedence & Advisory Locking** (`app/services/sla_service.py`):
  - 4-tier resolution hierarchy: (1) Exact category + priority, (2) Category only, (3) Priority only, (4) Global fallback.
  - Concurrency protection: PostgreSQL transaction-scoped advisory locks on logical key `(category_id, priority)` prevent concurrent creation or update conflicts.
- **Deterministic Escalation Progression** (`app/services/sla_service.py`):
  - Response escalation: Level 0 (Normal, <75%), Level 1 (Warning, 75%–<100%), Level 2 (Breached, >=100%).
  - Resolution escalation: Level 0 (Normal, <75%), Level 1 (Warning, 75%–<100%), Level 2 (Breached, 100%–<150%), Level 3 (Severe breach, >=150%).
  - Idempotent evaluations prevent duplicate events; policy updates dynamically recalculate and audit de-escalation.
- **Append-Only Cycle History Snapshotting** (`app/services/sla_service.py`):
  - Snapshots completed cycles on `CLOSED`, `REJECTED`, `DUPLICATE`, or `REOPENED`.
  - Preserves completed response history across reopening cycles.
- **Administrative SLA API** (`app/api/v1/admin_sla.py`, `app/schemas/sla.py`):
  - Added endpoints under `/api/v1/admin/sla`: `GET /policies`, `POST /policies`, `PATCH /policies/{id}`, `POST /evaluate`, `GET /complaints/{id}`, `GET /complaints/{id}/history`.
  - Strictly restricted to `ADMINISTRATOR` role (`403 Forbidden` for citizens and workers).
  - Bounded batch evaluation enforces upper limit between 1 and 200 complaints.
- **Dedicated Test Suite** (`tests/test_phase6_3_sla_management.py`):
  - 60 dedicated tests covering all Section 11 requirements (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.2.1] — 2026-11-19

### Hardening & Data Integrity Audit (Phase 6.2.1 — Final Security, Data Integrity & Test Coverage Audit)

- **Unpublishing Audit Metadata Preservation** (`app/services/public_complaint_service.py`):
  - Hardened `request_unpublish`: repeated unpublish calls on an already-unpublished complaint preserve the initial unpublish timestamp (`unpublish_requested_at`) and original requester (`unpublish_requested_by_id`) without overwriting or erasing the recorded reason (`unpublish_reason`).
  - Documented scalar column scope: existing fields preserve the latest unpublishing request per publication lifecycle; full historical multi-cycle unpublish tracking is documented for evaluation in Phase 6.5.
- **Following Concurrency & Integrity Hardening** (`app/services/follower_service.py`, `tests/test_phase6_2_public_feed_and_followers.py`):
  - Verified `follow_complaint` handles concurrent race conditions safely via unique constraint and `db.rollback()` recovery, preventing session invalidation.
  - Added multi-threaded concurrency tests using Python's `ThreadPoolExecutor` across separate database sessions.
- **Public Feed Privacy Verification** (`app/schemas/public_complaint.py`, `app/services/public_complaint_service.py`):
  - Verified strict allowlist serialization: public payloads expose strictly 9 approved fields (`id`, `complaint_number`, `category_name`, `status`, `created_at`, `public_title`, `public_description`, `ward_or_district`, `city`).
  - Verified zero leakage of citizen PII, coordinates, street address, internal remarks, worker/assignment details, attachments, or AI assessment.
  - Verified that pagination totals (`total`, `total_pages`) filter before counting and never expose the count of private complaints.
- **Dedicated Test Suite Expanded** (`tests/test_phase6_2_public_feed_and_followers.py`):
  - Added 9 targeted tests covering multi-threaded follow concurrency, repeated unpublish audit preservation, pagination metadata privacy, strict field allowlist exclusion, moderation rollback, unpublishing rollback, revocation follow denial, and existing complaint data preservation.
  - Test suite expanded from 197 to 206 total passing tests (38 Phase 6.2/6.2.1 tests, 100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.2] — 2026-11-19

### Added (Phase 6.2 — Moderated Public Complaint Feed & Community Following)

- **Database Migration & Schema Extensions** (`alembic/versions/9e1f2a3b4c5d_005_public_visibility_and_followers.py`, `app/models/complaint.py`, `app/models/complaint_follower.py`):
  - Created migration `005_public_visibility_and_followers` (revision: `9e1f2a3b4c5d`, parent: `8d2e4f6a1c3b`).
  - Extended `complaints` table with columns: `is_public` (Boolean, default `False`), `public_title` (String(200)), `public_description` (Text), `moderated_at` (DateTime), `moderated_by_id` (ForeignKey to `users.id`), `unpublish_requested_at` (DateTime), `unpublish_requested_by_id` (ForeignKey to `users.id`), `unpublish_reason` (Text).
  - Created `complaint_followers` table with composite unique constraint `uq_complaint_followers_complaint_citizen (complaint_id, citizen_id)` and foreign keys to `complaints.id` (CASCADE) and `users.id` (CASCADE).
- **Administrator Public Moderation** (`app/services/public_complaint_service.py`, `app/api/v1/complaints.py`, `app/schemas/moderation.py`):
  - Added `POST /api/v1/complaints/{complaint_id}/moderate-public` restricted to `ADMINISTRATOR` role (`403 Forbidden` for citizens and workers).
  - Supports actions: `PUBLISH` (validates public content, sets `is_public = True`), `UPDATE` (updates approved content), and `REVOKE` (sets `is_public = False`).
  - Strict input validation: `public_title` (5–200 characters), `public_description` (10–2000 characters).
  - Business rule enforcement: prevents publishing `REJECTED` or `DUPLICATE` complaints (`422 Unprocessable Entity`).
  - Strict privacy rule: raw citizen-submitted title/description are never copied or used as fallback.
  - Moderation operations never mutate lifecycle state machine status.
- **Citizen Unpublishing Request** (`app/services/public_complaint_service.py`, `app/api/v1/complaints.py`, `app/schemas/moderation.py`):
  - Added `POST /api/v1/complaints/{complaint_id}/request-unpublish` restricted to `CITIZEN` owner (`403 Forbidden` for other citizens).
  - Immediately sets `is_public = False` and logs audit trail (`unpublish_requested_at`, `unpublish_requested_by_id`, `unpublish_reason`).
  - Idempotent: repeated unpublish requests preserve audit integrity.
- **Automatic Privacy Enforcement on Terminal Transitions** (`app/services/complaint_service.py`):
  - Integrated into `execute_transition`: any transition to `REJECTED` or `DUPLICATE` automatically revokes publication (`is_public = False`) in the same database transaction.
  - Rolled back atomically if transition fails.
- **Privacy-Safe Public Feed & Detail Endpoints** (`app/services/public_complaint_service.py`, `app/api/v1/public.py`, `app/schemas/public_complaint.py`):
  - Added unauthenticated `GET /api/v1/public/complaints` and `GET /api/v1/public/complaints/{complaint_id}`.
  - Strict allowlist projection: `id`, `complaint_number`, `category_name`, `status`, `created_at`, `public_title`, `public_description`, `ward_or_district`, `city`.
  - Zero exposure of citizen PII, internal remarks, assignment details, raw citizen text, or exact GPS coordinates (`latitude`, `longitude`, `address_line1`).
  - Private complaints return `404 Not Found` on detail endpoint.
- **Community Following** (`app/services/follower_service.py`, `app/api/v1/complaints.py`, `app/schemas/follower.py`):
  - Added `POST /api/v1/complaints/{complaint_id}/follow`, `DELETE /api/v1/complaints/{complaint_id}/follow`, and `GET /api/v1/complaints/following`.
  - Restricted strictly to `CITIZEN` role.
  - Following private complaints returns `404 Not Found`.
  - Follow actions are idempotent and protected by database uniqueness.
  - Following feed is strictly isolated to the authenticated citizen and automatically omits unpublished complaints.
- **Dedicated Test Suite** (`tests/test_phase6_2_public_feed_and_followers.py`):
  - 29 tests covering all 50 Phase 6.2 requirements across database defaults, migration reversibility, admin moderation, validation rules, public privacy allowlists, automatic privacy enforcement, citizen unpublishing, community following, and pagination.
  - Overall test suite expanded to 197 passing tests (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.1.1] — 2026-11-19

### Security & Privacy Hardening (Phase 6.1.1 — Targeted Timeline Privacy & Access-Control Correction)

- **Administrative Remarks Redaction Hardened** (`app/services/timeline_service.py`):
  - Enforced strict default redaction of administrative remarks for citizens (`remarks = None`).
  - Redacted administrative `REJECTED` and `DUPLICATE` remarks for citizens to prevent exposure of internal triage discussions and rationale.
  - Allowed remark exposure to citizens strictly when actor identity reliably proves complaint owner authorship (`h.changed_by_id == user.id == complaint.citizen_id`).
  - Preserved full, unredacted remark visibility for administrators.
- **Previous-Worker Cutoff Boundary Secured** (`app/services/timeline_service.py`):
  - Removed reliance on mutable `assignment.updated_at` for calculating reassignment cutoff.
  - Reassignment cutoff is now anchored strictly to immutable `AssignmentProgress` records (`description.startswith("Reassigned to ")`) or verified worker activity timestamps.
  - Unrelated assignment updates (e.g. notes edits) can no longer accidentally extend historical access to subsequent events.
- **Assignment Dispatch Notes Scoped** (`app/services/timeline_service.py`):
  - Restricted `assignment.notes` visibility to administrators and the specific worker assigned to that assignment.
- **Focused Regression Tests Added** (`tests/test_phase6_1_dashboard_and_timeline.py`):
  - Added 5 targeted regression tests verifying rejection remark redaction, duplicate remark redaction, citizen-authored remark display, assignment update isolation, and unassigned worker 403 enforcement. Total test suite reaches 160 tests passing (100%).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.6.1] — 2026-11-19

### Added (Phase 6.1 — Citizen Dashboard & Unified Complaint Timeline)

- **Citizen Dashboard Service & Endpoint** (`app/services/dashboard_service.py`, `app/api/v1/citizens.py`, `app/schemas/dashboard.py`):
  - Added `GET /api/v1/citizens/me/dashboard` restricted to `CITIZEN` role.
  - Ownership strictly scoped to `complaint.citizen_id == current_user.id` (zero external citizen exposure).
  - High-efficiency single-query PostgreSQL conditional aggregation (`func.count().filter(...)`) computing metrics across all 10 approved statuses and 4 priority levels in one database pass.
  - Capped activity feeds (max 5 records) for `recent_submissions`, `recent_updates`, and `action_required` (complaints awaiting verification).
- **Unified Chronological Timeline Service & Endpoint** (`app/services/timeline_service.py`, `app/api/v1/complaints.py`, `app/schemas/timeline.py`):
  - Added `GET /api/v1/complaints/{id}/timeline` consolidating milestones across `complaints`, `complaint_status_history`, `assignments`, and `assignment_progress`.
  - Enforced strict authorization: Author Citizen (allowed), Non-author Citizen (403 Forbidden), Assigned Field Worker (allowed), Unassigned Worker (403 Forbidden), Administrator (unrestricted).
  - Implemented bounded access for previously assigned workers (`event.timestamp <= reassignment_cutoff`).
  - Privacy and redaction: internal administrative remarks, triage notes, and dispatch instructions are redacted for citizens. Rejection, duplicate, and citizen-initiated transition remarks remain visible.
- **Automated Test Suite Expansion** (`tests/test_phase6_1_dashboard_and_timeline.py`):
  - Added 20 dedicated automated tests covering empty dashboard states, status and priority breakdowns, activity feed limits, ownership scoping, role restrictions, timeline authorization matrix, previously assigned worker cutoff boundaries, remark redaction, and 404 handling.
  - Full project test suite expanded to 155 tests (100% pass rate).
- **Schema & Lifecycle Invariants Preserved**:
  - Implemented entirely using existing tables (`complaints`, `categories`, `locations`, `complaint_status_history`, `assignments`, `assignment_progress`).
  - Alembic HEAD remains strictly at `8d2e4f6a1c3b` with zero migrations created or executed.
  - Zero changes to the approved complaint lifecycle transition matrix.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.5.1] — 2026-11-19

### Changed & Audited (Phase 5.1 — Assignment Integrity, Lifecycle Consistency & Security Audit)

- **Lifecycle State Machine Restored to Approved Matrix** (`app/core/constants.py`, `app/services/complaint_service.py`):
  - Enforced strict Phase 4 transition rules in `COMPLAINT_STATUS_TRANSITIONS`; removed unauthorized direct transitions.
  - Added support for atomic multi-step transition chaining via `commit=False` parameter in `execute_transition`.
- **Atomic Reassignment of In-Progress Complaints** (`app/services/assignment_service.py`):
  - Implemented legal chained transition (`IN_PROGRESS -> ON_HOLD -> UNDER_REVIEW -> ASSIGNED`) with single-commit atomicity and full audit history.
- **Deadlock Prevention via Standardized Lock Ordering** (`app/services/assignment_service.py`):
  - Standardized lock acquisition order: exclusive lock on `Complaint` first, followed by `Assignment`.
- **Worker Service-Layer Authorization Hardening** (`app/services/assignment_service.py`):
  - Added service-level active employment validation in `get_worker_tasks` and `get_worker_task_by_id`, immediately blocking deactivated workers regardless of token expiration.
- **Department & Worker Endpoint Parity** (`app/api/v1/departments.py`, `app/api/v1/workers.py`, `app/services/department_service.py`):
  - Added `DELETE` aliases for department and worker deactivation alongside `PATCH .../deactivate`.
  - Added business rule validation in `deactivate_department` preventing deactivation if active worker assignments (`ASSIGNED`, `IN_PROGRESS`) exist.
- **Test Suite Expansion** (`tests/test_assignments.py`, `tests/test_database.py`):
  - Expanded assignment test suite from 21 to 49 comprehensive tests; full project test suite reaches 135 tests passing (100% pass rate).

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.5.0] — 2026-11-19

### Added (Phase 5 — Worker Assignment & Department Management)

- **Database Models & Alembic Migration 004** (`app/models/assignment.py`, `app/models/assignment_progress.py`, `alembic/versions/8d2e4f6a1c3b_004_assignment_enhancements_and_progress.py`):
  - Added `accepted_at` and `started_at` nullable UTC timestamps to `assignments`.
  - Added partial unique index `uq_active_assignment_per_complaint` on `assignments (complaint_id) WHERE status IN ('ASSIGNED', 'IN_PROGRESS')` to prevent concurrent duplicate active assignments at the PostgreSQL engine level.
  - Added `AssignmentProgress` model and table for immutable milestone progress updates and work observation logs.
- **Pydantic Schemas** (`app/schemas/department.py`, `app/schemas/worker.py`, `app/schemas/assignment.py`):
  - Department management schemas: `DepartmentCreateRequest`, `DepartmentUpdateRequest`, `DepartmentResponse`.
  - Worker provisioning and profile schemas: `WorkerCreateRequest`, `WorkerUpdateRequest`, `WorkerResponse`, `WorkerDetailResponse`.
  - Assignment workflow schemas: `ComplaintAssignRequest`, `ComplaintReassignRequest`, `WorkProgressRequest`, `WorkCompleteRequest`, `AssignmentProgressResponse`, `AssignmentResponse`, `AssignmentDetailResponse`, `WorkerTaskResponse`, `WorkerTaskDetailResponse`.
- **Business Services** (`app/services/department_service.py`, `app/services/worker_service.py`, `app/services/assignment_service.py`):
  - `department_service`: CRUD operations, case-insensitive uniqueness checks, and safe soft-deactivation.
  - `worker_service`: Atomic provisioning of `User` with `FIELD_WORKER` role and `Worker` profile; profile management, availability toggles, and safe deactivation.
  - `assignment_service`: Complaint assignment with category-department validation and row locks; worker task acceptance, work commencement, milestone progress tracking, and remediation completion; concurrency-safe reassignment with reason capture; IDOR-safe worker task queue querying.
- **API Routers & Endpoints** (`app/api/v1/departments.py`, `app/api/v1/workers.py`, `app/api/v1/assignments.py`, `app/api/v1/complaints.py`):
  - Department endpoints: `POST /departments`, `GET /departments`, `GET /departments/{id}`, `PATCH /departments/{id}`, `DELETE /departments/{id}`.
  - Field worker endpoints: `POST /workers`, `GET /workers`, `GET /workers/{id}`, `PATCH /workers/{id}`, `DELETE /workers/{id}`.
  - Worker self-task endpoints: `GET /workers/me/tasks`, `GET /workers/me/tasks/{id}`, `POST /workers/me/tasks/{id}/accept`, `POST /workers/me/tasks/{id}/start`, `POST /workers/me/tasks/{id}/progress`, `POST /workers/me/tasks/{id}/complete`.
  - Complaint assignment endpoints: `POST /complaints/{id}/assign`, `POST /complaints/{id}/reassign`, `GET /complaints/{id}/assignments`.
  - Platform assignment monitoring: `GET /assignments`, `GET /assignments/{id}`.
- **Automated Test Suite** (`tests/test_assignments.py`):
  - 21 comprehensive tests covering department CRUD, worker provisioning, assignment preconditions, IDOR defense, full work execution lifecycle, reassignment, and database partial unique index enforcement.
- **State Machine Integration** (`app/services/complaint_service.py`):
  - Supported `ASSIGNED -> IN_PROGRESS` and `IN_PROGRESS -> RESOLVED_AWAITING_VERIFICATION` transitions initiated by designated field workers.
  - Added timestamp safety check for reopening when timestamps are missing.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.4.1] — 2026-11-19

### Changed (Phase 4.1 — Lifecycle Consistency & Quality Audit)

- **Reopening Grace Period Enforcement** (`app/services/complaint_service.py`):
  - Enforced a server-side 14-day grace period in `execute_transition` when transitioning to `REOPENED`. Reopenings requested more than 14 days after `closed_at` or `resolved_at` are rejected with `BusinessRuleViolationError` (HTTP 422).
- **Test Suite Modernization & Warning Reduction** (`tests/test_auth.py`, `tests/test_complaints.py`):
  - Migrated 12 test assertions from deprecated `status.HTTP_422_UNPROCESSABLE_ENTITY` to standard `status.HTTP_422_UNPROCESSABLE_CONTENT`, eliminating all test-originating deprecation warnings.
  - Added `test_reopen_outside_14_day_grace_period_rejected` to `tests/test_complaints.py`, bringing total tests to 85.
- **Documentation Rectifications** (`TESTING.md`):
  - Corrected test class and method names under `TestLifecycleTransitions` to accurately reflect implementation.
  - Removed hypothetical documentation references to unmodeled `CANCELLED` status and confirmed standardization on `RESOLVED_AWAITING_VERIFICATION`.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.4.0] — 2026-11-19

### Added (Phase 4 — Complaint Management & Lifecycle State Machine)

- **Complaint & Category Schemas** (`app/schemas/category.py`, `app/schemas/complaint.py`):
  - `CategoryResponse`: Schema for civic complaint categories.
  - `LocationCreate` / `LocationResponse`: Geospatial coordinate validation (`[-90, 90]` latitude, `[-180, 180]` longitude).
  - `ComplaintCreateRequest`: Citizen complaint submission payload (title, description, category_id, location).
  - `ComplaintResponse`: Summary schema including tracking number, status, priority, category, and location.
  - `ComplaintDetailResponse`: Full complaint detail including citizen identity and status history.
  - `ComplaintStatusHistoryResponse`: Audit entry schema for complaint state transitions.
  - `ComplaintReviewRequest`: Administrator triage schema for reclassifying category and setting priority with mandatory reason.
  - `ComplaintTransitionRequest`: State machine transition payload with mandatory reason.
- **Complaint & Category Services** (`app/services/category_service.py`, `app/services/complaint_service.py`):
  - `init_categories`: Idempotent seeder initializing 7 standard civic categories across 5 departments.
  - `get_active_categories`: Public category listing filtering by `is_active=True`.
  - `generate_complaint_number`: Sequence-based atomic reference number generator (`CP-YYYY-XXXXX`) backed by PostgreSQL `complaint_number_seq`.
  - `create_complaint`: Submits civic complaints with trusted server-side defaults (`SUBMITTED`, `MEDIUM`) and initial audit history entry.
  - `get_complaint_by_id`: Enforces IDOR security check ensuring citizens can only inspect their own complaints while administrators can inspect all.
  - `list_complaints`: Filtered and paginated complaints retrieval scoped to citizen owner or platform-wide for administrators.
  - `review_complaint`: Administrative triage endpoint allowing category reclassification and priority adjustment with audit history logging.
  - `execute_transition`: Serialized complaint lifecycle state machine using PostgreSQL row-level locks (`with_for_update`), strict transition matrix, role authorization, and audit trail generation.
- **Complaint & Category APIs** (`app/api/v1/categories.py`, `app/api/v1/complaints.py`):
  - `GET /api/v1/categories/`: Public endpoint listing active categories.
  - `POST /api/v1/complaints/`: Authenticated citizen endpoint to submit a complaint (HTTP 201).
  - `GET /api/v1/complaints/`: Authenticated endpoint listing complaints with role scoping and filters.
  - `GET /api/v1/complaints/{id}`: Detailed complaint retrieval protected by IDOR ownership checks.
  - `GET /api/v1/complaints/{id}/history`: Detailed status transition audit history.
  - `PATCH /api/v1/complaints/{id}/review`: Administrator triage endpoint to update priority and category.
  - `POST /api/v1/complaints/{id}/transitions`: Authorized state transition endpoint.
- **Database Migration** (`alembic/versions/7f3a8b2c4d1e_003_seed_departments_categories_and_seq.py`):
  - Created native PostgreSQL sequence `complaint_number_seq` starting at 10001.
  - Seeded 5 core municipal departments (`PWD`, `ELECTRICAL`, `WATER_SEWAGE`, `WASTE_MGMT`, `HEALTH_SANITATION`).
  - Seeded 7 standard civic categories.
- **Automated Test Suite** (`tests/test_complaints.py`):
  - 35 automated tests covering categories, submissions, server defaults, IDOR defense, admin triage, transition matrix validation, preconditions, and PostgreSQL row-level locking concurrency.

### Changed

- Updated `app/core/exceptions.py`: `InvalidStateTransitionError` now accepts an optional explanatory reason.
- Updated `app/main.py`: Application lifespan initializes default civic categories idempotently at startup.
- Updated `app/api/v1/router.py`: Mounted `/categories` and `/complaints` routers.
- Updated `DATABASE.md`, `API_DOCUMENTATION.md`, `ARCHITECTURE.md`, `TESTING.md`, `DEVELOPMENT_LOG.md`, and `README.md`.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.3.0] — 2026-11-19

### Added (Phase 3 — Authentication & Authorization)

- **Authentication Schemas** (`app/schemas/auth.py`):
  - `UserRegisterRequest`: Public registration payload with email normalisation, name cleaning, password confirmation validation, and 8-72 character boundary enforcing bcrypt safety.
  - `UserLoginRequest`: Email and password login payload.
  - `UserResponse`: Safe user profile schema excluding password hashes and internal security fields.
  - `TokenResponse`: JWT bearer token schema with `access_token`, `token_type`, `expires_in`, and nested user profile.
- **Authentication Service** (`app/services/auth_service.py`):
  - `init_roles`: Idempotent seeding ensuring CITIZEN, ADMINISTRATOR, and FIELD_WORKER roles exist.
  - `register_citizen`: Secure citizen registration service assigning the `CITIZEN` role by default and checking email uniqueness.
  - `authenticate_user`: Constant-time password verification using bcrypt against database hashes, including a dummy verification for nonexistent accounts to prevent side-channel timing attacks and account enumeration.
  - `generate_auth_token`: Issue HMAC-SHA256 JWT access tokens embedding user ID, email, and role.
- **Security & Authorization Dependencies** (`app/api/deps.py`):
  - `get_current_user`: Extract and decode JWT bearer token, fetching the authenticated user from the database.
  - `get_current_active_user`: Enforce active account status (`is_active is True`).
  - `require_roles`: Role-based access control factory verifying user role against permitted roles.
  - `require_citizen`, `require_admin`, `require_worker`: Declarative role dependency shortcuts.
- **Authentication API Endpoints** (`app/api/v1/auth.py`):
  - `POST /api/v1/auth/register` (HTTP 201): Public citizen registration returning safe user profile.
  - `POST /api/v1/auth/login` (HTTP 200): Email/password authentication returning signed JWT access token.
  - `GET /api/v1/auth/me` (HTTP 200): Authenticated profile retrieval requiring valid Bearer token.
- **Offline Administrator Provisioning** (`app/core/admin_provision.py`):
  - CLI command (`python -m app.core.admin_provision`) to safely provision verified administrator accounts offline, preventing public self-registration.
- **Role Seed Migration** (`alembic/versions/5c60c8914494_002_seed_initial_roles.py`):
  - Idempotent Alembic data migration inserting CITIZEN (1), ADMINISTRATOR (2), and FIELD_WORKER (3) into `roles`.
- **Comprehensive Auth Test Suite** (`tests/test_auth.py`):
  - 25 automated tests covering registration, login, timing attack resistance, token expiration, profile retrieval, RBAC protection, and admin provisioning.

### Changed

- Updated `tests/conftest.py` with SQLAlchemy 2.0 savepoints (`join_transaction_mode="create_savepoint"`) for isolated test transactions with the FastAPI TestClient.
- Mounted auth router under `/api/v1/auth` in `app/api/v1/router.py`.
- Updated `API_DOCUMENTATION.md`, `SECURITY.md`, `ARCHITECTURE.md`, `DEVELOPMENT_LOG.md`, and `TESTING.md`.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.2.0] — 2026-11-19

### Added (Phase 2 — Database Models & Alembic Migrations)

- SQLAlchemy 2.0 ORM models for all 13 core entities:
  - `Role` (`app/models/role.py`): Authorization roles for Citizens, Administrators, and Field Workers.
  - `User` (`app/models/user.py`): Core user identity with UUID PK, unique email, bcrypt hash, role FK.
  - `Department` (`app/models/department.py`): Municipal departments with unique code and contact details.
  - `Category` (`app/models/category.py`): Civic complaint categories linked to managing departments.
  - `Worker` (`app/models/worker.py`): 1-to-1 extension profile for field resolution technicians.
  - `Location` (`app/models/location.py`): Structured coordinates with database-level latitude/longitude check constraints.
  - `Complaint` (`app/models/complaint.py`): Core civic complaint entity with tracking number, status, and priority enums.
  - `Assignment` (`app/models/assignment.py`): Audit trail of complaint task allocations to field workers.
  - `Attachment` (`app/models/attachment.py`): Metadata and filesystem relative storage paths for evidence.
  - `ComplaintStatusHistory` (`app/models/status_history.py`): Immutable audit log of all complaint status transitions.
  - `Notification` (`app/models/notification.py`): In-app notification messages linked to recipients and complaints.
  - `Feedback` (`app/models/feedback.py`): Citizen reviews with 1-to-1 unique constraint and 1-5 rating check constraint.
  - `AIAssessment` (`app/models/ai_assessment.py`): AI/ML inference storage with confidence score check constraint.
- `TimestampMixin` in `app/db/base.py` for timezone-aware UTC `created_at` and `updated_at`.
- Central model registry in `app/models/__init__.py` for `Base.metadata` autodiscovery.
- Initial Alembic migration `001_initial_schema` (`dc808166f213_001_initial_schema.py`) creating all 13 tables, foreign keys, indexes, and check constraints in topological order.
- Dynamic environment configuration in `alembic/env.py` resolving `DATABASE_URL` safely without hardcoding secrets.
- Comprehensive database test suite (`tests/test_database.py`): 16 tests verifying metadata, constraints, relationships, cascades, and migration reversibility on `civicpulse_test`.

### Changed

- Updated `app/core/constants.py` with `UserRole` (`CITIZEN`, `ADMINISTRATOR`, `FIELD_WORKER`) and `AssignmentStatus`.
- Refined `app/config.py` `DATABASE_URL` using `URL.create` for RFC 3986 compliance.
- Updated `DATABASE.md` with complete Entity-Relationship diagram and schema specifications.
- Updated `ARCHITECTURE.md` with Data Layer model details.
- Updated `TESTING.md` with Phase 2 database and migration testing results.

---

## [0.8.3] — 2026-11-21

### Validated & Resolved (Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency)

- **Environment Variable Consistency & Pydantic Alias Support (`app/config.py`)**:
  - Resolved `APP_ENV` vs `ENVIRONMENT` naming conflict using Pydantic `AliasChoices("APP_ENV", "ENVIRONMENT")`.
  - Resolved `DB_POOL_SIZE` vs `POSTGRES_POOL_SIZE`, `DB_MAX_OVERFLOW` vs `POSTGRES_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` vs `POSTGRES_POOL_TIMEOUT` using `AliasChoices`.
  - Resolved `JWT_SECRET_KEY` vs `SECRET_KEY`, `JWT_ALGORITHM` vs `ALGORITHM`, and token lifespan parameters using `AliasChoices`.
  - Added direct `DATABASE_URL` string support with automatic normalization of legacy `postgres://` and standard `postgresql://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.
  - Preserved `APP_DEBUG` as a dedicated setting without aliasing to `DEBUG`, avoiding fatal bool-parsing collisions with Windows system toolchains (`DEBUG="release"`).
- **Frontend API Base URL Normalization & Resilience (`frontend/src/services/apiClient.js`)**:
  - Implemented automatic URL normalization that strips trailing slashes and guarantees the `/api/v1` path prefix is appended if only a root origin is supplied.
  - Prevents 404 and double-slash routing errors regardless of whether the user sets `https://<service>.onrender.com`, `https://<service>.onrender.com/api/v1`, or an address with trailing slashes.
- **Administrator Provisioning Audit & Verification (`scripts/create_initial_admin.py`)**:
  - Verified that the canonical provisioning script is `scripts/create_initial_admin.py` and purged incorrect references to `scripts.provision_admin`.
  - Verified that credentials are accepted either interactively via masked terminal input (`getpass.getpass()`) or headlessly via environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_NAME`), never leaking passwords in process tables (`ps aux`) or CLI history.
  - Verified in-memory password erasure (`del password`) immediately following bcrypt hashing.
- **Free-Tier Deployment Runbook Update (`FREE_DEPLOYMENT.md`)**:
  - Updated environment variable reference tables to explicitly document canonical names alongside accepted aliases.
  - Added documentation for the single `DATABASE_URL` connection string alternative.
  - Clarified frontend base URL expectations and verified administrator provisioning instructions.
- **Automated Preflight Test Suite (`tests/test_phase8_production.py`)**:
  - Added `TestPhase83PreflightConsistency` suite with 4 new tests covering environment variable aliases, driver URI normalization, administrator script path contracts, and API client URL resilience (23/23 tests passing in file).

---

---

## [0.1.0] — 2026-11-18

### Added (Phase 1 — Project Foundation)

- FastAPI application factory with lifespan management (`app/main.py`).
- Environment-based configuration via pydantic-settings (`app/config.py`).
- SQLAlchemy engine and session factory with lazy initialisation (`app/db/session.py`).
- Declarative base class for ORM models (`app/db/base.py`).
- Domain exception hierarchy with 8 exception types (`app/core/exceptions.py`).
- Global exception handlers mapping domain exceptions to HTTP responses.
- Application enumerations: UserRole, ComplaintStatus, PriorityLevel, NotificationType, AttachmentType (`app/core/constants.py`).
- Complaint lifecycle state machine transitions (`COMPLAINT_STATUS_TRANSITIONS`).
- Password hashing with bcrypt via Passlib (`app/core/security.py`).
- JWT access and refresh token creation and validation (`app/core/security.py`).
- Request logging middleware with unique request ID generation (`app/core/middleware.py`).
- Standard API response schemas: StandardResponse, ErrorResponse, PaginationParams, PaginatedResponse (`app/schemas/common.py`).
- Health-check endpoint: `GET /api/v1/health`.
- Test infrastructure with pytest and FastAPI TestClient.
- 5 health-check tests verifying response status, structure, content, and middleware.
- Project documentation: README, ARCHITECTURE, DATABASE, API_DOCUMENTATION, SECURITY, TESTING, AI_DOCUMENTATION, DEVELOPMENT_LOG, CHANGELOG.
- `.env.example` template with all configuration variables.
- `.gitignore` for Python, IDE, OS, and upload file exclusions.
- `requirements.txt` with pinned dependency versions.
