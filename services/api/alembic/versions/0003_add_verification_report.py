"""Add verification_data column to document records.

Stores the full, structured verification report so it can be retrieved
without re-running the pipeline.

Revision: 0003_add_verification_report
"""
import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_records",
        sa.Column("verification_data", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_records", "verification_data")
