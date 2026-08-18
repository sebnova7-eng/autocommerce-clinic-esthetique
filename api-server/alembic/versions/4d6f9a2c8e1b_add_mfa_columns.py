"""add mfa columns to utilisateurs

Revision ID: 4d6f9a2c8e1b
Revises: 7a1c9e2f4b3d
Create Date: 2026-07-22 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d6f9a2c8e1b'
down_revision: Union[str, None] = '7a1c9e2f4b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('utilisateurs', sa.Column('mfa_secret', sa.String(length=100), nullable=True))
    op.add_column('utilisateurs', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('utilisateurs', sa.Column('mfa_backup_codes', sa.Text(), nullable=True))
    op.add_column('utilisateurs', sa.Column('mfa_setup_at', sa.DateTime(), nullable=True))
    op.add_column('utilisateurs', sa.Column('mfa_failed_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('utilisateurs', sa.Column('mfa_locked_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('utilisateurs', 'mfa_locked_until')
    op.drop_column('utilisateurs', 'mfa_failed_attempts')
    op.drop_column('utilisateurs', 'mfa_setup_at')
    op.drop_column('utilisateurs', 'mfa_backup_codes')
    op.drop_column('utilisateurs', 'mfa_enabled')
    op.drop_column('utilisateurs', 'mfa_secret')
