"""PaddleOCR engine adapter.

Isolated in this module so importing ``paddleocr`` (which is heavy and
requires the dedicated AI Docker image) does not affect the core API
service.  Only imported lazily when ``OCR_ENGINE=paddleocr``.

Includes timeout enforcement and retry with exponential backoff.
"""
from __future__ import annotations

import concurrent.futures
import time

import numpy as np

from app.pipeline.ocr import BaseOCREngine, OCRResult

_OCR_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 2
_RETRY_BACKOFF = 1.5  # seconds, doubles each retry


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR wrapper with timeout and retry."""

    name = "paddleocr"

    def __init__(self, timeout: float = _OCR_TIMEOUT_SECONDS, max_retries: int = _MAX_RETRIES):
        from paddleocr import PaddleOCR

        self._engine = PaddleOCR(
            use_angle_cls=True, lang="en", show_log=False, use_gpu=False
        )
        self._timeout = timeout
        self._max_retries = max_retries

    def _run_ocr(self, image: np.ndarray) -> list:
        """Run PaddleOCR with timeout enforcement."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._engine.ocr, image, cls=True)
            return future.result(timeout=self._timeout)

    def run(self, image: np.ndarray) -> OCRResult:
        """Run OCR with retry and exponential backoff on transient failures."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                result = self._run_ocr(image)
                return self._parse_result(result)
            except concurrent.futures.TimeoutError:
                last_exc = TimeoutError(
                    f"PaddleOCR timed out after {self._timeout}s "
                    f"(attempt {attempt + 1}/{self._max_retries + 1})"
                )
            except Exception as exc:
                last_exc = exc

            if attempt < self._max_retries:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))

        return OCRResult(
            full_text="",
            words=[],
            confidence=0.0,
            engine=f"{self.name}:failed:{last_exc}",
        )

    @staticmethod
    def _parse_result(result: list | None) -> OCRResult:
        """Parse raw PaddleOCR output into OCRResult."""
        words: list[dict] = []
        full_text_parts: list[str] = []

        if not result:
            return OCRResult(full_text="", words=[], confidence=0.0, engine="paddleocr")

        for line in result:
            if not line:
                continue
            for item in line:
                box, (text, confidence) = item[0], item[1]
                words.append(
                    {
                        "text": text,
                        "confidence": float(confidence),
                        "box": box,
                    }
                )
                full_text_parts.append(text)

        full_text = "\n".join(full_text_parts)
        avg_conf = (
            sum(w["confidence"] for w in words) / len(words) if words else 0.0
        )

        return OCRResult(
            full_text=full_text,
            words=words,
            confidence=round(avg_conf, 4),
            engine="paddleocr",
        )
