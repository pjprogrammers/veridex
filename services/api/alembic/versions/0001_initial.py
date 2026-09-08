"""Initial schema: users, cases, documents, checks, audit, registry, faces.

Creates the base tables required by the application models. Later
migrations (0002+) alter these tables; keep this revision in sync with
app/models/models.py when bootstrap columns change.

Revision: 0001
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "verification_cases",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("case_number", sa.String(50), unique=True, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("risk_score", sa.Float()),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id")),
        sa.Column("description", sa.Text()),
        sa.Column("document_hash", sa.String(64)),
        sa.Column("case_metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_verification_cases_case_number", "verification_cases", ["case_number"], unique=True)
    op.create_index("ix_verification_cases_status", "verification_cases", ["status"])
    op.create_index("ix_verification_cases_risk_level", "verification_cases", ["risk_level"])
    op.create_index("ix_case_status_created", "verification_cases", ["status", "created_at"])

    op.create_table(
        "document_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("case_id", UUID, sa.ForeignKey("verification_cases.id")),
        sa.Column("document_type", sa.String(50)),
        sa.Column("country", sa.String(2)),
        sa.Column("document_number", sa.String(50)),
        sa.Column("storage_key", sa.String(255)),
        sa.Column("content_hash", sa.String(64), unique=True),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("quality_score", sa.Float()),
        sa.Column("ocr_data", sa.JSON()),
        sa.Column("mrz_data", sa.JSON()),
        sa.Column("forensic_data", sa.JSON()),
        sa.Column("extracted_fields", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_document_records_document_type", "document_records", ["document_type"])
    op.create_index("ix_document_records_content_hash", "document_records", ["content_hash"], unique=True)

    op.create_table(
        "verification_checks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("case_id", UUID, sa.ForeignKey("verification_cases.id")),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", sa.JSON()),
        sa.Column("output", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_check_case_type", "verification_checks", ["case_id", "check_type"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("case_id", UUID, sa.ForeignKey("verification_cases.id")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", UUID),
        sa.Column("actor_role", sa.String(50)),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON()),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])

    op.create_table(
        "registry_entries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("registry_type", sa.String(50), nullable=False),
        sa.Column("document_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("holder_name", sa.String(255)),
        sa.Column("issuing_country", sa.String(2)),
        sa.Column("additional_data", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_number", "registry_type", name="uq_registry_doc_type"),
    )
    op.create_index("ix_registry_doc_number", "registry_entries", ["document_number"])

    op.create_table(
        "stored_faces",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("identity_id", sa.String(100), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("source_note", sa.String(255)),
        sa.Column("is_synthetic", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stored_faces_identity_id", "stored_faces", ["identity_id"])
    op.create_index("ix_face_identity_id", "stored_faces", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_face_identity_id", table_name="stored_faces")
    op.drop_index("ix_stored_faces_identity_id", table_name="stored_faces")
    op.drop_table("stored_faces")
    op.drop_index("ix_registry_doc_number", table_name="registry_entries")
    op.drop_table("registry_entries")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_check_case_type", table_name="verification_checks")
    op.drop_table("verification_checks")
    op.drop_index("ix_document_records_content_hash", table_name="document_records")
    op.drop_index("ix_document_records_document_type", table_name="document_records")
    op.drop_table("document_records")
    op.drop_index("ix_case_status_created", table_name="verification_cases")
    op.drop_index("ix_verification_cases_risk_level", table_name="verification_cases")
    op.drop_index("ix_verification_cases_status", table_name="verification_cases")
    op.drop_index("ix_verification_cases_case_number", table_name="verification_cases")
    op.drop_table("verification_cases")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
