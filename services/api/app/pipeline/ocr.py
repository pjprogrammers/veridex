"""OCR engine abstraction.

`OCRResult` is the canonical output of any OCR engine. The actual engine is
selected by the `OCR_ENGINE` environment variable. The default is a
deterministic baseline for testing and offline use; PaddleOCR can be enabled
in the AI-enabled Docker image by setting `OCR_ENGINE=paddleocr`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from app.core.config import get_settings

settings = get_settings()


@dataclass
class OCRResult:
    """Normalized OCR output independent of the underlying engine."""

    full_text: str = ""
    words: list[dict] = field(default_factory=list)  # [{text, confidence, box}]
    confidence: float = 0.0
    engine: str = ""


@dataclass
class OCRExtractionResult:
    """Structured OCR output with extracted fields, raw text, and timing."""

    fields: list[dict] = field(default_factory=list)  # [{field_name, value, confidence, bbox}]
    raw_text: str = ""
    processing_time_ms: int = 0
    engine: str = ""

    def to_dict(self) -> dict:
        return {
            "fields": self.fields,
            "raw_text": self.raw_text,
            "processing_time_ms": self.processing_time_ms,
            "engine": self.engine,
        }


class BaseOCREngine(ABC):
    """Interface all OCR engines implement."""

    name: str

    @abstractmethod
    def run(self, image: np.ndarray) -> OCRResult:
        """Run OCR on a (preferably grayscale) numpy image."""

    def extract_text(self, image: np.ndarray) -> str:
        return self.run(image).full_text


class BaselineOCREngine(BaseOCREngine):
    """Deterministic fallback OCR.

    This is a placeholder that does no real character recognition but provides
    a consistent interface and a tokenizer that can be driven by known text
    (used by tests and the synthetic demo). Real OCR is provided by
    PaddleOCR when available.
    """

    name = "baseline"

    def run(self, image: np.ndarray) -> OCRResult:
        return OCRResult(
            full_text="",
            words=[],
            confidence=0.0,
            engine=self.name,
        )


def _load_paddle_engine():
    """Lazily import PaddleOCR. Importing it is heavy and fails without
    the dedicated AI image, so it is deferred until actually requested."""
    from app.pipeline.ocr_paddle import PaddleOCREngine

    return PaddleOCREngine(
        timeout=float(settings.OCR_TIMEOUT_SECONDS),
        max_retries=settings.OCR_MAX_RETRIES,
    )


def get_ocr_engine() -> BaseOCREngine:
    """Factory to create the configured OCR engine."""
    engine_name = settings.OCR_ENGINE
    if engine_name == "paddleocr":
        try:
            return _load_paddle_engine()
        except Exception:
            from app.core.logging import structlog

            structlog.get_logger().warning(
                "paddleocr_unavailable", fallback="baseline"
            )
            return BaselineOCREngine()
    return BaselineOCREngine()
