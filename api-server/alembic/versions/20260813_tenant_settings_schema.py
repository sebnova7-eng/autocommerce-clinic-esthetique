"""Make clinic settings uniqueness tenant-scoped.

Revision ID: 20260813_tenant_settings_schema
Revises: block5_webhook_idempotency
"""
from alembic import op

revision = "20260813_tenant_settings_schema"
down_revision = "block5_webhook_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial schema incorrectly made `key` globally unique. Replace it
    # with a non-unique lookup index plus the intended per-clinic constraint.
    op.drop_index("ix_clinic_settings_key", table_name="clinic_settings")
    op.create_index(
        "ix_clinic_settings_key",
        "clinic_settings",
        ["key"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_clinic_settings_clinic_key",
        "clinic_settings",
        ["clinic_id", "key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_clinic_settings_clinic_key",
        "clinic_settings",
        type_="unique",
    )
    op.drop_index("ix_clinic_settings_key", table_name="clinic_settings")
    op.create_index(
        "ix_clinic_settings_key",
        "clinic_settings",
        ["key"],
        unique=True,
    )
