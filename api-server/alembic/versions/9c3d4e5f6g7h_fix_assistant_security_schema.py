"""fix assistant security schema

Revision ID: 9c3d4e5f6g7h
Revises: 8b2c3d4e5f6g
Create Date: 2026-07-26 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9c3d4e5f6g7h'
down_revision = '8b2c3d4e5f6g'
branch_labels = None
depends_on = None


def upgrade():
    # Fix NumeroWhitelist
    # Check if columns exist before adding (safety)
    # op.add_column('numero_whitelist', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    # op.add_column('numero_whitelist', sa.Column('raison_revocation', sa.Text(), nullable=True))
    # op.add_column('numero_whitelist', sa.Column('last_key_rotation', sa.DateTime(), nullable=True))

    # Fix CommandeAssistant
    op.add_column('commandes_assistant', sa.Column('intent_detecte', sa.String(length=100), nullable=True))
    op.add_column('commandes_assistant', sa.Column('outil_appele', sa.String(length=100), nullable=True))
    op.add_column('commandes_assistant', sa.Column('role_applique', sa.String(length=50), nullable=True))
    op.add_column('commandes_assistant', sa.Column('parametres_appel', sa.JSON(), nullable=True))
    op.add_column('commandes_assistant', sa.Column('tool_payload_json', sa.JSON(), nullable=True))
    op.add_column('commandes_assistant', sa.Column('erreur_message', sa.Text(), nullable=True))
    op.add_column('commandes_assistant', sa.Column('utilisateur_id', sa.Integer(), nullable=True))
    
    # Indexes for CommandeAssistant
    op.create_index('ix_commande_utilisateur', 'commandes_assistant', ['utilisateur_id'], unique=False)
    op.create_index('ix_commande_outil', 'commandes_assistant', ['outil_appele'], unique=False)


def downgrade():
    op.drop_index('ix_commande_outil', table_name='commandes_assistant')
    op.drop_index('ix_commande_utilisateur', table_name='commandes_assistant')
    op.drop_column('commandes_assistant', 'utilisateur_id')
    op.drop_column('commandes_assistant', 'erreur_message')
    op.drop_column('commandes_assistant', 'tool_payload_json')
    op.drop_column('commandes_assistant', 'parametres_appel')
    op.drop_column('commandes_assistant', 'role_applique')
    op.drop_column('commandes_assistant', 'outil_appele')
    op.drop_column('commandes_assistant', 'intent_detecte')
