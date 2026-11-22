"""006_sla_management_and_escalation

Revision ID: a4b5c6d7e8f9
Revises: 9e1f2a3b4c5d
Create Date: 2026-11-19 22:45:00.000000

Adds SLA policies, dual-clock SLA tracking fields and check constraints to complaints,
append-only complaint_sla_history table, and database immutability trigger.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = '9e1f2a3b4c5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create sla_policies table
    op.create_table(
        'sla_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, comment='Primary UUID identifier for SLA policy'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='Descriptive name of SLA policy'),
        sa.Column('description', sa.Text(), nullable=True, comment='Policy scope and description notes'),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True, comment='Category dimension (nullable for fallback/priority policies)'),
        sa.Column('priority', sa.String(length=20), nullable=True, comment='Priority dimension (nullable for fallback/category policies)'),
        sa.Column('response_time_hours', sa.Integer(), nullable=False, comment='Target initial response time in hours (> 0)'),
        sa.Column('resolution_time_hours', sa.Integer(), nullable=False, comment='Target resolution time in hours (> 0)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='Whether policy is currently active for new resolutions'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('response_time_hours > 0', name='ck_sla_policies_response_time_hours'),
        sa.CheckConstraint('resolution_time_hours > 0', name='ck_sla_policies_resolution_time_hours'),
        sa.CheckConstraint("priority IS NULL OR priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name='ck_sla_policies_priority'),
    )

    # Indexes on sla_policies
    op.create_index('ix_sla_policies_category_id', 'sla_policies', ['category_id'])
    op.create_index('ix_sla_policies_priority', 'sla_policies', ['priority'])
    op.create_index('ix_sla_policies_is_active', 'sla_policies', ['is_active'])

    # Partial unique indexes for 4-tier deterministic precedence
    # 1. Category + Priority exact
    op.create_index(
        'uq_sla_policy_category_priority',
        'sla_policies',
        ['category_id', 'priority'],
        unique=True,
        postgresql_where=sa.text('category_id IS NOT NULL AND priority IS NOT NULL'),
    )
    # 2. Category only
    op.create_index(
        'uq_sla_policy_category_only',
        'sla_policies',
        ['category_id'],
        unique=True,
        postgresql_where=sa.text('category_id IS NOT NULL AND priority IS NULL'),
    )
    # 3. Priority only
    op.create_index(
        'uq_sla_policy_priority_only',
        'sla_policies',
        ['priority'],
        unique=True,
        postgresql_where=sa.text('category_id IS NULL AND priority IS NOT NULL'),
    )
    # 4. Global fallback (category IS NULL AND priority IS NULL)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_sla_policy_global ON sla_policies ((1))
        WHERE category_id IS NULL AND priority IS NULL
        """
    )

    # 2. Add SLA fields to complaints
    op.add_column(
        'complaints',
        sa.Column(
            'response_sla_policy_id',
            UUID(as_uuid=True),
            sa.ForeignKey('sla_policies.id', ondelete='SET NULL'),
            nullable=True,
            comment='SLA policy used for response clock target',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'response_deadline',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Target UTC deadline for initial response',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'responded_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when response clock completed (UTC)',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'response_pause_duration_seconds',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
            comment='Total accumulated pause duration for response clock in seconds',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'response_pause_started_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when current response pause started (UTC)',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'response_escalation_level',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
            comment='Current response escalation level: 0=Normal, 1=Warning, 2=Breached',
        ),
    )

    op.add_column(
        'complaints',
        sa.Column(
            'resolution_sla_policy_id',
            UUID(as_uuid=True),
            sa.ForeignKey('sla_policies.id', ondelete='SET NULL'),
            nullable=True,
            comment='SLA policy used for resolution clock target',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'resolution_deadline',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Target UTC deadline for complaint resolution',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'resolution_pause_duration_seconds',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
            comment='Total accumulated pause duration for resolution clock in seconds',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'resolution_pause_started_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when current resolution pause started (UTC)',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'resolution_escalation_level',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
            comment='Current resolution escalation level: 0=Normal, 1=Warning, 2=Breached, 3=Severe',
        ),
    )

    op.add_column(
        'complaints',
        sa.Column(
            'sla_cycle_number',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('1'),
            comment='Current SLA resolution cycle number (>= 1, increments on reopen)',
        ),
    )
    op.add_column(
        'complaints',
        sa.Column(
            'last_sla_evaluated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp of last on-demand or transition SLA evaluation (UTC)',
        ),
    )

    # Indexes on complaints SLA fields
    op.create_index('ix_complaints_response_sla_policy_id', 'complaints', ['response_sla_policy_id'])
    op.create_index('ix_complaints_resolution_sla_policy_id', 'complaints', ['resolution_sla_policy_id'])
    op.create_index('ix_complaints_response_deadline', 'complaints', ['response_deadline'])
    op.create_index('ix_complaints_resolution_deadline', 'complaints', ['resolution_deadline'])
    op.create_index('ix_complaints_responded_at', 'complaints', ['responded_at'])
    op.create_index('ix_complaints_response_escalation_level', 'complaints', ['response_escalation_level'])
    op.create_index('ix_complaints_resolution_escalation_level', 'complaints', ['resolution_escalation_level'])

    # Check constraints on complaints
    op.create_check_constraint(
        'ck_complaints_response_pause_duration',
        'complaints',
        'response_pause_duration_seconds >= 0',
    )
    op.create_check_constraint(
        'ck_complaints_resolution_pause_duration',
        'complaints',
        'resolution_pause_duration_seconds >= 0',
    )
    op.create_check_constraint(
        'ck_complaints_response_escalation_level',
        'complaints',
        'response_escalation_level BETWEEN 0 AND 2',
    )
    op.create_check_constraint(
        'ck_complaints_resolution_escalation_level',
        'complaints',
        'resolution_escalation_level BETWEEN 0 AND 3',
    )
    op.create_check_constraint(
        'ck_complaints_sla_cycle_number',
        'complaints',
        'sla_cycle_number >= 1',
    )

    # 3. Create complaint_sla_history table
    op.create_table(
        'complaint_sla_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, comment='Primary UUID identifier for SLA history entry'),
        sa.Column('complaint_id', UUID(as_uuid=True), sa.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False, comment='SLA cycle sequence number (>= 1)'),
        sa.Column('policy_id', UUID(as_uuid=True), sa.ForeignKey('sla_policies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('policy_name', sa.String(length=100), nullable=True),
        sa.Column('policy_snapshot', sa.JSON(), nullable=True, comment='Snapshot of policy parameters at cycle completion'),
        sa.Column('response_target_seconds', sa.Integer(), nullable=True, comment='Target response duration in seconds'),
        sa.Column('resolution_target_seconds', sa.Integer(), nullable=True, comment='Target resolution duration in seconds'),
        sa.Column('actual_response_seconds', sa.Integer(), nullable=True, comment='Actual elapsed response seconds (null if unobserved)'),
        sa.Column('actual_resolution_seconds', sa.Integer(), nullable=True, comment='Actual elapsed resolution seconds (null if unobserved)'),
        sa.Column('response_breached', sa.Boolean(), nullable=True, comment='Whether response SLA breached (null if unknown)'),
        sa.Column('resolution_breached', sa.Boolean(), nullable=True, comment='Whether resolution SLA breached (null if unknown)'),
        sa.Column('response_escalation_level', sa.Integer(), nullable=True),
        sa.Column('resolution_escalation_level', sa.Integer(), nullable=True),
        sa.Column('cycle_started_at', sa.DateTime(timezone=True), nullable=False, comment='Cycle start timestamp (UTC)'),
        sa.Column('cycle_ended_at', sa.DateTime(timezone=True), nullable=False, comment='Cycle completion/end timestamp (UTC)'),
        sa.Column('end_reason', sa.String(length=50), nullable=False, comment='Lifecycle event ending the cycle (REOPENED, RESOLVED, REJECTED, DUPLICATE)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('complaint_id', 'cycle_number', name='uq_complaint_sla_history_cycle'),
        sa.CheckConstraint('cycle_number >= 1', name='ck_complaint_sla_history_cycle_number'),
        sa.CheckConstraint('actual_response_seconds IS NULL OR actual_response_seconds >= 0', name='ck_complaint_sla_history_response_seconds'),
        sa.CheckConstraint('actual_resolution_seconds IS NULL OR actual_resolution_seconds >= 0', name='ck_complaint_sla_history_resolution_seconds'),
    )

    op.create_index('ix_complaint_sla_history_complaint_id', 'complaint_sla_history', ['complaint_id'])
    op.create_index('ix_complaint_sla_history_policy_id', 'complaint_sla_history', ['policy_id'])

    # 4. PostgreSQL Immutability Trigger for complaint_sla_history
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_sla_history_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'complaint_sla_history records are immutable and cannot be updated or deleted';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_prevent_sla_history_mutation
        BEFORE UPDATE OR DELETE ON complaint_sla_history
        FOR EACH ROW EXECUTE FUNCTION prevent_sla_history_mutation();
        """
    )


def downgrade() -> None:
    # 1. Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_sla_history_mutation ON complaint_sla_history;")
    op.execute("DROP FUNCTION IF EXISTS prevent_sla_history_mutation();")

    # 2. Drop complaint_sla_history table
    op.drop_table('complaint_sla_history')

    # 3. Drop check constraints and indexes from complaints
    op.drop_constraint('ck_complaints_sla_cycle_number', 'complaints', type_='check')
    op.drop_constraint('ck_complaints_resolution_escalation_level', 'complaints', type_='check')
    op.drop_constraint('ck_complaints_response_escalation_level', 'complaints', type_='check')
    op.drop_constraint('ck_complaints_resolution_pause_duration', 'complaints', type_='check')
    op.drop_constraint('ck_complaints_response_pause_duration', 'complaints', type_='check')

    op.drop_index('ix_complaints_resolution_escalation_level', table_name='complaints')
    op.drop_index('ix_complaints_response_escalation_level', table_name='complaints')
    op.drop_index('ix_complaints_responded_at', table_name='complaints')
    op.drop_index('ix_complaints_resolution_deadline', table_name='complaints')
    op.drop_index('ix_complaints_response_deadline', table_name='complaints')
    op.drop_index('ix_complaints_resolution_sla_policy_id', table_name='complaints')
    op.drop_index('ix_complaints_response_sla_policy_id', table_name='complaints')

    # 4. Drop columns from complaints
    op.drop_column('complaints', 'last_sla_evaluated_at')
    op.drop_column('complaints', 'sla_cycle_number')
    op.drop_column('complaints', 'resolution_escalation_level')
    op.drop_column('complaints', 'resolution_pause_started_at')
    op.drop_column('complaints', 'resolution_pause_duration_seconds')
    op.drop_column('complaints', 'resolution_deadline')
    op.drop_column('complaints', 'resolution_sla_policy_id')
    op.drop_column('complaints', 'response_escalation_level')
    op.drop_column('complaints', 'response_pause_started_at')
    op.drop_column('complaints', 'response_pause_duration_seconds')
    op.drop_column('complaints', 'responded_at')
    op.drop_column('complaints', 'response_deadline')
    op.drop_column('complaints', 'response_sla_policy_id')

    # 5. Drop sla_policies table
    op.drop_index('uq_sla_policy_global', table_name='sla_policies')
    op.drop_index('uq_sla_policy_priority_only', table_name='sla_policies')
    op.drop_index('uq_sla_policy_category_only', table_name='sla_policies')
    op.drop_index('uq_sla_policy_category_priority', table_name='sla_policies')
    op.drop_table('sla_policies')
