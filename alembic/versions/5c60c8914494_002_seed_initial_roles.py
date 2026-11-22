"""002_seed_initial_roles

Revision ID: 5c60c8914494
Revises: dc808166f213
Create Date: 2026-11-19 06:44:23.000000

Seeds the three mandatory application authorization roles:
- CITIZEN
- ADMINISTRATOR
- FIELD_WORKER
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c60c8914494'
down_revision: Union[str, Sequence[str], None] = 'dc808166f213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Idempotently seed the three core application roles."""
    roles_table = sa.table(
        'roles',
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('is_active', sa.Boolean),
    )

    op.execute(
        """
        INSERT INTO roles (name, description, is_active, created_at, updated_at)
        VALUES 
            ('CITIZEN', 'Public citizens reporting and tracking issues', true, now(), now()),
            ('ADMINISTRATOR', 'System administrators managing complaints and workers', true, now(), now()),
            ('FIELD_WORKER', 'Field workers assigned to investigate and resolve issues', true, now(), now())
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    """Remove the seeded application roles if no users depend on them."""
    op.execute(
        """
        DELETE FROM roles 
        WHERE name IN ('CITIZEN', 'ADMINISTRATOR', 'FIELD_WORKER');
        """
    )
