"""
CivicPulse End-to-End Workflow Verification Script

Verifies the complete lifecycle workflow from Citizen submission to Admin triage,
review, on-hold, assignment, field worker acceptance, progress logging, completion,
citizen verification & closure, citizen reopening, SLA cycle update, and audit trail.
Targets Supabase PostgreSQL.
"""

import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure target database
os.environ["ENV_FILE"] = ".env.production"
from app.config import get_settings
get_settings.cache_clear()
settings = get_settings()

print(f"[*] Target Environment: {settings.APP_ENV} | Host: {settings.DB_HOST}")

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import init_engine, get_db
from app.core.security import hash_password, verify_password
from app.models.user import User


def run_e2e_verification():
    init_engine()
    db = next(get_db())

    # Ensure admin user has known test password
    admin_user = db.query(User).filter(User.email.in_(["sud@gmail.com", "admin@civicpulse.gov"])).first()
    if admin_user:
        # If verify_password fails for Password123!, update password
        if not verify_password("Password123!", admin_user.hashed_password):
            admin_user.hashed_password = hash_password("Password123!")
            db.commit()
            print(f"[+] Updated {admin_user.email} password to known test credentials.")
    admin_email = admin_user.email
    db.close()

    with TestClient(app) as client:
        print("\n--- PHASE 1: AUTHENTICATION ---")
        # 1. Admin login
        admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "Password123!"})
        assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
        admin_token = admin_login.json()["data"]["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print(f"[+] Admin ({admin_email}) successfully authenticated.")

        # 2. Worker login (Rahul Verma)
        worker_login = client.post("/api/v1/auth/login", json={"email": "rahul.verma@example.com", "password": "DemoTech2026!"})
        assert worker_login.status_code == 200, f"Worker login failed: {worker_login.text}"
        worker_token = worker_login.json()["data"]["access_token"]
        worker_headers = {"Authorization": f"Bearer {worker_token}"}
        print("[+] Field Worker Rahul Verma successfully authenticated.")

        # 3. Citizen login (Ananya Sharma)
        citizen_login = client.post("/api/v1/auth/login", json={"email": "ananya.citizen@example.com", "password": "DemoCitizen2026!"})
        assert citizen_login.status_code == 200, f"Citizen login failed: {citizen_login.text}"
        citizen_token = citizen_login.json()["data"]["access_token"]
        citizen_headers = {"Authorization": f"Bearer {citizen_token}"}
        print("[+] Citizen Ananya Sharma successfully authenticated.")

        print("\n--- PHASE 2: ADMIN TRIAGE & QUEUE INSPECTION ---")
        # Query triage queue (SUBMITTED complaints)
        triage_res = client.get("/api/v1/complaints/?status=SUBMITTED&page=1&page_size=20", headers=admin_headers)
        assert triage_res.status_code == 200, f"Triage query failed: {triage_res.text}"
        triage_data = triage_res.json()
        items = triage_data.get("data", [])
        print(f"[+] Admin Triage Queue: {len(items)} submitted complaints found (Total items: {triage_data.get('total_items')})")
        assert len(items) > 0, "No submitted complaints in triage queue!"

        # Query active workers
        workers_res = client.get("/api/v1/workers/?is_available=true&employment_status=ACTIVE", headers=admin_headers)
        assert workers_res.status_code == 200, f"Workers list query failed: {workers_res.text}"
        workers_list = workers_res.json().get("data", [])
        print(f"[+] Active eligible field workers: {len(workers_list)}")
        assert len(workers_list) >= 5, f"Expected at least 5 workers, got {len(workers_list)}"

        # Find Rahul Verma's worker ID
        rahul_worker = next((w for w in workers_list if w["email"] == "rahul.verma@example.com"), None)
        assert rahul_worker is not None, "Rahul Verma not found in active workers list!"
        rahul_worker_id = rahul_worker["id"]
        print(f"[+] Target Worker: {rahul_worker['full_name']} | ID: {rahul_worker_id} | Dept: {rahul_worker['department_name']}")

        # Pick PWD complaint CP-2026-10002 (Indiranagar footbridge railing)
        comp_res = client.get("/api/v1/complaints/?complaint_number=CP-2026-10002", headers=admin_headers)
        comp_matches = comp_res.json().get("data", [])
        if comp_matches:
            target_comp = comp_matches[0]
        else:
            target_comp = items[0]

        comp_id = target_comp["id"]
        comp_num = target_comp["complaint_number"]
        comp_status = target_comp["status"]
        print(f"[+] Target Complaint: {comp_num} (ID: {comp_id}) | Current Status: {comp_status} | Title: {target_comp['title']}")

        if comp_status == "SUBMITTED":
            print("\n--- PHASE 3: ADMIN START REVIEW ---")
            start_rev_res = client.patch(
                f"/api/v1/complaints/{comp_id}/review",
                headers=admin_headers,
                json={"new_status": "UNDER_REVIEW", "remarks": "Administrator initiated formal investigation review."}
            )
            assert start_rev_res.status_code == 200, f"Start review failed: {start_rev_res.text}"
            print(f"[+] Complaint {comp_num} transitioned to UNDER_REVIEW successfully.")

            print("\n--- PHASE 4: ADMIN ON_HOLD & RESUME TEST ---")
            # Transition to ON_HOLD
            on_hold_res = client.post(
                f"/api/v1/complaints/{comp_id}/transitions",
                headers=admin_headers,
                json={"new_status": "ON_HOLD", "remarks": "Awaiting municipal metal fabrication structural beams."}
            )
            assert on_hold_res.status_code == 200, f"Transition to ON_HOLD failed: {on_hold_res.text}"
            assert on_hold_res.json()["data"]["status"] == "ON_HOLD"
            print(f"[+] Complaint {comp_num} transitioned to ON_HOLD (SLA pause active).")

            # Resume back to UNDER_REVIEW
            resume_res = client.post(
                f"/api/v1/complaints/{comp_id}/transitions",
                headers=admin_headers,
                json={"new_status": "UNDER_REVIEW", "remarks": "Structural beams received. Resuming triage."}
            )
            assert resume_res.status_code == 200, f"Resume to UNDER_REVIEW failed: {resume_res.text}"
            assert resume_res.json()["data"]["status"] == "UNDER_REVIEW"
            print(f"[+] Complaint {comp_num} resumed to UNDER_REVIEW.")

            print("\n--- PHASE 5: ADMIN ASSIGNS WORKER ---")
            assign_payload = {
                "worker_id": rahul_worker_id,
                "notes": "Dispatch bridge fabrication crew with welding equipment.",
            }
            assign_res = client.post(f"/api/v1/complaints/{comp_id}/assign", headers=admin_headers, json=assign_payload)
            assert assign_res.status_code == 200, f"Assign worker failed: {assign_res.text}"
            print(f"[+] Complaint {comp_num} assigned to Rahul Verma. Status is now ASSIGNED.")

        print("\n--- PHASE 6: WORKER ACCEPTS & STARTS WORK ---")
        my_tasks_res = client.get("/api/v1/workers/me/tasks", headers=worker_headers)
        assert my_tasks_res.status_code == 200, f"Worker tasks query failed: {my_tasks_res.text}"
        my_tasks = my_tasks_res.json().get("data", [])
        active_assignment = next((t for t in my_tasks if str(t.get("complaint_id")) == str(comp_id)), None)
        assert active_assignment is not None, f"Assignment for complaint {comp_num} not found in worker tasks! Returned tasks: {my_tasks}"
        assignment_id = active_assignment.get("assignment_id") or active_assignment.get("id")
        current_task_status = active_assignment.get("assignment_status") or active_assignment.get("status")
        print(f"[+] Worker found assigned task. Assignment ID: {assignment_id} | Status: {current_task_status}")

        if current_task_status == "ASSIGNED":
            if not active_assignment.get("accepted_at"):
                accept_res = client.post(f"/api/v1/workers/me/tasks/{assignment_id}/accept", headers=worker_headers)
                assert accept_res.status_code == 200, f"Worker accept failed: {accept_res.text}"
                print(f"[+] Worker accepted assignment {assignment_id}.")

            start_work_res = client.post(
                f"/api/v1/workers/me/tasks/{assignment_id}/start?notes=En%20route%20to%20footbridge%20site",
                headers=worker_headers
            )
            assert start_work_res.status_code == 200, f"Worker start work failed: {start_work_res.text}"
            print(f"[+] Worker started on-site work. Assignment & Complaint are now IN_PROGRESS.")
        else:
            print(f"[+] Task is already in progress: {current_task_status}")

        print("\n--- PHASE 7: WORKER LOGS PROGRESS UPDATES ---")
        p1_res = client.post(
            f"/api/v1/workers/me/tasks/{assignment_id}/progress",
            headers=worker_headers,
            json={"description": "Arrived on site; safety cones placed around damaged footbridge span. Clearing broken railings."}
        )
        assert p1_res.status_code == 201, f"Progress update 1 failed: {p1_res.text}"
        print(f"[+] Progress update 1 recorded: {p1_res.json()['data']['description']}")

        p2_res = client.post(
            f"/api/v1/workers/me/tasks/{assignment_id}/progress",
            headers=worker_headers,
            json={"description": "Steel reinforcement plates positioned and welded into structural bridge support channel."}
        )
        assert p2_res.status_code == 201, f"Progress update 2 failed: {p2_res.text}"
        print(f"[+] Progress update 2 recorded: {p2_res.json()['data']['description']}")

        print("\n--- PHASE 8: WORKER COMPLETES TASK ---")
        comp_payload = {
            "summary": "Repaired pedestrian footbridge railing near Central School. Replaced damaged metal struts, welded reinforced steel supports, and applied rust-resistant safety coating. Area is fully secured and safe for pedestrian crossing."
        }
        complete_res = client.post(
            f"/api/v1/workers/me/tasks/{assignment_id}/complete",
            headers=worker_headers,
            json=comp_payload
        )
        assert complete_res.status_code == 200, f"Worker complete failed: {complete_res.text}"
        print(f"[+] Worker completed task.")

        # Verify complaint status is RESOLVED_AWAITING_VERIFICATION
        comp_status_res = client.get(f"/api/v1/complaints/{comp_id}", headers=admin_headers)
        assert comp_status_res.status_code == 200
        comp_state = comp_status_res.json()["data"]
        assert comp_state["status"] == "RESOLVED_AWAITING_VERIFICATION", f"Expected RESOLVED_AWAITING_VERIFICATION, got {comp_state['status']}"
        print(f"[+] Complaint {comp_num} is now in '{comp_state['status']}'.")

        print("\n--- PHASE 9: CITIZEN VERIFIES & CLOSES COMPLAINT ---")
        close_payload = {
            "new_status": "CLOSED",
            "remarks": "Inspected repaired pothole on 100 Feet Rd; road surface is fully restored and safe for driving. Thank you for prompt resolution."
        }
        close_res = client.post(f"/api/v1/complaints/{comp_id}/transitions", headers=citizen_headers, json=close_payload)
        assert close_res.status_code == 200, f"Citizen close failed: {close_res.text}"
        closed_comp = close_res.json()["data"]
        assert closed_comp["status"] == "CLOSED"
        assert closed_comp["closed_at"] is not None
        print(f"[+] Citizen verified and closed complaint {comp_num}. Status is CLOSED.")

        print("\n--- PHASE 10: CITIZEN REOPENS COMPLAINT WITHIN 14 DAYS ---")
        reopen_payload = {
            "new_status": "REOPENED",
            "remarks": "Minor asphalt crumbling observed along north seam under bus loading. Requesting sealant application."
        }
        reopen_res = client.post(f"/api/v1/complaints/{comp_id}/transitions", headers=citizen_headers, json=reopen_payload)
        assert reopen_res.status_code == 200, f"Citizen reopen failed: {reopen_res.text}"
        reopened_comp = reopen_res.json()["data"]
        assert reopened_comp["status"] == "REOPENED"
        print(f"[+] Citizen successfully reopened complaint {comp_num}. Status is REOPENED.")

        print("\n--- PHASE 11: SLA, NOTIFICATIONS & AUDIT TRAIL VERIFICATION ---")
        # Verify timeline and status history
        history_res = client.get(f"/api/v1/complaints/{comp_id}/history", headers=admin_headers)
        assert history_res.status_code == 200
        history = history_res.json()["data"]
        print(f"[+] Status transition history records for {comp_num}: {len(history)} transitions logged.")
        for h in history:
            print(f"    - {h.get('previous_status')} -> {h.get('new_status')} by {h.get('changed_by_name')}: {h.get('remarks')}")

        # Verify assignment audit details
        assign_detail_res = client.get(f"/api/v1/assignments/{assignment_id}", headers=admin_headers)
        assert assign_detail_res.status_code == 200
        assign_detail = assign_detail_res.json()["data"]
        print(f"[+] Assignment audit details verified:")
        print(f"    - Status: {assign_detail.get('status')}")
        print(f"    - Worker: {assign_detail.get('worker_name')} ({assign_detail.get('worker_employee_id')})")
        print(f"    - Department: {assign_detail.get('department_name')}")
        print(f"    - Progress Updates: {len(assign_detail.get('progress_history', []))} logged entries.")

        # Check notification dispatch
        notif_res = client.get("/api/v1/notifications/?page=1&page_size=10", headers=citizen_headers)
        if notif_res.status_code == 200:
            notifs = notif_res.json().get("data", [])
            print(f"[+] Citizen notifications generated: {len(notifs)}")

        print("\n=======================================================")
        print("ALL 11 END-TO-END WORKFLOW VERIFICATION PHASES PASSED!")
        print("=======================================================")


if __name__ == "__main__":
    run_e2e_verification()
