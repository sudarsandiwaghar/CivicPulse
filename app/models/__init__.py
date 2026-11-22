"""
CivicPulse Models Package

Central model registry for SQLAlchemy ORM models.
All models are imported here so that:
    1. Base.metadata collects all table definitions.
    2. Alembic's env.py can discover all models via target_metadata = Base.metadata.
    3. Other packages can cleanly import models from app.models.

Models exported (13 core tables):
    - Role                    (table: roles)
    - User                    (table: users)
    - Department              (table: departments)
    - Category                (table: categories)
    - Worker                  (table: workers)
    - Location                (table: locations)
    - Complaint               (table: complaints)
    - Assignment              (table: assignments)
    - Attachment              (table: attachments)
    - ComplaintStatusHistory  (table: complaint_status_history)
    - Notification            (table: notifications)
    - Feedback                (table: feedback)
    - AIAssessment            (table: ai_assessments)
"""

from app.models.ai_assessment import AIAssessment
from app.models.assignment import Assignment
from app.models.assignment_progress import AssignmentProgress
from app.models.attachment import Attachment
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_follower import ComplaintFollower
from app.models.department import Department
from app.models.feedback import Feedback
from app.models.location import Location
from app.models.notification import Notification
from app.models.role import Role
from app.models.sla_policy import SLAPolicy
from app.models.complaint_sla_history import ComplaintSLAHistory
from app.models.status_history import ComplaintStatusHistory
from app.models.user import User
from app.models.worker import Worker

__all__ = [
    "Role",
    "User",
    "Department",
    "Category",
    "Worker",
    "Location",
    "Complaint",
    "ComplaintFollower",
    "Assignment",
    "AssignmentProgress",
    "Attachment",
    "ComplaintStatusHistory",
    "Notification",
    "Feedback",
    "AIAssessment",
    "SLAPolicy",
    "ComplaintSLAHistory",
]
