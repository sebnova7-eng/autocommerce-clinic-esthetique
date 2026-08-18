"""add default date_emission to factures

Revision ID: f8baad288795
Revises: 4d6f9a2c8e1b
Create Date: 2026-07-22 12:27:40.615461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8baad288795'
down_revision: Union[str, None] = '4d6f9a2c8e1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('factures', schema=None) as batch_op:
        batch_op.alter_column(
            'date_emission',
            existing_type=sa.Date(),
            server_default=sa.text('CURRENT_DATE'),
            existing_nullable=False
        )


def downgrade() -> None:
    op.alter_column(
        'factures', 'date_emission',
        existing_type=sa.Date(),
        server_default=None,
        existing_nullable=False
    )
