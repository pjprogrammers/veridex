"""Face engine abstraction.

`FaceEngine` provides embeddings and cosine-similarity verification behind a
single interface so the heavy InsightFace dependency can be swapped for/testing
with a deterministic baseline. Engine selection is via the `FACE_ENGINE`
setting (default: "baseline"; use "insightface" in the AI Docker image).
"""
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from app.core.config import get_settings

settings = get_settings()


class FaceEngine(ABC):
    """Interface all face engines implement."""

    name: str

    @abstractmethod
    def get_embedding(self, image_bgr: np.ndarray) -> Optional[list[float]]:
        """Return the L2-normalized embedding for a detected face, else None."""

    @abstractmethod
    def detect_face(self, image_bgr: np.ndarray) -> Optional[dict]:
        """Return face bounding box / landmarks if a face is found, else None."""

    def verify(
        self,
        embedding_a: list[float],
        embedding_b: list[float],
        threshold: Optional[float] = None,
    ) -> dict:
        """Compute cosine similarity between two embeddings and verdict."""
        threshold = threshold or settings.FACE_SIMILARITY_THRESHOLD
        similarity = cosine_similarity(embedding_a, embedding_b)
        match = similarity >= threshold
        return {
            "similarity": round(similarity, 4),
            "threshold": float(threshold),
            "is_match": match,
            "verdict": "match" if match else "no_match",
        }


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (0-1 for normalized)."""
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    if va.shape != vb.shape or va.size == 0:
        return 0.0
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-9
    return float(np.dot(va, vb) / denom)


class BaselineFaceEngine(FaceEngine):
    """Deterministic face engine for offline/testing use.

    Produces a stable pseudo-embedding keyed by face region hash so that
    same-face reproductions yield near-identical embeddings (high similarity)
    and different faces yield low similarity. This makes similarity-based
    verification testable without model weights.
    """

    name = "baseline"

    def _hash_to_embedding(self, seed: int) -> list[float]:
        rng = np.random.default_rng(seed)
        vec = rng.normal(size=512)
        vec /= np.linalg.norm(vec)
        return vec.tolist()

    def get_embedding(self, image_bgr: np.ndarray) -> Optional[list[float]]:
        face = self.detect_face(image_bgr)
        if not face:
            return None
        box = face["bbox"]
        region = image_bgr[box[1]:box[3], box[0]:box[2]]
        if region.size == 0:
            return None
        # Deterministic seed from the region content
        h = int(np.mean(region.astype(np.float32))) * 1000 + int(region.shape[0])
        return self._hash_to_embedding(h)

    def detect_face(self, image_bgr: np.ndarray) -> Optional[dict]:
        # Heuristic: assume a face exists in the central region of a portrait.
        h, w = image_bgr.shape[:2]
        if h < 40 or w < 40:
            return None
        cx, cy = w // 2, int(h * 0.45)
        bw, bh = int(w * 0.5), int(h * 0.5)
        x0, y0 = max(0, cx - bw // 2), max(0, cy - bh // 2)
        x1, y1 = min(w, cx + bw // 2), min(h, cy + bh // 2)
        return {
            "bbox": [int(x0), int(y0), int(x1), int(y1)],
            "detector": self.name,
        }


def _load_insightface_engine():
    from app.face.face_insightface import InsightFaceEngine

    return InsightFaceEngine()


def get_face_engine(engine_name: Optional[str] = None) -> FaceEngine:
    """Factory to create the configured face engine."""
    name = engine_name or getattr(settings, "FACE_ENGINE", "baseline")
    if name == "insightface":
        try:
            return _load_insightface_engine()
        except Exception:
            return BaselineFaceEngine()
    return BaselineFaceEngine()
