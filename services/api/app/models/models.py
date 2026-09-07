"""VERIDEX API - Database Models"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import SafeUuid


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# RBAC — roles / permissions
# ---------------------------------------------------------------------------

# Association table: users <-> roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", SafeUuid(), ForeignKey("users.id"), primary_key=True),  # type: ignore[var-annotated]
    Column("role_id", SafeUuid(), ForeignKey("roles.id"), primary_key=True),  # type: ignore[var-annotated]
)


class Role(TimestampMixin, Base):
    """Authoritative role definition.  RBAC decisions are read from here,
    not from the ``users.role`` legacy column."""
    __tablename__ = "roles"

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, default=list)  # e.g. ["cases:read", "cases:write", "audit:read"]

    users = relationship("User", secondary=user_roles, back_populates="roles", lazy="selectin")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    # Legacy string column kept for JWT backward-compat; RBAC source-of-truth
    # is the users -> user_roles -> roles graph.
    role = Column(String(50), nullable=False, default="officer")
    is_active = Column(Boolean, default=True)

    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")


class VerificationCase(TimestampMixin, Base):
    __tablename__ = "verification_cases"
    __table_args__ = (Index("ix_case_status_created", "status", "created_at"),)

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    case_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="in_review", index=True)
    risk_level = Column(String(20), nullable=False, default="unknown", index=True)
    risk_score = Column(Float, default=0.0)
    created_by = Column(SafeUuid(), ForeignKey("users.id"))  # type: ignore[var-annotated]
    description = Column(Text)
    document_hash = Column(String(64))  # SHA-256
    case_metadata = Column(JSON, default=dict)

    # Relationships
    documents = relationship("DocumentRecord", back_populates="case", cascade="all, delete-orphan")
    checks = relationship("VerificationCheck", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="case")


class DocumentRecord(TimestampMixin, Base):
    __tablename__ = "document_records"

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    case_id = Column(SafeUuid(), ForeignKey("verification_cases.id"))  # type: ignore[var-annotated]
    document_type = Column(String(50), index=True)
    country = Column(String(2))
    document_number = Column(String(50))
    storage_key = Column(String(255))  # MinIO key (original)
    original_key = Column(String(255))  # sanitized original object key
    processed_key = Column(String(255))  # OCR-ready processed object key
    preview_key = Column(String(255))  # lightweight preview object key
    original_filename = Column(String(255))
    status = Column(String(30), default="UPLOADED", index=True)
    processing_error = Column(Text)
    preprocess_metadata = Column(JSON, default=dict)
    content_hash = Column(String(64), unique=True, index=True)  # SHA-256
    mime_type = Column(String(100))
    file_size = Column(Integer)
    quality_score = Column(Float, default=0.0)
    ocr_data = Column(JSON, default=dict)
    mrz_data = Column(JSON, default=dict)
    forensic_data = Column(JSON, default=dict)
    extracted_fields = Column(JSON, default=dict)
    verification_data = Column(JSON, default=dict)
    classification_data = Column(JSON, default=dict)
    ocr_extracted_fields = Column(JSON, default=dict)

    case = relationship("VerificationCase", back_populates="documents")


class VerificationCheck(TimestampMixin, Base):
    __tablename__ = "verification_checks"
    __table_args__ = (Index("ix_check_case_type", "case_id", "check_type"),)

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    case_id = Column(SafeUuid(), ForeignKey("verification_cases.id"))  # type: ignore[var-annotated]
    check_type = Column(String(50), nullable=False)  # mrz_validation, ocr_cross_check, face_match, etc.
    status = Column(String(20), nullable=False, default="pending")  # passed, failed, warning, pending
    detail = Column(JSON, default=dict)
    output = Column(JSON, default=dict)

    case = relationship("VerificationCase", back_populates="checks")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SafeUuid(), ForeignKey("verification_cases.id")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(SafeUuid())
    actor_role: Mapped[Optional[str]] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    previous_hash: Mapped[Optional[str]] = mapped_column(
        String(64)
    )  # SHA-256 of previous entry (tamper-evident chain)
    current_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of this entry
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    case = relationship("VerificationCase", back_populates="audit_logs")


class RegistryEntry(TimestampMixin, Base):
    __tablename__ = "registry_entries"
    __table_args__ = (
        UniqueConstraint("document_number", "registry_type", name="uq_registry_doc_type"),
        Index("ix_registry_doc_number", "document_number"),
    )

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    registry_type = Column(String(50), nullable=False)  # police, immigration, blacklist
    document_number = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)  # valid, reported_stolen, blacklisted, watchlist, expired
    holder_name = Column(String(255))
    issuing_country = Column(String(2))
    additional_data = Column(JSON, default=dict)


class StoredFace(TimestampMixin, Base):
    __tablename__ = "stored_faces"
    __table_args__ = (Index("ix_face_identity_id", "identity_id"),)

    id = Column(SafeUuid(), primary_key=True, default=uuid.uuid4)  # type: ignore[var-annotated]
    identity_id = Column(String(100), nullable=False, index=True)  # synthetic identity ID
    embedding = Column(JSON, nullable=False)  # face embedding vector
    source_note = Column(String(255))
    is_synthetic = Column(Boolean, default=True)
