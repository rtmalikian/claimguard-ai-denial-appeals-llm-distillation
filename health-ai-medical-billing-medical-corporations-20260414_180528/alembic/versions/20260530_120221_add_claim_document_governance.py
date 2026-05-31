"""add claim document governance fields

Revision ID: 20260530_120221
Revises: 20260530_112226
Create Date: 2026-05-30 12:02:21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260530_120221"
down_revision = "20260530_112226"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column(
            "document_access_scope",
            sa.String(length=32),
            nullable=False,
            server_default="billing_team",
        ),
    )
    op.add_column(
        "claims",
        sa.Column("document_retention_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("document_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("document_deleted_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("document_deletion_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("document_created_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_claims_document_access_scope"),
        "claims",
        ["document_access_scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claims_document_retention_until"),
        "claims",
        ["document_retention_until"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claims_document_deleted_at"),
        "claims",
        ["document_deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claims_document_deleted_by_user_id"),
        "claims",
        ["document_deleted_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claims_document_created_by_user_id"),
        "claims",
        ["document_created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_claims_document_created_by_user_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_document_deleted_by_user_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_document_deleted_at"), table_name="claims")
    op.drop_index(op.f("ix_claims_document_retention_until"), table_name="claims")
    op.drop_index(op.f("ix_claims_document_access_scope"), table_name="claims")
    op.drop_column("claims", "document_created_by_user_id")
    op.drop_column("claims", "document_deletion_reason")
    op.drop_column("claims", "document_deleted_by_user_id")
    op.drop_column("claims", "document_deleted_at")
    op.drop_column("claims", "document_retention_until")
    op.drop_column("claims", "document_access_scope")
