# CivicPulse — Testing Methodology & Results

## Overview

CivicPulse uses **pytest** as the test framework. Tests are organised by domain in the `tests/` directory and cover unit tests, database/model tests, API integration tests, and migration reversibility.

## Test Infrastructure

| Component | Technology | Purpose |
|---|---|---|
| Framework | pytest (v9.2.0) | Test discovery, execution, fixtures |
| API Client | FastAPI TestClient (httpx) | HTTP-level integration tests |
| Test Database | PostgreSQL 18 (`civicpulse_test`) | Isolated test database for migrations and ORM tests |
| Fixtures | `tests/conftest.py`, `tests/test_database.py` | Shared test client, engine, and transaction rollback sessions |

## Running Tests

```
pytest                          # Run all tests
pytest -v                       # Verbose output with test names
pytest tests/test_database.py   # Run database and migration tests
pytest tests/test_config.py     # Run configuration tests
pytest tests/test_health.py     # Run health check tests
pytest -k "test_complaint"      # Run tests matching a keyword
pytest --tb=short               # Shorter traceback on failures
```

---

## Current Test Results

| Test File | Tests | Status | Scope |
|---|---|---|---|
| `tests/test_health.py` | 5 | ✅ All passed | Phase 1 Health check API & middleware |
| `tests/test_config.py` | 3 | ✅ All passed | Application configuration & URL encoding |
| `tests/test_database.py` | 16 | ✅ All passed | Models, constraints, cascades, Alembic migrations |
| `tests/test_auth.py` | 25 | ✅ All passed | Phase 3 Registration, Login, Timing-safety, JWT, RBAC, Admin Provisioning |
| `tests/test_complaints.py` | 37 | ✅ All passed | Phase 4 Submission, Retrieval, Triage Review, State Machine, Locking, Categories, Grace Period |
| `tests/test_assignments.py` | 49 | ✅ All passed | Phase 5 & 5.1 Department Management, Worker Provisioning, Assignment Workflow, IDOR, Lifecycle Integrity, Concurrency, Milestone Progress Audit |
| `tests/test_phase6_1_dashboard_and_timeline.py` | 33 | ✅ All passed | Phase 6.1, 6.1.1 & 6.1.2 Citizen Dashboard, Timeline Redaction, Rejection/Duplicate Redaction, Multi-Assignment Interval Authorization, Anti-Spoofing, Worker Remark Redaction |
| `tests/test_phase6_2_public_feed_and_followers.py` | 38 | ✅ All passed | Phase 6.2 & 6.2.1 Public Feed Privacy, Allowlist Serialization, Admin Moderation, Citizen Unpublishing, Community Following, Lifecycle Auto-Privacy, Follow Concurrency & Unpublish Audit Preservation |
| `tests/test_phase6_3_sla_management.py` | 74 | ✅ All passed | Phase 6.3, 6.3.1 & 6.3.2 SLA Policies, 4-Tier Precedence, Advisory Locks, Dual Clocks, ON_HOLD Pause Accounting, Deterministic Escalation (0–3), Decimal Boundary Precision, Exclusive Resolution Stop Condition, Append-Only Cycle History, DB Trigger Immutability, Admin API |
| `tests/test_phase6_4_notifications.py` | 62 | ✅ All passed | Phase 6.4 & 6.4.1 In-App Notifications, Migration 007, Partial Unique Index Arbiter Verification, Deterministic Event Keys, Multi-threaded Concurrent Idempotency, Transaction Atomicity & Rollback Integrity, SLA Warning/Breach Classification, Follower Privacy Boundaries, Actor Exclusion, Inbox API & IDOR Security |
| `tests/test_phase6_5_final_audit.py` | 20 | ✅ All passed | Phase 6.5 Final Backend Integration, Security, Privacy, Partial Unique Index Arbiter, Outer Rollback Integrity, Reassignment Cutoff, Unpublish History, SLA Independence, Performance & Joinedloading |
| `tests/test_phase6_5_1_reconciliation.py` | 7 | ✅ All passed | Phase 6.5.1 Final API Contract, Schema Reconciliation, Public Feed Zero-Pincode & Coarse-Location Verification, Route Inventory & Migration Chain Integrity |
| **Total** | **369** | **✅ 369/369 Passed** | **Full backend test suite across 12 test files (0 warnings from project code)** |

---

### Phase 6.2 Test Specifications (`tests/test_phase6_2_public_feed_and_followers.py`)

#### Database & Migration Integrity
- `test_new_complaints_default_to_private`: Verifies newly created complaints have `is_public=False` by default.
- `test_database_server_default_is_false`: Verifies raw database insert without `is_public` column uses server default `false`.
- `test_complaint_followers_table_constraints`: Verifies `(complaint_id, citizen_id)` composite unique constraint and cascade deletion.

#### Moderation & Authorization
- `test_admin_can_publish_complaint`: Verifies administrator can publish complaint with curated public title and description.
- `test_admin_can_update_approved_public_content`: Verifies administrator can update approved public content with `UPDATE` action.
- `test_admin_can_revoke_publication`: Verifies administrator can revoke public visibility with `REVOKE` action.
- `test_citizen_and_worker_cannot_moderate_public`: Verifies citizens and field workers receive HTTP 403 Forbidden when calling moderate-public.
- `test_invalid_public_content_validation`: Verifies length constraints for `public_title` (5–200) and `public_description` (10–2000).
- `test_publishing_rejected_and_duplicate_complaints_blocked`: Verifies publishing blocked for `REJECTED` and `DUPLICATE` complaints (HTTP 422).
- `test_moderation_does_not_modify_lifecycle_status`: Verifies moderation actions do not alter the complaint's lifecycle state machine status.

#### Public Feed Privacy & Allowlist Serialization
- `test_public_feed_includes_only_published_complaints`: Verifies public listing contains strictly `is_public == True` complaints.
- `test_public_complaint_detail_privacy_and_404_on_private`: Verifies unauthenticated detail returns HTTP 404 for private complaints and strict allowlist fields (zero PII, zero raw text, zero exact coordinates, zero internal remarks).
- `test_unpublished_complaint_immediately_unavailable`: Verifies revoked complaints immediately return HTTP 404.

#### Lifecycle Integration & Automatic Privacy
- `test_transition_to_rejected_automatically_revokes_publication`: Verifies transition to `REJECTED` automatically sets `is_public = False`.
- `test_transition_to_duplicate_automatically_revokes_publication`: Verifies transition to `DUPLICATE` automatically sets `is_public = False`.
- `test_failed_transition_rolls_back_visibility_change`: Verifies failed transitions atomically roll back without partially changing visibility.

#### Citizen Unpublishing
- `test_complaint_owner_can_request_unpublish`: Verifies complaint author can request unpublish; immediately sets `is_public = False` and logs reason.
- `test_non_owner_citizen_cannot_request_unpublish`: Verifies non-owner citizens receive HTTP 403 Forbidden.
- `test_repeated_unpublish_requests_are_consistent`: Verifies idempotent unpublish behavior.
- `test_citizen_cannot_republish_complaint`: Verifies citizens cannot publish or republish complaints (HTTP 403).

#### Community Following
- `test_citizen_can_follow_and_unfollow_public_complaint`: Verifies citizen can follow public complaint and unfollow deletes follow record.
- `test_citizen_cannot_follow_private_complaint`: Verifies following private complaint returns HTTP 404.
- `test_worker_and_admin_cannot_follow`: Verifies workers and administrators receive HTTP 403 Forbidden when attempting to follow.
- `test_following_feed_isolated_to_authenticated_citizen`: Verifies citizen following feed is strictly isolated to the caller.
- `test_unpublished_complaints_disappear_from_following_feed`: Verifies unpublished complaints immediately disappear from following feed.
- `test_citizen_cannot_remove_another_citizens_follow`: Verifies citizen unfollow cannot affect another citizen's follow record.

#### Pagination & Query Filtering
- `test_public_feed_pagination_and_sorting`: Verifies deterministic page/page_size ordering (most recent first).
- `test_public_feed_category_and_status_filtering`: Verifies status filtering on public feed.
- `test_public_feed_category_filtering`: Verifies category filtering on public feed.

#### Phase 6.2.1 Audit & Integrity Verification
- `test_concurrent_duplicate_follow_attempts`: Verifies unique constraint race condition handling and session recovery after IntegrityError rollback.
- `test_concurrent_follow_multithreaded_safety`: Executes multi-threaded ThreadPoolExecutor test across separate database sessions verifying concurrent safety.
- `test_repeated_unpublishing_preserves_initial_audit_metadata`: Verifies repeated citizen unpublish calls do not overwrite initial unpublish timestamp or destroy reason.
- `test_public_feed_pagination_metadata_does_not_leak_private_count`: Verifies public total count reflects strictly public complaints and excludes private counts.
- `test_public_response_strict_field_exclusion`: Verifies all 9 allowlist fields are present and confirms zero leakage of forbidden fields (PII, GPS, citizen text, notes).
- `test_failed_moderation_rolls_back_cleanly`: Verifies nested transaction rollback cleanly restores pre-moderation visibility state.
- `test_failed_unpublishing_rolls_back_cleanly`: Verifies nested transaction rollback cleanly restores pre-unpublish visibility state.
- `test_following_after_publication_revocation_returns_404`: Verifies attempting to follow a revoked public complaint returns 404 Not Found.
- `test_existing_complaints_data_preservation_and_structure`: Verifies existing complaint relationships, coordinates, and fields remain intact.

---

### Phase 4 Test Specifications (`tests/test_complaints.py`)

#### Category Retrieval (`TestActiveCategories`)
- `test_list_active_categories`: Verifies `GET /api/v1/categories/` returns all seeded active civic categories.
- `test_inactive_category_excluded`: Verifies categories with `is_active=False` are excluded from the public categories endpoint.

#### Complaint Submission & Validation (`TestComplaintSubmission`)
- `test_citizen_complaint_submission_success`: Verifies citizen can submit complaint with valid title, description, category, and coordinates; returns HTTP 201 with generated tracking number (`CP-YYYY-XXXXX`), status `SUBMITTED`, priority `MEDIUM`.
- `test_submission_auto_generates_complaint_number`: Verifies sequential complaint numbering backed by PostgreSQL `complaint_number_seq`.
- `test_submission_with_invalid_category_fails`: Verifies referencing non-existent category raises HTTP 404 Not Found.
- `test_submission_with_inactive_category_fails`: Verifies submitting to deactivated category raises HTTP 400 Bad Request.
- `test_submission_with_invalid_coordinates_rejected`: Verifies latitude/longitude validation (e.g. lat > 90) raises HTTP 422 Unprocessable Entity.
- `test_submission_client_cannot_override_server_defaults`: Verifies client attempting to inject `status="RESOLVED"` or `priority="CRITICAL"` has them overridden with server defaults (`SUBMITTED`, `MEDIUM`).
- `test_submission_creates_initial_status_history`: Verifies initial status history record (`SUBMITTED`) is atomically created upon submission.
- `test_unauthenticated_submission_rejected`: Verifies submission without Bearer token returns HTTP 401 Unauthorized.
- `test_non_citizen_submission_rejected`: Verifies non-citizens (workers or administrators) cannot submit complaints via citizen submission endpoint (HTTP 403 Forbidden).

#### Complaint Retrieval, Scoping & IDOR Defense (`TestComplaintRetrievalAndIDOR`)
- `test_citizen_can_view_own_complaint_detail`: Verifies citizen successfully retrieves their own complaint detail by ID.
- `test_citizen_blocked_from_other_citizen_complaint_idor`: Verifies IDOR defense; a citizen attempting to view another citizen's complaint receives HTTP 403 Forbidden.
- `test_admin_can_view_any_complaint`: Verifies administrator can view any complaint detail regardless of owner.
- `test_get_nonexistent_complaint_returns_404`: Verifies requesting non-existent UUID returns HTTP 404 Not Found.
- `test_citizen_list_returns_only_own_complaints`: Verifies `GET /api/v1/complaints/` scopes results strictly to complaints filed by the authenticated citizen.
- `test_admin_list_can_view_all_complaints`: Verifies administrator listing returns complaints across all citizens.
- `test_admin_list_filter_by_status`: Verifies administrator query filter `?status=UNDER_REVIEW`.
- `test_admin_list_filter_by_category`: Verifies administrator query filter `?category_id=...`.
- `test_admin_list_filter_by_priority`: Verifies administrator query filter `?priority=HIGH`.
- `test_complaint_pagination`: Verifies limit and offset pagination parameters on list endpoints.

#### Administrative Review & Triage (`TestComplaintReview`)
- `test_admin_can_review_complaint`: Verifies admin can reclassify category and adjust priority with required reason.
- `test_admin_review_missing_reason_rejected`: Verifies review without reason string returns HTTP 422.
- `test_citizen_blocked_from_review_endpoint`: Verifies citizens receive HTTP 403 Forbidden when calling review endpoint.
- `test_review_records_audit_history`: Verifies priority or category change logs audit record in status history.

#### Lifecycle State Machine & Preconditions (`TestLifecycleTransitions`)
- `test_admin_moves_submitted_to_under_review`: Verifies transition from `SUBMITTED` -> `UNDER_REVIEW`.
- `test_citizen_cannot_approve_own_review`: Verifies citizen cannot transition their own complaint to `UNDER_REVIEW` (HTTP 403).
- `test_admin_rejects_complaint_with_reason`: Verifies transition `SUBMITTED` -> `REJECTED` with required reason.
- `test_terminal_state_rejected_cannot_transition`: Verifies `REJECTED` terminal state blocks any outgoing transition (HTTP 422).
- `test_admin_marks_duplicate_with_valid_original`: Verifies admin can mark complaint as `DUPLICATE` referencing an existing complaint.
- `test_mark_duplicate_self_reference_rejected`: Verifies marking a complaint as a duplicate of itself is rejected (HTTP 422).
- `test_transition_to_assigned_without_assignment_rejected`: Verifies transition to `ASSIGNED` requires active assignment record (blocked with HTTP 422 in Phase 4).
- `test_citizen_verifies_and_closes_resolved_complaint`: Verifies citizen owner can verify and close complaint in `RESOLVED_AWAITING_VERIFICATION` (sets `closed_at`).
- `test_citizen_reopens_unsatisfactory_resolution`: Verifies citizen owner can reopen `RESOLVED_AWAITING_VERIFICATION` with recorded reason.
- `test_reopened_complaint_triaged_to_under_review`: Verifies admin can triage `REOPENED` complaint back to `UNDER_REVIEW`.
- `test_arbitrary_illegal_transition_rejected`: Verifies arbitrary illegal jumps (e.g. `SUBMITTED` -> `CLOSED`) are rejected with HTTP 422.
- `test_reopen_outside_14_day_grace_period_rejected`: Verifies reopening attempts past the 14-day grace period are rejected with HTTP 422.

#### Concurrency & Row-Level Locking (`TestComplaintConcurrencyAndLocking`)
- `test_concurrent_state_transitions_serialized_with_row_lock`: Verifies PostgreSQL row-level locking (`with_for_update`) serializes concurrent status transition requests across separate database sessions, preventing race conditions or split-brain status histories.

---

### Phase 3 Test Specifications (`tests/test_auth.py`)

#### Citizen Registration (`TestRegistration`)
- `test_successful_citizen_registration`: Verifies citizen registration with valid payload returns HTTP 201, safe user fields, and default `CITIZEN` role.
- `test_duplicate_email_registration_rejected`: Verifies registering an existing email raises HTTP 409 Conflict.
- `test_duplicate_email_case_insensitivity`: Verifies email normalization (case insensitivity) detects duplicates.
- `test_invalid_email_format_rejected`: Verifies Pydantic rejects malformed email strings (HTTP 422).
- `test_mismatched_password_confirmation_rejected`: Verifies mismatched `password` and `password_confirm` raise HTTP 422.
- `test_short_password_rejected`: Verifies passwords shorter than 8 characters are rejected (HTTP 422).
- `test_privileged_role_cannot_be_injected`: Verifies client payloads attempting to pass `role: "ADMINISTRATOR"` or `"FIELD_WORKER"` ignore the injected role and assign `CITIZEN`.

#### User Login & Timing Safety (`TestLogin`)
- `test_successful_login`: Verifies correct credentials return HTTP 200, JWT access token, and user profile.
- `test_incorrect_password_rejected`: Verifies wrong password returns HTTP 401 Unauthorized.
- `test_nonexistent_email_rejected_with_identical_error`: Verifies nonexistent email returns identical HTTP 401 error message ("Invalid email or password") and undergoes constant-time dummy verification.
- `test_inactive_user_login_rejected`: Verifies deactivated user accounts (`is_active=False`) are rejected at login with HTTP 401.

#### Profile & Token Verification (`TestUserProfileAndTokens`)
- `test_authenticated_me_endpoint_success`: Verifies valid Bearer token retrieves user profile via `GET /api/v1/auth/me`.
- `test_missing_authorization_header_rejected`: Verifies unauthenticated request to `/me` returns HTTP 401.
- `test_invalid_bearer_token_rejected`: Verifies malformed or forged JWT returns HTTP 401.
- `test_expired_token_rejected`: Verifies expired token returns HTTP 401 Token Expired.
- `test_token_contains_valid_claims`: Verifies decoded JWT payload contains valid `sub`, `email`, `role`, and `exp`.
- `test_inactive_user_token_access_rejected`: Verifies deactivated user token access is rejected with HTTP 403 Forbidden.

#### Role-Based Access Control (`TestRoleBasedAccessControl`)
- `test_citizen_accesses_citizen_endpoint`: Verifies citizen token successfully accesses citizen-permitted endpoints.
- `test_citizen_blocked_from_admin_endpoint`: Verifies citizen token receives HTTP 403 Forbidden when requesting admin endpoints.
- `test_citizen_blocked_from_worker_endpoint`: Verifies citizen token receives HTTP 403 Forbidden when requesting worker endpoints.
- `test_admin_accesses_admin_endpoint`: Verifies administrator token successfully accesses admin endpoints.
- `test_worker_accesses_worker_endpoint`: Verifies worker token successfully accesses worker endpoints.
- `test_forged_role_in_token_rejected_by_database_check`: Verifies that a forged JWT claim with elevated role is checked against live database role and rejected with HTTP 403.

#### Administrative Provisioning (`TestAdminProvisioning`)
- `test_provision_administrator_success`: Verifies offline CLI provisioning function creates a verified active administrator account.
- `test_provision_administrator_duplicate_rejected`: Verifies provisioning with duplicate email raises `EntityAlreadyExistsError`.

---

### Phase 2 Test Specifications (`tests/test_database.py`)

#### Metadata & Model Structure
- `test_all_13_tables_registered_in_metadata`: Confirms `Base.metadata` contains all 13 core tables.
- `test_primary_keys_defined`: Validates primary key configuration across all models.
- `test_roles_model_structure`: Confirms `roles.name` unique index.
- `test_users_model_structure`: Confirms `users.email` unique index and `role_id` foreign key.
- `test_complaints_foreign_keys`: Confirms complaints link to users, categories, and locations.
- `test_feedback_unique_complaint_id`: Validates 1-to-1 unique constraint on `feedback.complaint_id`.
- `test_workers_unique_user_id`: Validates 1-to-1 unique constraint on `workers.user_id`.

#### PostgreSQL Schema & Constraints Inspection (on `civicpulse_test`)
- `test_all_13_tables_exist_in_database`: Verifies table existence in PostgreSQL 18 catalog.
- `test_locations_check_constraints_in_database`: Verifies `chk_location_latitude_range` and `chk_location_longitude_range`.
- `test_feedback_rating_check_constraint_in_database`: Verifies `chk_feedback_rating_range` (1..5).
- `test_ai_assessment_confidence_check_constraint`: Verifies `chk_ai_confidence_range` (0.0..1.0).

#### ORM Persistence & Relationships
- `test_create_role_and_user_hierarchy`: Verifies insert and bi-directional ORM relationship traversal.
- `test_complaint_full_lifecycle_graph`: Creates a complete entity graph (Role -> User -> Dept -> Cat -> Loc -> Complaint -> StatusHistory) and verifies ORM relationships.
- `test_invalid_latitude_raises_check_violation`: Verifies PostgreSQL rejects latitude outside `[-90, 90]`.
- `test_invalid_rating_raises_check_violation`: Verifies PostgreSQL rejects feedback rating > 5.

#### Alembic Migration Reversibility
- `test_migration_reversibility_on_test_db`: Executes `command.downgrade(cfg, 'base')` on `civicpulse_test`, verifies all tables are cleanly dropped, executes `command.upgrade(cfg, 'head')`, and verifies all tables and migrations are cleanly restored.

---

### Phase 5 Test Specifications (`tests/test_assignments.py`)

#### Department Management (`TestDepartmentManagement`)
- `test_admin_can_create_department`: Verifies administrator can create a municipal department (`POST /api/v1/departments`).
- `test_duplicate_department_code_rejected`: Verifies unique constraint on department code rejects duplicates with HTTP 400.
- `test_citizen_cannot_create_or_modify_departments`: Verifies citizens and workers are forbidden from department CRUD (HTTP 403).
- `test_admin_can_update_and_deactivate_department`: Verifies update and soft-deactivation (`DELETE /api/v1/departments/{id}`).

#### Worker Provisioning (`TestWorkerProvisioning`)
- `test_admin_can_provision_field_worker`: Verifies atomic creation of User (`FIELD_WORKER` role) and Worker profile with department assignment.
- `test_duplicate_employee_id_rejected`: Verifies duplicate employee ID is rejected with HTTP 400.
- `test_provision_to_inactive_department_rejected`: Verifies assigning worker to inactive department fails with HTTP 422.
- `test_worker_deactivation_disables_login_and_availability`: Verifies deleting worker sets status `TERMINATED` and disables user account, immediately blocking login.

#### Complaint Assignment (`TestComplaintAssignment`)
- `test_admin_can_assign_under_review_complaint`: Verifies admin can assign an `UNDER_REVIEW` complaint to eligible worker, moving complaint to `ASSIGNED`.
- `test_assignment_fails_if_complaint_not_under_review`: Verifies complaints in other states (e.g. `SUBMITTED`) cannot be assigned (HTTP 422).
- `test_assignment_department_mismatch_rejected`: Verifies worker department must match complaint category department (HTTP 422).
- `test_assignment_to_inactive_worker_rejected`: Verifies assigning inactive or unavailable worker is rejected (HTTP 422).
- `test_duplicate_active_assignment_rejected`: Verifies assigning an already assigned complaint is rejected (HTTP 422).

#### Worker Task Queue & IDOR Defense (`TestWorkerTaskQueueAndIDOR`)
- `test_worker_can_retrieve_only_own_assigned_tasks`: Verifies `/api/v1/workers/me/tasks` returns only tasks assigned to the authenticated worker.
- `test_worker_cannot_inspect_other_worker_task_by_id_idor`: Verifies IDOR defense: inspecting another technician's task returns HTTP 403 Forbidden.

#### Work Execution Workflow (`TestWorkExecutionWorkflow`)
- `test_complete_worker_remediation_lifecycle`: End-to-end lifecycle verification:
  1. Admin assigns complaint (`UNDER_REVIEW` -> `ASSIGNED`).
  2. Worker accepts task (`accepted_at` recorded).
  3. Worker starts work (`started_at` recorded, assignment and complaint -> `IN_PROGRESS`).
  4. Worker logs intermediate milestone (`/progress`).
  5. Worker completes remediation (`assignment -> COMPLETED`, complaint -> `RESOLVED_AWAITING_VERIFICATION`).
  6. Citizen verifies and closes complaint (`CLOSED`).
- `test_worker_cannot_complete_unstarted_task`: Verifies completing a task that has not been started is rejected (HTTP 422).

#### Complaint Reassignment (`TestComplaintReassignment`)
- `test_admin_reassigns_complaint_successfully`: Verifies admin can reassign active complaint to replacement worker; old assignment marked `REASSIGNED`, new assignment created, complaint returned to `ASSIGNED` if was `IN_PROGRESS`.
- `test_reassignment_requires_valid_reason`: Verifies missing reason is rejected with HTTP 422.
- `test_reassignment_to_same_worker_rejected`: Verifies reassigning to the existing technician is rejected with HTTP 422.
- `test_reassign_in_progress_complaint_follows_legal_transitions_atomically`: Verifies `IN_PROGRESS` complaint reassignment transitions legally through approved Phase 4 transitions (`IN_PROGRESS -> ON_HOLD -> UNDER_REVIEW -> ASSIGNED`) with complete status history audit log entries.
- `test_direct_transition_to_assigned_from_in_progress_rejected`: Verifies that direct illegal jump from `IN_PROGRESS` to `ASSIGNED` is rejected by state machine.
- `test_direct_transition_to_under_review_from_assigned_rejected`: Verifies that direct illegal jump from `ASSIGNED` to `UNDER_REVIEW` is rejected.
- `test_failed_reassignment_rolls_back_atomically`: Verifies that if any step in reassignment fails, the entire transaction rolls back completely without leaving orphaned status history or modified assignments.

#### Concurrency & Database Integrity (`TestConcurrencyAndDatabaseIntegrity`)
- `test_db_partial_unique_index_blocks_duplicate_active_assignment`: Direct database verification that PostgreSQL partial unique index `uq_active_assignment_per_complaint` enforces single active assignment at the engine level.
- `test_concurrent_multi_threaded_assignment_serialized_by_lock`: Multi-threaded test verifying that concurrent race conditions on complaint assignment are properly serialized by PostgreSQL row locks (`with_for_update`) so exactly 1 worker assignment succeeds and the duplicate is safely rejected.

#### Assignment Integrity & Terminal Constraints (`TestAssignmentIntegrityAndTerminalConstraints`)
- `test_cannot_add_progress_to_completed_assignment`: Verifies completed assignments cannot accept further progress logs.
- `test_cannot_add_progress_to_reassigned_assignment`: Verifies superseded reassigned assignments cannot accept further progress logs.
- `test_cannot_complete_already_completed_assignment`: Verifies terminal assignments cannot be completed again.
- `test_cannot_complete_reassigned_assignment`: Verifies superseded reassigned assignments cannot be completed.
- `test_cannot_accept_already_in_progress_or_completed_assignment`: Verifies terminal assignments cannot be accepted again.

#### Worker Authorization Matrix (`TestWorkerAuthorizationMatrix`)
- `test_worker_cannot_accept_another_worker_task`: Verifies IDOR protection prevents accepting other workers' tasks.
- `test_worker_cannot_start_another_worker_task`: Verifies IDOR protection prevents starting other workers' tasks.
- `test_worker_cannot_submit_progress_for_another_worker_task`: Verifies IDOR protection prevents adding progress to other workers' tasks.
- `test_worker_cannot_complete_another_worker_task`: Verifies IDOR protection prevents completing other workers' tasks.
- `test_deactivated_worker_blocked_from_task_queue`: Verifies deactivated worker account is rejected from viewing task queues.
- `test_deactivated_worker_blocked_from_task_operations`: Verifies deactivated worker account is rejected from all task operations at the service layer.
- `test_citizen_blocked_from_worker_endpoints`: Verifies citizen role is rejected from worker endpoints.
- `test_worker_cannot_provision_another_worker`: Verifies worker role cannot provision worker accounts.
- `test_worker_cannot_access_admin_assignments_monitoring`: Verifies worker role cannot access global assignment monitoring.
- `test_unauthenticated_requests_rejected_with_401`: Verifies unauthenticated requests to worker endpoints return 401.

#### Department & Worker Deactivation Parity (`TestDepartmentAndWorkerDeactivationParity`)
- `test_patch_and_delete_department_deactivation_parity`: Verifies parity between `PATCH /api/v1/departments/{id}/deactivate` and `DELETE /api/v1/departments/{id}`.
- `test_patch_and_delete_worker_deactivation_parity`: Verifies parity between `PATCH /api/v1/workers/{id}/deactivate` and `DELETE /api/v1/workers/{id}`.
- `test_cannot_assign_to_worker_in_deactivated_department`: Verifies assignment is rejected if worker belongs to an inactive department.
- `test_cannot_deactivate_department_with_active_assignments`: Verifies business rule preventing deactivation of departments that have ongoing active assignments.
- `test_deactivation_preserves_historical_records`: Verifies soft-deactivation preserves historical assignment and progress records intact.

#### Progress History & Milestone Audit (`TestProgressHistoryAudit`)
- `test_immutable_progress_record_content_and_timestamps`: Verifies progress records are immutable and chronological.
- `test_admin_can_inspect_progress_updates_via_assignment_detail`: Verifies administrator can inspect complete progress audit history via `GET /api/v1/assignments/{id}`.
- `test_worker_can_inspect_own_task_progress_history`: Verifies worker can inspect own task progress history via `GET /api/v1/workers/me/tasks/{id}`.

---

### Phase 6.1, 6.1.1 & 6.1.2 Test Specifications (`tests/test_phase6_1_dashboard_and_timeline.py`)

#### Citizen Dashboard (`GET /api/v1/citizens/me/dashboard`)
- Empty dashboard metrics and schema integrity (10 statuses, 4 priorities).
- Status breakdown accurate counting.
- Priority breakdown accurate counting.
- Awaiting verification and action-required metrics calculation.
- Activity list capping (max 5 records) and sorting order.
- Citizen ownership scoping (no data leakage from other citizens).
- Role restriction (Worker and Admin roles return 403 Forbidden).
- Authentication requirement (401 Unauthorized for unauthenticated requests).

#### Unified Timeline Authorization & Boundaries (`GET /api/v1/complaints/{id}/timeline`)
- Author citizen access allowed.
- Non-author citizen rejected with 403 Forbidden.
- Unassigned worker rejected with 403 Forbidden.
- Assigned worker allowed.
- Previously assigned worker access bounded by verified reassignment cutoff.
- Administrator unrestricted full access.
- Chronological event ordering across all four source entities.
- Non-existent complaint ID returns 404 EntityNotFoundError.
- Newly submitted complaint clean timeline return.

#### Targeted Security & Privacy Verification (Phase 6.1.1 & 6.1.2)
- Administrative rejection remarks redacted for citizens (`remarks = None`).
- Administrative duplicate merge remarks redacted for citizens (`remarks = None`).
- Citizen-authored remarks visible when actor identity reliably proves ownership.
- Assignment updates (`assignment.updated_at`) cannot extend historical access.
- **Scenario 1**: Reassignment marker created through trusted reassignment service accepted as verified boundary.
- **Scenario 2**: Worker-generated progress entry containing `"Reassigned to ..."` text cannot impersonate a reassignment marker.
- **Scenario 3**: Missing or unreliable reassignment marker denies previous-worker access (returns 403 Forbidden fail-closed).
- **Scenario 4**: Completed assignment uses verified completion boundary; missing `completed_at` denies access.
- **Scenario 5**: Reassignment followed by second assignment to the same worker:
  - Worker CAN see events during assignment 1.
  - Worker CANNOT see events during intervening period.
  - Worker CAN see events during assignment 2.
  - Worker CANNOT see events after assignment 2.
- **Scenario 6**: Worker cannot see administrative remarks (triage notes, hold notes, rejection/duplicate notes, confidential resident flags). Worker sees only own authored remarks and designated dispatch remarks.
- **Scenario 7**: Administrator retains full timeline visibility including all administrative deliberations.
- **Scenario 8**: Citizen privacy regression tests from Phase 6.1.1 continue to pass.

---

### Phase 6.3 & 6.3.1 Test Specifications (`tests/test_phase6_3_sla_management.py`)

#### Schema & Database Integrity
- `test_1_sla_policies_table_exists`: Verifies `sla_policies` table exists with primary key and required columns.
- `test_2_complaint_sla_history_table_exists`: Verifies `complaint_sla_history` table exists with columns and unique constraint `(complaint_id, cycle_number)`.
- `test_3_complaints_table_has_all_sla_columns`: Verifies `complaints` table has all 13 SLA columns.
- `test_4_sla_policies_partial_unique_indexes`: Verifies the 4 partial unique indexes on `sla_policies`.
- `test_5_complaint_sla_check_constraints`: Verifies check constraints on pause durations, escalation levels (0–2 response, 0–3 resolution), and cycle number.
- `test_6_reject_invalid_sla_durations`: Verifies check constraint rejects non-positive target durations.
- `test_7_database_trigger_blocks_sla_history_mutation`: Verifies PostgreSQL trigger `trg_prevent_sla_history_mutation` rejects `UPDATE` and `DELETE` on history records.

#### Policy Precedence & Hierarchy (4 Tiers)
- `test_8_precedence_tier_1_category_and_priority_matched`: Verifies Tier 1 exact match takes highest precedence.
- `test_9_precedence_tier_2_category_only_matched`: Verifies Tier 2 category-only match when exact match absent.
- `test_10_precedence_tier_3_priority_only_matched`: Verifies Tier 3 priority-only match when category match absent.
- `test_11_precedence_tier_4_global_fallback`: Verifies Tier 4 global fallback policy when no category or priority match.
- `test_12_no_matching_policy_leaves_sla_fields_null`: Verifies complaint SLA fields remain null if no policy exists.
- `test_13_inactive_policies_ignored_in_precedence`: Verifies inactive policies are excluded from resolution.
- `test_14_concurrent_policy_creation_prevented_by_advisory_lock`: Verifies advisory locks serialize concurrent policy creation.

#### Dual-Clock Independent Lifecycle
- `test_15_response_clock_starts_at_complaint_creation`: Verifies response clock starts at `created_at`.
- `test_16_response_clock_stops_on_under_review_transition`: Verifies response clock completes when status changes to `UNDER_REVIEW`.
- `test_17_response_clock_stops_on_early_rejection`: Verifies response clock completes when status changes directly to `REJECTED`.
- `test_18_response_clock_stops_on_early_duplicate`: Verifies response clock completes when status changes directly to `DUPLICATE`.
- `test_19_response_clock_does_not_restart_on_assignment`: Verifies response clock remains completed and does not restart when assigned.
- `test_20_resolution_clock_starts_at_complaint_creation`: Verifies resolution clock starts at `created_at`.
- `test_21_resolution_clock_stops_on_resolved_awaiting_verification`: Verifies resolution clock stops when status changes to `RESOLVED_AWAITING_VERIFICATION`.
- `test_22_resolution_clock_stops_on_direct_closure`: Verifies resolution clock stops on terminal `CLOSED`.
- `test_23_resolution_clock_does_not_stop_on_under_review`: Verifies resolution clock remains running when response clock completes.
- `test_24_resolution_clock_does_not_stop_on_assignment`: Verifies resolution clock continues through `ASSIGNED` status.

#### Pause Accounting (ON_HOLD Transitions)
- `test_25_transition_to_on_hold_records_pause_start_for_active_clocks`: Verifies active clocks record pause start time.
- `test_26_completed_response_clock_is_not_paused_on_hold`: Verifies completed response clock is not paused.
- `test_27_transition_out_of_on_hold_accumulates_pause_duration`: Verifies pause seconds accumulate into `resolution_pause_duration_seconds`.
- `test_28_transition_out_of_on_hold_extends_effective_deadline`: Verifies effective deadline extended by pause duration.
- `test_29_multiple_on_hold_periods_accumulate_correctly`: Verifies consecutive hold periods accumulate additively.
- `test_30_dynamic_evaluation_while_on_hold_includes_in_progress_pause`: Verifies live evaluation dynamically computes in-progress pause without DB mutation.

#### Escalation Levels & Dynamic Evaluation
- `test_31_response_escalation_level_0_under_75_percent`: Verifies Response Level 0 when < 75%.
- `test_32_response_escalation_level_1_at_75_percent_warning`: Verifies Response Level 1 when 75% to < 100%.
- `test_33_response_escalation_level_2_at_100_percent_breach`: Verifies Response Level 2 when >= 100%.
- `test_34_resolution_escalation_level_0_under_75_percent`: Verifies Resolution Level 0 when < 75%.
- `test_35_resolution_escalation_level_1_at_75_percent_warning`: Verifies Resolution Level 1 when 75% to < 100%.
- `test_36_resolution_escalation_level_2_at_100_percent_breach`: Verifies Resolution Level 2 when 100% to < 150%.
- `test_37_resolution_escalation_level_3_at_150_percent_severe_breach`: Verifies Resolution Level 3 when >= 150%.
- `test_38_evaluate_sla_batch_processes_and_updates_escalation`: Verifies batch evaluation updates escalation levels across complaints.
- `test_39_idempotent_escalation_evaluation_does_not_duplicate_events`: Verifies repeated evaluation does not produce duplicate side effects.
- `test_40_dynamic_deescalation_on_policy_duration_increase`: Verifies policy target increase de-escalates active complaint.
- `test_41_policy_target_update_audited_in_status_history`: Verifies escalation change from policy update is logged in status history.

#### Reopening Cycle Integration & History Snapshots
- `test_42_snapshot_cycle_history_created_on_reopening`: Verifies cycle 1 snapshotted when citizen reopens complaint.
- `test_43_reopen_increments_cycle_number`: Verifies `sla_cycle_number` increments to 2 on reopen.
- `test_44_reopen_starts_fresh_resolution_clock`: Verifies fresh resolution deadline and reset pause counters.
- `test_45_reopen_preserves_completed_response_clock`: Verifies response clock remains completed from cycle 1.
- `test_46_reopen_beyond_14_days_grace_period_rejected`: Verifies reopen after 14 days is rejected (422).
- `test_47_terminal_status_creates_final_cycle_snapshot`: Verifies terminal `CLOSED` snapshots final cycle.
- `test_48_rejection_terminal_status_creates_final_cycle_snapshot`: Verifies terminal `REJECTED` snapshots cycle.
- `test_49_duplicate_terminal_status_creates_final_cycle_snapshot`: Verifies terminal `DUPLICATE` snapshots cycle.
- `test_50_repeated_snapshots_for_same_cycle_are_idempotent`: Verifies duplicate cycle snapshot is safely ignored.

#### Administrative API Endpoints & RBAC
- `test_51_admin_can_list_sla_policies`: Verifies `GET /api/v1/admin/sla/policies`.
- `test_52_admin_can_create_sla_policy`: Verifies `POST /api/v1/admin/sla/policies`.
- `test_53_admin_can_update_sla_policy`: Verifies `PATCH /api/v1/admin/sla/policies/{id}`.
- `test_54_pagination_and_batch_size_limits_are_enforced`: Verifies batch evaluation limit (1–200).
- `test_55_admin_can_inspect_complaint_sla_details`: Verifies `GET /api/v1/admin/sla/complaints/{id}`.
- `test_56_admin_can_inspect_complaint_sla_history`: Verifies `GET /api/v1/admin/sla/complaints/{id}/history`.
- `test_57_citizen_forbidden_from_admin_sla_endpoints`: Verifies citizens receive HTTP 403 Forbidden.
- `test_58_worker_forbidden_from_admin_sla_endpoints`: Verifies workers receive HTTP 403 Forbidden.
- `test_59_unauthenticated_request_rejected`: Verifies unauthenticated requests return HTTP 401 Unauthorized.
- `test_60_admin_sla_detail_returns_404_for_nonexistent_complaint`: Verifies non-existent complaint returns 404.

#### Phase 6.3.1 Boundary & Lifecycle Corrections
- `test_61_response_clock_remains_active_after_assignment_and_worker_acceptance`: Verifies response clock remains active during `ASSIGNED` and worker acceptance, completing only on `UNDER_REVIEW`.
- `test_62_exact_escalation_boundaries`: Verifies exact evaluation at 74.99%, 75%, 99.99%, 100%, 149.99%, and 150%.
- `test_63_reopen_from_closed_creates_new_cycle_and_snapshots_history`: Verifies citizen can reopen from `CLOSED` within 14 days, incrementing cycle to 2 and snapshotting cycle 1.
- `test_64_reopen_from_resolved_snapshots_with_end_reason_reopened`: Verifies reopening from `RESOLVED_AWAITING_VERIFICATION` snapshots cycle with `end_reason="REOPENED"` and actual resolution seconds.
- `test_65_concurrent_reopen_snapshot_idempotency_and_db_uniqueness`: Verifies concurrent snapshot attempts handle uniqueness constraint safely.
- `test_66_transaction_rollback_preserves_lifecycle_and_sla_consistency`: Verifies transition failure rolls back cleanly without partial SLA state mutations.
- `test_67_sla_policy_target_change_audits_escalation_in_status_history`: Verifies policy duration changes record status history audit entry with admin user identity.

#### Phase 6.3.2 Final Resolution Semantics, Precision & Verification
- `test_68_moving_from_resolved_to_closed_does_not_create_second_resolution_completion`: Verifies moving from `RESOLVED_AWAITING_VERIFICATION` to `CLOSED` does not re-stop resolution clock, preserves worker resolution timestamp, and calculates snapshot duration using `resolved_at` rather than `closed_at`.
- `test_69_rejection_before_resolution_does_not_falsely_complete_resolution_sla`: Verifies complaint rejection does not fabricate `resolved_at`, preserves elapsed seconds, records `end_reason="REJECTED"`, and never marks resolution SLA as met (`resolution_breached is not False`).
- `test_70_duplicate_classification_before_resolution_does_not_falsely_complete_resolution_sla`: Verifies duplicate marking does not fabricate `resolved_at`, preserves elapsed seconds, records `end_reason="DUPLICATE"`, and never marks resolution SLA as met (`resolution_breached is not False`).
- `test_71_terminated_complaints_do_not_receive_active_resolution_escalations`: Verifies terminated complaints (`REJECTED`, `DUPLICATE`, `CLOSED`) never receive active resolution escalations even when evaluated far in the future.
- `test_72_reopening_preserves_cycle_actual_resolution_timestamp_and_starts_fresh_cycle`: Verifies reopening preserves cycle 1 actual worker resolution timestamp in snapshot history and starts cycle 2 resolution from reopen timestamp.
- `test_73_exact_decimal_escalation_threshold_comparisons_and_sub_threshold_boundaries`: Verifies deterministic threshold evaluations using `Decimal` precision at values immediately below (e.g. 74.9999%, 99.9999%, 149.9999%), exactly at (75%, 100%, 150%), and immediately above (75.0001%, 100.0001%, 150.0001%), and confirms no rounding promotion occurs on micro-fractional boundary values.
- `test_74_admin_sla_detail_terminated_complaint_does_not_retroactively_breach`: Verifies terminated complaints inspected in `GET /api/v1/admin/sla/complaints/{id}` do not retroactively report `resolution_breached=True` merely because wall-clock time passed after termination.

---

### Phase 6.4 Test Specifications (`tests/test_phase6_4_notifications.py`)

#### Database Migration & Schema Integrity
- `test_migration_007_partial_unique_index_exists`: Verifies partial unique index `uq_notifications_recipient_event_key` exists on `notifications` with predicate `(event_key IS NOT NULL)`.
- `test_migration_007_check_constraint_empty_event_key`: Verifies check constraint `ck_notifications_event_key_not_empty` rejects empty string `event_key`.
- `test_migration_007_check_constraint_whitespace_event_key`: Verifies check constraint rejects whitespace-only `event_key`.
- `test_migration_007_null_event_key_allows_duplicates`: Verifies notifications with `event_key=None` can be inserted multiple times for the same recipient.
- `test_migration_007_duplicate_event_key_rejected`: Verifies raw database insert of duplicate `(recipient_id, event_key)` violates unique index.

#### Notification Service Idempotency & Concurrency
- `test_create_notifications_idempotent_on_conflict`: Verifies `create_notifications` uses `ON CONFLICT (recipient_id, event_key) WHERE event_key IS NOT NULL DO NOTHING` without errors.
- `test_create_notifications_deduplicates_recipients`: Verifies passing duplicate recipient IDs schedules only 1 row per unique user.
- `test_create_notifications_empty_recipients`: Verifies empty recipient collection returns 0 scheduled rows without executing database queries.
- `test_create_notifications_empty_or_whitespace_event_key_raises`: Verifies empty or whitespace-only `event_key` raises `ValueError` at service layer.
- `test_notification_transaction_rollback_atomicity`: Verifies notifications emitted during a business transaction revert completely if outer transaction rolls back.

#### Complaint Lifecycle Event Integration
- `test_complaint_submitted_notification`: Verifies citizen receives confirmation notification with complaint tracking number upon creation.
- `test_complaint_submitted_idempotent`: Verifies repeated calls to `notify_complaint_submitted` do not produce duplicate notifications.
- `test_transition_under_review_notifies_owner`: Verifies transition to `UNDER_REVIEW` notifies owner; admin actor excluded.
- `test_transition_under_review_notifies_followers_if_public`: Verifies followers receive notifications on `UNDER_REVIEW` only if complaint is public.
- `test_transition_on_hold_notifies_owner_and_worker`: Verifies transition to `ON_HOLD` notifies owner and assigned worker.
- `test_transition_resolved_notifies_owner`: Verifies worker marking resolved notifies owner with `RESOLUTION_SUBMITTED`; worker excluded.
- `test_transition_closed_notifies_worker`: Verifies citizen confirming resolution notifies assigned worker; citizen excluded.
- `test_transition_reopened_notifies_worker`: Verifies citizen reopening complaint notifies assigned worker; citizen excluded.
- `test_transition_rejected_notifies_owner_only`: Verifies `REJECTED` notifies owner only; zero notifications sent to followers; internal remarks not leaked.
- `test_transition_duplicate_notifies_owner_only`: Verifies `DUPLICATE` notifies owner only; zero notifications sent to followers; internal remarks not leaked.

#### Worker Assignment & Milestone Events
- `test_assignment_dispatched_notifies_worker_and_owner`: Verifies dispatch notifies worker (`ASSIGNMENT`) and owner (`ASSIGNMENT`); admin actor excluded.
- `test_assignment_dispatched_notifies_public_followers`: Verifies assignment dispatch notifies public followers when complaint is public.
- `test_worker_activity_accepted_notifies_owner`: Verifies worker acceptance notifies owner; worker excluded.
- `test_worker_activity_started_notifies_owner_and_followers`: Verifies work start notifies owner and public followers.
- `test_worker_activity_progress_notifies_owner_and_followers`: Verifies progress update milestone notifies owner and public followers.
- `test_assignment_reassigned_notifies_new_worker_old_worker_owner`: Verifies reassignment notifies replacement worker, previous worker, and owner; admin excluded.

#### SLA Escalation Notifications
- `test_sla_response_warning_level_1`: Verifies Response SLA Level 1 warning (75%) dispatches notification with cycle-aware event key.
- `test_sla_response_breach_level_2`: Verifies Response SLA Level 2 breach (100%) dispatches breach notification.
- `test_sla_resolution_warning_and_breaches`: Verifies Resolution SLA Level 1 (75%), Level 2 (100%), and Level 3 (150%) generate distinct notifications.
- `test_sla_escalation_only_on_increase`: Verifies evaluating SLA when `new_level <= prev_level` generates zero notifications.
- `test_sla_escalation_idempotent`: Verifies repeated evaluation at same escalation level does not duplicate notifications.
- `test_sla_escalation_never_broadcast_to_followers`: Verifies SLA escalation notifications are delivered strictly to owner and worker, never followers.
- `test_sla_cycle_aware_event_keys_on_reopening`: Verifies reopening increments cycle number, generating distinct cycle 2 SLA escalation notifications.

#### Follower Privacy Boundaries & Content Redaction
- `test_private_complaint_zero_follower_notifications`: Verifies private complaint (`is_public=False`) never sends notifications to followers.
- `test_notification_content_no_pii_no_coordinates_no_remarks`: Verifies notification titles and bodies contain zero coordinates, PII, or internal remarks.
- `test_actor_exclusion_worker_own_action`: Verifies worker logging progress does not receive an echo notification.
- `test_recipient_deduplication_owner_is_follower`: Verifies owner registered as follower receives strictly 1 notification.

#### Authenticated REST API & IDOR Security
- `test_api_list_notifications_paginated`: Verifies `GET /api/v1/notifications` returns paginated list of current user's notifications.
- `test_api_list_notifications_unread_only`: Verifies `GET /api/v1/notifications?unread_only=true` returns strictly unread notifications.
- `test_api_unread_count`: Verifies `GET /api/v1/notifications/unread-count` returns accurate unread badge count.
- `test_api_mark_notification_as_read`: Verifies `PATCH /api/v1/notifications/{id}/read` marks notification read and sets `read_at`.
- `test_api_mark_notification_as_read_idor_defense`: Verifies marking another user's notification as read returns 404 EntityNotFoundError.
- `test_api_mark_notification_as_read_non_existent`: Verifies non-existent UUID returns 404 EntityNotFoundError.
- `test_api_mark_all_read`: Verifies `POST /api/v1/notifications/read-all` marks all unread notifications read for current user.
- `test_api_route_ordering_no_uuid_collision`: Verifies fixed routes `/unread-count` and `/read-all` do not collide with UUID path parameter.
- `test_api_unauthenticated_forbidden`: Verifies unauthenticated requests return 401 Unauthorized.

#### Phase 6.4.1 Audit & Verification Tests
- `test_transaction_atomicity_complaint_and_notification`: Verifies complaint submission and initial notification are persisted atomically in the same database transaction.
- `test_transaction_rollback_business_event_reverts_notification`: Verifies that rolling back a nested business event transaction reverts both the business update and its dispatched notification.
- `test_notification_helper_never_independently_commits`: Verifies notification creation and dispatch helpers never independently commit the caller's transaction.
- `test_notification_failure_aborts_business_transaction`: Verifies that a notification failure raises a ValueError before commit and the caller's savepoint is rolled back cleanly.
- `test_concurrent_idempotency_multithreaded_sessions`: Verifies concurrent idempotency using 5 simultaneous threads with independent SQLAlchemy sessions and connections inserting identical `(recipient_id, event_key)` without constraint violations.
- `test_concurrent_different_recipients_same_event_key`: Verifies different recipients can independently receive the identical logical `event_key`.
- `test_partial_unique_index_used_by_postgres`: Verifies PostgreSQL catalog index predicate `WHERE (event_key IS NOT NULL)`, check constraint `ck_notifications_event_key_not_empty`, and confirms PostgreSQL rejects `ON CONFLICT` without the matching partial predicate (42P10).
- `test_sla_admin_read_without_escalation_generates_zero_notifications`: Verifies evaluating SLA or viewing SLA details without persisted escalation level increases generates zero notifications.
- `test_sla_terminated_complaint_receives_zero_resolution_escalations`: Verifies complaints terminated via `REJECTED` or `DUPLICATE` never evaluate resolution SLA or dispatch resolution escalation notifications.
- `test_sla_event_key_structure`: Verifies strict compliance of SLA event keys with format `sla:{complaint_id}:cycle:{sla_cycle_number}:{clock_type}:level:{level}`.
- `test_reassignment_old_worker_receives_only_reassignment_notification`: Verifies reassigned worker receives strictly `ASSIGNMENT_REASSIGNED` and receives zero subsequent progress milestone notifications.
- `test_notification_payload_redaction_comprehensive`: Verifies complete redaction of coordinates, street addresses, citizen emails, internal remarks, and progress descriptions across all follower notifications.
- `test_api_cross_user_isolation`: Verifies citizen A cannot view or mark citizen B's notifications read (IDOR defense returns HTTP 404).
- `test_api_mark_read_idempotent`: Verifies marking an already-read notification as read returns HTTP 200 and preserves original `read_at` timestamp.
- `test_api_mark_all_read_isolation`: Verifies batch read by citizen A marks strictly citizen A's notifications without mutating citizen B's notifications.
- `test_api_idor_cross_role_access`: Verifies cross-role IDOR defense across Citizen, Field Worker, and Administrator accounts.

---

### Phase 6.5 Test Specifications (`tests/test_phase6_5_final_audit.py`)

#### Specific Verification A — Notification Conflict Handling & Partial Index Arbiter
- `test_notification_on_conflict_target_matches_partial_unique_index`: Verifies that `create_notifications` uses SQLAlchemy `ON CONFLICT` targeting `index_elements=["recipient_id", "event_key"]` with `index_where=text("event_key IS NOT NULL")`, exactly matching PostgreSQL index `uq_notifications_recipient_event_key` without raising 42P10 syntax errors.
- `test_notification_independent_recipients_same_event_key`: Verifies that distinct users can independently receive notifications sharing identical event keys.
- `test_notification_insertion_failure_prevents_partial_commit`: Verifies that notification insertion failure aborts before commit, preventing partial database state.

#### Specific Verification B — Outer Transaction Rollback Integrity
- `test_outer_transaction_rollback_reverts_business_event_and_notification`: Proves via an independent raw database connection and transaction (`BEGIN...ROLLBACK`) that an outer transaction rollback completely reverts both the business entity mutation and the dispatched notification row, without relying on nested savepoints.

#### Specific Verification C — Reassignment Timeline Integrity & Anti-Spoofing
- `test_reassignment_immediate_replacement_cutoff`: Verifies that the replacement assignment's `assigned_at` timestamp serves as the immutable operational cutoff for the prior worker's timeline visibility window.
- `test_reassignment_worker_cannot_forge_cutoff_with_injected_progress`: Verifies that a worker injecting synthetic progress notes with `"Reassigned to ..."` cannot fabricate or manipulate the timeline cutoff boundary, as the service requires an actual replacement assignment.

#### Specific Verification D — Public Unpublish Request History
- `test_unpublish_audit_fields_immutable_during_unpublish_state`: Verifies that complaint-level unpublish audit fields (`unpublish_requested_at`, `unpublish_requested_by_id`, `unpublish_reason`) preserve the initial citizen audit request and are not overwritten by repeated requests.
- `test_unpublish_requires_explicit_admin_moderation_to_republish`: Verifies that citizens cannot republish unpublished complaints; publication strictly requires administrator moderation.

#### Security & Privacy Audit Verification
- `test_security_citizen_cannot_access_other_citizen_complaint_timeline`: Verifies cross-citizen timeline IDOR defense returns HTTP 403.
- `test_security_worker_cannot_access_unassigned_complaint_timeline`: Verifies field worker attempting to view unassigned complaint timeline returns HTTP 403.
- `test_security_public_response_zero_leakage_all_endpoints`: Verifies absolute zero-leakage across all public feed endpoints (no PII, no coordinates, no raw citizen text, no internal remarks).
- `test_security_inactive_user_token_blocked`: Verifies that deactivated users cannot authenticate or access protected endpoints (HTTP 401).
- `test_security_cross_user_notification_idor_defense`: Verifies cross-user notification IDOR defense returns HTTP 404.

#### SLA Dual Clocks & Lifecycle Verification
- `test_sla_dual_clocks_complete_independence`: Verifies that response clock completion does not halt or interfere with independent resolution clock progression.
- `test_sla_on_hold_pause_accounting_dual_clocks`: Verifies that placing a complaint on hold pauses SLA clocks without mutating accumulated pause durations in the database during active hold.
- `test_sla_reopened_complaint_new_cycle_and_immutable_history`: Verifies that reopening a complaint snapshots cycle 1 to immutable history and advances to `sla_cycle_number = 2`.
- `test_sla_warning_and_breach_type_classification`: Verifies strict enum classification: Level 1 produces `SLA_WARNING`, Level 2/3 produces `SLA_BREACH`.

#### Performance & Query Optimization Verification
- `test_perf_dashboard_single_query_aggregation`: Verifies citizen dashboard metrics execute via conditional aggregation in a single query.
- `test_perf_timeline_joinedloads_worker_user_and_department`: Verifies that complaint timeline queries eager load `Worker.user` and `Worker.department` via `joinedload`, eliminating secondary lazy queries.
- `test_perf_notification_inbox_bounded_and_indexed`: Verifies that notification inbox pagination strictly caps page size at 100, enforces deterministic sorting, and queries use indexed filters.

---

### Phase 6.5.1 Test Specifications (`tests/test_phase6_5_1_reconciliation.py`)

#### Public Feed Privacy & Coarse-Location Verification
- `test_public_feed_list_contains_zero_pincode_or_precise_location`: Verifies that `GET /api/v1/public/complaints` serialized JSON response contains strictly the 9 approved allowlisted fields (`id`, `complaint_number`, `category_name`, `status`, `created_at`, `public_title`, `public_description`, `ward_or_district`, `city`) and proves `pincode`, exact coordinates, street address, landmark, and citizen PII are 100% absent.
- `test_public_feed_detail_contains_zero_pincode_or_precise_location`: Verifies that `GET /api/v1/public/complaints/{id}` serialized JSON response contains strictly the 9 approved allowlisted fields and confirms zero leakage of `pincode` or precise location.

#### Actual Registered Route Inventory
- `test_actual_registered_routes_match_api_inventory`: Verifies that registered route paths in the FastAPI application match authoritative paths (`/api/v1/citizens/me/dashboard`, `/api/v1/public/complaints`, `/api/v1/complaints/{complaint_id}/transitions`, etc.) and proves earlier report narrative inaccuracies do NOT exist.

#### Authorization & Boundaries
- `test_public_and_private_complaint_access_boundaries`: Verifies private complaints return 404 on unauthenticated public routes, return 200 to owner citizen, and return 403 to non-owner citizens.
- `test_role_based_authorization_boundaries`: Verifies RBAC cross-role boundaries: citizens cannot access worker queues (403) or admin SLA routes (403); workers cannot access citizen dashboards (403).

#### Model Fields & Database Reconciliation
- `test_model_fields_and_database_schema_consistency`: Verifies that `Assignment.accepted_at` exists (not `acknowledged_at`), `ComplaintFollower.followed_at` exists (not `created_at`), `AssignmentProgress.description` exists (not `notes`), and `Complaint.moderated_at` exists (not `published_at`).
- `test_alembic_migration_chain_integrity`: Verifies that the database `alembic_version` is `b7c8d9e0f1a2` matching the 7-migration linear chain.

---

1. **Test files** are named `test_<domain>.py`.
2. **Test classes** group related tests: `class TestModelMetadata`, `class TestDatabaseSchemaInspection`.
3. **Isolation**: Database tests run against `civicpulse_test` inside transaction rollbacks so no test data persists.
4. **No production data destruction**: Tests never run against the `civicpulse` development database.
5. **No mock data in place of database functionality**: Actual PostgreSQL constraints and SQL queries are exercised.

---

## Coverage

*Detailed line-by-line coverage reporting will be configured in Phase 13 (Security Hardening & Testing).*
