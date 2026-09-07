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
    """Convert a parsed MRZResult into a serializable dict."""
    if not result.mrz_detected:
        return {
            "mrz_detected": False,
            "mrz_valid": False,
            "warnings": result.warnings,
            "raw_lines": result.raw_mrz,
        }
    parsed = result.parsed_fields
    return {
        "mrz_detected": True,
        "mrz_valid": result.mrz_valid,
        "format": result.format,
        "check_digits": result.check_digits,
        "check_digits_valid": result.mrz_valid,
        "raw_lines": result.raw_mrz,
        "warnings": result.warnings,
        # Flatten parsed fields for backward compatibility (verified/report
        # consumers and the risk engine read these keys).
        "document_type": parsed.get("document_code", ""),
        "document_number": parsed.get("passport_number", ""),
        "issuing_country": parsed.get("issuing_state", ""),
        "nationality": parsed.get("nationality", ""),
        "surname": parsed.get("surname", ""),
        "given_names": parsed.get("given_names", ""),
        "date_of_birth": parsed.get("date_of_birth", ""),
        "sex": parsed.get("sex", ""),
        "expiry_date": parsed.get("expiry_date", ""),
        "personal_number": parsed.get("personal_number", ""),
        "final_check_digit": parsed.get("final_check_digit", ""),
    }


def _build_extracted_fields(analysis: DocumentAnalysis) -> dict:
    """Combine OCR text and MRZ data into structured identity fields."""
    fields: dict = {}
    if analysis.mrz and analysis.mrz.get("mrz_valid"):
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
        mrz_parsed=bool(result.mrz and result.mrz.get("mrz_valid")),
    )
    result.document_type = type_result["document_type"]
    result.type_confidence = type_result["confidence"]

    # 6. Structured extracted fields
    result.extracted_fields = _build_extracted_fields(result)

    return result


def _extract_mrz_from_ocr(words: list[dict]) -> mrz.MRZResult | None:
    """Detect the MRZ region from OCR word boxes and parse it.

    Uses ``mrz_region`` to find dense, evenly-spaced rows (the MRZ zone),
    assembles candidate lines, then parses them with the ICAO validator.
    """
    from app.pipeline.mrz_region import extract_mrz_from_words

    region = extract_mrz_from_words(words)
    if not region.detected:
        return None

    parsed = mrz.parse_mrz(region.lines)
    if parsed.mrz_detected:
        # Surface region-level warnings onto the parse result.
        parsed.warnings.extend(region.warnings)
        return parsed
    return None
