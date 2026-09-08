"""Structured AI-layer errors.

The AI layer must never silently collapse a model failure into a false
verification result. Failures are raised as typed exceptions carrying a stable
machine-readable ``code`` so callers can map them to structured responses
instead of guessing from a boolean.
"""
from __future__ import annotations


class AIError(Exception):
    """Base class for every AI-layer error."""

    code: str = "AI_ERROR"
    detail: str = ""

    def __init__(self, detail: str = "", *, code: str | None = None):
        self.detail = detail or self.detail
        if code is not None:
            self.code = code
        super().__init__(self.detail)

    def to_dict(self) -> dict:
        return {"error": self.code, "detail": self.detail}


class ModelUnavailableError(AIError):
    """A required inference model could not be loaded or built."""

    code = "AI_ERROR"


class InvalidInputError(AIError):
    """The supplied image/input is unreadable or otherwise unsuitable."""

    code = "INVALID_INPUT"


class OCREngineError(AIError):
    """OCR inference failed (model, runtime, or input-to-OCR)."""

    code = "OCR_ERROR"


class FaceEngineError(AIError):
    """Face inference failed."""

    code = "AI_ERROR"


def error_for(exc: Exception) -> AIError:
    """Wrap an arbitrary exception into a structured :class:`AIError`."""
    if isinstance(exc, AIError):
        return exc
    return AIError(detail=f"{type(exc).__name__}: {exc}")
