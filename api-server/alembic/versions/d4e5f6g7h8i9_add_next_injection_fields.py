"""add next injection fields

Revision ID: d4e5f6g7h8i9
Revises: ca7adcd5a7ff
Create Date: 2026-07-30 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'ca7adcd5a7ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add duree_effet_jours to produits_injectables
    op.add_column('produits_injectables', sa.Column('duree_effet_jours', sa.Integer(), nullable=False, server_default='90'))
    
    # Add next injection columns to utilisations_lot
    op.add_column('utilisations_lot', sa.Column('prochaine_injection_date', sa.Date(), nullable=True))
    op.add_column('utilisations_lot', sa.Column('prochaine_injection_envoyee', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('utilisations_lot', 'prochaine_injection_envoyee')
    op.drop_column('utilisations_lot', 'prochaine_injection_date')
    op.drop_column('produits_injectables', 'duree_effet_jours')
