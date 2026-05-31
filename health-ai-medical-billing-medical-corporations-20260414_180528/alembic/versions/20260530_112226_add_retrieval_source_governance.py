"""add retrieval source governance fields

Revision ID: 20260530_112226
Revises: 20260529_123731
Create Date: 2026-05-30 11:22:26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260530_112226"
down_revision = "20260529_123731"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_source_documents",
        sa.Column(
            "access_scope",
            sa.String(length=32),
            nullable=False,
            server_default="owner",
        ),
    )
    op.add_column(
        "retrieval_source_documents",
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "retrieval_source_documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "retrieval_source_documents",
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "retrieval_source_documents",
        sa.Column("deletion_reason", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_retrieval_source_documents_access_scope"),
        "retrieval_source_documents",
        ["access_scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_source_documents_retention_until"),
        "retrieval_source_documents",
        ["retention_until"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_source_documents_deleted_at"),
        "retrieval_source_documents",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_source_documents_deleted_by_user_id"),
        "retrieval_source_documents",
        ["deleted_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_retrieval_source_documents_deleted_by_user_id"),
        table_name="retrieval_source_documents",
    )
    op.drop_index(
        op.f("ix_retrieval_source_documents_deleted_at"),
        table_name="retrieval_source_documents",
    )
    op.drop_index(
        op.f("ix_retrieval_source_documents_retention_until"),
        table_name="retrieval_source_documents",
    )
    op.drop_index(
        op.f("ix_retrieval_source_documents_access_scope"),
        table_name="retrieval_source_documents",
    )
    op.drop_column("retrieval_source_documents", "deletion_reason")
    op.drop_column("retrieval_source_documents", "deleted_by_user_id")
    op.drop_column("retrieval_source_documents", "deleted_at")
    op.drop_column("retrieval_source_documents", "retention_until")
    op.drop_column("retrieval_source_documents", "access_scope")
