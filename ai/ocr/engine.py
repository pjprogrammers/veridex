"""PaddleOCR engine wrapper and the complete document OCR pipeline.

Models are owned by VERIDEX under ``data/models/paddleocr`` (downloads are
redirected there via ``PADDLE_PDX_CACHE_HOME``). The heavy PaddleOCR import is
deferred until the first actual inference, and the engine instance is cached
per process so models load exactly once.
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from uuid import uuid4

import numpy as np

from ai import config
from ai.config import PADDLEOCR_VERSION
from ai.errors import InvalidInputError, OCREngineError
from ai.ocr.mrz import compare_visual_mrz, detect_mrz_lines, parse_mrz
from ai.ocr.parser import extract_fields
from ai.ocr.preprocess import load_image, preprocess_for_ocr, validate_image
from ai.ocr.schemas import OCREngineResult, TextBlock

# Make PaddleX store (and download) all of its models under VERIDEX-owned dirs,
# before any paddlex/paddleocr module can be imported.
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(config.PADDLEOCR_MODELS_DIR))


def _has_model_files(directory) -> bool:
    """True when a directory already contains provisioned model files."""
    try:
        entries = list(directory.iterdir())
    except OSError:
        return False
    if not entries:
        return False
    names = {e.name.lower() for e in entries}
    return bool(
        names
        & {
            "inference.pdmodel", "inference.yml",
            "model.pdiparams", "model.onnx",
            "config.yml", "model.ckpt", "export_model.yml",
        }
    )


class BaseOCREngine(ABC):
    """Interface all OCR engines implement."""

    name = "base"
    version = ""

    @abstractmethod
    def recognize(self, image: np.ndarray) -> list[TextBlock]:
        """Return normalized text blocks for a BGR image."""

    def warm(self) -> None:
        """Preload models (loads once per process)."""


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR 3.x adapter producing normalized :class:`TextBlock` output."""

    name = "paddleocr"
    version = PADDLEOCR_VERSION

    def __init__(self):
        self._engine = None

    def warm(self) -> None:
        self._ensure_engine()

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        # Redirect PaddleX model storage into VERIDEX-owned dirs before import.
        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(config.PADDLEOCR_MODELS_DIR))
        from paddleocr import PaddleOCR

        det_dir = config.PADDLEOCR_DETECTION_MODEL_DIR
        rec_dir = config.PADDLEOCR_RECOGNITION_MODEL_DIR
        device = "gpu:0" if config.AI_USE_GPU else "cpu"
        try:
            self._engine = PaddleOCR(
                text_detection_model_name=config.PADDLEOCR_DETECTION_MODEL,
                text_detection_model_dir=str(det_dir) if _has_model_files(det_dir) else None,
                text_recognition_model_name=config.PADDLEOCR_RECOGNITION_MODEL,
                text_recognition_model_dir=str(rec_dir) if _has_model_files(rec_dir) else None,
                use_textline_orientation=True,
                text_det_limit_side_len=config.PREPROCESS_MAX_WIDTH,
                device=device,
                # The PP-OCRv6 PIR models fail on PaddlePaddle's oneDNN CPU
                # kernels ("ConvertPirAttribute2RuntimeAttribute not support
                # pi::ArrayAttribute..."), so force the plain paddle run mode.
                enable_mkldnn=False,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            raise OCREngineError(f"PaddleOCR could not be initialized: {exc}") from exc
        return self._engine

    @staticmethod
    def normalize_result(result) -> list[TextBlock]:
        """Convert a PaddleOCR 3.x result dict into normalized text blocks.

        PaddleOCR 3.x ``predict`` yields dict-like objects exposing
        ``rec_texts``, ``rec_scores`` and per-line geometry. Prefer the true
        quadrilateral polygons (``rec_polys``/``dt_polys``, each a (4, 2)
        array); older fields like ``rec_boxes`` are flat ``[x1, y1, x2, y2]``
        rectangles and are converted into usable corners.
        """
        if result is None:
            return []
        rec_texts: list[str] = list(result.get("rec_texts") or [])
        rec_scores = result.get("rec_scores") or []

        polys: list | None = None
        raw_polys = result.get("rec_polys") or result.get("dt_polys")
        if raw_polys is not None:
            polys = list(raw_polys)
        raw_boxes = result.get("rec_boxes")
        if polys is None and raw_boxes is not None and len(raw_boxes):
            polys = [list(b) for b in raw_boxes]

        blocks: list[TextBlock] = []
        for i, text in enumerate(rec_texts):
            if not text:
                continue
            conf = float(rec_scores[i]) if i < len(rec_scores) else 0.0
            box = polys[i] if polys and i < len(polys) else []
            bbox: list = []
            try:
                arr = np.asarray(box, dtype=float)
                if arr.ndim == 2 and arr.shape[0] == 4 and arr.shape[1] == 2:
                    # Quadrilateral polygon -> corner points.
                    bbox = [
                        [int(round(float(x))), int(round(float(y)))]
                        for x, y in arr
                    ]
                elif arr.ndim == 1 and arr.shape[0] == 4:
                    # Flat [x1, y1, x2, y2] rectangle -> axis-aligned corners.
                    x1, y1, x2, y2 = arr.tolist()
                    bbox = [
                        [int(round(min(x1, x2))), int(round(min(y1, y2)))],
                        [int(round(max(x1, x2))), int(round(min(y1, y2)))],
                        [int(round(max(x1, x2))), int(round(max(y1, y2)))],
                        [int(round(min(x1, x2))), int(round(max(y1, y2)))],
                    ]
            except (TypeError, ValueError, IndexError):
                bbox = []
            blocks.append(
                TextBlock(
                    text=str(text),
                    confidence=max(0.0, min(1.0, conf)),
                    bbox=bbox,
                    low_confidence=conf < config.PADDLEOCR_LOW_CONFIDENCE,
                )
            )
        return blocks

    def recognize(self, image: np.ndarray) -> list[TextBlock]:
        engine = self._ensure_engine()
        try:
            result = engine.predict(image)
        except Exception as exc:
            raise OCREngineError(f"PaddleOCR inference failed: {exc}") from exc
        if not result:
            return []
        # The OCR pipeline returns one entry per input page; we always pass one.
        blocks: list[TextBlock] = []
        for page in result:
            blocks.extend(self.normalize_result(page))
        return blocks


_ocr_engine_singleton: PaddleOCREngine | None = None


def get_ocr_engine() -> PaddleOCREngine:
    """Return the process-wide PaddleOCR engine (loaded exactly once)."""
    global _ocr_engine_singleton
    if _ocr_engine_singleton is None:
        _ocr_engine_singleton = PaddleOCREngine()
    return _ocr_engine_singleton


def warm_ocr() -> None:
    """Eagerly warm the OCR engine at process startup (see spec §19)."""
    get_ocr_engine().warm()


def process_document(
    image: np.ndarray | bytes | str,
    *,
    document_type: str = "generic",
    engine: BaseOCREngine | None = None,
    preprocess_options: dict | None = None,
) -> OCREngineResult:
    """Full OCR pipeline: validate -> preprocess -> OCR -> fields -> MRZ.

    The original image is never modified; the pipeline keeps ``original`` and
    ``preprocessed`` separate and reports per-stage latency. OCR failures are
    returned as structured errors — never silently as "not a match".
    """
    started = time.perf_counter()
    if not isinstance(image, np.ndarray):
        loaded = load_image(image)
        if loaded is None:
            raise InvalidInputError("image could not be decoded")
        image = loaded
    validate_image(image)

    ocr_engine = engine or get_ocr_engine()
    timings: dict[str, float] = {}

    preprocess_started = time.perf_counter()
    processed = preprocess_for_ocr(image, options=preprocess_options)
    timings["preprocess_latency_ms"] = round((time.perf_counter() - preprocess_started) * 1000, 2)

    preprocessed = processed["preprocessed"]
    result = OCREngineResult(
        document_id=uuid4(),
        engine=ocr_engine.name,
        engine_version=ocr_engine.version,
        image_width=int(processed["metadata"]["width"]),
        image_height=int(processed["metadata"]["height"]),
        overall_confidence=0.0,
    )

    ocr_started = time.perf_counter()
    try:
        blocks = ocr_engine.recognize(preprocessed)
    except OCREngineError as exc:
        timings["ocr_latency_ms"] = round((time.perf_counter() - ocr_started) * 1000, 2)
        timings["total_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result.latency_ms = timings
        result.error = exc.code
        result.error_detail = exc.detail
        return result
    timings["ocr_latency_ms"] = round((time.perf_counter() - ocr_started) * 1000, 2)

    result.text_blocks = blocks

    # Normalized field extraction (visual zone).
    fields = extract_fields(blocks, document_type=document_type)
    result.fields = dict(fields)

    # Independent MRZ path.
    mrz_lines = detect_mrz_lines(blocks)
    if mrz_lines:
        result.mrz = parse_mrz(mrz_lines)

    # Cross-validation (anomaly signal only, never proof of fraud).
    if result.mrz is not None and result.mrz.detected:
        result.consistency = compare_visual_mrz(fields, result.mrz.parsed_fields)

    if blocks:
        result.overall_confidence = round(
            sum(b.confidence for b in blocks) / len(blocks), 4
        )
    timings["total_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    result.latency_ms = timings
    return result
