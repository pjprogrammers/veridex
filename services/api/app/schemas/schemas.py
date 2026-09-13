"""VERIDEX API - Pydantic Schemas"""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ---- Auth Schemas ----
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    role: Optional[str] = "officer"


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ---- Verification Schemas ----
class VerificationRequest(BaseModel):
    case_description: Optional[str] = None
    verify_face_against: Optional[str] = None  # identity to compare face against
    check_registry: bool = True
    perform_forensics: bool = True
    scenario: Optional[str] = None  # static demo scenario key (SIH prototype)


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    case_id: uuid.UUID
    document_type: str
    storage_key: str
    content_hash: str
    quality_score: float
    message: str


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]


class RiskAssessment(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    level: RiskLevel
    factors: list[str]
    explanation: str
    recommendations: list[str]


# ---- Health Schemas ----
class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "error"]
    version: str
    services: dict[str, str]
    timestamp: datetime


# ---- Audit Schemas ----
class AuditEntryResponse(BaseModel):
    id: int
    case_id: Optional[uuid.UUID]
    action: str
    actor_id: Optional[uuid.UUID]
    actor_role: Optional[str]
    timestamp: datetime
    previous_hash: Optional[str]
    current_hash: str
    payload: dict

    class Config:
        from_attributes = True
