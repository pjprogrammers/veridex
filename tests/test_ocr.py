"""Deterministic tests for the ai.ocr sub-package.

Preprocessing, spatial field extraction, MRZ cross-validation, OCR result
normalization, and the full document-ocr pipeline (using a synthetic fake
engine — no real PaddleOCR weights needed).
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.errors import InvalidInputError
from ai.ocr.engine import (
    OCREngineResult,
    PaddleOCREngine,
    get_ocr_engine,
    process_document,
)
from ai.ocr.mrz import compare_visual_mrz
from ai.ocr.parser import extract_fields, spatial_order
from ai.ocr.preprocess import (
    correct_orientation,
    correct_perspective,
    denoise_image,
    load_image,
    normalize_contrast,
    preprocess_for_ocr,
    resize_image,
    to_bgr,
    validate_image,
)
from ai.ocr.schemas import FieldValue, TextBlock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(w=600, h=400):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = 80
    return img


def _passport_blocks():
    """Synthetic text blocks for a passport visual zone (labels + values)."""
    return [
        TextBlock(text="SURNAME", confidence=0.9, bbox=[[30, 100], [120, 100], [120, 120], [30, 120]]),
        TextBlock(text="DOE", confidence=0.97, bbox=[[150, 100], [220, 100], [220, 120], [150, 120]]),
        TextBlock(text="GIVEN NAMES", confidence=0.88, bbox=[[30, 130], [140, 130], [140, 150], [30, 150]]),
        TextBlock(text="JOHN", confidence=0.95, bbox=[[150, 130], [210, 130], [210, 150], [150, 150]]),
        TextBlock(text="DATE OF BIRTH", confidence=0.85, bbox=[[30, 160], [180, 160], [180, 180], [30, 180]]),
        TextBlock(text="20 JAN 1999", confidence=0.92, bbox=[[200, 160], [330, 160], [330, 180], [200, 180]]),
        TextBlock(text="DOCUMENT NO", confidence=0.9, bbox=[[30, 200], [170, 200], [170, 220], [30, 220]]),
        TextBlock(text="P1234567", confidence=0.99, bbox=[[200, 200], [300, 200], [300, 220], [200, 220]]),
        TextBlock(text="NATIONALITY", confidence=0.88, bbox=[[30, 240], [160, 240], [160, 260], [30, 260]]),
        TextBlock(text="IND", confidence=0.93, bbox=[[200, 240], [260, 240], [260, 260], [200, 260]]),
        TextBlock(text="SEX", confidence=0.87, bbox=[[30, 270], [70, 270], [70, 290], [30, 290]]),
        TextBlock(text="M", confidence=0.96, bbox=[[200, 270], [230, 270], [230, 290], [200, 290]]),
    ]


class FakeOCREngine:
    name = "fake_ocr"
    version = "0.0.0"
    _blocks: list[TextBlock]

    def __init__(self, blocks: list[TextBlock]):
        self._blocks = blocks

    def recognize(self, image: np.ndarray) -> list[TextBlock]:
        return list(self._blocks)

    def warm(self):
        pass


# ===========================================================================
# PREPROCESSING
# ===========================================================================

def test_load_image_bytes_valid():
    img = _make_image()
    _, buf = cv2.imencode(".jpg", img)
    loaded = load_image(buf.tobytes())
    assert loaded is not None
    assert loaded.shape == (400, 600, 3)


def test_load_image_bytes_corrupt():
    assert load_image(b"\xff\xd8\xff\x00garbage") is None


def test_load_image_path_nonexistent():
    assert load_image("/tmp/ai_test_nonexistent.jpg") is None


def test_validate_image_none():
    with pytest.raises(InvalidInputError):
        validate_image(None)


def test_validate_image_too_small():
    with pytest.raises(InvalidInputError):
        validate_image(np.zeros((5, 5, 3), dtype=np.uint8))


def test_validate_image_4d():
    with pytest.raises(InvalidInputError):
        validate_image(np.zeros((100, 100, 3, 1), dtype=np.uint8))


def test_to_bgr_gray():
    gray = np.full((60, 60), 120, dtype=np.uint8)
    result = to_bgr(gray)
    assert result.ndim == 3
    assert result.shape[2] == 3
    np.testing.assert_array_equal(result[:, :, 0], 120)


def test_resize_image_no_resize_needed():
    img = _make_image(w=500, h=300)
    out = resize_image(img, max_width=2000)
    np.testing.assert_array_equal(out, img)


def test_resize_image_downscales():
    img = _make_image(w=3000, h=2000)
    out = resize_image(img, max_width=2000)
    assert out.shape[1] == 2000
    assert out.shape[0] == round(2000 * (2000 / 3000))


def test_correct_orientation_landscape():
    img = _make_image(w=1000, h=300)
    out, angle = correct_orientation(img)
    assert out.shape[1] >= out.shape[0]
    assert isinstance(angle, float)


def test_correct_orientation_square():
    img = _make_image(w=500, h=500)
    _, angle = correct_orientation(img)
    assert angle == 0.0


def test_denoise_smoke():
    img = _make_image(w=100, h=100)
    out = denoise_image(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_normalize_contrast_smoke():
    img = _make_image(w=100, h=100)
    out = normalize_contrast(img)
    assert out.shape == img.shape


def test_correct_perspective_no_change():
    img = _make_image(w=800, h=600)
    out, conf = correct_perspective(img)
    assert out.shape == img.shape


def test_preprocess_for_ocr_returns_metadata():
    img = _make_image(w=600, h=400)
    result = preprocess_for_ocr(img)
    assert result["preprocessed"] is not None
    assert result["original"] is not None
    assert result["metadata"]["width"] > 0
    assert isinstance(result["metadata"]["stages_applied"], list)


def test_preprocess_for_ocr_stages_options():
    img = _make_image(w=600, h=400)
    result = preprocess_for_ocr(img, {"contrast": False, "denoise": False})
    stages = result["metadata"]["stages_applied"]
    assert "contrast" not in stages
    assert "denoise" not in stages


def test_preprocess_original_untouched():
    img = _make_image(w=600, h=400)
    original_id = id(img)
    result = preprocess_for_ocr(img)
    assert id(result["original"]) != original_id


# ===========================================================================
# SPATIAL ORDER / FIELD EXTRACTION
# ===========================================================================

def test_spatial_order_top_to_bottom():
    blocks = [
        TextBlock(text="BOTTOM", confidence=0.9, bbox=[[10, 200], [200, 200], [200, 220], [10, 220]]),
        TextBlock(text="TOP", confidence=0.9, bbox=[[10, 10], [200, 10], [200, 30], [10, 30]]),
    ]
    rows = spatial_order(blocks)
    assert rows[0][0].text == "TOP"
    assert rows[1][0].text == "BOTTOM"


def test_spatial_order_left_to_right_in_row():
    blocks = [
        TextBlock(text="RIGHT", confidence=0.9, bbox=[[150, 10], [250, 10], [250, 30], [150, 30]]),
        TextBlock(text="LEFT", confidence=0.9, bbox=[[10, 10], [120, 10], [120, 30], [10, 30]]),
    ]
    rows = spatial_order(blocks)
    assert len(rows) == 1
    assert rows[0][0].text == "LEFT"
    assert rows[0][1].text == "RIGHT"


def test_spatial_order_empty():
    assert spatial_order([]) == []


def test_extract_fields_passport():
    blocks = _passport_blocks()
    fields = extract_fields(blocks, document_type="passport")
    assert "document_number" in fields
    assert "P1234567" in fields["document_number"].value.upper()
    assert fields["document_number"].confidence > 0
    assert "full_name" in fields
    assert "JOHN" in fields["full_name"].value.upper()
    assert "DOE" in fields["full_name"].value.upper()
    assert "date_of_birth" in fields
    assert "nationality" in fields
    assert fields["nationality"].confidence > 0


def test_extract_fields_confidence_flags():
    low = TextBlock(text="DOCUMENT NO", confidence=0.2, bbox=[[10, 10], [80, 10], [80, 25], [10, 25]])
    val = TextBlock(text="ABC123", confidence=0.3, bbox=[[100, 10], [200, 10], [200, 25], [100, 25]])
    fields = extract_fields([low, val], document_type="generic")
    assert "document_number" in fields
    assert fields["document_number"].low_confidence is True


# ===========================================================================
# MRZ CROSS-VALIDATION
# ===========================================================================

def test_compare_visual_mrz_all_match():
    visual = {
        "document_number": FieldValue(value="P1234567", confidence=0.99),
        "full_name": FieldValue(value="DOE JOHN", confidence=0.95),
        "date_of_birth": FieldValue(value="990120", confidence=0.93),
        "expiry_date": FieldValue(value="300101", confidence=0.91),
        "nationality": FieldValue(value="IND", confidence=0.90),
    }
    mrz = {
        "passport_number": "P1234567",
        "full_name": "DOE JOHN",
        "date_of_birth": "990120",
        "expiry_date": "300101",
        "nationality": "IND",
    }
    result = compare_visual_mrz(visual, mrz)
    for key, entry in result.items():
        assert entry.match is True, f"{key} should match"


def test_compare_visual_mrz_mismatch():
    visual = {"document_number": FieldValue(value="P9999999", confidence=0.99)}
    mrz = {"passport_number": "P1234567"}
    result = compare_visual_mrz(visual, mrz)
    assert result["passport_number"].match is False


def test_compare_visual_mrz_missing_visual():
    result = compare_visual_mrz({}, {"passport_number": "P1234567"})
    assert result["passport_number"].match is None


# ===========================================================================
# OCR RESULT NORMALIZATION (no real model)
# ===========================================================================

def test_normalize_result_empty():
    assert PaddleOCREngine.normalize_result(None) == []


def test_normalize_result_basic():
    fake = {
        "rec_texts": ["HELLO", "WORLD"],
        "rec_scores": [0.95, 0.9],
        "rec_boxes": [
            [[10, 10], [100, 10], [100, 30], [10, 30]],
            [[10, 40], [100, 40], [100, 60], [10, 60]],
        ],
    }
    blocks = PaddleOCREngine.normalize_result(fake)
    assert len(blocks) == 2
    assert blocks[0].text == "HELLO"
    assert blocks[0].confidence == pytest.approx(0.95)
    assert len(blocks[0].bbox) == 4


def test_normalize_result_empty_text_skipped():
    fake = {"rec_texts": ["", "OK"], "rec_scores": [0.9, 0.95], "rec_boxes": []}
    blocks = PaddleOCREngine.normalize_result(fake)
    assert len(blocks) == 1
    assert blocks[0].text == "OK"


# ===========================================================================
# FULL DOCUMENT OCR PIPELINE (synthetic)
# ===========================================================================

def test_process_document_full_pipeline():
    img = _make_image(w=600, h=400)
    blocks = _passport_blocks()
    engine = FakeOCREngine(blocks)
    result = process_document(img, document_type="passport", engine=engine)
    assert isinstance(result, OCREngineResult)
    assert result.succeeded
    assert result.error is None
    assert result.overall_confidence > 0
    assert len(result.text_blocks) == len(blocks)
    assert "document_number" in result.fields
    assert "latency_ms" in result.model_fields_set
    assert result.latency_ms.get("ocr_latency_ms", 0) >= 0
    assert result.latency_ms.get("total_latency_ms", 0) >= 0


def test_process_document_bytes_input():
    img = _make_image(w=600, h=400)
    _, buf = cv2.imencode(".jpg", img)
    engine = FakeOCREngine([])
    result = process_document(buf.tobytes(), engine=engine)
    assert result.succeeded


def test_process_document_invalid_bytes():
    engine = FakeOCREngine([])
    with pytest.raises(InvalidInputError):
        process_document(b"\x00\x01\x02", engine=engine)


def test_process_document_mrz_detected():
    from tests.test_mrz import _build_td3

    td3_lines = _build_td3()
    blocks = [
        TextBlock(text=td3_lines[0], confidence=0.91, bbox=[[10, 400], [300, 400], [300, 420], [10, 420]]),
        TextBlock(text=td3_lines[1], confidence=0.92, bbox=[[10, 422], [300, 422], [300, 442], [10, 442]]),
        TextBlock(text="SURNAME", confidence=0.9, bbox=[[30, 100], [120, 100], [120, 120], [30, 120]]),
        TextBlock(text="ERIKSSON", confidence=0.97, bbox=[[150, 100], [250, 100], [250, 120], [150, 120]]),
    ]
    img = _make_image(w=600, h=500)
    result = process_document(img, document_type="passport", engine=FakeOCREngine(blocks))
    assert result.mrz is not None
    assert result.mrz.detected is True
    assert result.mrz.valid is True
    assert result.consistency.get("passport_number") is not None


def test_engine_singleton():
    e1 = get_ocr_engine()
    e2 = get_ocr_engine()
    assert e1 is e2


# ---------------------------------------------------------------------------
# Real-world layout & recognition robustness
# ---------------------------------------------------------------------------

def test_extract_fields_metric_layout_label_above_value():
    """Metric passport pages print the label ABOVE its value, same column."""
    blocks = [
        TextBlock(text="NATIONALITY", confidence=0.99, bbox=[[60, 130], [210, 130], [210, 150], [60, 150]]),
        TextBlock(text="DOCUMENT NO", confidence=0.88, bbox=[[390, 130], [535, 130], [535, 150], [390, 150]]),
        TextBlock(text="SEX", confidence=0.9, bbox=[[700, 130], [745, 130], [745, 150], [700, 150]]),
        TextBlock(text="GBR", confidence=0.99, bbox=[[60, 175], [120, 175], [120, 195], [60, 195]]),
        TextBlock(text="P12345678", confidence=0.98, bbox=[[390, 175], [540, 175], [540, 195], [390, 195]]),
        TextBlock(text="M", confidence=0.97, bbox=[[700, 175], [728, 175], [728, 195], [700, 195]]),
        TextBlock(text="SURNAME", confidence=0.9, bbox=[[60, 230], [160, 230], [160, 250], [60, 250]]),
        TextBlock(text="SMITH", confidence=0.99, bbox=[[60, 270], [145, 270], [145, 290], [60, 290]]),
        TextBlock(text="GIVEN NAME", confidence=0.9, bbox=[[60, 310], [175, 310], [175, 330], [60, 330]]),
        TextBlock(text="JORDAN", confidence=0.99, bbox=[[60, 350], [150, 350], [150, 370], [60, 370]]),
        TextBlock(text="DATE OF BIRTH", confidence=0.9, bbox=[[60, 430], [235, 430], [235, 450], [60, 450]]),
        TextBlock(text="91-04-15", confidence=0.99, bbox=[[60, 470], [190, 470], [190, 490], [60, 490]]),
    ]
    fields = extract_fields(blocks, document_type="passport")
    assert fields["document_number"].value == "P12345678"
    assert fields["nationality"].value == "GBR"
    assert fields["sex"].value == "M"
    assert fields["surname"].value == "SMITH"
    assert fields["given_names"].value == "JORDAN"
    assert fields["full_name"].value == "SMITH JORDAN"
    assert fields["date_of_birth"].value == "910415"
    assert fields["document_number"].confidence > 0.9


def test_extract_fields_fullwidth_values_asciified():
    """OCR output often mixes fullwidth forms — values normalize to ASCII."""
    blocks = [
        TextBlock(text="ＳＵＲＮＡＭＥ", confidence=0.9, bbox=[[30, 100], [140, 100], [140, 120], [30, 120]]),
        TextBlock(
            text="ＪＯＲＤＡＮ",
            confidence=0.95,
            bbox=[[150, 100], [260, 100], [260, 120], [150, 120]],
        ),
        TextBlock(
            text="ＤＯＣＵＭＥＮＴ ＮＯ",
            confidence=0.9,
            bbox=[[30, 130], [200, 130], [200, 150], [30, 150]],
        ),
        TextBlock(
            text="Ｐ１２３４５６７８",
            confidence=0.98,
            bbox=[[210, 130], [340, 130], [340, 150], [210, 150]],
        ),
    ]
    fields = extract_fields(blocks, document_type="passport")
    assert fields["surname"].value == "JORDAN"
    assert fields["document_number"].value == "P12345678"


def test_normalize_result_polygon_boxes():
    """real CC (4,2) polygon boxes and flat rec_boxes become usable corners."""
    result = {
        "rec_texts": ["HELLO", "DOCUMENT NO"],
        "rec_scores": [0.99, 0.88],
        "rec_polys": [np.array([[1, 2], [101, 2], [101, 32], [1, 32]], dtype=int),
                      np.array([[200, 4], [320, 4], [320, 24], [200, 24]], dtype=int)],
    }
    blocks = PaddleOCREngine.normalize_result(result)
    assert len(blocks) == 2
    assert blocks[0].bbox == [[1, 2], [101, 2], [101, 32], [1, 32]]
    assert blocks[1].text == "DOCUMENT NO"
    assert not blocks[0].low_confidence

    flat = {
        "rec_texts": ["FLAT"],
        "rec_scores": [0.5],
        "rec_boxes": np.array([[10, 20, 210, 60]], dtype=int),
    }
    blocks = PaddleOCREngine.normalize_result(flat)
    assert blocks[0].bbox == [[10, 20], [210, 20], [210, 60], [10, 60]]


def test_normalize_result_skips_blank_text():
    result = {"rec_texts": ["KEEP", ""], "rec_scores": [0.9, 0.9],
              "rec_polys": [np.array([[0, 0], [9, 0], [9, 9], [0, 9]], dtype=int)] * 2}
    blocks = PaddleOCREngine.normalize_result(result)
    assert [b.text for b in blocks] == ["KEEP"]
