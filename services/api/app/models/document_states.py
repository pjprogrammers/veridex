"""Document ingestion states.

Lifecycle of a document as it moves through the ingestion and
preprocessing pipeline. `READY` indicates the document is OCR-ready;
producing an OCR-ready image does not guarantee OCR accuracy.
"""

DOCUMENT_STATE_UPLOADED = "UPLOADED"
DOCUMENT_STATE_VALIDATING = "VALIDATING"
DOCUMENT_STATE_CLASSIFYING = "CLASSIFYING"
DOCUMENT_STATE_PREPROCESSING = "PREPROCESSING"
DOCUMENT_STATE_READY = "READY"
DOCUMENT_STATE_FAILED = "FAILED"

VALID_DOCUMENT_STATES = {
    DOCUMENT_STATE_UPLOADED,
    DOCUMENT_STATE_VALIDATING,
    DOCUMENT_STATE_CLASSIFYING,
    DOCUMENT_STATE_PREPROCESSING,
    DOCUMENT_STATE_READY,
    DOCUMENT_STATE_FAILED,
}

# Allowed upload MIME types for the ingestion endpoint.
ALLOWED_PREPROCESS_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
