"""Add document ingestion fields to document_records.

Adds ingestion state, separate storage keys for
original/processed/preview, preprocessing metadata, original filename,
and an error slot for failed ingestion.

Revision: 0004_add_document_ingestion
"""
import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_records", sa.Column("original_key", sa.String(255), nullable=True))
    op.add_column("document_records", sa.Column("processed_key", sa.String(255), nullable=True))
    op.add_column("document_records", sa.Column("preview_key", sa.String(255), nullable=True))
    op.add_column("document_records", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column(
        "document_records",
        sa.Column("status", sa.String(30), nullable=True, server_default="UPLOADED"),
    )
    op.add_column("document_records", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column(
        "document_records", sa.Column("preprocess_metadata", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("document_records", "preprocess_metadata")
    op.drop_column("document_records", "processing_error")
    op.drop_column("document_records", "status")
    op.drop_column("document_records", "original_filename")
    op.drop_column("document_records", "preview_key")
    op.drop_column("document_records", "processed_key")
    op.drop_column("document_records", "original_key")
