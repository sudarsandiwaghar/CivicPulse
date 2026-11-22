"""007_notification_event_keys

Revision ID: b7c8d9e0f1a2
Revises: a4b5c6d7e8f9
Create Date: 2026-11-20 16:30:00.000000

Adds event_key column, not-empty check constraint, and partial unique index on (recipient_id, event_key)
to notifications table for idempotent notification delivery and concurrency safety.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add event_key column to notifications (nullable to preserve legacy notifications)
    op.add_column(
        'notifications',
        sa.Column(
            'event_key',
            sa.String(length=255),
            nullable=True,
            comment='Unique event identifier for idempotent notification delivery',
        ),
    )

    # 2. Add check constraint ensuring non-null event_key is not empty or whitespace
    op.create_check_constraint(
        'ck_notifications_event_key_not_empty',
        'notifications',
        sa.text("event_key IS NULL OR length(trim(event_key)) > 0"),
    )

    # 3. Create PostgreSQL partial unique index on (recipient_id, event_key) WHERE event_key IS NOT NULL
    op.create_index(
        'uq_notifications_recipient_event_key',
        'notifications',
        ['recipient_id', 'event_key'],
        unique=True,
        postgresql_where=sa.text('event_key IS NOT NULL'),
    )


def downgrade() -> None:
    # 1. Drop partial unique index
    op.drop_index(
        'uq_notifications_recipient_event_key',
        table_name='notifications',
        postgresql_where=sa.text('event_key IS NOT NULL'),
    )

    # 2. Drop check constraint
    op.drop_constraint(
        'ck_notifications_event_key_not_empty',
        'notifications',
        type_='check',
    )

    # 3. Drop event_key column
    op.drop_column('notifications', 'event_key')
