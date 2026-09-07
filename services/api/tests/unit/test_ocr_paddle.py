"""Unit tests for PaddleOCR timeout + retry policy (engine mocked)."""
import sys

import numpy as np

from app.pipeline import ocr_paddle


class _EngineStub:
    """Fake PaddleOCR whose behaviour is driven by a callable."""

    def __init__(self, behavior):
        self.behavior = behavior

    def ocr(self, image, cls=True):
        return self.behavior()


def _set_fake_paddle(monkeypatch, behavior):
    """Patch the lazy `from paddleocr import PaddleOCR` used by the engine."""
    import types

    fake_paddle_module = types.ModuleType("paddleocr")
    fake_paddle_module.PaddleOCR = lambda **kw: _EngineStub(behavior)
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddle_module)


def test_retry_on_transient_failure(monkeypatch):
    counts = {"n": 0}

    def behavior():
        counts["n"] += 1
        if counts["n"] < 3:
            raise RuntimeError("transient blip")
        item = [[[0, 0], [30, 0], [30, 10], [0, 10]], ("HELLO", 0.9)]
        return [[item]]

    _set_fake_paddle(monkeypatch, behavior)

    engine = ocr_paddle.PaddleOCREngine(max_retries=3, timeout=1)
    result = engine.run(np.zeros((10, 10, 3), dtype=np.uint8))
    # succeeded on 3rd attempt (2 transient failures then success) -> 3 calls
    assert counts["n"] == 3
    assert result.engine == "paddleocr"
    assert result.full_text == "HELLO"


def test_max_retries_exhausted(monkeypatch):
    counts = {"n": 0}

    def behavior():
        counts["n"] += 1
        raise RuntimeError("always broken")

    _set_fake_paddle(monkeypatch, behavior)

    engine = ocr_paddle.PaddleOCREngine(max_retries=2, timeout=0.1)
    result = engine.run(np.zeros((10, 10, 3), dtype=np.uint8))
    assert counts["n"] == 3  # initial + 2 retries
    assert result.confidence == 0.0
    assert "failed" in result.engine


def test_timeout_returns_failed_result(monkeypatch):
    import time

    def behavior():
        time.sleep(5)  # longer than timeout
        return []

    _set_fake_paddle(monkeypatch, behavior)

    engine = ocr_paddle.PaddleOCREngine(max_retries=0, timeout=0.1)
    result = engine.run(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.confidence == 0.0
    assert "failed" in result.engine
