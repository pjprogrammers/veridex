"""VERIDEX AI — Structured OCR schemas.

Defines the exact JSON contract the OCR engine produces (see "OCR OUTPUT
CONTRACT" in the VERIDEX spec). Every field retains its confidence and, where
available, its original bounding box — the AI layer emits evidence, not
conclusions.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """A single detected/recognized text region.

    ``bbox`` preserves the original detected polygon coordinates, in order
    top-left -> top-right -> bottom-right -> bottom-left.
    """

    text: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[list[int]] = Field(default_factory=list)
    low_confidence: bool = False


class FieldValue(BaseModel):
    """A normalized, extracted document field with provenance."""

    value: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[list[int]] | None = None
    low_confidence: bool = False


class MRZCheckDigits(BaseModel):
    document_number: bool | None = None
    date_of_birth: bool | None = None
    expiry_date: bool | None = None
    composite: bool | None = None
    personal_number: bool | None = None


class MRZResult(BaseModel):
    """Parsed and check-digit-validated Machine Readable Zone."""

    detected: bool = False
    format: str = ""
    valid: bool = False
    lines: list[str] = Field(default_factory=list)
    check_digits: MRZCheckDigits = Field(default_factory=MRZCheckDigits)
    parsed_fields: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ConsistencyEntry(BaseModel):
    """Visual-OCR vs MRZ comparison for one field."""

    visual: str | None = None
    mrz: str | None = None
    match: bool | None = None


class PreprocessMetadata(BaseModel):
    width: int = 0
    height: int = 0
    rotation: float = 0.0
    stages_applied: list[str] = Field(default_factory=list)
    document_boundary_confidence: float = 0.0


class OCREngineResult(BaseModel):
    """Canonical structured output of one OCR request."""

    document_id: UUID = Field(default_factory=uuid4)
    engine: str = "paddleocr"
    engine_version: str = "3.7.0"
    image_width: int = 0
    image_height: int = 0
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    text_blocks: list[TextBlock] = Field(default_factory=list)
    mrz: MRZResult | None = None
    consistency: dict[str, ConsistencyEntry] = Field(default_factory=dict)
    overall_confidence: float = 0.0
    latency_ms: dict[str, float] = Field(default_factory=dict)
    error: str | None = None
    error_detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    @property
    def ocr_latency_ms(self) -> float:
        return float(self.latency_ms.get("ocr_latency_ms", 0.0))
