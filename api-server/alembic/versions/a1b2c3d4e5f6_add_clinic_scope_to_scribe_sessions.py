"""add clinic scope to medical scribe sessions

Revision ID: b7c8d9e0f1a2
Revises: 261421ffceed
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "261421ffceed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("medical_scribe_sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("clinic_id", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_index(
            "ix_medical_scribe_sessions_clinic_id",
            ["clinic_id"],
            unique=False,
        )
    with op.batch_alter_table("medical_scribe_sessions", schema=None) as batch_op:
        batch_op.alter_column("clinic_id", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("medical_scribe_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_medical_scribe_sessions_clinic_id")
        batch_op.drop_column("clinic_id")
