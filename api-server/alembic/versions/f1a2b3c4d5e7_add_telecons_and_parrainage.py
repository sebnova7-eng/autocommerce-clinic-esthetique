"""add teleconsultation and parrainage tables

Revision ID: f1a2b3c4d5e7
Revises: e1a2b3c4d5e6
Create Date: 2026-07-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e7'
down_revision = 'e1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # ### teleconsultations ###
    op.create_table('teleconsultations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('rdv_id', sa.Integer(), nullable=False),
    sa.Column('lien_visio', sa.String(length=500), nullable=False),
    sa.Column('statut', sa.String(length=20), nullable=False),
    sa.Column('duree_reelle', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['rdv_id'], ['rendez_vous.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('rdv_id')
    )

    # ### parrainages ###
    op.create_table('parrainages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('parrain_patient_id', sa.Integer(), nullable=False),
    sa.Column('filleul_patient_id', sa.Integer(), nullable=True),
    sa.Column('code_parrain', sa.String(length=20), nullable=False),
    sa.Column('statut', sa.String(length=20), nullable=False),
    sa.Column('date_parrainage', sa.DateTime(), nullable=False),
    sa.Column('recompense_attribuee', sa.Boolean(), nullable=False),
    sa.Column('recompense_utilisee', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['parrain_patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['filleul_patient_id'], ['patients.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parrainages_code_parrain'), 'parrainages', ['code_parrain'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_parrainages_code_parrain'), table_name='parrainages')
    op.drop_table('parrainages')
    op.drop_table('teleconsultations')
