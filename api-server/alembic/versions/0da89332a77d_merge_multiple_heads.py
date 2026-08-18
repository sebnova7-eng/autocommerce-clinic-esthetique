"""merge multiple heads

Revision ID: 0da89332a77d
Revises: b2c3d4e5f6g7, f1a2b3c4d5e7
Create Date: 2026-07-26 23:57:46.881185

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '0da89332a77d'
down_revision: Union[str, None] = ('b2c3d4e5f6g7', 'f1a2b3c4d5e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
