"""Document processing pipeline.

Orchestrates loading a document image, assessing quality, preprocessing,
identifying the document type, running OCR, and parsing the MRZ.
The output is a structured, serializable result used by the API and the
verification orchestrator.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.core.config import get_settings
from app.pipeline import docktype, mrz, preprocess, quality
from app.pipeline.ocr import BaseOCREngine, get_ocr_engine

settings = get_settings()


@dataclass
class DocumentAnalysis:
    """The structured result of analyzing a single document."""

    document_type: str = docktype.UNKNOWN
    type_confidence: float = 0.0
    quality: dict = field(default_factory=dict)
    preprocessing_stages: list = field(default_factory=list)
    ocr_text: str = ""
    ocr_engine: str = ""
    ocr_confidence: float = 0.0
    ocr_words: list = field(default_factory=list)
    mrz: dict = field(default_factory=dict)
    extracted_fields: dict = field(default_factory=dict)
    width: int = 0
    height: int = 0


def load_image(data: bytes) -> np.ndarray:
    """Decode image bytes into a numpy BGR image. Raises on invalid input."""
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode image data")
    return image


def _mrz_to_dict(result: mrz.MRZResult) -> dict:
    return {
        "valid": result.valid,
        "format": result.format,
        "document_type": result.document_type,
        "document_number": result.document_number,
        "issuing_country": result.issuing_country,
        "nationality": result.nationality,
        "surname": result.surname,
        "given_names": result.given_names,
        "date_of_birth": result.date_of_birth,
        "sex": result.sex,
        "expiry_date": result.expiry_date,
        "check_digits_valid": result.check_digits_valid,
        "errors": result.errors,
        "raw_lines": result.raw_lines,
    }


def _build_extracted_fields(analysis: DocumentAnalysis) -> dict:
    """Combine OCR text and MRZ data into structured identity fields."""
    fields: dict = {}
    if analysis.mrz and analysis.mrz.get("valid"):
        fields.update(
            {
                "document_number": analysis.mrz.get("document_number"),
                "surname": analysis.mrz.get("surname"),
                "given_names": analysis.mrz.get("given_names"),
                "date_of_birth": analysis.mrz.get("date_of_birth"),
                "sex": analysis.mrz.get("sex"),
                "expiry_date": analysis.mrz.get("expiry_date"),
                "nationality": analysis.mrz.get("nationality"),
                "issuing_country": analysis.mrz.get("issuing_country"),
            }
        )
    return {k: v for k, v in fields.items() if v}


def analyze_document(
    image: np.ndarray,
    ocr_engine: BaseOCREngine | None = None,
    preprocess_options: dict | None = None,
) -> DocumentAnalysis:
    """Run the full document analysis pipeline on a loaded image."""
    engine = ocr_engine or get_ocr_engine()

    result = DocumentAnalysis()
    result.width = int(image.shape[1])
    result.height = int(image.shape[0])

    # 1. Quality assessment
    result.quality = quality.assess_image_quality(image)

    # 2. Preprocessing
    processed = preprocess.preprocess_document(image, preprocess_options)
    result.preprocessing_stages = processed["stages_applied"]
    gray = processed["gray"]

    # 3. OCR on the preprocessed grayscale image
    ocr_result = engine.run(gray)
    result.ocr_text = ocr_result.full_text
    result.ocr_engine = ocr_result.engine
    result.ocr_confidence = ocr_result.confidence
    result.ocr_words = ocr_result.words

    # 4. MRZ extraction from the OCR text
    # MRZ lines are the last dense lines; we look across the raw OCR.
    mrz_result = _extract_mrz_from_ocr(ocr_result.words)
    result.mrz = _mrz_to_dict(mrz_result) if mrz_result else {}

    # 5. Document type identification
    type_result = docktype.identify_document_type(
        image=image,
        ocr_text=result.ocr_text,
        mrz_parsed=bool(result.mrz and result.mrz.get("valid")),
    )
    result.document_type = type_result["document_type"]
    result.type_confidence = type_result["confidence"]

    # 6. Structured extracted fields
    result.extracted_fields = _build_extracted_fields(result)

    return result


def _extract_mrz_from_ocr(words: list[dict]) -> mrz.MRZResult | None:
    """Assemble candidate MRZ lines from OCR word boxes.

    MRZ text appears as dense, evenly spaced uppercase lines. This constructs
    lines by y-coordinate clustering and horizontal concatenation, then
    attempts to parse them.
    """
    if not words:
        return None

    # Group words into rows by y-center bucket.
    rows: dict[int, list] = {}
    for w in words:
        box = w.get("box")
        if not box or len(box) < 4:
            continue
        y_center = int(sum(p[1] for p in box[:4]) / 4)
        key = y_center // 12  # 12px vertical bucket
        rows.setdefault(key, []).append(w)

    candidate_lines = []
    for key in sorted(rows):
        row_words = sorted(rows[key], key=lambda w: min(p[0] for p in w["box"]))
        line = "".join(
            w["text"].replace(" ", "") for w in row_words if w["text"].isalnum()
        )
        if len(line) >= 30:
            candidate_lines.append(line)

    if not candidate_lines:
        return None

    parsed = mrz.parse_mrz(candidate_lines)
    if parsed.valid:
        return parsed
    # Fall back to trying each detectable line pair on raw words
    return None
