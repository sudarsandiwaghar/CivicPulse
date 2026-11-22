"""004_assignment_enhancements_and_progress

Revision ID: 8d2e4f6a1c3b
Revises: 7f3a8b2c4d1e
Create Date: 2026-11-19 13:30:00.000000

Adds accepted_at, started_at, and partial unique index on active assignments,
and creates the assignment_progress table for immutable work milestone tracking.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '8d2e4f6a1c3b'
down_revision: Union[str, Sequence[str], None] = '7f3a8b2c4d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add accepted_at and started_at to assignments table
    op.add_column(
        'assignments',
        sa.Column(
            'accepted_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when worker accepted the assignment (UTC)'
        )
    )
    op.add_column(
        'assignments',
        sa.Column(
            'started_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when worker initiated work (UTC)'
        )
    )

    # 2. Add partial unique index: maximum one active assignment (ASSIGNED or IN_PROGRESS) per complaint
    op.create_index(
        'uq_active_assignment_per_complaint',
        'assignments',
        ['complaint_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('ASSIGNED', 'IN_PROGRESS')")
    )

    # 3. Create assignment_progress table
    op.create_table(
        'assignment_progress',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, comment='Primary UUID identifier for progress record'),
        sa.Column('assignment_id', UUID(as_uuid=True), sa.ForeignKey('assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('worker_id', UUID(as_uuid=True), sa.ForeignKey('workers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, comment='Work progress notes or field observations'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='Timestamp when progress was recorded (UTC)'),
    )
    op.create_index('ix_assignment_progress_assignment_id', 'assignment_progress', ['assignment_id'])
    op.create_index('ix_assignment_progress_worker_id', 'assignment_progress', ['worker_id'])
    op.create_index('ix_assignment_progress_created_at', 'assignment_progress', ['assignment_id', 'created_at'])


def downgrade() -> None:
    # 1. Drop assignment_progress table and its indexes
    op.drop_table('assignment_progress')

    # 2. Drop partial unique index
    op.drop_index('uq_active_assignment_per_complaint', table_name='assignments')

    # 3. Drop added columns
    op.drop_column('assignments', 'started_at')
    op.drop_column('assignments', 'accepted_at')
