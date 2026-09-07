"""Document ingestion service.

Handles validation (MIME, extension, size, corrupt images), filename
sanitization, and storage of the original document plus its processed
and preview variants in separate MinIO objects. The original is never
overwritten.
"""
import re

import numpy as np
import structlog

from app.core.config import get_settings
from app.core.storage import delete_file, download_file, upload_file
from app.models.document_states import ALLOWED_PREPROCESS_MIME_TYPES
from app.pipeline.preprocess import decode_image, encode_jpeg

settings = get_settings()
logger = structlog.get_logger()

# Map declared MIME types to accepted extensions. Extension and MIME must
# agree; the actual decode is the source of truth for images.
MIME_TO_EXT = {
    "image/jpeg": {"jpg", "jpeg", "jpe"},
    "image/png": {"png"},
    "image/webp": {"webp"},
    "application/pdf": {"pdf"},
}

EXT_TO_MIME = {
    ext: mime
    for mime, exts in MIME_TO_EXT.items()
    for ext in exts
}

# MinIO object content types.
IMAGE_MIME = "image/jpeg"
PDF_MIME = "application/pdf"


class DocumentUploadError(Exception):
    """Raised for user-facing upload validation failures."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def sanitize_filename(filename: str | None) -> str:
    """Strip path separators and unsafe characters from a user-supplied name.

    Never executes or exposes the raw name; returns a safe basename.
    """
    if not filename:
        return "document"
    # Drop any path components.
    base = filename.replace("\\", "/").split("/")[-1]
    # Keep only safe characters.
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = base.strip("._")
    return base[:120] or "document"


def _detect_ext(filename: str | None) -> str:
    base = filename or ""
    if "." in base:
        return base.rsplit(".", 1)[-1].lower()
    return ""


def validate_upload(filename: str | None, mime_type: str | None, data_len: int) -> str:
    """Validate size, MIME, and extension consistency.

    Returns the canonical MIME type for storage. Raises DocumentUploadError.
    """
    if data_len == 0:
        raise DocumentUploadError("Empty file provided")
    if data_len > settings.max_upload_size_bytes:
        raise DocumentUploadError(
            f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB", status_code=413
        )

    mime = (mime_type or "").lower().strip()
    if mime not in ALLOWED_PREPROCESS_MIME_TYPES or mime not in MIME_TO_EXT:
        raise DocumentUploadError(f"Unsupported MIME type: {mime_type}", status_code=415)

    ext = _detect_ext(filename)
    if not ext or ext not in MIME_TO_EXT[mime]:
        raise DocumentUploadError(
            f"File extension '.{ext or 'none'}' does not match MIME type '{mime}'",
            status_code=415,
        )
    return mime


def verify_image_integrity(data: bytes) -> tuple[np.ndarray, str]:
    """Decode image bytes; raises DocumentUploadError for corrupt/mislabeled files.

    Returns (image, canonical_mime) where canonical_mime is 'image/jpeg'
    since we re-encode to a single normalized format for processed output.
    """
    image = decode_image(data)
    if image is None:
        raise DocumentUploadError(
            "File is not a valid image or is corrupted and cannot be decoded"
        )
    return image, IMAGE_MIME


def _safe_key_prefix(case_id: str | None, doc_id: str) -> str:
    if case_id:
        return f"cases/{case_id}/{doc_id}"
    return f"documents/{doc_id}"


def store_original(
    data: bytes,
    mime: str,
    doc_id: str,
    case_id: str | None = None,
    ext: str = "jpg",
) -> str:
    """Store the original upload as a distinct, read-only object."""
    base = _safe_key_prefix(case_id, doc_id)
    key = f"{base}/original.{ext}"
    upload_file(settings.MINIO_BUCKET, key, data, mime)
    return key


def store_processed(
    image: np.ndarray,
    doc_id: str,
    case_id: str | None = None,
    kind: str = "processed",
) -> str:
    """Store a processed or preview image as a normalized JPEG."""
    base = _safe_key_prefix(case_id, doc_id)
    key = f"{base}/{kind}.jpg"
    upload_file(settings.MINIO_BUCKET, key, encode_jpeg(image), IMAGE_MIME)
    return key


def load_original(
    storage_key: str,
) -> bytes:
    """Download the original object bytes from MinIO."""
    return download_file(settings.MINIO_BUCKET, storage_key)


def remove_document_objects(keys: list[str]) -> None:
    """Best-effort removal of a document's stored objects."""
    for key in keys:
        if not key:
            continue
        try:
            delete_file(settings.MINIO_BUCKET, key)
        except Exception:  # pragma: no cover - best effort cleanup
            logger.warning("object_cleanup_failed", key=key)
