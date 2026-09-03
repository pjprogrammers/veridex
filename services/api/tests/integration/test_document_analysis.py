"""Integration tests for the document analysis pipeline using synthetic images."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pytest

from app.pipeline.ocr import BaselineOCREngine
from app.pipeline.pipeline import analyze_document, load_image


def _make_synthetic_document_image(w=2000, h=1500):
    """Create a synthetic document-like image (light background, dark border)."""
    img = np.full((h, w, 3), 245, dtype=np.uint8)
    # Border like a document frame
    cv2_import = __import__("cv2")
    cv2_import.rectangle(img, (20, 20), (w - 20, h - 20), (200, 200, 200), 3)
    # Text-like dark blocks
    for y in range(200, 400, 40):
        cv2_import.rectangle(img, (200, y), (700, y + 25), (40, 40, 40), -1)
    # Dense MRZ-like region at bottom
    for y in range(h - 200, h - 40, 30):
        cv2_import.rectangle(img, (100, y), (w - 100, y + 15), (0, 0, 0), -1)
    return img


def test_load_image_valid_bytes():
    import cv2
    img = _make_synthetic_document_image()
    ok, buf = cv2.imencode(".png", img)
    assert ok
    decoded = load_image(buf.tobytes())
    assert decoded.shape == img.shape


def test_load_image_invalid_bytes():
    with pytest.raises(ValueError):
        load_image(b"not an image")


def test_analyze_document_full_pipeline():
    img = _make_synthetic_document_image()
    analysis = analyze_document(img, ocr_engine=BaselineOCREngine())

    assert analysis.width == 2000
    assert analysis.height == 1500
    # Baseline OCR returns empty but pipeline should still produce structure
    assert analysis.ocr_engine == "baseline"
    assert 0.0 <= analysis.quality["overall_score"] <= 1.0
    # MRZ-like region should trigger MRZ zone detection
    assert "preprocessing_stages" in analysis.__dict__


def test_analyze_document_quality_keyes():
    img = _make_synthetic_document_image()
    analysis = analyze_document(img)
    assert "overall_score" in analysis.quality
    assert "quality_label" in analysis.quality
