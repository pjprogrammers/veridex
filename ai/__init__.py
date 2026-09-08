"""VERIDEX — AI / CV layer.

Two independent AI operations, both producing evidence rather than decisions:

* ``run_ocr(document_image)``       — PaddleOCR document OCR + field/MRZ extraction.
* ``run_face_verification(...)``    — InsightFace face-to-face similarity.

The AI layer performs no business-risk classification (no CLEAR/REVIEW/ALERT).
Those belong to the downstream evidence/risk engine.
"""
from __future__ import annotations

import numpy as np

from ai.config import (
    FACE_MATCH_THRESHOLD,
    INSIGHTFACE_VERSION,
    ONNXRUNTIME_VERSION,
    PADDLEOCR_VERSION,
    PADDLEPADDLE_VERSION,
)
from ai.errors import error_for
from ai.face.engine import get_face_engine
from ai.face.schemas import FaceVerificationResult
from ai.ocr.engine import get_ocr_engine, process_document
from ai.ocr.schemas import OCREngineResult

__version__ = "0.1.0"

__all__ = [
    "AIStack",
    "FaceVerificationResult",
    "OCREngineResult",
    "get_face_engine",
    "get_ocr_engine",
    "process_document",
    "run_face_verification",
    "run_ocr",
]


class AIStack:
    """Describe the pinned AI stack exposed by this layer."""

    name = "veridex-ai"
    components = {
        "python": "3.11",
        "paddleocr": PADDLEOCR_VERSION,
        "paddlepaddle": PADDLEPADDLE_VERSION,
        "insightface": INSIGHTFACE_VERSION,
        "onnxruntime": ONNXRUNTIME_VERSION,
    }

    @classmethod
    def describe(cls) -> dict:
        return {"name": cls.name, "version": __version__, "components": cls.components}


def run_ocr(
    image: np.ndarray | bytes | str,
    *,
    document_type: str = "generic",
    engine=None,
) -> OCREngineResult:
    """Run the full OCR pipeline (preprocess -> PaddleOCR -> fields -> MRZ).

    This is the internal ``/ocr`` operation exposed by the AI service.
    """
    ocr_engine = engine or get_ocr_engine()
    return process_document(image, document_type=document_type, engine=ocr_engine)


def run_face_verification(
    document_image: np.ndarray,
    live_image: np.ndarray,
    *,
    threshold: float | None = None,
    engine=None,
) -> FaceVerificationResult:
    """Verify a document portrait against a live/user face.

    This is the internal ``/face/verify`` operation exposed by the AI service.
    """
    face_engine = engine or get_face_engine()
    try:
        return face_engine.verify(document_image, live_image, threshold=threshold)
    except Exception as exc:
        return FaceVerificationResult(
            face_detected_document=False,
            face_detected_live=False,
            document_face_count=0,
            live_face_count=0,
            document_face_quality=None,
            live_face_quality=None,
            similarity=None,
            threshold=(
                float(threshold)
                if threshold is not None
                else FACE_MATCH_THRESHOLD
            ),
            result="INCONCLUSIVE",
            error=error_for(exc).code,
            error_detail=error_for(exc).detail,
        )
