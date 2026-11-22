# CivicPulse

**Civic Issue Reporting, Monitoring & Intelligence Platform**

CivicPulse is a full-stack civic-tech platform that connects Citizens, Administrators, and Resolution Teams to streamline civic complaint management — from submission through investigation, resolution, and verification.

## Current Status

- **Phase 1 — Project Foundation & Configuration**: ✅ Complete
- **Phase 2 — Database Models & Alembic Migrations**: ✅ Complete (13 core entities, PostgreSQL 18, migrations verified)
- **Phase 3 — Authentication & Authorization**: ✅ Complete (JWT, bcrypt, citizen registration, login, RBAC, 49/49 tests passing)
- **Phase 4 — Complaint Management & Lifecycle State Machine**: ✅ Complete (Complaint submission, tracking number sequence, IDOR protection, admin triage, serialized state machine with PostgreSQL row-level locks, 85/85 tests passing)
- **Phase 5 — Worker Assignment & Department Management**: ✅ Complete (Department management, worker provisioning, complaint assignment/reassignment, worker task queues with IDOR defense, on-site milestones, PostgreSQL partial unique index)
- **Phase 5.1 — Assignment Integrity, Lifecycle Consistency & Security Audit**: ✅ Complete (Approved Phase 4 state machine strictly enforced, atomic reassignment transition chaining, standardized row-lock order, endpoint parity, service-layer deactivation guards, 135/135 tests passing)
- **Phase 6.1 — Citizen Dashboard & Unified Complaint Timeline**: ✅ Complete (Citizen personal metrics, single-query conditional aggregation, capped activity feeds, unified chronological complaint narrative, administrative remark redaction, bounded worker access, 168/168 tests passing)
- **Phase 6.2 — Moderated Public Complaint Feed & Community Following**: ✅ Complete (Alembic migration 005, public content moderation, citizen unpublishing, community following, privacy allowlist projection, automatic privacy enforcement, 206/206 tests passing)
- **Phase 6.3 — SLA Management, Dual Clocks & Intelligent Escalation**: ✅ Complete (Alembic migration 006, dual independent response/resolution clocks, pause accounting for ON_HOLD, 4-tier precedence with PostgreSQL advisory locks, deterministic escalation progression, append-only cycle history with database trigger immutability, admin SLA evaluation API)
- **Phase 6.3.1 — SLA Lifecycle Corrections & Escalation Verification**: ✅ Complete (Response/resolution clock semantic audit, reopen-from-closed grace period, status history audit logging)
- **Phase 6.3.2 — Final Resolution SLA Semantics, Precision & Verification**: ✅ Complete (Exclusive resolution stop condition at RESOLVED_AWAITING_VERIFICATION, Decimal escalation comparison without rounding, non-fabrication on rejected/duplicate, 280/280 tests passing across 9 test files)
- **Phase 6.4 — In-App Notifications & Event Integration**: ✅ Complete (Alembic migration 007, deterministic event keys with PostgreSQL partial unique index, ON CONFLICT DO NOTHING bulk dispatch, complaint lifecycle integration, worker milestones, SLA warnings & breaches, follower privacy boundaries, authenticated inbox API, 326/326 tests passing across 10 test files)
- **Phase 6.4.1 — Notification Event Classification, Transaction Integrity & Final Security Audit**: ✅ Complete (SLA Warning/Breach enum classification, transaction atomicity & rollback integrity proofs, multi-threaded concurrent idempotency verification, conflict arbiter index matching, follower redaction audit, IDOR security hardening, 342/342 tests passing across 10 test files)
- **Phase 6.5 — Final Integration, Security, Privacy, Database Integrity & Performance Audit**: ✅ Complete (Comprehensive audit of Phases 1–6.4.1, partial index arbiter matching, outer rollback integrity, reassignment cutoff anti-spoofing, unpublish audit immutability, query eager loading optimization, 0 project deprecation warnings, 362/362 tests passing across 11 test files)
- **Phase 6.5.1 — Final API Contract, Database Schema & Privacy Reconciliation**: ✅ Complete (Authoritative 53-route inventory, 1:1 model-to-DB column parity, verified public feed zero-pincode allowlist, true Alembic migration chain reconciliation, 369/369 tests passing across 12 test files)
- **Phase 7.1 — Frontend Foundation, UI Design System & Authentication**: ✅ Complete (React 19, TypeScript, Vite, React Router v7, official palette design tokens, component library, public/auth layouts, secure in-memory JWT authentication, role guards, foundation portals for Citizen, Administrator, and Field Worker, build verified in 264ms)
- **Phase 7.2 — Citizen Dashboard, Complaint Submission & Tracking**: ✅ Complete (Complete Citizen Portal integrated with FastAPI backend: personalized dashboard with live backend metrics, complaint submission form with dynamic category lookup and geolocation, paginated complaint listing with status/priority filtering, detailed dossier with location coordinates and visual milestone stepper, unified chronological timeline, and citizen lifecycle actions for verification and reopening)
- **Phase 7.3 — Public Complaint Feed & Community Following**: ✅ Complete (Unauthenticated public community feed with category/status filtering, public detail view enforcing strict privacy allowlist without PII or coordinates, and authenticated citizen community following with dedicated Following feed)
- **Frontend Stack Migration — TypeScript to JavaScript (JS/JSX)**: ✅ Complete (100% converted to pure ES6+ JavaScript and React JSX; zero TypeScript syntax or configuration remaining; clean Vite production build)
- **Phase 7.4 — Field Worker Portal: Dashboard, Assigned Tasks & Resolution Workflow**: ✅ Complete (Operational technician dashboard with live metrics, assigned work orders queue with status/priority filtering, detailed task dossier with authorized location data and navigation links, full lifecycle actions for acceptance, work start, progress logs, and resolution completion)
- **Phase 7.5 — Administrator Portal: Dashboard, Complaint Triage, Workforce & Department Management**: ✅ Complete (Central operational command center with real platform metrics, 8-tab triage management, dual-clock SLA performance card, full worker dispatch and reassignment modals, department CRUD management, public community moderation directory, and strict RBAC guards)
- **Phase 7.6 — SLA Monitoring, Policy Management & Notification Center**: ✅ Complete (Dual-clock SLA monitoring dashboard with on-demand evaluation, policy management enforcing resolution hierarchy, cross-role notification center with unread badge counter, individual/bulk read triggers, and role-aware navigation)
- **Phase 7.7 — Maps, Geolocation & Location-Based Complaint Visualization**: ✅ Complete (Interactive Leaflet 1.9.4 and OpenStreetMap integration: citizen incident location picker with draggable pin and native GPS detection, dedicated citizen complaint map at `/citizen/map`, municipal administrator geospatial intelligence and ward hotspots dashboard at `/admin/map`, field worker navigation map embedded in task details, and verified public privacy protections)
- **Phase 7.8 — Full-System Integration, Security, Accessibility & Production Readiness Audit**: ✅ Complete (Full-system verification of Phases 7.1–7.7: rectified `categoryService.getCategories` and map pagination integration defects, removed unverified municipal center assumptions with neutral national fallback, enforced SLA batch evaluation confirmation, enhanced dialog keyboard accessibility, verified zero console logs, clean Vite production build in 692ms, 0 linter errors, and 369/369 backend tests passing)
- **Phase 7.9 — End-to-End User Journeys, Acceptance Testing & Release Readiness**: ✅ Complete (Full multi-role acceptance verification across Citizen, Administrator, and Field Worker portals; complete cross-role complaint resolution and verification lifecycle; negative and security RBAC/IDOR/privacy validations; route-level dynamic code splitting with React.lazy and Suspense reducing initial bundle size by 61.8% to 289 kB; clean Vite production build in 238ms; 0 linter errors; 369/369 backend tests passing across 12 test files)
- **Phase 7.9.1 — Browser-Based Acceptance Verification, Test Data Cleanup & Release Sign-Off**: ✅ Complete (Verified live server & asset delivery across all 53 JS chunks via HTTP; executed targeted test data cleanup restoring development database to pristine 0-user state; documented Chrome DevTools protocol host session boundaries; verified clean frontend production build in 550ms with 0 errors and 0 TS files; 369/369 backend regression tests passing)
- **Phase 8.0 — Production Deployment Preparation**: ✅ Complete (Environment-aware configuration with dev/prod separation, disabled docs in prod, dynamic CORS parser, parameterized PostgreSQL connection pool and SSL mode, sanitized global exception handler, secure initial admin CLI utility, production `.env.production.example` and `frontend/.env.production.example` templates, Nginx reverse proxy configuration with TLS/HSTS/CSP, systemd Gunicorn service unit, authoritative `DEPLOYMENT.md` operational runbook, clean Vite build in 470ms, 0 lint errors, 100% JS/JSX compliance, 0 localStorage tokens, 369/369 tests passing)
- **Phase 8.1 — Deployment Runbook Validation & Launch Preparation**: ✅ Complete (Validated deployment configuration and runbooks: removed HSTS preload to protect municipal subdomains, corrected Nginx health check proxy target to /api/v1/health, resolved static asset header inheritance, isolated script blocking in upload locations, hardened systemd with PYTHONDONTWRITEBYTECODE and automatic LogsDirectory, added pre-restoration safety snapshots and archive integrity verification, documented destructive Alembic rollback limitations, and added automated deployment artifact and headless admin execution test suite; 384/384 backend tests passing)
- **Phase 8.2 — Free-Tier Demonstration Deployment Preparation**: ✅ Complete (Configured zero-cost demonstration deployment architecture using Cloudflare Pages for React SPA, Render for FastAPI backend, and Supabase for PostgreSQL with PostGIS: added Cloudflare Pages `_redirects` and `_headers` with Render CSP whitelisting, added PEP 508 `gunicorn` marker in `requirements.txt` for Render Linux compatibility, resolved Render-to-Supabase IPv4 limitation via Supavisor pooler port 5432 session mode, authored comprehensive `FREE_DEPLOYMENT.md` runbook, verified 0 lint errors, clean 613ms Vite build, 100% JS/JSX and in-memory JWT compliance, 388/388 backend tests passing)
- **Phase 8.3 — Free-Tier Deployment Preflight & Configuration Consistency**: ✅ Complete (Resolved environment variable naming conflicts across Pydantic settings with AliasChoices, added resilient URL parsing in frontend apiClient, updated deployment documentation; 388/388 tests passing)
- **Phase 8.4 — Supabase Database Connection & Migration Readiness**: ✅ Complete (Created standalone verify_db_connection.py preflight utility, hardened .gitignore rules for production credentials, validated unbroken linear Alembic chain; 392/392 tests passing)
- **Phase 8.5 — Dual-Environment Database Setup & Free Cloud Deployment Preparation**: ✅ Complete (Configured and verified dual-environment operation: local PostgreSQL 18.7 on localhost:5433 with civicpulse/civicpulse_test databases, production safety validator blocking test databases in production, comprehensive FREE_DEPLOYMENT.md documentation; 400/400 tests passing)
- **Phase 8.6 — Hosted Supabase Database Initialization**: ⚠️ Preflight Verified / Awaiting Hosted Credentials (Enhanced verify_db_connection.py CLI with --url and --env-file flags and isolated engine instantiation, verified local PostgreSQL 18 environment preserved intact at revision b7c8d9e0f1a2, 402/402 tests passing; awaiting user-supplied hosted DATABASE_URL to apply migrations)
- **Phase 8.7 — Database Environment Isolation Fix + Frontend Completion**: ✅ Complete (Resolved diagnostic configuration inconsistency, synchronized Settings DB_* parameters with DATABASE_URL, added unreplaced template placeholder validation, enforced production localhost safety guards, verified all 3 frontend portals with in-memory JWT authentication; 408/408 backend tests passing, clean Vite build in 266ms)
- **Phase 8.8 — Supabase Hosted PostgreSQL Connection & Initial Migration Preflight**: ⚠️ Preflight Verified / Awaiting Hosted Credentials (Audited 7-migration source of truth chain to head b7c8d9e0f1a2, verified .gitignore secret protection, preserved local PostgreSQL 18.7 database intact, reinforced strict stop conditions; awaiting user-supplied hosted DATABASE_URL to apply migrations)
- **Phase 8.9 — Actual Supabase Connection, Hosted Schema Preflight & Verification**: ⚠️ Preflight Verified / Awaiting Hosted Credentials (Enhanced get_settings() with dynamic multi-tier environment loading, queried active schema to resolve 18-table count discrepancy, verified local database preservation; 409/409 backend tests passing)

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, JavaScript (ES6+ / JSX), Vite, React Router v7, Leaflet 1.9.4, OpenStreetMap, HTML5, CSS3, Fetch API |
| Backend | Python 3.11, FastAPI |
| Data Validation | Pydantic 2.x |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL + PostGIS |
| Migrations | Alembic |
| Authentication | JWT (PyJWT) + bcrypt (in-memory frontend handling) |
| File Processing | Pillow |
| Testing | pytest |

## Project Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (with PostGIS extension for geospatial phases)

### Installation

1. **Clone the repository** and navigate to the project directory.

2. **Create and activate a virtual environment** (recommended):
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # Linux/macOS
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Fill in database credentials and JWT secret key
   - Generate a JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

5. **Create the PostgreSQL database:**
   ```sql
   CREATE DATABASE civicpulse;
   CREATE USER civicpulse WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE civicpulse TO civicpulse;
   ```

6. **Run database migrations** (available from Phase 2):
   ```
   alembic upgrade head
   ```

7. **Start the development server:**
   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Start the frontend development server (Phase 7.1+):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   The frontend runs at: http://localhost:5173

9. **Access API documentation:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Running Tests

```
pytest -v
```

## Project Structure

```
CivicPulse/
├── app/                    # Backend application source code (FastAPI)
│   ├── api/v1/             # Versioned API route handlers
│   ├── core/               # Security, exceptions, constants, middleware
│   ├── db/                 # Database engine and session management
│   ├── models/             # SQLAlchemy ORM models (17 registered models)
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business logic layer
│   └── ai/                 # AI/ML processing modules
├── frontend/               # Frontend application source code (React 19, Vite)
│   ├── src/
│   │   ├── components/     # Reusable design system UI components
│   │   ├── context/        # Authentication & state management
│   │   ├── layouts/        # Public and Authenticated layouts
│   │   ├── pages/          # Home, Auth, Citizen, Worker, and Admin portals
│   │   ├── routes/         # Protected routing and RBAC guards
│   │   ├── services/       # Centralized API client & domain services
│   │   ├── styles/         # Official palette tokens & global CSS
│   │   └── types/          # Domain models, schema validators and contracts (JS ES6+)
│   └── package.json
├── alembic/                # Database migrations (PostgreSQL 18)
├── tests/                  # Test suite (409 backend tests)
├── uploads/                # Local file storage (gitignored)
└── docs/                   # Additional documentation
```

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Backend architecture and design decisions |
| [DATABASE.md](DATABASE.md) | Database schema and relationships |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | API endpoint reference |
| [SECURITY.md](SECURITY.md) | Security architecture |
| [TESTING.md](TESTING.md) | Testing methodology and results |
| [AI_DOCUMENTATION.md](AI_DOCUMENTATION.md) | AI/ML architecture |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production VPS deployment runbook (Nginx + systemd + PostgreSQL) |
| [FREE_DEPLOYMENT.md](FREE_DEPLOYMENT.md) | Free-tier deployment runbook (Cloudflare Pages + Render + Supabase) |
| [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Phase-wise progress |
| [CHANGELOG.md](CHANGELOG.md) | Version changelog |

## User Categories

| Role | Description |
|---|---|
| **Citizen** | Submits complaints, tracks status, provides feedback |
| **Administrator** | Manages complaints, departments, workers, assignments |
| **Worker** | Receives assignments, investigates, resolves complaints |

## License

Proprietary — All rights reserved.
