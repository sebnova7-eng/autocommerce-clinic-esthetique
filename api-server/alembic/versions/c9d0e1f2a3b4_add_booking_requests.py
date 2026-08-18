"""add public booking request workflow

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "booking_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.Column("prenom", sa.String(length=100), nullable=False),
        sa.Column("telephone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("praticien_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("acte_id", sa.Integer(), sa.ForeignKey("actes_medicaux.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date_heure", sa.DateTime(), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rendez_vous_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_notes", sa.String(length=500), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="public_gateway"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("clinic_id", "request_fingerprint", name="uq_booking_requests_fingerprint"),
    )
    op.create_index("ix_booking_requests_clinic_id", "booking_requests", ["clinic_id"])
    op.create_index("ix_booking_requests_statut", "booking_requests", ["statut"])
    op.create_index("ix_booking_requests_clinic_status", "booking_requests", ["clinic_id", "statut"])


def downgrade() -> None:
    op.drop_index("ix_booking_requests_clinic_status", table_name="booking_requests")
    op.drop_index("ix_booking_requests_statut", table_name="booking_requests")
    op.drop_index("ix_booking_requests_clinic_id", table_name="booking_requests")
    op.drop_table("booking_requests")
