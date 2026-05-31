"""add retrieval source store

Revision ID: 20260529_123731
Revises: 20260527_163233
Create Date: 2026-05-29 12:37:31
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_123731"
down_revision = "20260527_163233"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_source_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("title_encrypted", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("jurisdiction", sa.String(length=64), nullable=True),
        sa.Column("payer_type", sa.String(length=64), nullable=True),
        sa.Column("source_date", sa.String(length=32), nullable=True),
        sa.Column("source_url_encrypted", sa.Text(), nullable=True),
        sa.Column("phi_status", sa.String(length=32), nullable=False),
        sa.Column("license_status", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id"),
    )
    op.create_index(op.f("ix_retrieval_source_documents_id"), "retrieval_source_documents", ["id"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_source_id"), "retrieval_source_documents", ["source_id"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_source_type"), "retrieval_source_documents", ["source_type"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_jurisdiction"), "retrieval_source_documents", ["jurisdiction"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_payer_type"), "retrieval_source_documents", ["payer_type"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_source_date"), "retrieval_source_documents", ["source_date"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_phi_status"), "retrieval_source_documents", ["phi_status"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_license_status"), "retrieval_source_documents", ["license_status"], unique=False)
    op.create_index(op.f("ix_retrieval_source_documents_created_by_user_id"), "retrieval_source_documents", ["created_by_user_id"], unique=False)

    op.create_table(
        "retrieval_source_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(length=96), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text_encrypted", sa.Text(), nullable=False),
        sa.Column("page_number", sa.String(length=32), nullable=True),
        sa.Column("section_label_encrypted", sa.Text(), nullable=True),
        sa.Column("extra_metadata_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["source_document_id"], ["retrieval_source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(op.f("ix_retrieval_source_chunks_id"), "retrieval_source_chunks", ["id"], unique=False)
    op.create_index(op.f("ix_retrieval_source_chunks_chunk_id"), "retrieval_source_chunks", ["chunk_id"], unique=False)
    op.create_index(op.f("ix_retrieval_source_chunks_source_document_id"), "retrieval_source_chunks", ["source_document_id"], unique=False)
    op.create_index(op.f("ix_retrieval_source_chunks_chunk_index"), "retrieval_source_chunks", ["chunk_index"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_retrieval_source_chunks_chunk_index"), table_name="retrieval_source_chunks")
    op.drop_index(op.f("ix_retrieval_source_chunks_source_document_id"), table_name="retrieval_source_chunks")
    op.drop_index(op.f("ix_retrieval_source_chunks_chunk_id"), table_name="retrieval_source_chunks")
    op.drop_index(op.f("ix_retrieval_source_chunks_id"), table_name="retrieval_source_chunks")
    op.drop_table("retrieval_source_chunks")
    op.drop_index(op.f("ix_retrieval_source_documents_created_by_user_id"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_license_status"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_phi_status"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_source_date"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_payer_type"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_jurisdiction"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_source_type"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_source_id"), table_name="retrieval_source_documents")
    op.drop_index(op.f("ix_retrieval_source_documents_id"), table_name="retrieval_source_documents")
    op.drop_table("retrieval_source_documents")
