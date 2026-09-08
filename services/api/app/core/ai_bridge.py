"""VERIDEX API — bridge to the standalone AI/CV layer at the repo root.

The ``ai`` package lives at the repository root, independent of
``services/api``. This bridge locates it, puts it on ``sys.path``, and offers a
guarded, non-raising accessor so the API stays healthy even when the heavy AI
dependencies (PaddleOCR / InsightFace) are not installed in the current
environment. Endpoints that need the layer report a clean 503 in that case.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
_settings = get_settings()

# Model artifacts that mark a directory as containing a usable model pack.
_MODEL_ARTIFACTS = {
    "inference.pdmodel",
    "inference.yml",
    "model.pdiparams",
    "model.onnx",
    "config.yml",
    "model.ckpt",
    "export_model.yml",
    "model.pdmodel",
}

# Suffixes that also identify model artifacts (e.g. InsightFace packs ship
# named ``*.onnx`` files like ``det_10g.onnx`` rather than ``model.onnx``).
_MODEL_ARTIFACT_SUFFIXES = (".onnx", ".pdiparams", ".pdmodel", ".pb", ".pt")


def _candidate_roots() -> list[Path]:
    """Directories that may contain the top-level ``ai`` package."""
    roots: list[Path] = []
    if _settings.AI_PACKAGE_DIR:
        roots.append(Path(_settings.AI_PACKAGE_DIR))
    roots.append(Path.cwd())  # API image: ./ai is mounted under the workdir
    roots.append(Path(__file__).resolve().parents[4])  # local-dev repo root
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root.resolve())
        if key not in seen and (root / "ai").is_dir():
            seen.add(key)
            unique.append(root)
    return unique


def ensure_importable() -> None:
    """Add the root that contains ``ai/`` to ``sys.path`` (idempotent)."""
    if "ai" in sys.modules:
        return
    for root in _candidate_roots():
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))


def ai_module():
    """Return the loaded ``ai`` module, importing it if necessary."""
    ensure_importable()
    return sys.modules.get("ai") or importlib.import_module("ai")


def ai_available() -> bool:
    """True when the ``ai`` package can be imported in this environment."""
    try:
        return ai_module() is not None
    except Exception:  # noqa: BLE001 - importability is a state, not an error
        return False


def _has_model_artifacts(
    directory: Path, _limit: int = 4, _depth: int = 0
) -> bool:
    """True when the directory tree holds recognizable model artifacts.

    PaddleX caches into ``official_models/<name>/`` and InsightFace nests a
    model pack under ``models/<pack>/``, so scanning just the top level
    misses real deployments. The search is bounded to ``_limit`` levels.
    """
    if _depth > _limit:
        return False
    try:
        entries = list(directory.iterdir())
    except OSError:
        return False
    if any(
        entry.name.lower() in _MODEL_ARTIFACTS
        or entry.name.lower().endswith(_MODEL_ARTIFACT_SUFFIXES)
        for entry in entries
    ):
        return True
    return any(
        entry.is_dir() and _has_model_artifacts(entry, _limit, _depth + 1)
        for entry in entries
    )


def models_status() -> dict:
    """Report locally provisioned model artifacts (dirs + presence flags)."""
    try:
        from ai import config as ai_config
    except Exception:  # noqa: BLE001
        return {}
    status: dict = {}
    for name, directory in ai_config.model_dirs().items():
        status[name] = {
            "path": str(directory),
            "present": _has_model_artifacts(directory),
        }
    pack_name = getattr(ai_config, "INSIGHTFACE_MODEL_NAME", None)
    pack_dir = Path(ai_config.INSIGHTFACE_MODELS_DIR) / "models"
    if pack_name:
        pack = pack_dir / pack_name
        status["insightface_pack"] = {
            "path": str(pack),
            "present": pack.is_dir() and any(pack.rglob("*.onnx")),
        }
    return status


def ai_stack() -> dict:
    """Describe the AI layer and locally available models (never raises)."""
    try:
        module = ai_module()
        describe = getattr(module, "AIStack", None)
        payload: dict = {
            "name": "veridex-ai",
            "available": True,
            "version": getattr(module, "__version__", "0.0.0"),
        }
        if describe is not None:
            payload.update(describe.describe())
        payload["models"] = models_status()
        return payload
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "veridex-ai",
            "available": False,
            "version": "0.0.0",
            "reason": str(exc),
            "models": models_status(),
        }
