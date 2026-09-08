"""VERIDEX AI layer configuration.

All AI model storage is owned by VERIDEX under ``data/models`` rather than
scattered in undocumented locations. Every setting can be overridden through
environment variables so Docker/K8s deployments can relocate the model store
without touching code.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Version pins (see VERIDEX — AI / CV layer specification)
# ---------------------------------------------------------------------------

PYTHON_VERSION = "3.11"
PADDLEOCR_VERSION = "3.7.0"
PADDLEPADDLE_VERSION = "3.3.1"
INSIGHTFACE_VERSION = "1.0.1"
ONNXRUNTIME_VERSION = "1.29.0"

# Default PaddleOCR model names (PaddleOCR 3.7.0). Overridable via env so the
# exact det/rec combination can be calibrated per deployment.
PADDLEOCR_DETECTION_MODEL = os.environ.get("PADDLEOCR_DETECTION_MODEL", "PP-OCRv6_medium_det")
PADDLEOCR_RECOGNITION_MODEL = os.environ.get("PADDLEOCR_RECOGNITION_MODEL", "PP-OCRv6_medium_rec")

# ---------------------------------------------------------------------------
# Model storage — VERIDEX-owned
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODELS_ROOT = Path(os.environ.get("VERIDEX_MODELS_DIR", _PROJECT_ROOT / "data" / "models"))

PADDLEOCR_MODELS_DIR = Path(
    os.environ.get("PADDLEOCR_MODELS_DIR", MODELS_ROOT / "paddleocr")
)
PADDLEOCR_DETECTION_MODEL_DIR = Path(
    os.environ.get("PADDLEOCR_DETECTION_MODEL_DIR", PADDLEOCR_MODELS_DIR / "det")
)
PADDLEOCR_RECOGNITION_MODEL_DIR = Path(
    os.environ.get("PADDLEOCR_RECOGNITION_MODEL_DIR", PADDLEOCR_MODELS_DIR / "rec")
)

INSIGHTFACE_MODELS_DIR = Path(
    os.environ.get("INSIGHTFACE_MODELS_DIR", MODELS_ROOT / "insightface")
)
INSIGHTFACE_MODEL_NAME = os.environ.get("INSIGHTFACE_MODEL_NAME", "buffalo_l")
INSIGHTFACE_DET_SIZE = tuple(
    int(v) for v in os.environ.get("INSIGHTFACE_DET_SIZE", "640,640").split(",")
)
INSIGHTFACE_DET_THRESHOLD = float(os.environ.get("INSIGHTFACE_DET_THRESHOLD", "0.5"))

# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

# CPU by default; GPU is optional and explicit.
AI_DEVICE = os.environ.get("AI_DEVICE", "cpu").lower()
AI_USE_GPU = AI_DEVICE in ("gpu", "cuda", "cuda:0")
AI_CTX_ID = 0 if AI_USE_GPU else -1

# Keep the source image untouched; cap the longest edge of the OCR input.
PREPROCESS_MAX_WIDTH = int(os.environ.get("PREPROCESS_MAX_WIDTH", "2000"))
PREPROCESS_MIN_WIDTH = int(os.environ.get("PREPROCESS_MIN_WIDTH", "600"))

# ---------------------------------------------------------------------------
# OCR pipeline
# ---------------------------------------------------------------------------

PADDLEOCR_MIN_CONFIDENCE = float(os.environ.get("PADDLEOCR_MIN_CONFIDENCE", "0.0"))
# Below this, a detected text block is preserved but flagged low-confidence.
PADDLEOCR_LOW_CONFIDENCE = float(os.environ.get("PADDLEOCR_LOW_CONFIDENCE", "0.5"))

# ---------------------------------------------------------------------------
# Face pipeline
# ---------------------------------------------------------------------------

# Configurable — must be calibrated against the chosen model and a
# representative validation set. Never treated as a universal scientific truth.
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.55"))

# Quality floors. Below HARD floor the face is unusable (LOW_QUALITY); between
# the floor and the soft threshold the verdict is INCONCLUSIVE.
FACE_MIN_QUALITY_HARD = float(os.environ.get("FACE_MIN_QUALITY_HARD", "0.15"))
FACE_MIN_QUALITY_SOFT = float(os.environ.get("FACE_MIN_QUALITY_SOFT", "0.35"))

# Minimum face size is expressed as a fraction of the image diagonal (0 = off).
FACE_MIN_SIZE_RATIO = float(os.environ.get("FACE_MIN_SIZE_RATIO", "0.05"))
FACE_MIN_EMBEDDING_DIM = 64


def model_dirs() -> dict[str, Path]:
    """Return every model directory the AI layer owns, for warm-up/discovery."""
    return {
        "paddleocr": PADDLEOCR_MODELS_DIR,
        "paddleocr_detection": PADDLEOCR_DETECTION_MODEL_DIR,
        "paddleocr_recognition": PADDLEOCR_RECOGNITION_MODEL_DIR,
        "insightface": INSIGHTFACE_MODELS_DIR,
    }
