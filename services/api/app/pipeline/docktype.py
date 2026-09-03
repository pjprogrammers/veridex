"""Document type identification.

Identifies the type of travel/identity document from its visual layout and
text cues. Uses deterministic heuristics (aspect ratio, MRZ presence, header
text). Returns a normalized document type.
"""
import cv2
import numpy as np

# Normalized document types
PASSPORT = "passport"
NATIONAL_ID = "national_id"
DRIVERS_LICENSE = "drivers_license"
RESIDENCE_PERMIT = "residence_permit"
VISA = "visa"
UNKNOWN = "unknown"

DOCUMENT_TYPES = [PASSPORT, NATIONAL_ID, DRIVERS_LICENSE, RESIDENCE_PERMIT, VISA]

# Text cues that indicate document types
PASSPORT_CUES = ["PASSPORT", "REISEPASS", "PASSEPORT", "PASAPORTE"]
ID_CUES = [
    "NATIONAL IDENTIFICATION",
    "IDENTITY CARD",
    "IDENTIFICATION CARD",
    "CARTE D'IDENTIT",
    "DNI",
    "AUSWEIS",
]
LICENSE_CUES = [
    "DRIVING LICENCE",
    "DRIVER'S LICENSE",
    "DRIVING LICENSE",
    "LICENSE",
    "PERMIS DE CONDUIRE",
    "FUHRERSCHEIN",
]
RESIDENCE_CUES = ["RESIDENCE PERMIT", "RESIDENT PERMIT", "AUFENTHALTSTITEL"]
VISA_CUES = ["VISA", "VISAS"]


def _aspect_ratio_candidate(w: float, h: float) -> str | None:
    """Passports are ~1.25:1 (ID-3), ID cards ~1.6:1 (CR80/ID-1)."""
    if w <= 0 or h <= 0:
        return None
    ratio = max(w, h) / min(w, h)
    if 1.1 <= ratio <= 1.4:
        return PASSPORT
    if 1.5 <= ratio <= 1.75:
        return NATIONAL_ID
    return None


def _has_mrz_structure(image: np.ndarray) -> bool:
    """Detect the presence of an MRZ zone by looking for rows of closely
    spaced dark text near the bottom of the image."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    bottom = gray[int(h * 0.75):, :]
    if bottom.size == 0:
        return False
    _, binary = cv2.threshold(bottom, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Density of text pixels in the bottom region
    density = float(np.mean(binary > 0))
    # MRZ rows are dense with characters
    return density > 0.08


def _score_text_cues(ocr_text: str) -> dict[str, float]:
    """Score each document type based on text cues found in OCR output."""
    upper = ocr_text.upper()
    scores = {t: 0.0 for t in DOCUMENT_TYPES}

    for cue in PASSPORT_CUES:
        if cue in upper:
            scores[PASSPORT] += 1.0
    for cue in ID_CUES:
        if cue in upper:
            scores[NATIONAL_ID] += 1.0
    for cue in LICENSE_CUES:
        if cue in upper:
            scores[DRIVERS_LICENSE] += 1.0
    for cue in RESIDENCE_CUES:
        if cue in upper:
            scores[RESIDENCE_PERMIT] += 1.0
    for cue in VISA_CUES:
        if cue in upper:
            scores[VISA] += 1.0

    return scores


def identify_document_type(
    image: np.ndarray, ocr_text: str = "", mrz_parsed: bool = False
) -> dict:
    """Identify document type using layout, MRZ presence, and text cues.

    Returns the best candidate plus confidence and all candidate scores.
    """
    h, w = image.shape[:2]
    candidates: dict[str, float] = {t: 0.0 for t in DOCUMENT_TYPES}

    # Layout-based signal
    ar = _aspect_ratio_candidate(w, h)
    if ar:
        candidates[ar] += 2.0

    # MRZ presence strongly indicates passport (or ID with MRZ)
    has_mrz = _has_mrz_structure(image)
    if has_mrz and mrz_parsed:
        candidates[PASSPORT] += 3.0
    elif has_mrz:
        candidates[PASSPORT] += 1.0

    # Text cue signals
    text_scores = _score_text_cues(ocr_text)
    for doc_type, score in text_scores.items():
        if score > 0:
            candidates[doc_type] += 1.0 + score

    # Determine best and confidence
    best = max(candidates, key=lambda k: candidates[k])
    best_score = candidates[best]
    total = sum(candidates.values())
    confidence = best_score / total if total > 0 else 0.0
    if best_score == 0:
        best = UNKNOWN
        confidence = 0.0

    return {
        "document_type": best,
        "confidence": round(confidence, 4),
        "scores": candidates,
        "has_mrz_zone": has_mrz,
        "detected_type": best if best != UNKNOWN else None,
    }
