"""Bloc 5 — idempotence des messages entrants webhook.

Revision ID: block5_webhook_idempotency
Revises: block3_refresh_tokens
"""
from alembic import op

revision = "block5_webhook_idempotency"
down_revision = "block3_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_messages_conversation_external_id",
        "messages_omnicanal",
        ["conversation_id", "external_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_conversation_external_id",
        "messages_omnicanal",
        type_="unique",
    )
