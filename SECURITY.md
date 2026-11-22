# CivicPulse — Security Architecture

## Overview

CivicPulse implements multiple security layers to protect user data, prevent unauthorized access, and ensure complaint management integrity.

## Current Implementation (Phase 3)

| Security Feature | Status | Module |
|---|---|---|
| Password hashing (bcrypt) | ✅ Implemented | `app/core/security.py` |
| 72-character password boundary | ✅ Implemented | `app/schemas/auth.py` |
| JWT token management (HS256) | ✅ Implemented | `app/core/security.py` |
| Timing attack mitigation | ✅ Implemented | `app/services/auth_service.py` |
| Public registration guard (CITIZEN only) | ✅ Implemented | `app/schemas/auth.py`, `app/services/auth_service.py` |
| Offline Administrator Provisioning CLI | ✅ Implemented | `app/core/admin_provision.py` |
| Role-Based Access Control (RBAC) | ✅ Implemented | `app/api/deps.py` |
| Active account enforcement | ✅ Implemented | `app/api/deps.py`, `app/services/auth_service.py` |
| Database-backed token verification | ✅ Implemented | `app/api/deps.py` |
| Domain exception hierarchy | ✅ Implemented | `app/core/exceptions.py` |
| Environment-based secrets | ✅ Implemented | `app/config.py` |
| Request ID tracing | ✅ Implemented | `app/core/middleware.py` |
| `.env` gitignored | ✅ Configured | `.gitignore` |

## Planned Security Features

| Feature | Phase | Description |
|---|---|---|
| User authentication endpoints | Phase 3 | ✅ Implemented (`/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me`) |
| Role-based access control | Phase 3 | ✅ Implemented (`require_citizen`, `require_admin`, `require_worker`) |
| Complaint ownership validation | Phase 4 | Citizens can only view/edit their own complaints |
| Input validation | Phase 4+ | Pydantic schema validation on all inputs |
| File upload validation | Phase 7 | File type, size, and content validation |
| Rate limiting | Phase 13 | Request rate limiting per client |
| Audit logging | Phase 13 | Sensitive operation logging |
| SQL injection prevention | Phase 13 | Verification via SQLAlchemy parameterised queries |
| CORS configuration | Phase 13 | Restrict allowed origins for frontend |

## Authentication Design

### Password Storage & Input Boundary
- Passwords are hashed with **bcrypt** (cost factor 12) via Passlib.
- Bcrypt truncates inputs silently at 72 bytes. To prevent truncation vulnerabilities where passwords differing only after character 72 are treated as identical, `UserRegisterRequest` and `UserLoginRequest` enforce `max_length=72` via Pydantic schema validation.
- Plain-text passwords are never logged, stored in the database, or returned in API responses.

### Timing-Safe Verification & Anti-Enumeration
- During authentication, when an email does not exist in the database, the system executes a dummy bcrypt verification against a static benchmark hash.
- This ensures authentication requests consume identical CPU time regardless of whether the email exists, defeating side-channel timing attacks.
- Identical error messages ("Invalid email or password") are returned for nonexistent users and invalid passwords to prevent username enumeration.

### JWT Tokens
- **Access tokens**: Signed with HMAC-SHA256 (`HS256`) using `JWT_SECRET_KEY` from environment configuration.
- **Claims**:
  - `sub`: User UUID string
  - `email`: User registered email
  - `role`: User role name (`CITIZEN`, `ADMINISTRATOR`, `FIELD_WORKER`)
  - `exp`: UTC expiration timestamp (default: 30 minutes)
  - `iat`: UTC issuance timestamp
- Tokens never contain passwords, secrets, or sensitive PII.

### Authorization Model (RBAC)
- Three application roles: `CITIZEN`, `ADMINISTRATOR`, `FIELD_WORKER`.
- Enforced at route handlers using FastAPI dependency injection (`app/api/deps.py`):
  - `get_current_user`: Decodes JWT, validates signature/expiration, and fetches the live user from PostgreSQL.
  - `get_current_active_user`: Enforces `user.is_active is True`. Deactivated accounts cannot perform actions even with a valid JWT.
  - `require_roles(*roles)`: Factory returning a dependency that verifies `user.role.name` against permitted roles.
  - Role shortcuts: `require_citizen`, `require_admin`, `require_worker`.
- Tokens are verified against current database state on every request to prevent forged or stale role claims.

### Administrative Account Provisioning
- CivicPulse provides NO public self-registration endpoint for `ADMINISTRATOR` or `FIELD_WORKER` roles.
- `POST /api/v1/auth/register` hardcodes assignment to the `CITIZEN` role.
- Initial or emergency administrative users are provisioned exclusively via an offline CLI utility:
  ```bash
  python -m app.core.admin_provision --email admin@civicpulse.org --password "<SECURE_PASSWORD>" --name "System Administrator"
  ```
- This utility directly seeds the administrator into PostgreSQL with appropriate bcrypt hashing and idempotency checks.

## Security Configuration

All security-sensitive values are managed via environment variables:
- `JWT_SECRET_KEY` — Must be a strong, randomly generated value.
- `DB_PASSWORD` — PostgreSQL password.
- None of these appear in committed code or documentation.

## Incident Response

*To be expanded in Phase 13.*
