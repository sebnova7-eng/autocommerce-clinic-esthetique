"""add_omnicanal_models

Ajoute les nouveaux modèles omnicanal :
  - channel_configs
  - conversations
  - messages_omnicanal
  - channel_events
  - numeros_whitelist
  - sessions_assistant
  - commandes_assistant
  - confirmations_sensibles
  - alertes_securite

Rétrocompatibilité : les tables existantes (social_messages, social_posts, etc.)
ne sont JAMAIS modifiées ni supprimées.
"""

from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f8baad288795'  # add_default_date_emission
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── channel_configs ────────────────────────────────────
    op.create_table(
        'channel_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('canal', sa.String(20), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False, server_default='non_configure'),
        sa.Column('api_key_enc', sa.Text(), nullable=True),
        sa.Column('api_secret_enc', sa.Text(), nullable=True),
        sa.Column('webhook_verify_token_enc', sa.Text(), nullable=True),
        sa.Column('account_id', sa.String(255), nullable=True),
        sa.Column('business_account_id', sa.String(255), nullable=True),
        sa.Column('sender_phone', sa.String(20), nullable=True),
        sa.Column('sender_name', sa.String(200), nullable=True),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('messages_par_jour', sa.Integer(), nullable=True),
        sa.Column('messages_envoyes_aujourdhui', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('derniere_reinitialisation_quota', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('canal', name='uq_channel_configs_canal'),
    )
    op.create_index('ix_channel_configs_clinic_canal', 'channel_configs', ['clinic_id', 'canal'])

    # ── conversations ──────────────────────────────────────
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('canal_config_id', sa.Integer(), nullable=True),
        sa.Column('canal', sa.String(20), nullable=False),
        sa.Column('contact_external_id', sa.String(255), nullable=False),
        sa.Column('contact_nom', sa.String(200), nullable=True),
        sa.Column('patient_id', sa.Integer(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='ouverte'),
        sa.Column('dernier_message_at', sa.DateTime(), nullable=True),
        sa.Column('nb_messages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['canal_config_id'], ['channel_configs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assignee_id'], ['utilisateurs.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_conversations_contact', 'conversations', ['contact_external_id'])
    op.create_index('ix_conversations_patient', 'conversations', ['patient_id'])
    op.create_index('ix_conversations_statut', 'conversations', ['clinic_id', 'statut'])
    op.create_index('ix_conversations_clinic_canal', 'conversations', ['clinic_id', 'canal'])

    # ── messages_omnicanal ─────────────────────────────────
    op.create_table(
        'messages_omnicanal',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('type_message', sa.String(20), nullable=False, server_default='texte'),
        sa.Column('contenu', sa.Text(), nullable=True),
        sa.Column('pieces_jointes', sa.Text(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='envoye'),
        sa.Column('external_message_id', sa.String(255), nullable=True),
        sa.Column('delivre_a', sa.DateTime(), nullable=True),
        sa.Column('lu_a', sa.DateTime(), nullable=True),
        sa.Column('nb_retries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dernier_retry_at', sa.DateTime(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('reponse_auto', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('template_name', sa.String(200), nullable=True),
        sa.Column('template_language', sa.String(10), nullable=True),
        sa.Column('template_params', sa.Text(), nullable=True),
        sa.Column('erreur', sa.Text(), nullable=True),
        sa.Column('patient_id', sa.Integer(), nullable=True),
        sa.Column('envoye_par_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['envoye_par_id'], ['utilisateurs.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_messages_conversation_statut', 'messages_omnicanal', ['conversation_id', 'statut'])
    op.create_index('ix_messages_clinic_date', 'messages_omnicanal', ['clinic_id', 'created_at'])
    op.create_index('ix_messages_external_id', 'messages_omnicanal', ['external_message_id'])

    # ── channel_events ─────────────────────────────────────
    op.create_table(
        'channel_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('type_evenement', sa.String(50), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages_omnicanal.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_channel_events_message_date', 'channel_events', ['message_id', 'timestamp'])
    op.create_index('ix_channel_events_clinic_date', 'channel_events', ['clinic_id', 'timestamp'])

    # ── numeros_whitelist ──────────────────────────────────
    op.create_table(
        'numeros_whitelist',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('numero', sa.String(20), nullable=False),
        sa.Column('nom', sa.String(200), nullable=True),
        sa.Column('utilisateur_id', sa.Integer(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='active'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_id', sa.Integer(), nullable=True),
        sa.Column('raison_revocation', sa.String(300), nullable=True),
        sa.Column('last_key_rotation', sa.DateTime(), nullable=True),
        sa.Column('permissions_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('numero', name='uq_numeros_whitelist_numero'),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revoked_by_id'], ['utilisateurs.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_whitelist_clinic_numero', 'numeros_whitelist', ['clinic_id', 'numero'])

    # ── sessions_assistant ─────────────────────────────────
    op.create_table(
        'sessions_assistant',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('whitelist_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.String(20), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False, server_default='active'),
        sa.Column('token_session', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('nb_tours', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('nb_erreurs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('derniere_activite', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['whitelist_id'], ['numeros_whitelist.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_sessions_assistant_token', 'sessions_assistant', ['token_session'])
    op.create_index('ix_sessions_assistant_statut', 'sessions_assistant', ['clinic_id', 'statut'])

    # ── commandes_assistant ────────────────────────────────
    op.create_table(
        'commandes_assistant',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('whitelist_id', sa.Integer(), nullable=True),
        sa.Column('numero', sa.String(20), nullable=False),
        sa.Column('type_commande', sa.String(50), nullable=False),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('reponse', sa.Text(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='executed'),
        sa.Column('raison_refus', sa.Text(), nullable=True),
        sa.Column('contexte_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions_assistant.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['whitelist_id'], ['numeros_whitelist.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_commandes_assistant_numero', 'commandes_assistant', ['clinic_id', 'numero'])
    op.create_index('ix_commandes_assistant_date', 'commandes_assistant', ['clinic_id', 'created_at'])

    # ── confirmations_sensibles ────────────────────────────
    op.create_table(
        'confirmations_sensibles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('utilisateur_id', sa.Integer(), nullable=True),
        sa.Column('type_operation', sa.String(50), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='en_attente'),
        sa.Column('code_confirmation', sa.String(8), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('confirme_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_confirmations_clinic_date', 'confirmations_sensibles', ['clinic_id', 'created_at'])

    # ── alertes_securite ───────────────────────────────────
    op.create_table(
        'alertes_securite',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('type_alerte', sa.String(50), nullable=False),
        sa.Column('severite', sa.String(20), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False, server_default='nouvelle'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('numero_concerne', sa.String(20), nullable=True),
        sa.Column('utilisateur_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('resolue_par_id', sa.Integer(), nullable=True),
        sa.Column('resolue_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolue_par_id'], ['utilisateurs.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_alertes_clinic_type', 'alertes_securite', ['clinic_id', 'type_alerte'])
    op.create_index('ix_alertes_clinic_statut', 'alertes_securite', ['clinic_id', 'statut'])
    op.create_index('ix_alertes_clinic_severite', 'alertes_securite', ['clinic_id', 'severite'])
    op.create_index('ix_alertes_date', 'alertes_securite', ['clinic_id', 'created_at'])


def downgrade() -> None:
    # Ordre inverse des créations
    op.drop_table('alertes_securite')
    op.drop_table('confirmations_sensibles')
    op.drop_table('commandes_assistant')
    op.drop_table('sessions_assistant')
    op.drop_table('numeros_whitelist')
    op.drop_table('channel_events')
    op.drop_table('messages_omnicanal')
    op.drop_table('conversations')
    op.drop_table('channel_configs')
