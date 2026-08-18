"""merge heads

Revision ID: 62f1dcc65ced
Revises: 9c3d4e5f6g7h, a1b2c3d4e5f6
Create Date: 2026-07-26 18:05:28.319614

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '62f1dcc65ced'
down_revision: Union[str, None] = ('9c3d4e5f6g7h', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
