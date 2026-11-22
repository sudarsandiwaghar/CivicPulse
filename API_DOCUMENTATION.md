# CivicPulse — API Documentation

## Overview

CivicPulse exposes a RESTful JSON API under the `/api/v1` prefix. All endpoints follow consistent conventions for request/response structure, authentication, and error handling.

**Interactive documentation** is available when the server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Endpoints requiring authentication accept a signed JWT bearer token passed in the standard `Authorization` header:

```http
Authorization: Bearer <access_token>
```

Tokens are issued via `POST /api/v1/auth/login` and must be signed using the HMAC-SHA256 algorithm. Every authenticated request verifies token signature, expiration (`exp`), subject (`sub`), and validates that the user account is active in the database.

Protected endpoints enforce Role-Based Access Control (RBAC). If a token has valid credentials but lacks the required role, a `403 Forbidden` error is returned.

## Response Format

All responses use a consistent JSON envelope:

### Success Response
```json
{
    "success": true,
    "message": "Description of result",
    "data": { ... }
}
```

### Error Response
```json
{
    "success": false,
    "message": "Error category",
    "detail": "Specific error description"
}
```

### Paginated Response
```json
{
    "success": true,
    "message": "Data retrieved successfully",
    "data": [ ... ],
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8
}
```

## HTTP Status Codes

| Code | Meaning | Usage |
|---|---|---|
| 200 | OK | Successful retrieval or update |
| 201 | Created | Successful entity creation |
| 400 | Bad Request | Invalid input, file upload errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Entity does not exist |
| 409 | Conflict | Duplicate entity |
| 422 | Unprocessable Entity | Validation error, invalid state transition |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |

---

## Endpoints

### System

#### `GET /api/v1/health`

Health check endpoint. No authentication required.

**Response (200):**
```json
{
    "success": true,
    "message": "CivicPulse API is running",
    "data": {
        "status": "healthy",
        "version": "0.1.0"
    }
}
```

---

### Authentication & Authorization

All authentication routes are mounted under `/api/v1/auth`.

#### `POST /api/v1/auth/register`

Register a new citizen account. Public registration is strictly restricted to the `CITIZEN` role. Privileged accounts (`ADMINISTRATOR`, `FIELD_WORKER`) cannot be self-registered and must be provisioned offline by administrators.

**Request Body:**
```json
{
    "full_name": "Priya Sharma",
    "email": "priya.sharma@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}
```

**Field Rules:**
- `full_name`: 2 to 150 characters, leading/trailing whitespace trimmed.
- `email`: Valid RFC 5322 email string. Automatically trimmed and lowercased.
- `password`: 8 to 72 characters (strictly enforcing bcrypt 72-byte limit).
- `password_confirm`: Must match `password` identically.

**Response (201 Created):**
```json
{
    "success": true,
    "message": "Citizen registered successfully",
    "data": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "email": "priya.sharma@example.com",
        "full_name": "Priya Sharma",
        "phone_number": null,
        "role": "CITIZEN",
        "is_active": true,
        "is_verified": false,
        "created_at": "2026-11-19T06:30:00Z",
        "updated_at": "2026-11-19T06:30:00Z"
    }
}
```

**Error Responses:**
- `409 Conflict`: Email address is already registered.
  ```json
  {
      "success": false,
      "message": "Entity already exists",
      "detail": "A user with this email address already exists"
  }
  ```
- `422 Unprocessable Entity`: Validation failure (e.g., password mismatch, short password, invalid email format).

---

#### `POST /api/v1/auth/login`

Authenticate with email and password to receive a signed JWT bearer token. Uses constant-time verification to prevent timing attacks and account enumeration.

**Request Body:**
```json
{
    "email": "priya.sharma@example.com",
    "password": "SecurePassword123!"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "message": "Login successful",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 1800,
        "user": {
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "email": "priya.sharma@example.com",
            "full_name": "Priya Sharma",
            "phone_number": null,
            "role": "CITIZEN",
            "is_active": true,
            "is_verified": false,
            "created_at": "2026-11-19T06:30:00Z",
            "updated_at": "2026-11-19T06:30:00Z"
        }
    }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials or inactive account (identical message returned to prevent account enumeration).
  ```json
  {
      "success": false,
      "message": "Authentication failed",
      "detail": "Invalid email or password"
  }
  ```
- `422 Unprocessable Entity`: Malformed request body or invalid email format.

---

#### `GET /api/v1/auth/me`

Retrieve profile details of the currently authenticated user. Requires a valid JWT token in the `Authorization` header.

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "success": true,
    "message": "User profile retrieved successfully",
    "data": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "email": "priya.sharma@example.com",
        "full_name": "Priya Sharma",
        "phone_number": null,
        "role": "CITIZEN",
        "is_active": true,
        "is_verified": false,
        "created_at": "2026-11-19T06:30:00Z",
        "updated_at": "2026-11-19T06:30:00Z"
    }
}
```

**Error Responses:**
- `401 Unauthorized`: Missing `Authorization` header, invalid token signature, or token expired.
  ```json
  {
      "success": false,
      "message": "Authentication failed",
      "detail": "Token has expired"
  }
  ```
- `403 Forbidden`: Account is inactive/disabled.
  ```json
  {
      "success": false,
      "message": "Permission denied",
      "detail": "User account is inactive"
  }
  ```

---

### Categories

All category endpoints are mounted under `/api/v1/categories`.

#### `GET /api/v1/categories/`

Retrieve all active complaint categories with their managing department details. Public / unauthenticated or authenticated access.

**Response (200 OK):**
```json
{
    "success": true,
    "message": "Active categories retrieved successfully",
    "data": [
        {
            "id": 1,
            "department_id": 1,
            "department_name": "Public Works Department",
            "name": "Roads and Potholes",
            "description": "Issues related to damaged road surfaces, potholes, and broken dividers",
            "is_active": true,
            "created_at": "2026-11-19T07:37:00Z",
            "updated_at": "2026-11-19T07:37:00Z"
        }
    ]
}
```

---

### Complaints & Lifecycle State Machine

All complaint endpoints are mounted under `/api/v1/complaints`.

#### `POST /api/v1/complaints/`

File a new civic issue report. Restricted to authenticated users with the `CITIZEN` role. All ownership, initial status (`SUBMITTED`), default priority (`MEDIUM`), and tracking numbers (`CP-YYYY-XXXXX`) are calculated and enforced server-side.

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
    "title": "Severe pothole near 100ft road intersection",
    "description": "A deep road crater at the signal intersection causing vehicle damage and traffic hazards.",
    "category_id": 1,
    "location": {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "address_line": "100ft Road, Indiranagar",
        "area_name": "Ward 80",
        "city": "Bengaluru",
        "pincode": "560038",
        "landmark": "Opposite Metro Pillar 120"
    }
}
```

**Response (201 Created):**
```json
{
    "success": true,
    "message": "Complaint submitted successfully",
    "data": {
        "id": "7fa4335c-2936-4fc6-bc20-9286a0b271d4",
        "complaint_number": "CP-2026-10001",
        "citizen_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "citizen_name": "Priya Sharma",
        "category_id": 1,
        "category_name": "Roads and Potholes",
        "location": {
            "id": "1fa85f64-5717-4562-b3fc-2c963f66afa1",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "address_line": "100ft Road, Indiranagar",
            "area_name": "Ward 80",
            "city": "Bengaluru",
            "pincode": "560038",
            "landmark": "Opposite Metro Pillar 120"
        },
        "title": "Severe pothole near 100ft road intersection",
        "description": "A deep road crater at the signal intersection causing vehicle damage and traffic hazards.",
        "status": "SUBMITTED",
        "priority": "MEDIUM",
        "resolved_at": null,
        "closed_at": null,
        "created_at": "2026-11-19T07:45:00Z",
        "updated_at": "2026-11-19T07:45:00Z"
    }
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Bearer token.
- `403 Forbidden`: Authenticated user is not a Citizen.
- `404 Not Found`: Category ID does not exist.
- `422 Unprocessable Entity`: Coordinate out of bounds or inactive category.

---

#### `GET /api/v1/complaints/`

Retrieve paginated complaints.
- **Citizens**: Automatically scoped to their own complaints (`citizen_id == current_user.id`).
- **Administrators**: Can view all complaints across all users and filter by status, priority, category, date range, or keyword.
- **Field Workers**: Blocked in Phase 4 (Worker assignments and task access belong to Phase 5).

**Query Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | null | Filter by lifecycle status (e.g. `SUBMITTED`, `UNDER_REVIEW`, `RESOLVED_AWAITING_VERIFICATION`, `CLOSED`) |
| `priority` | string | null | Filter by priority (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `category_id` | integer | null | Filter by category ID |
| `complaint_number` | string | null | Search by complaint tracking reference |
| `search` | string | null | Substring search in title, description, or reference code |
| `start_date` | string (ISO 8601) | null | Filter complaints created on or after UTC date |
| `end_date` | string (ISO 8601) | null | Filter complaints created on or before UTC date |
| `page` | integer | 1 | Page number (1-based) |
| `page_size` | integer | 20 | Number of items per page (max 100) |
| `sort_by` | string | "created_at" | Column to sort by (`created_at`, `priority`, `status`, etc.) |
| `sort_order` | string | "desc" | Sort direction (`asc` or `desc`) |

**Response (200 OK):**
```json
{
    "success": true,
    "message": "Complaints retrieved successfully",
    "data": [ ... ],
    "page": 1,
    "page_size": 20,
    "total_items": 42,
    "total_pages": 3
}
```

---

#### `GET /api/v1/complaints/{complaint_id}`

Retrieve complete details for a single complaint.
- **Citizens**: Can view only their authored complaints (IDOR protected; accessing another user's complaint returns `403 Forbidden`).
- **Administrators**: Can view any complaint.

**Response (200 OK):**
Returns `ComplaintDetailResponse` including incident location and complete chronological `status_history`.

---

#### `GET /api/v1/complaints/{complaint_id}/history`

Retrieve the immutable audit log of status transitions for a specific complaint.
- **Citizens**: Only permitted for their authored complaints.
- **Administrators**: Permitted for all complaints.

**Response (200 OK):**
```json
{
    "success": true,
    "message": "Complaint status history retrieved successfully",
    "data": [
        {
            "id": "8bb12345-5717-4562-b3fc-2c963f66afa2",
            "complaint_id": "7fa4335c-2936-4fc6-bc20-9286a0b271d4",
            "changed_by_id": "a98ce3c4-5aec-4a41-a5ce-23af5f7ab674",
            "changed_by_name": "System Administrator",
            "previous_status": "SUBMITTED",
            "new_status": "UNDER_REVIEW",
            "remarks": "Admin triaging complaint for dispatch.",
            "created_at": "2026-11-19T07:50:00Z"
        },
        {
            "id": "8bb12345-5717-4562-b3fc-2c963f66afa1",
            "complaint_id": "7fa4335c-2936-4fc6-bc20-9286a0b271d4",
            "changed_by_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "changed_by_name": "Priya Sharma",
            "previous_status": null,
            "new_status": "SUBMITTED",
            "remarks": "Initial complaint submission by citizen",
            "created_at": "2026-11-19T07:45:00Z"
        }
    ]
}
```

---

#### `PATCH /api/v1/complaints/{complaint_id}/review`

Administrative triage, review, priority adjustment, and category reclassification. Restricted to users with the `ADMINISTRATOR` role.

**Request Body:**
```json
{
    "new_status": "UNDER_REVIEW",
    "category_id": 2,
    "priority": "HIGH",
    "reason": "Located adjacent to school crossing; adjusting priority and reclassifying.",
    "original_complaint_id": null
}
```

**Rules:**
- `priority`: Adjusting priority strictly requires a non-empty `reason`.
- `new_status`: If updating status, transitions must comply with the lifecycle transition matrix.
- `original_complaint_id`: Required when marking as `DUPLICATE`.
- Audit history is recorded in `ComplaintStatusHistory` within the same database transaction.

---

#### `POST /api/v1/complaints/{complaint_id}/transitions`

Execute a validated lifecycle state machine transition.

**Request Body:**
```json
{
    "new_status": "CLOSED",
    "remarks": "Citizen confirmed issue is resolved cleanly.",
    "original_complaint_id": null
}
```

---

### Complaint Lifecycle State Machine Matrix

The following state machine governs all transitions in CivicPulse. Arbitrary status updates that violate this matrix are rejected with `HTTP 422 Unprocessable Entity`:

| Current Status | Target Status | Permitted Roles | Preconditions & Requirements |
|---|---|---|---|
| `SUBMITTED` | `UNDER_REVIEW` | `ADMINISTRATOR` | Moves complaint into review. Citizens cannot review their own complaints. |
| `SUBMITTED` | `REJECTED` | `ADMINISTRATOR` | Rejection `remarks` (reason) must be non-empty. |
| `SUBMITTED` | `DUPLICATE` | `ADMINISTRATOR` | Requires valid `original_complaint_id` (must exist, cannot reference self, cannot reference rejected/duplicate complaint). |
| `UNDER_REVIEW` | `ASSIGNED` | `ADMINISTRATOR` | Precondition: Requires an active worker assignment. (Phase 5 integration). |
| `UNDER_REVIEW` | `REJECTED` | `ADMINISTRATOR` | Rejection `remarks` (reason) must be non-empty. |
| `UNDER_REVIEW` | `DUPLICATE` | `ADMINISTRATOR` | Requires valid `original_complaint_id`. |
| `UNDER_REVIEW` | `ON_HOLD` | `ADMINISTRATOR` | Hold `remarks` (reason) must be non-empty. |
| `ASSIGNED` | `IN_PROGRESS` | `ADMINISTRATOR`, `FIELD_WORKER` | Precondition: Requires active worker assignment record (Phase 5). |
| `ASSIGNED` | `ON_HOLD` | `ADMINISTRATOR` | Hold `remarks` (reason) must be non-empty. |
| `IN_PROGRESS` | `RESOLVED_AWAITING_VERIFICATION` | `ADMINISTRATOR`, `FIELD_WORKER` | Marks complaint as resolved by field worker. Sets `resolved_at = now()`. |
| `IN_PROGRESS` | `ON_HOLD` | `ADMINISTRATOR` | Hold `remarks` (reason) must be non-empty. |
| `RESOLVED_AWAITING_VERIFICATION` | `CLOSED` | `CITIZEN` (owner), `ADMINISTRATOR` | Citizen verification closure. Sets `closed_at = now()`. |
| `RESOLVED_AWAITING_VERIFICATION` | `REOPENED` | `CITIZEN` (owner), `ADMINISTRATOR` | Citizen unsatisfied with resolution. Requires non-empty reason. Clears timestamps. |
| `ON_HOLD` | `UNDER_REVIEW` | `ADMINISTRATOR` | Resumes complaint back to active review. |
| `ON_HOLD` | `IN_PROGRESS` | `ADMINISTRATOR` | Precondition: only when supported by an existing active worker assignment. |
| `REOPENED` | `UNDER_REVIEW` | `ADMINISTRATOR` | Administrator triages reopened complaint back into active review. |
| `CLOSED` | `REOPENED` | `CITIZEN` (owner), `ADMINISTRATOR` | Explicit reopening of closed issue with recorded justification. |
| `REJECTED` | *(Terminal)* | *None* | No transitions permitted from `REJECTED`. |
| `DUPLICATE` | *(Terminal)* | *None* | No transitions permitted from `DUPLICATE`. |

---

## 4. Department Management (`/api/v1/departments`)

Endpoints for municipal departments responsible for civic resolution.

### Create Department
`POST /api/v1/departments`
- **Access**: `ADMINISTRATOR`
- **Request Body**:
```json
{
    "name": "Public Health Division",
    "code": "HEALTH_DIV",
    "description": "Handles disease prevention and vector control",
    "contact_email": "health@city.gov",
    "contact_phone": "+919876543210"
}
```
- **Response**: `201 Created` with department details.

### List Departments
`GET /api/v1/departments`
- **Access**: Authenticated (`CITIZEN`, `ADMINISTRATOR`, `FIELD_WORKER`)
- **Query Params**: `is_active` (boolean), `search` (string), `page` (int), `page_size` (int)
- **Response**: `200 OK` paginated list.

### Get Department by ID
`GET /api/v1/departments/{id}`
- **Access**: Authenticated
- **Response**: `200 OK` with department details.

### Update Department
`PATCH /api/v1/departments/{id}`
- **Access**: `ADMINISTRATOR`
- **Request Body**: Optional fields: `name`, `code`, `description`, `contact_email`, `contact_phone`, `is_active`.
- **Response**: `200 OK` with updated department.

### Deactivate Department
`PATCH /api/v1/departments/{id}/deactivate` (or `DELETE /api/v1/departments/{id}`)
- **Access**: `ADMINISTRATOR`
- **Behavior**: Safe soft-deactivation (`is_active = False`). Rejects deactivation if active worker assignments (`ASSIGNED`, `IN_PROGRESS`) exist. Preserves historical assignment records.
- **Response**: `200 OK`.

---

## 5. Field Worker Management (`/api/v1/workers`)

Endpoints for field technician provisioning, profile management, and task queues.

### Provision Field Worker
`POST /api/v1/workers`
- **Access**: `ADMINISTRATOR`
- **Description**: Atomically creates a `FIELD_WORKER` User (with bcrypt-hashed password) and Worker profile linked to a valid municipal department.
- **Request Body**:
```json
{
    "email": "worker.patel@civicpulse.org",
    "password": "SecurePassword123!",
    "full_name": "Rajesh Patel",
    "phone": "+919876543211",
    "department_id": 1,
    "employee_id": "EMP-PWD-101",
    "skills": ["asphalt_patching", "pothole_repair", "compactor_operation"],
    "is_available": true
}
```
- **Response**: `201 Created` with worker details and employee metadata.

### List Field Workers
`GET /api/v1/workers`
- **Access**: `ADMINISTRATOR`
- **Query Params**: `department_id` (int), `is_available` (bool), `employment_status` (`ACTIVE`, `ON_LEAVE`, `SUSPENDED`, `TERMINATED`), `page`, `page_size`.
- **Response**: `200 OK` paginated list.

### Get Worker Detail
`GET /api/v1/workers/{id}`
- **Access**: `ADMINISTRATOR`
- **Response**: `200 OK` with worker profile, department info, and active assignment count.

### Update Worker Profile
`PATCH /api/v1/workers/{id}`
- **Access**: `ADMINISTRATOR`
- **Request Body**: Optional: `phone`, `department_id`, `skills`, `is_available`, `employment_status`.
- **Response**: `200 OK`.

### Deactivate Worker
`PATCH /api/v1/workers/{id}/deactivate` (or `DELETE /api/v1/workers/{id}`)
- **Access**: `ADMINISTRATOR`
- **Behavior**: Sets `employment_status = INACTIVE`, `is_available = False`, and deactivates the underlying user account (`is_active = False`), instantly revoking login and blocking service-layer task operations. Preserves historical assignment records.
- **Response**: `200 OK`.

---

## 6. Worker Self-Task Operations (`/api/v1/workers/me/tasks`)

Endpoints restricted strictly to authenticated field technicians to inspect and manage their assigned workloads without IDOR vulnerabilities.

### Get My Assigned Tasks
`GET /api/v1/workers/me/tasks`
- **Access**: `FIELD_WORKER`
- **Query Params**: `status` (`ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `REASSIGNED`), `priority` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `page`, `page_size`.
- **Response**: `200 OK` paginated list of tasks assigned strictly to the authenticated technician.

### Get Assigned Task Detail
`GET /api/v1/workers/me/tasks/{assignment_id}`
- **Access**: `FIELD_WORKER` (IDOR-safe: rejects access to other workers' tasks with `403 Forbidden`).
- **Response**: `200 OK` with complaint details, location coordinates, citizen contact info, and milestone progress log.

### Accept Task
`POST /api/v1/workers/me/tasks/{assignment_id}/accept`
- **Access**: `FIELD_WORKER`
- **Description**: Technician acknowledges assignment. Records `accepted_at` timestamp.
- **Response**: `200 OK`.

### Start Task
`POST /api/v1/workers/me/tasks/{assignment_id}/start`
- **Access**: `FIELD_WORKER`
- **Description**: Technician begins work on site. Automatically transitions assignment from `ASSIGNED` to `IN_PROGRESS`, sets `started_at`, and moves complaint to `IN_PROGRESS` through the state machine.
- **Response**: `200 OK`.

### Log Task Progress
`POST /api/v1/workers/me/tasks/{assignment_id}/progress`
- **Access**: `FIELD_WORKER`
- **Description**: Appends an immutable milestone or observation entry to the assignment's audit trail.
- **Request Body**:
```json
{
    "description": "Excavated loose road gravel and applied bitumen tack coat."
}
```
- **Response**: `201 Created` with progress log record.

### Complete Task
`POST /api/v1/workers/me/tasks/{assignment_id}/complete`
- **Access**: `FIELD_WORKER`
- **Description**: Technician submits completed work. Sets `assignment.status = COMPLETED`, `completed_at = now()`, and transitions complaint to `RESOLVED_AWAITING_VERIFICATION` for citizen verification.
- **Request Body**:
```json
{
    "summary": "Pothole filled with dense asphalt and leveled with roller. Surface restored."
}
```
- **Response**: `200 OK`.

---

## 7. Complaint Assignment & Reassignment (`/api/v1/complaints/{id}`)

Administrative endpoints for allocating technicians to civic issues.

### Assign Complaint
`POST /api/v1/complaints/{id}/assign`
- **Access**: `ADMINISTRATOR`
- **Preconditions**:
  - Complaint must be in `UNDER_REVIEW` status.
  - Worker must be `ACTIVE` and `is_available = True`.
  - Worker's department must match complaint's category department.
  - No active assignment may already exist (enforced by partial unique index and row lock).
- **Request Body**:
```json
{
    "worker_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "notes": "Urgent pothole repair near school zone"
}
```
- **Transitions**: Creates `Assignment` (status: `ASSIGNED`) and transitions complaint `UNDER_REVIEW -> ASSIGNED`.
- **Response**: `200 OK`.

### Reassign Complaint
`POST /api/v1/complaints/{id}/reassign`
- **Access**: `ADMINISTRATOR`
- **Preconditions**:
  - Complaint must be in `ASSIGNED` or `IN_PROGRESS` status.
  - Replacement worker must be eligible and different from the current worker.
  - Mandatory reason required.
- **Request Body**:
```json
{
    "new_worker_id": "4bb406ad-df30-486e-b0a4-4c2def153dac",
    "reason": "Previous technician reassigned to emergency sewer rupture",
    "notes": "Resume work from site milestone 1"
}
```
- **Transitions**: Marks previous assignment `REASSIGNED`, creates new `Assignment` (status: `ASSIGNED`), and if the complaint was previously `IN_PROGRESS`, executes an atomic chained transition conforming strictly to the approved Phase 4 state machine (`IN_PROGRESS -> ON_HOLD -> UNDER_REVIEW -> ASSIGNED`) with single-commit atomicity and complete status history audit logging. If the complaint was `ASSIGNED`, it remains `ASSIGNED`.
- **Response**: `200 OK`.

### Get Complaint Assignments History
`GET /api/v1/complaints/{id}/assignments`
- **Access**: `ADMINISTRATOR`
- **Response**: `200 OK` listing full chronological assignment history for the complaint.

---

## 8. Global Assignment Monitoring (`/api/v1/assignments`)

Administrative endpoints for platform-wide assignment tracking and oversight.

### List All Assignments
`GET /api/v1/assignments`
- **Access**: `ADMINISTRATOR`
- **Query Params**: `status` (`ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `REASSIGNED`), `worker_id` (UUID), `complaint_id` (UUID), `page`, `page_size`.
- **Response**: `200 OK` paginated list.

### Get Assignment Detail
`GET /api/v1/assignments/{id}`
- **Access**: `ADMINISTRATOR`
- **Response**: `200 OK` with full assignment details, technician profile, complaint metadata, and progress audit entries.

---

## 9. Citizen Dashboard (`/api/v1/citizens`)

Endpoints for authenticated citizens to view personal metrics, action queues, and recent activity.

### Get Citizen Personal Dashboard
`GET /api/v1/citizens/me/dashboard`
- **Access**: `CITIZEN` only (ownership strictly bound to `current_user.id`).
- **Response**: `200 OK` returning:
  - `metrics`: Total submitted, active complaints, awaiting verification, closed, rejected, duplicate, and complete breakdowns across all 10 approved lifecycle statuses and 4 priority levels.
  - `recent_submissions`: Latest 5 complaints ordered by `created_at DESC`.
  - `recent_updates`: Latest 5 complaints ordered by `updated_at DESC`.
  - `action_required`: Complaints in `RESOLVED_AWAITING_VERIFICATION` requiring citizen confirmation (max 5).

---

## 10. Unified Complaint Timeline (`/api/v1/complaints/{id}/timeline`)

Chronological audit timeline narrative combining records across complaints, status history, assignments, and field progress updates.

### Get Unified Complaint Timeline
`GET /api/v1/complaints/{complaint_id}/timeline`
- **Access**:
  - `CITIZEN` (Author only): Sees chronological operational timeline. **Redaction:** Internal administrative remarks and dispatch instructions are omitted.
  - `FIELD_WORKER` (Assigned only): Sees operational milestones. Bounded by assignment completion/reassignment cutoff for past assignments.
  - `ADMINISTRATOR`: Full unrestricted access to all public and internal milestones, notes, and remarks.
- **Response**: `200 OK` with `complaint_id`, `complaint_number`, `current_status`, and chronologically sorted list of `events`.

---

## 11. Moderated Public Complaint Feed (`/api/v1/public`)

Unauthenticated, privacy-safe public complaint discovery endpoints. Enforces strict allowlist serialization: zero citizen PII, zero internal administrative remarks, zero raw citizen-submitted titles or descriptions, and zero precise geographical coordinates.

### List Moderated Public Complaints
`GET /api/v1/public/complaints`
- **Access**: Public (Unauthenticated).
- **Query Parameters**:
  - `category_id` (integer, optional): Filter by category ID.
  - `status` (string, optional): Filter by complaint lifecycle status (e.g. `UNDER_REVIEW`, `IN_PROGRESS`, `RESOLVED`).
  - `page` (integer, default: `1`, minimum: `1`).
  - `page_size` (integer, default: `20`, minimum: `1`, maximum: `100`).
- **Privacy Enforcement**:
  - Returns strictly records where `is_public == True`.
  - Complaints in `REJECTED` or `DUPLICATE` status are excluded.
  - Only coarse geographic boundaries are revealed (`ward_or_district`, `city`). Precise coordinates (`latitude`, `longitude`) and street addresses are permanently omitted.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Public complaints retrieved successfully",
    "data": {
        "items": [
            {
                "id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
                "complaint_number": "CP-2026-00042",
                "category_name": "Public Infrastructure",
                "status": "IN_PROGRESS",
                "created_at": "2026-11-05T10:00:00Z",
                "public_title": "Damaged Storm Drain Near Market Road",
                "public_description": "Damaged storm drain grate creating a vehicular hazard. Field crew dispatched.",
                "ward_or_district": "Ward 12",
                "city": "Bengaluru"
            }
        ],
        "page": 1,
        "page_size": 20,
        "total_items": 1,
        "total_pages": 1
    }
}
```

### Get Public Complaint Detail
`GET /api/v1/public/complaints/{complaint_id}`
- **Access**: Public (Unauthenticated).
- **Path Parameters**: `complaint_id` (UUID).
- **Privacy Enforcement**:
  - If complaint exists but `is_public == False`, returns `404 Not Found` (never leaks existence or private status).
  - Employs strict allowlist projection: `id`, `complaint_number`, `category_name`, `status`, `created_at`, `public_title`, `public_description`, `ward_or_district`, `city`.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Public complaint retrieved successfully",
    "data": {
        "id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
        "complaint_number": "CP-2026-00042",
        "category_name": "Public Infrastructure",
        "status": "IN_PROGRESS",
        "created_at": "2026-11-05T10:00:00Z",
        "public_title": "Damaged Storm Drain Near Market Road",
        "public_description": "Damaged storm drain grate creating a vehicular hazard. Field crew dispatched.",
        "ward_or_district": "Ward 12",
        "city": "Bengaluru"
    }
}
```

---

## 12. Public Content Moderation & Citizen Unpublishing (`/api/v1/complaints`)

Administrative endpoints for publishing and editing public summaries, and citizen endpoints for requesting immediate unpublication.

### Moderate Complaint Public Content
`POST /api/v1/complaints/{complaint_id}/moderate-public`
- **Access**: `ADMINISTRATOR` only (`403 Forbidden` for citizens and field workers).
- **Path Parameters**: `complaint_id` (UUID).
- **Request Body**:
```json
{
    "action": "PUBLISH",
    "public_title": "Damaged Storm Drain Near Market Road",
    "public_description": "Damaged storm drain grate creating a vehicular hazard. Field crew dispatched."
}
```
- **Validation Rules**:
  - `action`: `PUBLISH`, `UPDATE`, or `REVOKE`.
  - `public_title`: Required for `PUBLISH` and `UPDATE` (length: 5 to 200 characters).
  - `public_description`: Required for `PUBLISH` and `UPDATE` (length: 10 to 2000 characters).
  - Complaints in `REJECTED` or `DUPLICATE` status **cannot** be published (`422 Unprocessable Entity`).
  - Raw citizen title/description are **never** used as fallback; administrator must supply curated content.
  - Moderation does not modify complaint lifecycle status.
- **Response**: `200 OK` returning updated moderation state.

### Citizen Request Unpublishing
`POST /api/v1/complaints/{complaint_id}/request-unpublish`
- **Access**: `CITIZEN` owner only (verified against `complaint.citizen_id == current_user.id`; non-owners receive `403 Forbidden`).
- **Path Parameters**: `complaint_id` (UUID).
- **Request Body**:
```json
{
    "reason": "Personal privacy request by resident."
}
```
- **Behavior**:
  - Immediately sets `is_public = False` in the database.
  - Atomically records `unpublish_requested_at`, `unpublish_requested_by_id`, and `unpublish_reason`.
  - Complaint immediately disappears from public feeds and following lists.
  - Operation is idempotent (subsequent requests retain audit history).
- **Response**: `200 OK`.

---

## 13. Community Following (`/api/v1/complaints`)

Endpoints allowing authenticated citizens to subscribe to public civic complaints in their community.

### Follow Public Complaint
`POST /api/v1/complaints/{complaint_id}/follow`
- **Access**: `CITIZEN` only (`403 Forbidden` for field workers and administrators).
- **Path Parameters**: `complaint_id` (UUID).
- **Preconditions**:
  - Complaint must exist and have `is_public == True`. Following a private complaint returns `404 Not Found`.
- **Behavior**:
  - Records follow relationship `(complaint_id, citizen_id)` protected by a composite database unique constraint.
  - Idempotent: repeated requests return success without duplicate rows.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Complaint followed successfully",
    "data": {
        "complaint_id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
        "is_following": true
    }
}
```

### Unfollow Public Complaint
`DELETE /api/v1/complaints/{complaint_id}/follow`
- **Access**: `CITIZEN` only.
- **Path Parameters**: `complaint_id` (UUID).
- **Behavior**:
  - Removes follow record for the calling citizen.
  - Strictly scoped to the authenticated caller's own follow record; cannot remove another citizen's follow.
  - Idempotent: returns `is_following: false` even if not previously following.
- **Response**: `200 OK`

### List Followed Complaints
`GET /api/v1/complaints/following`
- **Access**: `CITIZEN` only.
- **Query Parameters**: `page` (default: 1), `page_size` (default: 20).
- **Behavior**:
  - Lists public complaints currently followed by the authenticated citizen.
  - Isolated strictly to `complaint_followers.citizen_id == current_user.id`.
  - Automatically filters out unpublished complaints (`complaint.is_public == True`).
  - Uses public allowlist projection (no citizen PII or exact coordinates).
- **Response**: `200 OK` paginated list.

---

## 14. SLA Management, Dual Clocks & Escalation (`/api/v1/admin/sla`)

Administrator-only endpoints for Service Level Agreement policy configuration, dual-clock performance tracking, cycle audit history, and bounded batch evaluations.

### Dual-Clock SLA Architecture & Lifecycle Semantics
CivicPulse implements two independent SLA clocks per complaint:
1. **Response SLA Clock**:
   - **Start**: Initiated at complaint submission timestamp (`complaint.created_at`).
   - **Stop**: Stops when the complaint first transitions from `SUBMITTED` to `UNDER_REVIEW` (`responded_at = now_utc`).
   - **Early Terminal Exit**: If a complaint reaches `REJECTED` or `DUPLICATE` before being reviewed, the response clock stops at that transition.
   - **Permanent Completion**: Assignment, worker acceptance, starting work, progress updates, and reassignments do NOT complete the response clock. Once completed, the response clock remains permanently completed and is never reset upon reopening.
2. **Resolution SLA Clock**:
   - **Start**: Begins at `complaint.created_at` for Cycle 1 (or at reopening timestamp for Cycle > 1).
   - **Stop**: Stops strictly when transitioning from `IN_PROGRESS` to `RESOLVED_AWAITING_VERIFICATION` (`resolved_at = now_utc`).
   - **Pause Handling**: Pauses during `ON_HOLD` status. Active pause is calculated dynamically during evaluation queries without mutating stored counters; accumulated pause duration is applied upon transition out of `ON_HOLD`.
   - **Reopen Cycles**: Reopening from `RESOLVED_AWAITING_VERIFICATION` or `CLOSED` snapshots the completed cycle into immutable `complaint_sla_history`, increments `sla_cycle_number >= 1`, resets resolution clock state, resolves fresh policy targets, and starts a new resolution deadline while preserving the completed response clock.

### SLA Policy Precedence Hierarchy
When evaluating a complaint, active policies are resolved using deterministic 4-tier precedence:
1. **Exact category + priority match** (`category_id = c AND priority = p`).
2. **Category-specific policy** (`category_id = c AND priority IS NULL`).
3. **Priority-specific policy** (`category_id IS NULL AND priority = p`).
4. **Global fallback policy** (`category_id IS NULL AND priority IS NULL`).

### Escalation Thresholds & Exact Boundaries
Calculated as active elapsed SLA duration divided by the applicable target duration:
- **Response clock**:
  - Level 0 (Normal): Elapsed percentage < 75%
  - Level 1 (Warning): Elapsed percentage >= 75% and < 100%
  - Level 2 (Breached): Elapsed percentage >= 100%
- **Resolution clock**:
  - Level 0 (Normal): Elapsed percentage < 75%
  - Level 1 (Warning): Elapsed percentage >= 75% and < 100%
  - Level 2 (Breached): Elapsed percentage >= 100% and < 150%
  - Level 3 (Severe breach): Elapsed percentage >= 150%
  - Level 2 (Breached): Effective consumption 100% to < 150%
  - Level 3 (Severe breach): Effective consumption >= 150%

---

### List SLA Policies
`GET /api/v1/admin/sla/policies`
- **Access**: `ADMINISTRATOR` only (`403 Forbidden` for citizens and workers).
- **Query Parameters**: `active_only` (bool, default: false).
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "SLA policies retrieved successfully",
    "data": [
        {
            "id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
            "name": "Potholes High Priority SLA",
            "description": "Standard SLA for high-priority road surface issues",
            "category_id": 1,
            "priority": "HIGH",
            "response_time_hours": 4,
            "resolution_time_hours": 24,
            "is_active": true,
            "created_at": "2026-11-20T08:00:00Z",
            "updated_at": "2026-11-20T08:00:00Z"
        }
    ]
}
```

### Create SLA Policy
`POST /api/v1/admin/sla/policies`
- **Access**: `ADMINISTRATOR` only.
- **Request Body**:
```json
{
    "name": "Global Fallback SLA",
    "description": "Baseline policy applied when no specific category or priority SLA exists",
    "category_id": null,
    "priority": null,
    "response_time_hours": 24,
    "resolution_time_hours": 72,
    "is_active": true
}
```
- **Concurrency & Validation**:
  - Protected with PostgreSQL transaction-scoped advisory locks on the logical key `(category_id, priority)`.
  - Enforces database partial unique indexes to guarantee at most one policy per logical combination.
  - Durations must be positive integer hours (`1` to `8760`).
- **Response**: `201 Created`

### Update SLA Policy
`PATCH /api/v1/admin/sla/policies/{policy_id}`
- **Access**: `ADMINISTRATOR` only.
- **Path Parameters**: `policy_id` (UUID).
- **Request Body**: Partial update payload (`name`, `description`, `response_time_hours`, `resolution_time_hours`, `is_active`).
- **Behavior**:
  - Row locked with `with_for_update()`.
  - Preserves completed historical cycle snapshots in `complaint_sla_history`.
- **Response**: `200 OK`

### Bounded On-Demand SLA Evaluation
`POST /api/v1/admin/sla/evaluate`
- **Access**: `ADMINISTRATOR` only.
- **Request Body**:
```json
{
    "complaint_id": null,
    "department_id": null,
    "category_id": null,
    "priority": null,
    "status": null,
    "limit": 50
}
```
- **Behavior**:
  - Batch size is bounded between `1` and `200` to prevent database overload.
  - Dynamically computes active pause durations during `ON_HOLD` without mutating accumulated database fields.
  - Updates complaint deadlines and escalation levels deterministically.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "SLA batch evaluation completed successfully",
    "data": {
        "evaluated_count": 15,
        "escalated_count": 2,
        "results": [
            {
                "complaint_id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
                "complaint_number": "CP-2026-10042",
                "previous_response_escalation": 0,
                "new_response_escalation": 1,
                "previous_resolution_escalation": 0,
                "new_resolution_escalation": 0,
                "evaluated_at": "2026-11-20T08:30:00Z",
                "escalated": true
            }
        ]
    }
}
```

### Inspect Complaint SLA Performance Details
`GET /api/v1/admin/sla/complaints/{complaint_id}`
- **Access**: `ADMINISTRATOR` only.
- **Path Parameters**: `complaint_id` (UUID).
- **Behavior**:
  - Dynamically evaluates live SLA clock consumption and returns comprehensive dual-clock metrics, pause durations, and breach indicators.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Complaint SLA details retrieved successfully",
    "data": {
        "complaint_id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
        "complaint_number": "CP-2026-10042",
        "status": "IN_PROGRESS",
        "priority": "HIGH",
        "category_id": 1,
        "created_at": "2026-11-20T06:00:00Z",
        "sla_cycle_number": 1,
        "response_sla_policy_id": "f3b1c2d3-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
        "response_deadline": "2026-11-20T10:00:00Z",
        "responded_at": "2026-11-20T07:15:00Z",
        "response_pause_duration_seconds": 0,
        "response_pause_started_at": null,
        "response_escalation_level": 0,
        "response_breached": false,
        "resolution_sla_policy_id": "f3b1c2d3-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
        "resolution_deadline": "2026-11-21T06:00:00Z",
        "resolved_at": null,
        "resolution_pause_duration_seconds": 0,
        "resolution_pause_started_at": null,
        "resolution_escalation_level": 0,
        "resolution_breached": false,
        "last_sla_evaluated_at": "2026-11-20T08:30:00Z"
    }
}
```

### Inspect Complaint SLA Cycle History
`GET /api/v1/admin/sla/complaints/{complaint_id}/history`
- **Access**: `ADMINISTRATOR` only.
- **Path Parameters**: `complaint_id` (UUID).
- **Behavior**:
  - Retrieves chronological immutable snapshots of completed SLA cycles stored in `complaint_sla_history`.
  - Protected against UPDATE and DELETE by PostgreSQL database trigger `trg_prevent_sla_history_mutation`.
- **Response**: `200 OK`

---

## Notifications (Phase 6.4)

Provides database-backed in-app notifications and event integration across complaint lifecycle, worker assignments, milestone updates, and SLA escalations.

### Notification Types & Event Mapping
The system supports the following canonical `NotificationType` enum values:
- `STATUS_CHANGE`: Dispatched on general complaint lifecycle status transitions (`UNDER_REVIEW`, `ON_HOLD`, `CLOSED`, `REJECTED`, `DUPLICATE`) and worker acknowledgments (`ACCEPTED`, `STARTED`).
- `ASSIGNMENT`: Dispatched to workers and owners upon assignment dispatch or reassignment.
- `RESOLUTION_SUBMITTED`: Dispatched to owner and public followers when a complaint transitions to `RESOLVED_AWAITING_VERIFICATION`.
- `COMPLAINT_REOPENED`: Dispatched to assigned worker and public followers when a complaint is reopened.
- `SLA_WARNING`: Dispatched to owner and assigned worker when an SLA clock reaches warning threshold (Level 1 escalation).
- `SLA_BREACH`: Dispatched to owner and assigned worker when an SLA clock reaches breach threshold (Level 2 breach) or critical breach threshold (Level 3 critical breach).
- `FEEDBACK_REQUEST`: Dispatched when feedback or citizen verification is requested.
- `FEEDBACK_RECEIVED`: Dispatched when citizen submits resolution verification feedback.
- `SYSTEM`: Administrative or system-level notices.

### Notification Invariants & Security
- **Strict Role-Scoping & IDOR Defense**: Users can only list, view, and mark as read notifications where `recipient_id == current_user.id`. Marking another user's notification returns `404 Not Found`.
- **Idempotency via Event Keys**: Notifications are created using deterministic `event_key` identifiers combined with PostgreSQL partial unique index `uq_notifications_recipient_event_key` (`(recipient_id, event_key) WHERE event_key IS NOT NULL`) and `ON CONFLICT DO NOTHING`.
- **Follower Privacy Boundaries**: Public followers receive notifications strictly when `complaint.is_public == True`. Private complaints dispatch zero notifications to followers.
- **Actor Exclusion**: The user triggering an action does not receive an echo notification about their own action (with the exception of initial complaint submission confirmation for the submitting citizen).
- **Redaction**: Notifications never expose PII (emails, phone numbers), precise GPS coordinates, internal administrative remarks, or unapproved complaint text.

### List User Notifications
`GET /api/v1/notifications`
- **Access**: Authenticated (`CITIZEN`, `FIELD_WORKER`, `ADMINISTRATOR`).
- **Query Parameters**:
  - `page` (integer, default `1`, minimum `1`): Page number (1-indexed).
  - `page_size` (integer, default `20`, range `1-100`): Maximum items per page.
  - `unread_only` (boolean, default `false`): When `true`, filters strictly to unread notifications.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Notifications retrieved successfully",
    "data": {
        "items": [
            {
                "id": "7c8d9e0f-1a2b-3c4d-5e6f-7a8b9c0d1e2f",
                "recipient_id": "3a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
                "complaint_id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
                "notification_type": "STATUS_CHANGE",
                "title": "Complaint Submitted: CP-2026-10042",
                "message": "Your complaint has been successfully registered with tracking number CP-2026-10042 and is awaiting administrative triage.",
                "event_key": "complaint:e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c:submitted",
                "is_read": false,
                "read_at": null,
                "created_at": "2026-11-20T08:30:00Z"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20,
        "total_pages": 1,
        "unread_count": 1
    }
}
```

### Get Unread Notification Count
`GET /api/v1/notifications/unread-count`
- **Access**: Authenticated (`CITIZEN`, `FIELD_WORKER`, `ADMINISTRATOR`).
- **Behavior**: Retrieves the current count of unread notifications for UI badge rendering.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Unread notification count retrieved successfully",
    "data": {
        "unread_count": 3
    }
}
```

### Mark Notification as Read
`PATCH /api/v1/notifications/{notification_id}/read`
- **Access**: Authenticated (`CITIZEN`, `FIELD_WORKER`, `ADMINISTRATOR`).
- **Path Parameters**: `notification_id` (UUID).
- **Behavior**: Sets `is_read = true` and `read_at = current_timestamp` for the targeted notification. Returns `404 Not Found` if notification does not exist or belongs to another user.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "Notification marked as read successfully",
    "data": {
        "id": "7c8d9e0f-1a2b-3c4d-5e6f-7a8b9c0d1e2f",
        "recipient_id": "3a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
        "complaint_id": "e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c",
        "notification_type": "STATUS_CHANGE",
        "title": "Complaint Submitted: CP-2026-10042",
        "message": "Your complaint has been successfully registered with tracking number CP-2026-10042 and is awaiting administrative triage.",
        "event_key": "complaint:e2a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c:submitted",
        "is_read": true,
        "read_at": "2026-11-20T08:35:00Z",
        "created_at": "2026-11-20T08:30:00Z"
    }
}
```

### Mark All Notifications as Read
`POST /api/v1/notifications/read-all`
- **Access**: Authenticated (`CITIZEN`, `FIELD_WORKER`, `ADMINISTRATOR`).
- **Behavior**: Atomically updates all unread notifications belonging to the authenticated user to `is_read = true` and sets `read_at`.
- **Response**: `200 OK`
```json
{
    "success": true,
    "message": "All notifications marked as read",
    "data": {
        "marked_read_count": 3
    }
}
```

---

*Additional endpoint documentation will be added as each phase is implemented:*

| Phase | Endpoints | Status |
|---|---|---|
| Phase 1 | Health Check (`GET /health`) | ✅ Implemented |
| Phase 3 | Auth (`POST /auth/register`, `POST /auth/login`, `GET /auth/me`) | ✅ Implemented |
| Phase 4 | Categories (`GET /categories`), Complaints (`POST /complaints`, `GET /complaints`, `GET /complaints/{id}`, `GET /complaints/{id}/history`, `PATCH /complaints/{id}/review`, `POST /complaints/{id}/transitions`) | ✅ Implemented |
| Phase 5 | Departments (`/departments`), Field Workers (`/workers`), Worker Task Queue (`/workers/me/tasks`), Assignments (`/assignments`, `/complaints/{id}/assign`, `/complaints/{id}/reassign`) | ✅ Implemented |
| Phase 6.1 | Citizen Dashboard (`GET /citizens/me/dashboard`), Unified Timeline (`GET /complaints/{id}/timeline`) | ✅ Implemented |
| Phase 6.2 | Moderated Public Feed (`/public/complaints`), Public Content Moderation (`/complaints/{id}/moderate-public`), Citizen Unpublishing (`/complaints/{id}/request-unpublish`), Following (`/complaints/{id}/follow`, `/complaints/following`) | ✅ Implemented |
| Phase 6.3 | SLA Policies (`/admin/sla/policies`), Evaluation (`/admin/sla/evaluate`), Complaint SLA Details & History (`/admin/sla/complaints/{id}`) | ✅ Implemented |
| Phase 6.4 | In-App Notifications & Event Integration (`/notifications`, `/notifications/unread-count`, `/notifications/{id}/read`, `/notifications/read-all`) | ✅ Implemented |
| Phase 6.5 | Final Integration, Security, Privacy, Database Integrity & Performance Audit | Pending |
| Phase 7 | File Uploads, Evidence Attachments | Pending |
| Phase 8 | Citizen Satisfaction Feedback, Citizen Verification | Pending |
| Phase 9 | In-App & Multi-channel Notifications | Pending |
| Phase 10 | Spatial & Statistical Analytics | Pending |
