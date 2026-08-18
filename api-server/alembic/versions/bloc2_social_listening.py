"""add avis_clients table

Revision ID: bloc2_social_listening
Revises: bloc1_injection_workflow
Create Date: 2026-07-29 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bloc2_social_listening'
down_revision: Union[str, None] = 'bloc1_injection_workflow'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'avis_clients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), server_default='1', nullable=False),
        sa.Column('plateforme', sa.String(length=20), nullable=False),
        sa.Column('note', sa.Integer(), nullable=True),
        sa.Column('texte', sa.Text(), nullable=False),
        sa.Column('auteur_nom', sa.String(length=200), nullable=True),
        sa.Column('reponse_suggeree_ia', sa.Text(), nullable=True),
        sa.Column('reponse_publiee', sa.Text(), nullable=True),
        sa.Column('statut', sa.String(length=20), server_default='nouveau', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_avis_clinic_plateforme', 'avis_clients', ['clinic_id', 'plateforme'], unique=False)
    op.create_index('ix_avis_clinic_statut', 'avis_clients', ['clinic_id', 'statut'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_avis_clinic_statut', table_name='avis_clients')
    op.drop_index('ix_avis_clinic_plateforme', table_name='avis_clients')
    op.drop_table('avis_clients')
