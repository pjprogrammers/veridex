"""VERIDEX AI — Structured face schemas.

Contracts for detection, quality, embedding and face-to-face verification.
The verdict vocabulary is intentionally limited to what the AI layer can
actually prove (MATCH / NO_MATCH / INCONCLUSIVE / NO_FACE / MULTIPLE_FACES /
LOW_QUALITY). Business-risk decisions (CLEAR / REVIEW / ALERT) do not belong in
this layer.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Possible face-verification results (spec §15).
FACE_VERDICT = Literal["MATCH", "NO_MATCH", "INCONCLUSIVE", "NO_FACE", "MULTIPLE_FACES", "LOW_QUALITY"]

# Face-situation levels used between detector modules.
FACE_SITUATION = Literal["NO_FACE", "SINGLE_FACE", "MULTIPLE_FACES"]


class FaceDetection(BaseModel):
    """A single detected face."""

    bbox: list[int] = Field(default_factory=list)  # [x1, y1, x2, y2]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    landmarks: list[list[float]] = Field(default_factory=list)  # [[x, y], ...]
    quality: "FaceQuality | None" = None

    @field_validator("bbox")
    @classmethod
    def _four_coords(cls, v: list[int]) -> list[int]:
        if v and len(v) != 4:
            raise ValueError("bbox must be [x1, y1, x2, y2]")
        return v


class FaceQuality(BaseModel):
    """Face quality assessment for one detection (spec §12)."""

    score: float = Field(default=0.0, ge=0.0, le=1.0)
    blur: float = Field(default=0.0, ge=0.0, le=1.0)  # 1 = very blurry
    pose_ok: bool = True
    size_ok: bool = True
    exposure_ok: bool = True
    occlusion_ok: bool = True
    crop_complete: bool = True
    reasons: list[str] = Field(default_factory=list)


class FaceEmbedding(BaseModel):
    """An L2-normalized face embedding vector (never an image)."""

    vector: list[float] = Field(default_factory=list)
    dim: int = 0
    l2_norm: float = 0.0

    @field_validator("vector", mode="before")
    @classmethod
    def _coerce_vector(cls, v):
        if hasattr(v, "tolist"):
            return v.tolist()
        return v


class FaceVerificationResult(BaseModel):
    """Canonical face-to-face verification output (spec §15 / §17)."""

    face_detected_document: bool = False
    face_detected_live: bool = False
    document_face_count: int = 0
    live_face_count: int = 0
    document_face_quality: float | None = None
    live_face_quality: float | None = None
    similarity: float | None = None
    threshold: float = 0.55
    result: FACE_VERDICT = "INCONCLUSIVE"
    latency_ms: dict[str, float] = Field(default_factory=dict)
    error: str | None = None
    error_detail: str | None = None


FaceDetection.model_rebuild()
