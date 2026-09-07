"""Unit tests for the heuristic document classifier."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
import numpy as np

from app.pipeline.classifier import ClassificationResult
from app.pipeline.heuristic_classifier import HeuristicClassifier


def _draw_text(img, text, pos, font_scale=1.0, thickness=2):
    """Draw uppercase text on an image (simulates header text)."""
    cv2.putText(
        img, text.upper(), pos,
        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (10, 10, 10), thickness,
        cv2.LINE_AA,
    )


def _make_passport_image(w=500, h=400):
    """Synthetic passport-like image: 1.25:1 aspect ratio, MRZ zone, header."""
    img = np.full((h, w, 3), 240, dtype=np.uint8)
    # Header text.
    _draw_text(img, "PASSPORT", (50, 60), font_scale=0.9, thickness=2)
    # Simulated MRZ zone (dense dark rectangles at bottom).
    for y in range(int(h * 0.78), h - 15, 18):
        cv2.rectangle(img, (30, y), (w - 30, y + 10), (20, 20, 20), -1)
    return img


def _make_visa_image(w=540, h=400):
    """Synthetic visa-like image: ~1.35:1 aspect ratio, MRZ zone, header."""
    img = np.full((h, w, 3), 235, dtype=np.uint8)
    _draw_text(img, "VISA", (180, 55), font_scale=1.0, thickness=2)
    for y in range(int(h * 0.78), h - 15, 18):
        cv2.rectangle(img, (30, y), (w - 30, y + 10), (25, 25, 25), -1)
    return img


def _make_national_id_image(w=640, h=400):
    """Synthetic national ID: ~1.6:1 aspect ratio, MRZ zone, header."""
    img = np.full((h, w, 3), 242, dtype=np.uint8)
    _draw_text(img, "IDENTITY CARD", (80, 55), font_scale=0.7, thickness=2)
    for y in range(int(h * 0.78), h - 15, 18):
        cv2.rectangle(img, (30, y), (w - 30, y + 10), (30, 30, 30), -1)
    return img


def _make_unknown_image(w=800, h=800):
    """Plain bright image with no MRZ, no text cues — should be UNKNOWN."""
    img = np.full((h, w, 3), 230, dtype=np.uint8)
    # Uniform brightness — no dark features at the bottom.
    return img


def _make_low_quality_image(w=80, h=60):
    """Tiny, blurry image to test low-quality warnings."""
    img = np.full((h, w, 3), 180, dtype=np.uint8)
    # Apply heavy blur.
    img = cv2.GaussianBlur(img, (21, 21), 10)
    return img


# ------------------------------------------------------------------
# ClassificationResult tests
# ------------------------------------------------------------------


def test_classification_result_to_dict():
    r = ClassificationResult(
        document_type="passport",
        confidence=0.87,
        method="heuristic",
        template_id="v1",
        warnings=["low_resolution"],
    )
    d = r.to_dict()
    assert d["document_type"] == "passport"
    assert d["confidence"] == 0.87
    assert d["method"] == "heuristic"
    assert d["template_id"] == "v1"
    assert d["warnings"] == ["low_resolution"]


def test_classification_result_defaults():
    r = ClassificationResult()
    assert r.document_type == "unknown"
    assert r.confidence == 0.0
    assert r.warnings == []


# ------------------------------------------------------------------
# HeuristicClassifier tests
# ------------------------------------------------------------------


def test_classify_passport():
    c = HeuristicClassifier()
    img = _make_passport_image()
    result = c.classify(img, ocr_text="PASSPORT")
    assert result.document_type == "passport"
    assert result.confidence > 0.3
    assert result.method == "heuristic"
    assert result.template_id == "heuristic_v1"


def test_classify_visa():
    c = HeuristicClassifier()
    img = _make_visa_image()
    result = c.classify(img, ocr_text="VISA")
    assert result.document_type == "visa"
    assert result.confidence > 0.3
    assert result.method == "heuristic"


def test_classify_national_id():
    c = HeuristicClassifier()
    img = _make_national_id_image()
    result = c.classify(img, ocr_text="IDENTITY CARD")
    assert result.document_type == "national_id"
    assert result.confidence > 0.3
    assert result.method == "heuristic"


def test_classify_unknown_returns_unknown():
    c = HeuristicClassifier()
    img = _make_unknown_image()
    result = c.classify(img)
    assert result.document_type == "unknown"
    assert result.confidence < 0.4


def test_classify_low_quality_has_warnings():
    c = HeuristicClassifier()
    img = _make_low_quality_image()
    result = c.classify(img)
    assert "low_resolution" in result.warnings or "blurry_image" in result.warnings


def test_classify_without_ocr_text():
    """Without OCR text, the classifier should still work (text weight redistributed)."""
    c = HeuristicClassifier()
    img = _make_passport_image()
    result = c.classify(img)  # no ocr_text
    # Should still detect passport via aspect ratio + MRZ zone.
    assert result.document_type == "passport"
    assert result.confidence > 0.2


def test_classify_empty_image():
    c = HeuristicClassifier()
    img = np.zeros((0, 0, 3), dtype=np.uint8)
    result = c.classify(img)
    assert result.document_type == "unknown"
    assert len(result.warnings) > 0


def test_classify_confidence_bounded():
    c = HeuristicClassifier()
    img = _make_passport_image()
    result = c.classify(img, ocr_text="PASSPORT")
    assert 0.0 <= result.confidence <= 1.0
