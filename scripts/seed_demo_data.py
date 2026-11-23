"""
CivicPulse Demo Data Seeder

Seeds realistic demonstration field workers and civic complaints in the target database.
Supports both local and hosted Supabase environments.
Does not overwrite existing accounts or alter migration history.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings
from app.core.constants import PriorityLevel, UserRole
from app.core.security import hash_password
from app.db.session import get_db, init_engine
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.models.worker import Worker
from app.schemas.complaint import ComplaintCreateRequest, LocationCreate
from app.schemas.worker import WorkerCreateRequest
from app.services.complaint_service import create_complaint
from app.services.worker_service import create_worker


DEMO_WORKERS = [
    {
        "full_name": "Rahul Verma",
        "email": "rahul.verma@example.com",
        "dept_code": "PWD",
        "employee_id": "TECH-PWD-001",
        "designation": "Senior Road Maintenance Technician",
        "phone_number": "+91-9876500001",
        "password": "DemoTech2026!",
    },
    {
        "full_name": "Sneha Kulkarni",
        "email": "sneha.kulkarni@example.com",
        "dept_code": "ELECTRICAL",
        "employee_id": "TECH-EED-002",
        "designation": "Chief Electrical Lineman",
        "phone_number": "+91-9876500002",
        "password": "DemoTech2026!",
    },
    {
        "full_name": "Amit Patel",
        "email": "amit.patel@example.com",
        "dept_code": "WATER_SEWAGE",
        "employee_id": "TECH-WSD-003",
        "designation": "Water & Sewage Specialist",
        "phone_number": "+91-9876500003",
        "password": "DemoTech2026!",
    },
    {
        "full_name": "Priya Sharma",
        "email": "priya.sharma@example.com",
        "dept_code": "WASTE_MGMT",
        "employee_id": "TECH-SWM-004",
        "designation": "Waste Operations Officer",
        "phone_number": "+91-9876500004",
        "password": "DemoTech2026!",
    },
    {
        "full_name": "Vikram Singh",
        "email": "vikram.singh@example.com",
        "dept_code": "HEALTH_SANITATION",
        "employee_id": "TECH-HSD-005",
        "designation": "Public Health Officer",
        "phone_number": "+91-9876500005",
        "password": "DemoTech2026!",
    },
]

DEMO_CITIZENS = [
    {
        "email": "ananya.citizen@example.com",
        "full_name": "Ananya Sharma",
        "phone_number": "+91-9876500101",
        "password": "DemoCitizen2026!",
    },
    {
        "email": "rohit.citizen@example.com",
        "full_name": "Rohit Verma",
        "phone_number": "+91-9876500102",
        "password": "DemoCitizen2026!",
    },
]

DEMO_COMPLAINTS = [
    {
        "title": "[DEMO] Deep hazardous pothole near Indiranagar Metro pillar 42",
        "description": "Deep crater of approx 2 feet diameter on main carriageway causing severe bike skidding risks during peak traffic hours.",
        "category_name": "Roads and Potholes",
        "priority": PriorityLevel.HIGH,
        "latitude": 12.9783,
        "longitude": 77.6408,
        "address_line": "100 Feet Rd, Opposite Metro Pillar 42",
        "area_name": "Indiranagar",
        "city": "Bengaluru",
        "pincode": "560038",
        "landmark": "Near Indiranagar Metro Station",
    },
    {
        "title": "[DEMO] Broken pedestrian footbridge railing near Central School",
        "description": "Metal safety railing broken and dangling over stormwater drain, severe hazard for school children crossing daily.",
        "category_name": "Public Infrastructure",
        "priority": PriorityLevel.CRITICAL,
        "latitude": 12.9719,
        "longitude": 77.6412,
        "address_line": "HAL 2nd Stage, Footbridge Cross",
        "area_name": "Indiranagar",
        "city": "Bengaluru",
        "pincode": "560038",
        "landmark": "Adjacent to Kendriya Vidyalaya Gate",
    },
    {
        "title": "[DEMO] Non-functional high-mast streetlights along Ring Road",
        "description": "Cluster of four high-intensity streetlights completely off for 3 consecutive nights causing dark blind spot on highway ramp.",
        "category_name": "Streetlights",
        "priority": PriorityLevel.MEDIUM,
        "latitude": 12.9625,
        "longitude": 77.6482,
        "address_line": "Outer Ring Road junction, Domlur Flyover Ramp",
        "area_name": "Domlur",
        "city": "Bengaluru",
        "pincode": "560071",
        "landmark": "Near Domlur Flyover Descent",
    },
    {
        "title": "[DEMO] Damaged junction electrical feeder pillar with exposed cables",
        "description": "Municipal feeder box panel door smashed open with live 415V cables exposed within reach of pedestrian footpath.",
        "category_name": "Streetlights",
        "priority": PriorityLevel.CRITICAL,
        "latitude": 12.9754,
        "longitude": 77.6066,
        "address_line": "Brigade Road 4th Cross",
        "area_name": "Shanthala Nagar",
        "city": "Bengaluru",
        "pincode": "560001",
        "landmark": "Opposite Commercial Complex",
    },
    {
        "title": "[DEMO] Major drinking water pipeline rupture on 80 Feet Road",
        "description": "300mm potable distribution main burst with significant clean water gushing onto the road causing localized flooding and pressure drop.",
        "category_name": "Water Supply",
        "priority": PriorityLevel.HIGH,
        "latitude": 12.9701,
        "longitude": 77.6205,
        "address_line": "80 Feet Road, 4th Block",
        "area_name": "Koramangala",
        "city": "Bengaluru",
        "pincode": "560034",
        "landmark": "Near Maharaja Signal",
    },
    {
        "title": "[DEMO] Low drinking water supply pressure in block B residential units",
        "description": "Supply pressure dropping below 0.5 bar during scheduled morning supply hours since last maintenance work.",
        "category_name": "Water Supply",
        "priority": PriorityLevel.LOW,
        "latitude": 12.9345,
        "longitude": 77.6101,
        "address_line": "5th Cross, Koramangala 1st Block",
        "area_name": "Koramangala",
        "city": "Bengaluru",
        "pincode": "560034",
        "landmark": "Near Wipro Park",
    },
    {
        "title": "[DEMO] Overflowing underground sewage manhole near commercial area",
        "description": "Untreated sewage backing up and overflowing onto commercial street with foul odor, contaminating access ways and posing health risks.",
        "category_name": "Drainage and Sewage",
        "priority": PriorityLevel.HIGH,
        "latitude": 12.9667,
        "longitude": 77.5912,
        "address_line": "Market Road, 2nd Cross",
        "area_name": "Richmond Town",
        "city": "Bengaluru",
        "pincode": "560025",
        "landmark": "Near Johnson Market",
    },
    {
        "title": "[DEMO] Uncollected municipal garbage accumulation at corner bin",
        "description": "Solid waste overflowing around secondary collection point for 48 hours attracting stray animals and blocking pavement.",
        "category_name": "Waste Management",
        "priority": PriorityLevel.MEDIUM,
        "latitude": 12.9810,
        "longitude": 77.5975,
        "address_line": "Cubbon Road Corner",
        "area_name": "Tasker Town",
        "city": "Bengaluru",
        "pincode": "560051",
        "landmark": "Opposite General Post Office",
    },
    {
        "title": "[DEMO] Illegal construction debris dumped on vacant civic plot",
        "description": "Approx two truckloads of concrete rubble dumped overnight obstructing pedestrian passage and drainage ditch.",
        "category_name": "Waste Management",
        "priority": PriorityLevel.LOW,
        "latitude": 12.9542,
        "longitude": 77.6011,
        "address_line": "Langford Road Lane 3",
        "area_name": "Langford Gardens",
        "city": "Bengaluru",
        "pincode": "560025",
        "landmark": "Near Hockey Stadium",
    },
    {
        "title": "[DEMO] Public sanitation facility hygiene breakdown at bus terminus",
        "description": "Community restroom facility non-functional due to clogged drainage lines and missing daily sanitization schedule.",
        "category_name": "Public Sanitation",
        "priority": PriorityLevel.MEDIUM,
        "latitude": 12.9760,
        "longitude": 77.5729,
        "address_line": "Gubbi Thotadappa Road",
        "area_name": "Majestic",
        "city": "Bengaluru",
        "pincode": "560009",
        "landmark": "Majestic Bus Station Concourse",
    },
]


def seed_demo_data(env_file: str = ".env.production"):
    os.environ["ENV_FILE"] = env_file
    get_settings.cache_clear()
    settings = get_settings()
    print(f"[*] Seeding target: {settings.APP_ENV} | Host: {settings.DB_HOST} | Port: {settings.DB_PORT}")

    init_engine()
    db = next(get_db())

    try:
        # 1. Resolve Roles
        citizen_role = db.query(Role).filter(Role.name == UserRole.CITIZEN.value).first()
        worker_role = db.query(Role).filter(Role.name == UserRole.FIELD_WORKER.value).first()
        admin_role = db.query(Role).filter(Role.name == UserRole.ADMINISTRATOR.value).first()

        if not citizen_role or not worker_role or not admin_role:
            raise RuntimeError("Database roles not found. Run migrations first.")

        # 2. Provision Demonstration Citizens
        created_citizens = []
        for c_data in DEMO_CITIZENS:
            existing_user = db.query(User).filter(User.email == c_data["email"]).first()
            if not existing_user:
                new_citizen = User(
                    email=c_data["email"],
                    hashed_password=hash_password(c_data["password"]),
                    full_name=c_data["full_name"],
                    phone_number=c_data["phone_number"],
                    role_id=citizen_role.id,
                    is_active=True,
                    is_verified=True,
                )
                db.add(new_citizen)
                db.commit()
                db.refresh(new_citizen)
                print(f"[+] Created citizen: {new_citizen.full_name} ({new_citizen.email})")
                created_citizens.append(new_citizen)
            else:
                print(f"[-] Citizen already exists: {existing_user.full_name} ({existing_user.email})")
                created_citizens.append(existing_user)

        # 3. Provision Demonstration Field Workers
        created_workers = []
        for w_data in DEMO_WORKERS:
            existing_worker_user = db.query(User).filter(User.email == w_data["email"]).first()
            dept = db.query(Department).filter(Department.code == w_data["dept_code"]).first()
            if not dept:
                raise RuntimeError(f"Department code '{w_data['dept_code']}' not found in database.")

            if not existing_worker_user:
                worker_req = WorkerCreateRequest(
                    email=w_data["email"],
                    password=w_data["password"],
                    full_name=w_data["full_name"],
                    department_id=dept.id,
                    employee_id=w_data["employee_id"],
                    designation=w_data["designation"],
                    phone_number=w_data["phone_number"],
                )
                worker = create_worker(db=db, data=worker_req)
                print(f"[+] Created worker: {worker.user.full_name} ({worker.employee_id}) in {dept.name}")
                created_workers.append(worker)
            else:
                worker = db.query(Worker).filter(Worker.user_id == existing_worker_user.id).first()
                print(f"[-] Worker already exists: {existing_worker_user.full_name} ({worker.employee_id})")
                created_workers.append(worker)

        # 4. Provision Demonstration Complaints
        categories = {c.name: c for c in db.query(Category).all()}
        primary_citizen = created_citizens[0]

        created_complaints = []
        for comp_data in DEMO_COMPLAINTS:
            existing_comp = db.query(Complaint).filter(Complaint.title == comp_data["title"]).first()
            cat = categories.get(comp_data["category_name"])
            if not cat:
                raise RuntimeError(f"Category '{comp_data['category_name']}' not found in database.")

            if not existing_comp:
                loc_create = LocationCreate(
                    latitude=comp_data["latitude"],
                    longitude=comp_data["longitude"],
                    address_line=comp_data["address_line"],
                    area_name=comp_data["area_name"],
                    city=comp_data["city"],
                    pincode=comp_data["pincode"],
                    landmark=comp_data["landmark"],
                )
                comp_req = ComplaintCreateRequest(
                    title=comp_data["title"],
                    description=comp_data["description"],
                    category_id=cat.id,
                    location=loc_create,
                )
                complaint = create_complaint(db=db, citizen=primary_citizen, data=comp_req)
                # Set target demonstration priority
                complaint.priority = comp_data["priority"]
                db.commit()
                db.refresh(complaint)
                print(f"[+] Filed complaint: {complaint.complaint_number} | Priority: {complaint.priority.value} | {complaint.title[:45]}...")
                created_complaints.append(complaint)
            else:
                print(f"[-] Complaint already exists: {existing_comp.complaint_number} | {existing_comp.title[:45]}...")
                created_complaints.append(existing_comp)

        print("\n==========================================")
        print("SEEDING SUMMARY")
        print("==========================================")
        print(f"Total Workers in DB: {db.query(Worker).count()}")
        print(f"Total Complaints in DB: {db.query(Complaint).count()}")
        print("Done successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    env_file = sys.argv[1] if len(sys.argv) > 1 else ".env.production"
    seed_demo_data(env_file=env_file)
