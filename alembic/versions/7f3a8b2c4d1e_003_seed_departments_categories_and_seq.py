"""003_seed_departments_categories_and_seq

Revision ID: 7f3a8b2c4d1e
Revises: 5c60c8914494
Create Date: 2026-11-19 07:40:00.000000

Creates the complaint_number_seq sequence and seeds initial civic departments and categories:
- Departments: PWD, ELECTRICAL, WATER_SEWAGE, WASTE_MGMT, HEALTH_SANITATION
- Categories: Roads and Potholes, Public Infrastructure, Streetlights, Water Supply,
              Drainage and Sewage, Waste Management, Public Sanitation
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
# revision identifiers, used by Alembic.
revision: str = '7f3a8b2c4d1e'
down_revision: Union[str, Sequence[str], None] = '5c60c8914494'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create complaint sequence and seed initial departments and categories."""
    # 1. Create complaint reference sequence starting at 10001
    op.execute(
        """
        CREATE SEQUENCE IF NOT EXISTS complaint_number_seq
        START WITH 10001
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
        """
    )

    # 2. Seed departments
    op.execute(
        """
        INSERT INTO departments (name, code, description, contact_email, contact_phone, is_active, created_at, updated_at)
        VALUES
            ('Public Works Department', 'PWD', 'Roads, bridges, footpaths, and civil infrastructure', 'pwd@civicpulse.org', '1800-111-001', true, now(), now()),
            ('Electrical & Lighting Department', 'ELECTRICAL', 'Streetlights, poles, and public electrical fixtures', 'electrical@civicpulse.org', '1800-111-002', true, now(), now()),
            ('Water Supply & Sewerage Board', 'WATER_SEWAGE', 'Water supply pipes, quality, drainage, and sewage networks', 'water@civicpulse.org', '1800-111-003', true, now(), now()),
            ('Solid Waste Management Department', 'WASTE_MGMT', 'Garbage collection, waste dumping, and street sanitation', 'waste@civicpulse.org', '1800-111-004', true, now(), now()),
            ('Public Health & Sanitation Department', 'HEALTH_SANITATION', 'Public hygiene, pest control, and public sanitation facilities', 'health@civicpulse.org', '1800-111-005', true, now(), now())
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # 3. Seed categories linked to departments
    op.execute(
        """
        INSERT INTO categories (department_id, name, description, is_active, created_at, updated_at)
        SELECT d.id, c.name, c.description, true, now(), now()
        FROM (
            VALUES
                ('PWD', 'Roads and Potholes', 'Issues related to damaged road surfaces, potholes, and broken dividers'),
                ('PWD', 'Public Infrastructure', 'Maintenance of public parks, footpaths, bridges, and government buildings'),
                ('ELECTRICAL', 'Streetlights', 'Non-functioning street lights, exposed wiring, or damaged lamp poles'),
                ('WATER_SEWAGE', 'Water Supply', 'Drinking water contamination, pipe bursts, low water pressure, or supply disruption'),
                ('WATER_SEWAGE', 'Drainage and Sewage', 'Overflowing gutters, clogged drains, manhole damage, and sewage leaks'),
                ('WASTE_MGMT', 'Waste Management', 'Uncollected household garbage, overflow of public dustbins, and illegal dumping'),
                ('HEALTH_SANITATION', 'Public Sanitation', 'Public toilet cleanliness, stagnating water pools, and vector breeding spots')
        ) AS c(dept_code, name, description)
        JOIN departments d ON d.code = c.dept_code
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    """Remove seeded categories, departments, and complaint sequence."""
    op.execute(
        """
        DELETE FROM categories
        WHERE name IN (
            'Roads and Potholes',
            'Public Infrastructure',
            'Streetlights',
            'Water Supply',
            'Drainage and Sewage',
            'Waste Management',
            'Public Sanitation'
        );
        """
    )
    op.execute(
        """
        DELETE FROM departments
        WHERE code IN ('PWD', 'ELECTRICAL', 'WATER_SEWAGE', 'WASTE_MGMT', 'HEALTH_SANITATION');
        """
    )
    op.execute(
        """
        DROP SEQUENCE IF EXISTS complaint_number_seq;
        """
    )