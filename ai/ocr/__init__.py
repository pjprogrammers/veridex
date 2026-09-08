"""VERIDEX AI — OCR sub-package (PaddleOCR engine, preprocessing, parsing, MRZ)."""
from ai.ocr.engine import (
    BaseOCREngine,
    PaddleOCREngine,
    get_ocr_engine,
    process_document,
    warm_ocr,
)
from ai.ocr.mrz import (
    compare_visual_mrz,
    compute_check_digit,
    detect_mrz_lines,
    parse_mrz,
    validate_check_digit,
)
from ai.ocr.parser import extract_fields, spatial_order
from ai.ocr.schemas import (
    ConsistencyEntry,
    FieldValue,
    MRZResult,
    OCREngineResult,
    TextBlock,
)

__all__ = [
    "BaseOCREngine",
    "ConsistencyEntry",
    "FieldValue",
    "MRZResult",
    "OCREngineResult",
    "PaddleOCREngine",
    "TextBlock",
    "compare_visual_mrz",
    "compute_check_digit",
    "detect_mrz_lines",
    "extract_fields",
    "get_ocr_engine",
    "parse_mrz",
    "process_document",
    "spatial_order",
    "validate_check_digit",
    "warm_ocr",
]
