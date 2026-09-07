"""Heuristic document-type classifier.

Deterministic, locally-run classifier that works without ML models or
cloud APIs.  Uses three observable image properties:

1. **Aspect ratio** — passport (ID-3) ≈ 1.25:1, CR80/ID-1 ≈ 1.6:1,
   visa-like ≈ 1.3–1.4:1.
2. **MRZ zone** — dense text rows at the bottom indicate passport, ID,
   or visa with machine-readable data.
3. **Text cues** — header keywords (e.g. "PASSPORT", "VISA") when OCR
   text is provided.

The classifier is designed so the ``DocumentClassifier`` interface can
later be swapped for a YOLO/EfficientNet/MobileNet implementation
without touching callers.

Confidence is computed from weighted signal contributions — no
fabricated scores.  When fewer signals are available (e.g. no OCR
text), the remaining signals are re-weighted proportionally.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.classifier import ClassificationResult, DocumentClassifier

# Supported document types (must stay aligned with the API contract).
_PASSPORT = "passport"
_VISA = "visa"
_NATIONAL_ID = "national_id"
_DRIVERS_LICENSE = "drivers_license"
_UNKNOWN = "unknown"

_DOC_TYPES = [_PASSPORT, _VISA, _NATIONAL_ID, _DRIVERS_LICENSE]

# Signal weights — must sum to 1.0.
_W_ASPECT = 0.40
_W_MRZ = 0.30
_W_TEXT = 0.30

# Minimum confidence to avoid a false-positive classification.
_MIN_CONFIDENCE = 0.25

# ------------------------------------------------------------------
# Aspect-ratio signal
# ------------------------------------------------------------------

# (type, ideal_ratio, tolerance)
# ratio = max(w,h) / min(w,h); ideal values are midpoints.
_AR_PROFILES: list[tuple[str, float, float]] = [
    (_PASSPORT, 1.25, 0.18),       # 1.07 – 1.43
    (_NATIONAL_ID, 1.58, 0.18),     # 1.40 – 1.76
    (_DRIVERS_LICENSE, 1.58, 0.20), # 1.38 – 1.78 (overlaps ID)
    (_VISA, 1.38, 0.12),            # 1.26 – 1.50
]


def _aspect_ratio_scores(w: int, h: int) -> dict[str, float]:
    """Score each document type by how well the image aspect ratio fits."""
    if w <= 0 or h <= 0:
        return {t: 0.0 for t in _DOC_TYPES}
    ratio = max(w, h) / min(w, h)
    scores: dict[str, float] = {}
    for doc_type, ideal, tol in _AR_PROFILES:
        dist = abs(ratio - ideal)
        if dist <= tol:
            scores[doc_type] = max(0.0, 1.0 - (dist / tol))
        else:
            scores[doc_type] = 0.0
    return scores


# ------------------------------------------------------------------
# MRZ-zone signal
# ------------------------------------------------------------------


def _mrz_zone_scores(image: np.ndarray) -> dict[str, float]:
    """Detect MRZ zone presence and return type-specific scores.

    An MRZ zone strongly indicates passport, visa, or national ID
    (all three commonly carry MRZ).  Driving licences rarely have MRZ.
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except cv2.error:
        return {t: 0.0 for t in _DOC_TYPES}

    h, w = gray.shape
    if h < 20 or w < 20:
        return {t: 0.0 for t in _DOC_TYPES}

    bottom = gray[int(h * 0.75):, :]
    if bottom.size == 0:
        return {t: 0.0 for t in _DOC_TYPES}

    _, binary = cv2.threshold(bottom, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    density = float(np.mean(binary > 0))

    if density < 0.05:
        # No MRZ zone — no document type gets a bonus.
        return {t: 0.0 for t in _DOC_TYPES}

    if density < 0.08:
        score = 0.5
    else:
        score = 1.0

    return {
        _PASSPORT: score * 1.0,
        _VISA: score * 0.8,
        _NATIONAL_ID: score * 0.9,
        _DRIVERS_LICENSE: 0.0,
    }


# ------------------------------------------------------------------
# Text-cue signal
# ------------------------------------------------------------------

_TEXT_CUES: dict[str, list[str]] = {
    _PASSPORT: ["PASSPORT", "REISEPASS", "PASSEPORT", "PASAPORTE"],
    _VISA: ["VISA", "VISAS"],
    _NATIONAL_ID: [
        "NATIONAL IDENTIFICATION",
        "IDENTITY CARD",
        "IDENTIFICATION CARD",
        "CARTE D'IDENTIT",
        "DNI",
        "AUSWEIS",
    ],
    _DRIVERS_LICENSE: [
        "DRIVING LICENCE",
        "DRIVER'S LICENSE",
        "DRIVING LICENSE",
        "PERMIS DE CONDUIRE",
        "FUHRERSCHEIN",
    ],
}


def _text_signal_scores(ocr_text: str) -> tuple[dict[str, float], list[str]]:
    """Score document types by header text cues; returns (scores, warnings)."""
    scores = {t: 0.0 for t in _DOC_TYPES}
    warnings: list[str] = []
    if not ocr_text:
        return scores, warnings

    upper = ocr_text.upper()
    cues_found = 0
    for doc_type, cues in _TEXT_CUES.items():
        matched = sum(1 for cue in cues if cue in upper)
        if matched > 0:
            scores[doc_type] = min(1.0, matched * 0.5)
            cues_found += 1

    if cues_found > 1:
        warnings.append("conflicting_text_cues")
    return scores, warnings


# ------------------------------------------------------------------
# Image-quality heuristic
# ------------------------------------------------------------------


def _assess_quality(image: np.ndarray) -> tuple[float, list[str]]:
    """Quick quality assessment; returns (quality_score, warnings)."""
    warnings: list[str] = []
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except cv2.error:
        return 0.0, ["image_decode_error"]

    h, w = gray.shape
    if h == 0 or w == 0:
        return 0.0, ["empty_image"]

    # Resolution score (ideal width 1200+).
    res_score = min(w / 1200.0, 1.0)

    # Sharpness (variance of Laplacian).
    vol = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharp_score = min(vol / 600.0, 1.0)

    # Brightness (ideal around 128).
    mean_b = float(np.mean(gray))
    bright_score = max(0.0, 1.0 - abs(mean_b - 128.0) / 128.0)

    quality = 0.4 * res_score + 0.4 * sharp_score + 0.2 * bright_score

    if res_score < 0.3:
        warnings.append("low_resolution")
    if sharp_score < 0.2:
        warnings.append("blurry_image")
    if bright_score < 0.3:
        warnings.append("poor_lighting")

    return quality, warnings


# ------------------------------------------------------------------
# Classifier
# ------------------------------------------------------------------


class HeuristicClassifier(DocumentClassifier):
    """Deterministic, locally-run document-type classifier.

    Works without ML models or cloud APIs.  Implements the
    ``DocumentClassifier`` interface so it can be replaced with an
    ML-based classifier without changing callers.
    """

    METHOD = "heuristic"
    TEMPLATE_ID = "heuristic_v1"

    def classify(
        self,
        image: np.ndarray,
        *,
        ocr_text: str = "",
        preprocess_metadata: dict | None = None,
    ) -> ClassificationResult:
        """Classify the document type using layout, MRZ, and text cues."""
        warnings: list[str] = []

        # Image quality check.
        quality, quality_warnings = _assess_quality(image)
        warnings.extend(quality_warnings)

        # Signal: aspect ratio.
        h, w = image.shape[:2]
        ar_scores = _aspect_ratio_scores(w, h)

        # Signal: MRZ zone.
        mrz_scores = _mrz_zone_scores(image)

        # Signal: text cues.
        text_scores, text_warnings = _text_signal_scores(ocr_text)
        warnings.extend(text_warnings)

        # Determine available signals and re-weight accordingly.
        has_text = any(v > 0 for v in text_scores.values())
        if has_text:
            weights = {_PASSPORT: _W_ASPECT, _VISA: _W_ASPECT,
                       _NATIONAL_ID: _W_ASPECT, _DRIVERS_LICENSE: _W_ASPECT}
            mrz_w = _W_MRZ
            text_w = _W_TEXT
        else:
            # Redistribute text weight proportionally.
            redistribute = _W_TEXT / (_W_ASPECT + _W_MRZ)
            weights = {t: _W_ASPECT * (1 + redistribute) for t in _DOC_TYPES}
            mrz_w = _W_MRZ * (1 + redistribute)
            text_w = 0.0

        # Aggregate scores per document type.
        type_scores: dict[str, float] = {}
        for doc_type in _DOC_TYPES:
            s = (weights[doc_type] * ar_scores[doc_type]
                 + mrz_w * mrz_scores[doc_type]
                 + text_w * text_scores[doc_type])
            type_scores[doc_type] = round(s, 4)

        best_type = max(type_scores, key=type_scores.get)  # type: ignore[arg-type]
        best_score = type_scores[best_type]
        total = sum(type_scores.values())
        relative_confidence = best_score / total if total > 0 else 0.0
        # Blend with absolute signal strength so weak single-signal
        # results don't produce misleadingly high confidence.
        confidence = 0.65 * relative_confidence + 0.35 * best_score

        if best_score == 0 or confidence < _MIN_CONFIDENCE:
            return ClassificationResult(
                document_type=_UNKNOWN,
                confidence=round(confidence, 4),
                method=self.METHOD,
                template_id=self.TEMPLATE_ID,
                warnings=warnings,
            )

        return ClassificationResult(
            document_type=best_type,
            confidence=round(confidence, 4),
            method=self.METHOD,
            template_id=self.TEMPLATE_ID,
            warnings=warnings,
        )
