"""PaddleOCR engine adapter.

Isolated in this module so importing `paddleocr` (which is heavy and requires
the dedicated AI Docker image) does not affect the core API service. Only
imported lazily when `OCR_ENGINE=paddleocr`.
"""
import numpy as np

from app.pipeline.ocr import BaseOCREngine, OCRResult


class PaddleOCREngine(BaseOCREngine):
    name = "paddleocr"

    def __init__(self):
        from paddleocr import PaddleOCR

        self._engine = PaddleOCR(
            use_angle_cls=True, lang="en", show_log=False, use_gpu=False
        )

    def run(self, image: np.ndarray) -> OCRResult:
        result = self._engine.ocr(image, cls=True)
        words = []
        full_text_parts = []

        if not result:
            return OCRResult(full_text="", words=[], confidence=0.0, engine=self.name)

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
            engine=self.name,
        )
