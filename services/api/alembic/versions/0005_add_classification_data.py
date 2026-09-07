"""Add classification_data column to document_records.

Stores the structured output of the document-type classifier
(document_type, confidence, method, template_id, warnings).

Revision: 0005_add_classification_data
"""
import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_records", sa.Column("classification_data", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("document_records", "classification_data")
