"""Unit tests for document ingestion validation and sanitization."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
import numpy as np
import pytest

from app.services.ingestion import (
    DocumentUploadError,
    sanitize_filename,
    validate_upload,
    verify_image_integrity,
)


def _png_bytes():
    img = np.full((300, 400, 3), 200, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_sanitize_filename_removes_path_and_injection_chars():
    # Path components are stripped down to the safe basename.
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert "/" not in sanitize_filename("a/b/c.jpg")
    assert "\\" not in sanitize_filename("a\\b\\c.png")
    assert "../../../etc/passwd" not in sanitize_filename("a/b/c/d.png")
    # Unsafe shell chars are neutralized.
    assert "$" not in sanitize_filename("x$();rm -rf.jpg")
    assert sanitize_filename("") == "document"
    assert sanitize_filename(None) == "document"


def test_validate_upload_accepts_valid_jpeg():
    mime = validate_upload("scan.jpg", "image/jpeg", 1000)
    assert mime == "image/jpeg"


def test_validate_upload_mime_extension_mismatch():
    with pytest.raises(DocumentUploadError) as e:
        validate_upload("scan.jpg", "image/png", 1000)
    assert e.value.status_code == 415


def test_validate_upload_rejects_unsupported_mime():
    with pytest.raises(DocumentUploadError) as e:
        validate_upload("doc.gif", "image/gif", 1000)
    assert e.value.status_code == 415


def test_validate_upload_rejects_empty_and_oversized():
    with pytest.raises(DocumentUploadError):
        validate_upload("x.jpg", "image/jpeg", 0)
    # Oversize uses the configured limit (20MB).
    with pytest.raises(DocumentUploadError) as e:
        validate_upload("x.jpg", "image/jpeg", 21 * 1024 * 1024)
    assert e.value.status_code == 413


def test_verify_image_integrity_rejects_garbage_bytes():
    with pytest.raises(DocumentUploadError):
        verify_image_integrity(b"this is definitely not an image")
    with pytest.raises(DocumentUploadError):
        verify_image_integrity(b"")


def test_verify_image_integrity_accepts_png_and_returns_canonical_mime():
    data = _png_bytes()
    image, mime = verify_image_integrity(data)
    assert image is not None
    assert mime == "image/jpeg"  # normalized for downstream storage


def test_pdf_is_allowed_but_not_image_preprocessed():
    # PDFs pass validation (stored) but are not image-decodable.
    mime = validate_upload("passport.pdf", "application/pdf", 2048)
    assert mime == "application/pdf"
