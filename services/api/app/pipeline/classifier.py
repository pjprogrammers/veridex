"""Document classifier interface.

Defines the abstract ``DocumentClassifier`` contract and the
``ClassificationResult`` data structure.  Implementations may use
heuristics, lightweight ML models, or cloud APIs — the interface
remains identical so callers never need to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ClassificationResult:
    """Structured output of a document classification step.

    Attributes:
        document_type: Normalised type label, e.g. ``"passport"``,
            ``"visa"``, ``"national_id"``, ``"drivers_license"``,
            or ``"unknown"``.
        confidence: Float in [0.0, 1.0].  A score of 0.0 means the
            classifier could not determine the type.  No guarantee of
            calibration — interpret relative to other results from the
            same classifier.
        method: Short identifier for the classification method used,
            e.g. ``"heuristic"``, ``"yolo_v8"``, ``"mobilenet_v3"``.
        template_id: Optional template or model variant identifier.
            Useful for A/B testing or rollback; ``None`` when not
            applicable.
        warnings: Human-readable flags raised during classification
            (e.g. ``"low_quality_image"``).  Empty list when clean.
    """

    document_type: str = "unknown"
    confidence: float = 0.0
    method: str = ""
    template_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "document_type": self.document_type,
            "confidence": round(self.confidence, 4),
            "method": self.method,
            "template_id": self.template_id,
            "warnings": list(self.warnings),
        }


class DocumentClassifier(ABC):
    """Abstract base for document-type classifiers.

    Subclass this to implement heuristic, ML, or cloud-based
    classification.  The ``classify`` method receives a decoded BGR
    image and returns a ``ClassificationResult``.

    Example::

        classifier = HeuristicClassifier()
        result = classifier.some_method(image)
        print(result.document_type, result.confidence)
    """

    @abstractmethod
    def classify(
        self,
        image: np.ndarray,
        *,
        ocr_text: str = "",
        preprocess_metadata: dict | None = None,
    ) -> ClassificationResult:
        """Classify the document type from a decoded BGR image.

        Args:
            image: Decoded BGR image array (H, W, 3).
            ocr_text: Optional pre-extracted OCR text.  When provided,
                the classifier may use textual cues to improve accuracy.
            preprocess_metadata: Optional metadata from the preprocessing
                step (quality scores, dimensions, etc.).

        Returns:
            A ``ClassificationResult`` with the detected type,
            confidence, method used, and any warnings.
        """
