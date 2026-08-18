"""add simulations_ia table

Revision ID: bloc3_simulation_ia
Revises: bloc2_social_listening
Create Date: 2026-07-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bloc3_simulation_ia'
down_revision: Union[str, None] = 'bloc2_social_listening'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'simulations_ia',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), server_default='1', nullable=False),
        sa.Column('photo_source_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('zone_anatomique', sa.String(length=50), nullable=False),
        sa.Column('url_resultat', sa.String(length=500), nullable=False),
        sa.Column('consentement_id', sa.Integer(), nullable=False),
        sa.Column('genere_par_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['consentement_id'], ['consentements.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['genere_par_id'], ['utilisateurs.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['photo_source_id'], ['photos_clinic.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_simulations_ia_patient_id', 'simulations_ia', ['patient_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_simulations_ia_patient_id', table_name='simulations_ia')
    op.drop_table('simulations_ia')
