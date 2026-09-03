"""Tests for image quality assessment and preprocessing."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from app.pipeline.docktype import identify_document_type
from app.pipeline.preprocess import preprocess_document
from app.pipeline.quality import assess_image_quality


def _make_gray_image(w=1200, h=900, value=128):
    img = np.full((h, w, 3), value, dtype=np.uint8)
    return img


def test_quality_empty_image():
    result = assess_image_quality(None)
    assert result["overall_score"] == 0.0
    assert result["quality_label"] == "POOR"


def test_quality_good_synthetic_image():
    img = _make_gray_image()
    # Add some texture so Laplacian variance is positive
    img[100:200, 100:200] = 255
    img[300:400, 400:500] = 0
    result = assess_image_quality(img)
    assert 0.0 <= result["overall_score"] <= 1.0
    for key in ("resolution_score", "sharpness_score", "brightness_score", "contrast_score"):
        assert 0.0 <= result[key] <= 1.0


def test_quality_scores_are_bounded():
    img = _make_gray_image(100, 100, 200)
    result = assess_image_quality(img)
    assert result["overall_score"] <= 1.0


def test_preprocess_stages_default():
    img = _make_gray_image()
    processed = preprocess_document(img)
    assert "deskew" in processed["stages_applied"]
    assert processed["gray"].shape == img.shape[:2]


def test_preprocess_turnoff_stages():
    img = _make_gray_image()
    processed = preprocess_document(img, {"deskew": False, "denoise": False, "contrast": False})
    assert processed["stages_applied"] == []


def test_identify_document_type_passport():
    img = _make_gray_image(1500, 1200)
    # Add MRZ-like dense region at bottom
    img[900:, :] = np.random.randint(0, 2, (300, 1500, 3)) * 255
    result = identify_document_type(img, ocr_text="PASSPORT", mrz_parsed=True)
    assert result["document_type"] == "passport"


def test_identify_document_type_unknown():
    img = _make_gray_image(100, 100)
    result = identify_document_type(img, ocr_text="", mrz_parsed=False)
    assert result["document_type"] == "unknown"
