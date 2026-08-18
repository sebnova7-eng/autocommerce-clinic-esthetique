"""add commission double validation columns

Revision ID: 7a1c9e2f4b3d
Revises: 2bfa8a61841c
Create Date: 2026-07-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1c9e2f4b3d'
down_revision: Union[str, None] = '2bfa8a61841c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('commissions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('validee_par_id_2', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('validated_at_2', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            'fk_commissions_validee_par_id_2_utilisateurs',
            'utilisateurs',
            ['validee_par_id_2'], ['id'],
            ondelete='SET NULL',
        )
    # `statut` est stocké en String(20), pas en enum natif Postgres :
    # la nouvelle valeur "validation_partielle" ne nécessite donc pas
    # de migration de type, juste le code applicatif à jour.


def downgrade() -> None:
    op.drop_constraint('fk_commissions_validee_par_id_2_utilisateurs', 'commissions', type_='foreignkey')
    op.drop_column('commissions', 'validated_at_2')
    op.drop_column('commissions', 'validee_par_id_2')
