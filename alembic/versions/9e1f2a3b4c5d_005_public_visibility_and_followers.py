"""005_public_visibility_and_followers

Revision ID: 9e1f2a3b4c5d
Revises: 8d2e4f6a1c3b
Create Date: 2026-11-19 19:35:00.000000

Adds public moderation and visibility fields to complaints, and creates
the complaint_followers table for citizen community following.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '9e1f2a3b4c5d'
down_revision: Union[str, Sequence[str], None] = '8d2e4f6a1c3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add public visibility and moderation fields to complaints
    op.add_column(
        'complaints',
        sa.Column(
            'is_public',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='Whether complaint is approved and published for public discovery',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'public_title',
            sa.String(length=200),
            nullable=True,
            comment='Administrator-sanitized and approved title for public display',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'public_description',
            sa.Text(),
            nullable=True,
            comment='Administrator-sanitized and approved description for public display',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'moderated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when administrator last published or moderated public content (UTC)',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'moderated_by_id',
            UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            comment='Foreign key referencing administrator who last moderated public visibility',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'unpublish_requested_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when citizen requested unpublishing (UTC)',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'unpublish_requested_by_id',
            UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            comment='Foreign key referencing user who requested unpublishing',
        )
    )
    op.add_column(
        'complaints',
        sa.Column(
            'unpublish_reason',
            sa.Text(),
            nullable=True,
            comment='Citizen explanation or notes for requesting unpublishing',
        )
    )

    # 2. Indexes on complaints for public queries and moderation auditing
    op.create_index('ix_complaints_is_public', 'complaints', ['is_public'])
    op.create_index('ix_complaints_moderated_by_id', 'complaints', ['moderated_by_id'])
    op.create_index('ix_complaints_unpublish_requested_by_id', 'complaints', ['unpublish_requested_by_id'])

    # 3. Create complaint_followers table
    op.create_table(
        'complaint_followers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, comment='Primary UUID identifier for follow record'),
        sa.Column('complaint_id', UUID(as_uuid=True), sa.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False),
        sa.Column('citizen_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('followed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='Timestamp when citizen followed the complaint (UTC)'),
        sa.UniqueConstraint('complaint_id', 'citizen_id', name='uq_complaint_follower_citizen'),
    )
    op.create_index('ix_complaint_followers_complaint_id', 'complaint_followers', ['complaint_id'])
    op.create_index('ix_complaint_followers_citizen_id', 'complaint_followers', ['citizen_id'])


def downgrade() -> None:
    # 1. Drop complaint_followers table and its indexes
    op.drop_table('complaint_followers')

    # 2. Drop indexes on complaints
    op.drop_index('ix_complaints_unpublish_requested_by_id', table_name='complaints')
    op.drop_index('ix_complaints_moderated_by_id', table_name='complaints')
    op.drop_index('ix_complaints_is_public', table_name='complaints')

    # 3. Drop added columns from complaints
    op.drop_column('complaints', 'unpublish_reason')
    op.drop_column('complaints', 'unpublish_requested_by_id')
    op.drop_column('complaints', 'unpublish_requested_at')
    op.drop_column('complaints', 'moderated_by_id')
    op.drop_column('complaints', 'moderated_at')
    op.drop_column('complaints', 'public_description')
    op.drop_column('complaints', 'public_title')
    op.drop_column('complaints', 'is_public')
