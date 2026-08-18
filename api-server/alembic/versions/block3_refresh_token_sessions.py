"""Bloc 3 — sessions persistantes de refresh tokens.

Revision ID: block3_refresh_tokens
Revises: d4e5f6g7h8i9
"""
from alembic import op
import sqlalchemy as sa

revision = "block3_refresh_tokens"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("utilisateur_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refresh_token_sessions_jti", "refresh_token_sessions", ["jti"], unique=True)
    op.create_index("ix_refresh_token_sessions_utilisateur_id", "refresh_token_sessions", ["utilisateur_id"])
    op.create_index("ix_refresh_sessions_user_family", "refresh_token_sessions", ["utilisateur_id", "family_id"])
    op.create_index("ix_refresh_sessions_active_expiry", "refresh_token_sessions", ["expires_at", "revoked_at"])
    op.create_index("ix_refresh_token_sessions_family_id", "refresh_token_sessions", ["family_id"])
    op.create_index("ix_refresh_token_sessions_expires_at", "refresh_token_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_token_sessions_expires_at", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_family_id", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_sessions_active_expiry", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_sessions_user_family", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_utilisateur_id", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_jti", table_name="refresh_token_sessions")
    op.drop_table("refresh_token_sessions")
