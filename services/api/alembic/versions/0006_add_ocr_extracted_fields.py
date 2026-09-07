"""Add ocr_extracted_fields column.

Stores structured OCR extraction results (fields with per-field confidence
and bounding boxes) alongside the existing raw ocr_data.

Revision: 0006_add_ocr_extracted_fields
"""
import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_records",
        sa.Column("ocr_extracted_fields", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_records", "ocr_extracted_fields")
