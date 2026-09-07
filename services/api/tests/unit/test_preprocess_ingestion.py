"""Unit tests for Phase 3 document preprocessing functions."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
import numpy as np

from app.pipeline.preprocess import (
    decode_image,
    detect_document_boundary,
    encode_jpeg,
    normalize_resolution,
    perspective_crop,
    run_ingestion_preprocess,
)


def _make_document_image(w=2000, h=1500, border=60):
    """Synthetic passport-like image scannable by boundary detection."""
    img = np.full((h, w, 3), 245, dtype=np.uint8)
    # Inner document rectangle (light grey) against a darker background.
    cv2.rectangle(img, (border, border), (w - border, h - border), (200, 200, 200), -1)
    # Simulated MRZ dense lines near the bottom.
    for y in range(h - 240, h - 60, 28):
        cv2.rectangle(img, (border + 40, y), (w - border - 40, y + 14), (20, 20, 20), -1)
    # Simulated portrait box.
    cv2.rectangle(img, (border + 90, border + 90), (border + 420, border + 520), (120, 120, 120), -1)
    return img


def test_decode_image_success():
    img = _make_document_image()
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    decoded = decode_image(buf.tobytes())
    assert decoded is not None
    assert decoded.shape[0] == img.shape[0]
    assert decoded.shape[1] == img.shape[1]


def test_decode_image_rejects_corrupt_data():
    assert decode_image(b"") is None
    assert decode_image(b"not a real image at all") is None
    # Truncated JPEG header without enough data.
    corrupted = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8
    assert decode_image(corrupted) is None


def test_encode_jpeg_roundtrip():
    img = _make_document_image()
    data = encode_jpeg(img, quality=90)
    assert isinstance(data, bytes) and len(data) > 100
    decoded = decode_image(data)
    assert decoded is not None


def test_detect_document_boundary_finds_rectangle():
    img = _make_document_image()
    pts, confidence = detect_document_boundary(img)
    assert pts is not None
    assert 0.0 <= confidence <= 1.0
    # Corner points should roughly match the document rectangle.
    xs = pts[:, 0]
    ys = pts[:, 1]
    assert min(xs) <= 500
    assert max(xs) >= 1500
    assert min(ys) <= 500
    assert max(ys) >= 1000


def test_perspective_crop_maintains_size():
    img = _make_document_image()
    cropped, confidence = perspective_crop(img)
    assert confidence > 0.0
    # Cropped image should be no larger than the original frame.
    assert cropped.shape[0] <= img.shape[0]
    assert cropped.shape[1] <= img.shape[1]


def test_normalize_resolution_downscales_large_images():
    img = _make_document_image(w=4000, h=3000)
    out = normalize_resolution(img, target_width=2000)
    assert out.shape[1] == 2000
    ratio = 2000 / 4000
    assert abs(out.shape[0] - int(3000 * ratio)) <= 1


def test_run_ingestion_preprocess_returns_separate_outputs_and_metadata():
    img = _make_document_image()
    result = run_ingestion_preprocess(img)

    # Three outputs are kept separate; original untouched.
    assert result["original"] is img
    assert not np.array_equal(result["original"], result["processed"])
    assert result["preview"].shape[1] <= result["processed"].shape[1]

    meta = result["metadata"]
    assert meta["width"] == result["processed"].shape[1]
    assert meta["height"] == result["processed"].shape[0]
    assert "rotation" in meta
    assert 0.0 <= meta["quality_score"] <= 1.0
    assert 0.0 <= meta["blur_score"] <= 1.0
    assert 0.0 <= meta["brightness_score"] <= 1.0
    assert 0.0 <= meta["document_boundary_confidence"] <= 1.0
    assert "stages_applied" in meta
