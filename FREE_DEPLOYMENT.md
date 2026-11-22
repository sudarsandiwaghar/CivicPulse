# CivicPulse — Dual-Environment Database Setup & Free-Tier Deployment Guide
## Local Development (PostgreSQL 18) + Hosted Demonstration (Cloudflare Pages + Render + Supabase)

This guide provides instructions for operating CivicPulse across **two distinct environments** using a single unified codebase:
1. **Local Development Environment:** Native PostgreSQL 18 on `localhost:5433` with isolated development (`civicpulse`) and test (`civicpulse_test`) databases.
2. **Hosted Demonstration Environment:** 100% free cloud stack using Supabase PostgreSQL (Database), Render Web Service (Backend API), and Cloudflare Pages (Frontend SPA).

---

### Architecture Overview

```
                      [ USER CLIENTS ]
                             │
       ┌─────────────────────┴─────────────────────┐
       │                                           │
  (Local Dev)                                (Hosted Prod)
  http://localhost:5173                      https://<project>.pages.dev
       │                                           │
       │ Vite Dev Server                           │ Cloudflare Pages (SPA)
       ▼                                           ▼
  Local FastAPI Backend                      Render Free Web Service
  http://localhost:8000                      https://<app>.onrender.com
       │                                           │
       │ Local PostgreSQL 18                       │ Supavisor Pooler (Port 5432)
       │ (Port 5433)                               │ SSL (sslmode=require)
       ▼                                           ▼
  Local DBs:                                 Supabase PostgreSQL (Free)
  - civicpulse (Dev)                         - postgres (Live DB)
  - civicpulse_test (Pytest)                 - PostGIS + UUID Extensions
```

---

## 1. Dual-Environment Architecture & Safeguards

CivicPulse enforces strict separation between local and hosted production environments:

1. **Independent State & Isolation:** Local development and hosted databases never communicate, share credentials, or cross-replicate data.
2. **No Silent Fallbacks:** The backend will never silently fall back from a failed hosted production connection to `localhost`. If production credentials fail, the application halts immediately with clear diagnostics.
3. **Test Database Protection:** In `app/config.py`, an automated safeguard blocks any attempt to boot production mode against a database named `*_test` or `test`.
4. **Credential Isolation:** All `.env`, `.env.*`, `*.pem`, and `*.key` files are strictly excluded from Git in `.gitignore`. Hosted production secrets are injected solely through Render's dashboard.

---

## 2. Local PostgreSQL Development Environment

CivicPulse uses a local PostgreSQL 18 installation for development and automated testing.

### 2.1 Local Configuration Specifications
- **Host:** `localhost`
- **Port:** `5433` (Local PostgreSQL 18 service port)
- **Development Database:** `civicpulse`
- **Test Database:** `civicpulse_test` (Isolated database for `pytest` regression suite)
- **Local Database User:** `civicpulse`

### 2.2 Local Configuration File (`.env`)
Create or verify `.env` in the project root:
```ini
APP_NAME=CivicPulse
APP_VERSION=0.1.0
APP_ENV=development
APP_DEBUG=True
API_V1_PREFIX=/api/v1

# Local PostgreSQL 18 Configuration
DB_HOST=localhost
DB_PORT=5433
DB_USER=civicpulse
DB_PASSWORD=[YOUR_LOCAL_PASSWORD]
DB_NAME=civicpulse

# JWT Configuration (Local Secret)
JWT_SECRET_KEY=local_development_jwt_secret_key_at_least_32_bytes_long
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# File Storage & Limits
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=10
RATE_LIMIT_PER_MINUTE=60
LOG_LEVEL=INFO
```

### 2.3 Verify Local Connectivity & Schema
Run the standalone preflight diagnostic utility:
```bash
python scripts/verify_db_connection.py
```
- Verifies connectivity to `localhost:5433/civicpulse`.
- Confirms current Alembic schema revision matches head `b7c8d9e0f1a2`.
- Confirms the exact **18 application and tracking tables**:
  1. `ai_assessments`
  2. `alembic_version`
  3. `assignment_progress`
  4. `assignments`
  5. `attachments`
  6. `categories`
  7. `complaint_followers`
  8. `complaint_sla_history`
  9. `complaint_status_history`
  10. `complaints`
  11. `departments`
  12. `feedback`
  13. `locations`
  14. `notifications`
  15. `roles`
  16. `sla_policies`
  17. `users`
  18. `workers`

### 2.4 Run Local Backend Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Base URL: `http://localhost:8000/api/v1`
- Swagger UI (Development only): `http://localhost:8000/docs`

### 2.5 Run Local Frontend Development Server
```bash
cd frontend
npm run dev
```
- Frontend Application: `http://localhost:5173`
- Default API Client Target: `http://localhost:8000/api/v1`

---

## 3. Step 1: Provision Hosted Database on Supabase

### 3.1 Create Supabase Project
1. Log in to [Supabase Dashboard](https://supabase.com/dashboard).
2. Click **New Project**.
3. Fill in project details:
   - **Name**: `civicpulse-demo`
   - **Database Password**: Generate and save a strong password (e.g., using `python -c "import secrets; print(secrets.token_urlsafe(24))"`).
   - **Region**: Choose the region closest to you or your Render service region (e.g., `US East (N. Virginia)` or `Frankfurt`).
   - **Pricing Plan**: **Free** ($0/month).
4. Click **Create new project** and wait 1–2 minutes for provisioning.

### 3.2 Enable Required Database Extensions
CivicPulse requires `postgis` (for incident coordinates and geospatial queries) and `uuid-ossp` (for UUID generation):
1. In the Supabase sidebar, navigate to **Database** -> **Extensions**.
2. Search for `postgis` and toggle it **ON** (or verify it is enabled).
3. Search for `uuid-ossp` and toggle it **ON**.
   *(Alternatively, open **SQL Editor** and run:)*
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   ```

### 3.3 Retrieve the Connection String (CRITICAL: IPv4 Pooler)
> **IMPORTANT NETWORKING NOTE:** Render free tier instances **do NOT support outbound IPv6**. Supabase direct database connections (`db.[ref].supabase.co`) only resolve to IPv6 on the free tier. Therefore, you **MUST use the Supabase Connection Pooler** (Supavisor) host, which supports IPv4:

1. In Supabase, go to **Project Settings** (gear icon) -> **Database**.
2. Scroll to **Connection string** and select the **URI** tab.
3. Switch the mode from *Transaction* to **Session** (Port `5432`):
   - **Host**: `aws-0-[region].pooler.supabase.com`
   - **Port**: `5432`
   - **Database**: `postgres`
   - **User**: `postgres.[PROJECT-REF]`
   - **Password**: `[YOUR-SUPABASE-DB-PASSWORD]`
4. Note your database parameters:
   ```ini
   DB_HOST=aws-0-[region].pooler.supabase.com
   DB_PORT=5432
   DB_USER=postgres.[PROJECT-REF]
   DB_PASSWORD=[YOUR-SUPABASE-DB-PASSWORD]
   DB_NAME=postgres
   DB_SSLMODE=require
   ```

---

## 4. Step 2: Deploy Backend Web Service on Render

### 4.1 Create Render Web Service
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository** and connect your GitHub repository containing CivicPulse.
4. Configure the service parameters:
   - **Name**: `civicpulse-api` (or custom name; your URL will be `https://civicpulse-api.onrender.com`)
   - **Region**: Same geographical region as your Supabase database.
   - **Branch**: `master` (or your main branch).
   - **Root Directory**: Leave blank (uses repo root).
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
     *(Installs production dependencies without running migrations, as the hosted Supabase database is already initialized and migrated to head revision `b7c8d9e0f1a2`).*
   - **Start Command**:
     ```bash
     gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
     ```
     *(Memory-conscious worker configuration: 2 workers consuming ~240-280 MB RAM, safely below Render Free's 512 MB ceiling).*
   - **Instance Type**: **Free** (512 MB RAM, 0.1 CPU).

### 4.2 Configure Render Environment Variables
Under the **Environment Variables** section, add the following variables:

| Canonical Variable Name | Accepted Alias | Value | Description |
|---|---|---|---|
| `PYTHON_VERSION` | — | `3.11.9` | Ensures Python 3.11 runtime on Render |
| `APP_ENV` | `ENVIRONMENT` | `production` | Enforces production mode and disables Swagger UI |
| `APP_DEBUG` | — | `False` | Disables debug mode |
| `API_V1_PREFIX` | — | `/api/v1` | Standard API route prefix |
| `DB_HOST` | — | `aws-0-[region].pooler.supabase.com` | Supabase IPv4 Pooler host |
| `DB_PORT` | — | `5432` | Supabase Session Pooler port |
| `DB_USER` | — | `postgres.[PROJECT-REF]` | Supabase pooled user |
| `DB_PASSWORD` | — | `[YOUR_SUPABASE_DB_PASSWORD]` | Your Supabase database password |
| `DB_NAME` | — | `postgres` | Default Supabase database |
| `DB_SSLMODE` | — | `require` | Forces TLS encryption for database connection |
| `DB_POOL_SIZE` | `POSTGRES_POOL_SIZE` | `5` | Keeps connection count small for Supabase free limits |
| `DB_MAX_OVERFLOW` | `POSTGRES_MAX_OVERFLOW` | `2` | Limited overflow for 512 MB container |
| `DB_POOL_TIMEOUT` | `POSTGRES_POOL_TIMEOUT` | `30` | Connection timeout in seconds |
| `JWT_SECRET_KEY` | `SECRET_KEY` | `[GENERATE_A_64_CHAR_SECRET]` | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | `ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifespan |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifespan |
| `CORS_ORIGINS` | — | `https://civicpulse.pages.dev,http://localhost:5173` | Replace with your Cloudflare Pages URL after creating it |
| `UPLOAD_DIR` | — | `/tmp/uploads` | Ephemeral scratch upload storage on Render |
| `MAX_UPLOAD_SIZE_MB` | — | `10` | Upload file size ceiling |
| `RATE_LIMIT_PER_MINUTE` | — | `60` | Request rate limit |
| `LOG_LEVEL` | — | `INFO` | Logging level |

> **Single Connection String Alternative:**  
> Instead of setting individual `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `DB_SSLMODE` variables, you may set a single variable:
> ```ini
> DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[YOUR_PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require
> ```
> CivicPulse automatically normalizes both `postgresql://` and `postgres://` protocols to `postgresql+psycopg2://` for SQLAlchemy 2.0.

### 4.3 Configure Render Health Check
In Render, expand **Advanced**:
- **Health Check Path**: `/api/v1/health`
*(Render probes this path to verify successful boot before routing traffic).*

Click **Create Web Service**. Render will clone the repository, install dependencies with `pip install -r requirements.txt`, and start the backend service.

---

## 5. Step 3: Provision the Initial Administrator Account

Because CivicPulse does not seed default administrative credentials, run the initial provisioning utility once the database migrations are complete:

### Method A: Run Locally Pointed to Supabase (Easiest)
From your local terminal with virtual environment activated:
```bash
# Set temporary connection variables targeting your Supabase DB
export DB_HOST="aws-0-[region].pooler.supabase.com"
export DB_PORT="5432"
export DB_USER="postgres.[PROJECT-REF]"
export DB_PASSWORD="[YOUR_SUPABASE_DB_PASSWORD]"
export DB_NAME="postgres"
export DB_SSLMODE="require"

# Run provisioning utility
INITIAL_ADMIN_EMAIL="admin@city.gov" \
INITIAL_ADMIN_PASSWORD="YourStrongAdminPassword2026!" \
INITIAL_ADMIN_NAME="Municipal Administrator" \
python scripts/create_initial_admin.py
```

### Method B: Run via Render Shell Console
1. In Render Dashboard, click into your `civicpulse-api` service.
2. Click the **Shell** tab in the left sidebar to open a web terminal in your running container.
3. Run:
   ```bash
   python scripts/create_initial_admin.py
   ```
4. Enter the administrator email, full name, and password interactively when prompted.

---

## 6. Step 4: Deploy Frontend on Cloudflare Pages

### 6.1 Create Cloudflare Pages Project
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com).
2. In the sidebar, navigate to **Workers & Pages** -> **Create application** -> **Pages** tab.
3. Click **Connect to Git** and select your GitHub repository.
4. Configure the build settings:
   - **Project Name**: `civicpulse` (Your URL will be `https://civicpulse.pages.dev`).
   - **Production Branch**: `master` (or your main branch).
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Build Output Directory**: `dist`

### 6.2 Configure Environment Variables
Under **Environment Variables (Production)**, add:

| Variable Name | Value | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `https://civicpulse-api.onrender.com/api/v1` | Render backend API base URL (including `/api/v1`) |
| `VITE_MUNICIPAL_CITY` | `City of Springfield` | (Optional) Municipality display name |
| `VITE_MUNICIPAL_DEFAULT_LAT` | `39.7817` | (Optional) Municipal map latitude center |
| `VITE_MUNICIPAL_DEFAULT_LNG` | `-89.6501` | (Optional) Municipal map longitude center |

> **Base URL Format & Resilience:**  
> The canonical format is `https://<service>.onrender.com/api/v1` (without trailing slash).  
> The CivicPulse frontend client (`apiClient.js`) automatically strips trailing slashes and appends `/api/v1` if a root origin is supplied, preventing 404 and double-slash errors.

5. Click **Save and Deploy**.
6. Cloudflare Pages will build and deploy the React SPA in ~30 seconds.

### 6.3 Synchronize Render CORS Origins
Now that your Cloudflare Pages URL is known (e.g., `https://civicpulse.pages.dev`):
1. Return to **Render Dashboard** -> `civicpulse-api` -> **Environment**.
2. Update `CORS_ORIGINS` to include your exact Cloudflare Pages origin:
   ```ini
   CORS_ORIGINS=https://civicpulse.pages.dev
   ```
3. Click **Save Changes**. Render will automatically redeploy with the updated CORS whitelist.

---

## 7. Verification & End-to-End Test

Once both services are deployed, perform this verification checklist:

| Verification Step | Target URL / Action | Expected Result |
|---|---|---|
| **1. Backend Health Check** | `https://<render-app>.onrender.com/api/v1/health` | Returns HTTP 200 with `{"status": "healthy"}`. *(Note: May take ~50s if waking from sleep).* |
| **2. API Docs Disabled** | `https://<render-app>.onrender.com/docs` | Returns HTTP 404 Not Found (confirms production security). |
| **3. Frontend Shell** | `https://<cloudflare-project>.pages.dev/` | CivicPulse home page loads with navigation, statistics, and theme styling. |
| **4. SPA Deep Linking** | `https://<cloudflare-project>.pages.dev/login` | Direct browser refresh loads Login page cleanly without 404 (confirms `_redirects` rule). |
| **5. Administrator Login** | Login with provisioned admin credentials | Successfully authenticates, receives JWT in memory, and redirects to `/admin/dashboard`. |
| **6. Interactive Map** | `/citizen/report` or `/admin/map` | Leaflet interactive map loads OpenStreetMap tiles without CSP or mixed-content errors. |
| **7. Public Feed** | `/public/complaints` | Public complaints load without authentication. |

---

## 8. Free-Tier Operational Realities & Limitations

When running on free-tier infrastructure, be aware of the following operational characteristics:

### 1. Render Sleep & Cold Starts
- **Behavior**: Free web services spin down after **15 minutes of inactivity**.
- **Cold Start Delay**: The first visitor after a period of inactivity experiences a **50 to 90-second delay** while Render provisions and boots the container.
- **Client Impact**: Frontend displays loading indicators during this wake-up period. Once awake, response times are normal (~50–200ms).

### 2. Render Ephemeral Local Filesystem
- **Behavior**: Render free containers use an ephemeral local filesystem.
- **Limitation**: Any photographic evidence uploaded to `/tmp/uploads` is lost when the service sleeps, restarts, or redeploys.
- **Production Difference**: A full production deployment uses persistent cloud object storage (AWS S3, Cloudflare R2, Google Cloud Storage) or dedicated persistent disks.

### 3. Supabase 7-Day Inactivity Pausing & Recovery
- **Behavior**: Supabase automatically pauses free-tier database instances after **7 consecutive days of inactivity**.
- **Restoration**: If paused, log in to the Supabase Dashboard and click **Restore project** (takes ~1–2 minutes).
- **Storage Limit**: Free databases are capped at **500 MB** of storage, sufficient for thousands of demonstration complaints.

### 4. Cloudflare Pages Limits
- **Limits**: 500 builds per month, 100 custom domains, unlimited bandwidth.
- **SPA Routing**: Relies on `frontend/public/_redirects` (`/* /index.html 200`) to enable client-side React Router routing.

---

## 9. Local & Hosted Migration Reference

Both environments share the identical 7-migration Alembic sequence (`b7c8d9e0f1a2`):

### 9.1 Local Database (localhost:5433)
```powershell
# Run migrations to head
alembic upgrade head

# Verify local schema status
python scripts/verify_db_connection.py
```

### 9.2 Hosted Supabase Database (Session Pooler)
> **IMPORTANT:** Replace `[PROJECT-REF]`, `[PASSWORD]`, and `[REGION]` with your real Supabase credentials. CivicPulse automatically rejects unreplaced template brackets `[...]` to prevent socket/DNS errors.

**Method A — Using Terminal Environment Variable (PowerShell):**
```powershell
$env:DATABASE_URL="postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require"

# 1. Run preflight diagnostic check against hosted database
python scripts/verify_db_connection.py

# 2. Apply all migrations to cloud database
alembic upgrade head

# 3. Confirm head revision on cloud database
python scripts/verify_db_connection.py
```

**Method B — Using Git-Ignored `.env.production` File:**
Create `.env.production` in the project root (`.gitignore` automatically excludes it):
```ini
APP_ENV=production
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require
```
Then run:
```powershell
# 1. Run preflight diagnostic check
python scripts/verify_db_connection.py --env-file .env.production

# 2. Run migrations
alembic -x db_url="postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require" upgrade head
```

---

## 10. Summary of Configuration Artifacts in Repository

The CivicPulse repository includes the following built-in free-tier deployment files:

1. `frontend/public/_redirects`: Cloudflare Pages SPA rewrite rule (`/* /index.html 200`).
2. `frontend/public/_headers`: Production security headers with CSP permitting `https://*.onrender.com` API calls.
3. `requirements.txt`: Environment-conditioned `gunicorn>=22.0.0; sys_platform != "win32"` allowing Render to run Gunicorn without breaking local Windows development.
4. `scripts/create_initial_admin.py`: Headless/interactive admin creation utility compatible with remote Supabase databases.
5. `scripts/verify_db_connection.py`: Preflight connectivity, extension audit, and schema inspection diagnostic utility.
