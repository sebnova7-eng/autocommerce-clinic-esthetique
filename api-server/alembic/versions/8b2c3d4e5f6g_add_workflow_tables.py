"""add workflow tables

Revision ID: 8b2c3d4e5f6g
Revises: f8baad288795
Create Date: 2026-07-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8b2c3d4e5f6g'
down_revision = 'f8baad288795'
branch_labels = None
depends_on = None


def upgrade():
    # Table workflows
    op.create_table(
        'workflows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('nom', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_type', sa.String(length=20), nullable=False),
        sa.Column('trigger_config', sa.JSON(), nullable=True),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('cron_expression', sa.String(length=100), nullable=True),
        sa.Column('next_execution', sa.DateTime(), nullable=True),
        sa.Column('max_executions_per_day', sa.Integer(), nullable=True),
        sa.Column('execution_count_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_clinic_status', 'workflows', ['clinic_id', 'status'], unique=False)
    op.create_index('ix_workflow_clinic_enabled', 'workflows', ['clinic_id', 'enabled'], unique=False)

    # Table workflow_executions
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=True),
        sa.Column('trigger_reason', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_workflow_status', 'workflow_executions', ['workflow_id', 'status'], unique=False)
    op.create_index('ix_execution_clinic_date', 'workflow_executions', ['clinic_id', 'created_at'], unique=False)

    # Table workflow_templates
    op.create_table(
        'workflow_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('nom', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('categorie', sa.String(length=50), nullable=False),
        sa.Column('trigger_type', sa.String(length=20), nullable=False),
        sa.Column('trigger_config', sa.JSON(), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Table workflow_actions_log
    op.create_table(
        'workflow_actions_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_config', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_action_execution_type', 'workflow_actions_log', ['execution_id', 'action_type'], unique=False)

    # Table workflow_schedules
    op.create_table(
        'workflow_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('max_executions_per_day', sa.Integer(), nullable=True),
        sa.Column('execution_count_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_execution', sa.DateTime(), nullable=True),
        sa.Column('next_execution', sa.DateTime(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('workflow_schedules')
    op.drop_table('workflow_actions_log')
    op.drop_table('workflow_templates')
    op.drop_table('workflow_executions')
    op.drop_table('workflows')
