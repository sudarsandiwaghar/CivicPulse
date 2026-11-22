# CivicPulse — Production Deployment Guide

This guide describes the complete, production-grade deployment procedure for **CivicPulse** on a single Linux Virtual Private Server (VPS) running Ubuntu 22.04 LTS or 24.04 LTS.

The deployment topology utilizes:
- **Nginx**: Reverse proxy, TLS termination, HTTP/2, security headers, rate limiting, and static Single Page Application (SPA) file hosting.
- **Gunicorn + Uvicorn**: Master ASGI process manager with asynchronous Uvicorn worker processes managed by systemd.
- **FastAPI Backend**: Python 3.11+ application exposing REST endpoints under `/api/v1/`.
- **PostgreSQL 16+ with PostGIS**: Relational database with geospatial indexing and connection pooling.
- **React Frontend**: Optimized JavaScript ES6+ SPA compiled via Vite.

---

## 1. System Architecture & Topology

```
                              [ HTTPS: Port 443 ]
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │         Nginx 1.24+           │
                       │   (Reverse Proxy / TLS / SPA) │
                       └───────────────┬───────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
     [ Static Assets & SPA ]                       [ Reverse Proxy: /api/v1/ ]
     /var/www/civicpulse/frontend/dist                        │
     (index.html, JS, CSS, images)                            │
                                                              ▼
                                               ┌──────────────────────────────┐
                                               │   Gunicorn + Uvicorn Worker  │
                                               │      (127.0.0.1:8000)        │
                                               │       FastAPI Backend        │
                                               └──────────────┬───────────────┘
                                                              │
                                                              ▼
                                               ┌──────────────────────────────┐
                                               │   PostgreSQL 16+ / PostGIS   │
                                               │      (127.0.0.1:5432)        │
                                               │     civicpulse_production    │
                                               └──────────────────────────────┘
```

---

## 2. Hardware Sizing & Prerequisites

| Municipality Size | Registered Citizens | Active Field Workers | Recommended VPS Spec | Storage (NVMe SSD) |
|---|---|---|---|---|
| **Small (< 50k pop)** | Up to 10,000 | 5 – 25 | 2 vCPU / 4 GB RAM | 50 GB |
| **Medium (50k - 250k)** | Up to 75,000 | 25 – 100 | 4 vCPU / 8 GB RAM | 150 GB |
| **Large (> 250k pop)** | 100,000+ | 100+ | 8 vCPU / 16 GB RAM | 300 GB (or Managed DB) |

### System Prerequisites
- **Operating System**: Ubuntu 22.04 LTS or 24.04 LTS (x86_64)
- **Python**: Version 3.11 or higher
- **Node.js**: Version 20 LTS or higher (`node -v`, `npm -v`)
- **PostgreSQL**: Version 16 or 18 with PostGIS extension (`postgresql-16-postgis-3`)
- **Domain Name**: Fully qualified domain name (FQDN) pointed to VPS public IP via DNS A/AAAA records (e.g., `civicpulse.yourcity.gov`).

---

## 3. Server Provisioning & Security Hardening

### Step 3.1: System Updates & Core Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw fail2ban certbot python3-certbot-nginx \
    python3-pip python3-venv python3-dev build-essential libpq-dev
```

### Step 3.2: Create Unprivileged Application User
Never run the application or Gunicorn workers as `root`.
```bash
sudo useradd --system --create-home --shell /bin/bash civicpulse
sudo usermod -aG www-data civicpulse
```

### Step 3.3: Firewall Configuration (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## 4. PostgreSQL Production Database Setup

### Step 4.1: Install PostgreSQL and PostGIS
```bash
sudo apt install -y postgresql postgresql-contrib postgis postgresql-16-postgis-3
```

### Step 4.2: Create Production Database & User
Generate a strong database password:
```bash
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Database Password: $DB_PASS"
```

Provision the database cluster:
```bash
sudo -u postgres psql << EOF
CREATE USER civicpulse_app WITH PASSWORD '$DB_PASS' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE civicpulse_production OWNER civicpulse_app;
\c civicpulse_production
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
GRANT ALL PRIVILEGES ON DATABASE civicpulse_production TO civicpulse_app;
GRANT ALL ON SCHEMA public TO civicpulse_app;
EOF
```

### Step 4.3: Connection & Memory Optimization (`postgresql.conf`)
For a 4GB/8GB VPS, tune `/etc/postgresql/16/main/postgresql.conf`:
- `shared_buffers = 1GB` (25% of total system RAM)
- `work_mem = 16MB`
- `maintenance_work_mem = 256MB`
- `effective_cache_size = 3GB`
- `max_connections = 100`

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

## 5. Backend Application Deployment

### Step 5.1: Clone Repository and Set Permissions
```bash
sudo mkdir -p /var/www/civicpulse
sudo chown civicpulse:civicpulse /var/www/civicpulse
sudo -u civicpulse git clone https://github.com/your-org/CivicPulse.git /var/www/civicpulse
cd /var/www/civicpulse
```

### Step 5.2: Python Virtual Environment & Production Dependencies
```bash
sudo -u civicpulse python3.11 -m venv /var/www/civicpulse/venv
sudo -u civicpulse /var/www/civicpulse/venv/bin/pip install --upgrade pip setuptools wheel
sudo -u civicpulse /var/www/civicpulse/venv/bin/pip install -r requirements-prod.txt
```

### Step 5.3: Production Environment Configuration (`.env`)
Copy the production environment template:
```bash
sudo -u civicpulse cp .env.production.example .env
sudo chmod 600 .env
```

Generate a secure 64-character JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Edit `/var/www/civicpulse/.env` and update the required values:
```ini
APP_NAME=CivicPulse
APP_VERSION=0.8.0
APP_ENV=production
APP_DEBUG=False
ENABLE_DOCS=False

API_V1_PREFIX=/api/v1

DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=civicpulse_app
DB_PASSWORD=<YOUR_STRONG_DB_PASS>
DB_NAME=civicpulse_production
DB_POOL_SIZE=15
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_SSLMODE=prefer

JWT_SECRET_KEY=<YOUR_GENERATED_JWT_SECRET>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=https://civicpulse.yourcity.gov

UPLOAD_DIR=/var/www/civicpulse/uploads
MAX_UPLOAD_SIZE_MB=10
RATE_LIMIT_PER_MINUTE=60
LOG_LEVEL=WARNING
```

### Step 5.4: Create Upload and Log Directories
```bash
sudo mkdir -p /var/www/civicpulse/uploads
sudo mkdir -p /var/log/civicpulse
sudo chown -R civicpulse:civicpulse /var/www/civicpulse/uploads /var/log/civicpulse
sudo chmod 750 /var/www/civicpulse/uploads /var/log/civicpulse
```

### Step 5.5: Run Alembic Database Migrations
Execute all schema migrations in sequence (001 through 007):
```bash
sudo -u civicpulse /var/www/civicpulse/venv/bin/alembic upgrade head
```

Verify migration status:
```bash
sudo -u civicpulse /var/www/civicpulse/venv/bin/alembic current
```

### Step 5.6: Provision Initial Administrator Account
Run the standalone, idempotent provisioning utility without storing credentials in code or database seeds:
```bash
sudo -u civicpulse /var/www/civicpulse/venv/bin/python scripts/create_initial_admin.py
```
*Enter the municipal administrator email, full name, and a strong password (minimum 8 characters, uppercase, lowercase, digit, and special symbol).*

### Step 5.7: Install Systemd Service Unit
```bash
sudo cp deploy/systemd/civicpulse-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable civicpulse-backend
sudo systemctl start civicpulse-backend
```

Verify service status:
```bash
sudo systemctl status civicpulse-backend
curl http://127.0.0.1:8000/api/v1/health
```

---

## 6. Frontend Build & Static Deployment

### Step 6.1: Configure Frontend Production Environment
```bash
cd /var/www/civicpulse/frontend
sudo -u civicpulse cp .env.production.example .env.production
```

Ensure `frontend/.env.production` defines:
```ini
VITE_API_BASE_URL=/api/v1
VITE_MUNICIPAL_CITY=City of Springfield
VITE_MUNICIPAL_DEFAULT_LAT=39.7817
VITE_MUNICIPAL_DEFAULT_LNG=-89.6501
```

### Step 6.2: Install Node.js Dependencies & Compile Assets
```bash
sudo -u civicpulse npm ci
sudo -u civicpulse npm run build
```

This compiles optimized, hashed assets to `/var/www/civicpulse/frontend/dist` with sourcemaps enabled.

Verify output permissions:
```bash
sudo chmod -R 755 /var/www/civicpulse/frontend/dist
```

---

## 7. Nginx Reverse Proxy & TLS Configuration

### Step 7.1: Obtain Initial SSL/TLS Certificate (Avoiding Bootstrap Chicken-and-Egg)
In production, Nginx cannot start with `ssl_certificate` directives pointing to certificate files that do not exist yet. To bootstrap cleanly before enabling the SSL configuration:

```bash
# 1. Ensure DNS A/AAAA records point to your VPS public IP
# 2. Temporarily stop Nginx so port 80 is available for standalone ACME challenge
sudo systemctl stop nginx

# 3. Obtain initial Let's Encrypt certificates using Certbot standalone mode
sudo certbot certonly --standalone -d civicpulse.yourcity.gov

# 4. Start Nginx
sudo systemctl start nginx
```

### Step 7.2: Deploy Hardened Nginx Configuration
Copy the production Nginx configuration:
```bash
sudo cp deploy/nginx/civicpulse.conf /etc/nginx/sites-available/civicpulse.conf
```

Edit `/etc/nginx/sites-available/civicpulse.conf` and update:
1. `server_name civicpulse.example.gov;` -> replace with your actual FQDN (e.g., `civicpulse.yourcity.gov`).
2. `ssl_certificate` paths -> ensure they match `/etc/letsencrypt/live/civicpulse.yourcity.gov/`.
3. Verify that the ACME webroot directory exists for subsequent renewals:
   ```bash
   sudo mkdir -p /var/www/certbot
   sudo chown -R www-data:www-data /var/www/certbot
   ```

### Step 7.3: Enable Site & Verify Configuration
```bash
sudo ln -sf /etc/nginx/sites-available/civicpulse.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7.4: Automated Certificate Renewal Verification
Certbot automatically installs a systemd renewal timer (`certbot.timer`). Verify renewal operates via the ACME webroot configured in `civicpulse.conf`:
```bash
sudo certbot renew --dry-run
```

---

## 8. Backup, Restoration & Disaster Recovery Runbook

### Step 8.1: Automated Daily Database Backups
Create a dedicated local backup repository owned by the `postgres` system user:
```bash
sudo mkdir -p /var/backups/civicpulse
sudo chown postgres:postgres /var/backups/civicpulse
sudo chmod 700 /var/backups/civicpulse
```

Configure a daily cron job running under the `postgres` system user (`sudo crontab -e -u postgres`):
```cron
# Daily CivicPulse Database Backup at 02:30 AM (runs via local peer authentication without passwords)
30 2 * * * pg_dump -U postgres -d civicpulse_production -Fc > /var/backups/civicpulse/civicpulse_$(date +\%Y\%m\%d_\%H\%M\%S).dump
# Retain backups for 30 days
0 3 * * * find /var/backups/civicpulse -name "civicpulse_*.dump" -mtime +30 -delete
```

> **Security Note:** Running `pg_dump` under user `postgres` uses local Unix domain socket peer authentication. This avoids embedding database passwords in cron scripts or environment files.

### Step 8.2: Uploaded Media Backup
Back up the `/var/www/civicpulse/uploads` directory nightly to off-site object storage (AWS S3, Google Cloud Storage, or secondary backup server) using `rsync` or cloud storage sync:
```bash
# Example rsync to backup storage
rsync -avz --delete /var/www/civicpulse/uploads/ backup-user@backups.internal:/srv/backups/civicpulse-uploads/
```

### Step 8.3: Disaster Recovery Restoration Runbook

> **CRITICAL DATA LOSS PREVENTION RULES:**
> 1. **Never drop the active database** without taking an immediate pre-restoration safety snapshot first.
> 2. **Always test dump file integrity** using `pg_restore --list` before modifying the database.

To restore from a backup file:

```bash
TARGET_BACKUP="/var/backups/civicpulse/civicpulse_TARGET_RESTORE.dump"

# 1. Precondition Check: Verify backup archive integrity
if ! sudo -u postgres pg_restore --list "$TARGET_BACKUP" > /dev/null 2>&1; then
    echo "ERROR: Target dump file is corrupt or unreadable. ABORTING restoration."
    exit 1
fi

# 2. Stop backend service to prevent incoming transactions and lock contention
sudo systemctl stop civicpulse-backend

# 3. SAFETY BACKUP: Dump current database state before destructive actions
sudo -u postgres pg_dump -U postgres -d civicpulse_production -Fc > "/var/backups/civicpulse/pre_restore_safety_snapshot_$(date +%Y%m%d_%H%M%S).dump"

# 4. Terminate active client connections & recreate clean database
sudo -u postgres psql << EOF
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'civicpulse_production';
DROP DATABASE civicpulse_production;
CREATE DATABASE civicpulse_production OWNER civicpulse_app;
\c civicpulse_production
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
GRANT ALL PRIVILEGES ON DATABASE civicpulse_production TO civicpulse_app;
GRANT ALL ON SCHEMA public TO civicpulse_app;
EOF

# 5. Restore schema and data from custom dump archive
sudo -u postgres pg_restore -d civicpulse_production --no-owner --role=civicpulse_app "$TARGET_BACKUP"

# 6. Re-verify permissions for application role
sudo -u postgres psql -d civicpulse_production -c "GRANT ALL ON SCHEMA public TO civicpulse_app;"

# 7. Start backend service and verify operational health
sudo systemctl start civicpulse-backend
curl -I http://127.0.0.1:8000/api/v1/health
```

---

## 9. Zero-Downtime Deployment & Rollback Runbook

### Routine Application Update Procedure
```bash
cd /var/www/civicpulse

# 1. Pull latest verified release
sudo -u civicpulse git fetch origin master
sudo -u civicpulse git checkout tags/vX.Y.Z

# 2. Update backend virtual environment dependencies
sudo -u civicpulse /var/www/civicpulse/venv/bin/pip install -r requirements-prod.txt

# 3. Run database migrations
sudo -u civicpulse /var/www/civicpulse/venv/bin/alembic upgrade head

# 4. Build frontend SPA
cd /var/www/civicpulse/frontend
sudo -u civicpulse npm ci
sudo -u civicpulse npm run build

# 5. Gracefully reload backend workers without dropping connections
sudo systemctl reload civicpulse-backend

# 6. Verify production health endpoint
curl -I https://civicpulse.yourcity.gov/api/v1/health
```

### Emergency Rollback Procedure & Migration Limitations

> **WARNING — ALEMBIC DOWNGRADE DATA LOSS LIMITATION:**
> Alembic migrations in CivicPulse contain destructive `downgrade()` methods:
> - Migration `007` drops the `event_key` notification deduplication constraint.
> - Migration `006` permanently drops the `complaint_sla_history` table and SLA columns.
> - Migration `005` permanently drops the `complaint_followers` table and moderation columns.
> - Migration `004` permanently drops the `assignment_progress` work notes and photo logs.
>
> **Do NOT execute `alembic downgrade -1` routinely in production.**
> If an update fails verification:
> 1. **Code-Only Rollback (Recommended):** Revert the Git release tag and rebuild the frontend. The existing database schema is backward-compatible with earlier application code.
> 2. **Full Database Rollback:** If the new release introduced breaking schema changes that cannot run with older code, restore the database from the pre-deployment snapshot created in Step 8.3 rather than running destructive Alembic downgrades.

Safe Rollback Execution:
```bash
cd /var/www/civicpulse

# 1. Revert application code to previous release tag
sudo -u civicpulse git checkout tags/vPREVIOUS_VERSION

# 2. Re-install prior dependencies
sudo -u civicpulse /var/www/civicpulse/venv/bin/pip install -r requirements-prod.txt

# 3. Rebuild frontend for previous version
cd /var/www/civicpulse/frontend
sudo -u civicpulse npm ci
sudo -u civicpulse npm run build

# 4. Gracefully reload backend
sudo systemctl reload civicpulse-backend

# 5. Confirm service restoration
curl -I https://civicpulse.yourcity.gov/api/v1/health
```

---

## 10. Operational Monitoring & Health Verification

| Endpoint | Method | Expected Status | Purpose |
|---|---|---|---|
| `https://civicpulse.yourcity.gov/health` | GET | `200 OK` | Public uptime monitoring probe (proxied to `/api/v1/health`) |
| `https://civicpulse.yourcity.gov/api/v1/health` | GET | `200 OK` | Core API health verification payload |
| `https://civicpulse.yourcity.gov/docs` | GET | `404 Not Found` | Verifies Swagger UI is disabled in production |
| `https://civicpulse.yourcity.gov/redoc` | GET | `404 Not Found` | Verifies ReDoc is disabled in production |
| `https://civicpulse.yourcity.gov/openapi.json` | GET | `404 Not Found` | Verifies OpenAPI schema is unexposed |

Monitor backend logs live:
```bash
# Application error logs
sudo tail -f /var/log/civicpulse/error.log

# Systemd journal logs
sudo journalctl -u civicpulse-backend -f
```
