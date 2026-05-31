"""add claim and patient soft delete indexes

Revision ID: 20260531_033507
Revises: 20260531_004528
Create Date: 2026-05-31 03:35:07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260531_033507"
down_revision = "20260531_004528"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "patients",
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "patients",
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
    )

    op.create_index(op.f("ix_patients_deleted_at"), "patients", ["deleted_at"])
    op.create_index(
        op.f("ix_patients_deleted_by_user_id"),
        "patients",
        ["deleted_by_user_id"],
    )
    op.create_index(op.f("ix_claims_deleted_at"), "claims", ["deleted_at"])
    op.create_index(
        op.f("ix_claims_deleted_by_user_id"),
        "claims",
        ["deleted_by_user_id"],
    )
    op.create_index(
        op.f("ix_claims_submission_date"),
        "claims",
        ["submission_date"],
    )
    op.create_index(
        op.f("ix_claims_denial_prediction"),
        "claims",
        ["denial_prediction"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_claims_denial_prediction"), table_name="claims")
    op.drop_index(op.f("ix_claims_submission_date"), table_name="claims")
    op.drop_index(op.f("ix_claims_deleted_by_user_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_deleted_at"), table_name="claims")
    op.drop_index(op.f("ix_patients_deleted_by_user_id"), table_name="patients")
    op.drop_index(op.f("ix_patients_deleted_at"), table_name="patients")

    op.drop_column("claims", "deletion_reason")
    op.drop_column("claims", "deleted_by_user_id")
    op.drop_column("claims", "deleted_at")
    op.drop_column("patients", "deletion_reason")
    op.drop_column("patients", "deleted_by_user_id")
    op.drop_column("patients", "deleted_at")
