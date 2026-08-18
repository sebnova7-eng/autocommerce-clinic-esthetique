"""add type_injection to utilisations_lot

Revision ID: bloc1_injection_workflow
Revises: 0da89332a77d
Create Date: 2026-07-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bloc1_injection_workflow'
down_revision: Union[str, None] = '0da89332a77d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('utilisations_lot', sa.Column('type_injection', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('utilisations_lot', 'type_injection')
