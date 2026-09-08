"""Face alignment and embedding generation.

Embeddings are always stored as L2-normalized numerical vectors — never as
images. Alignment normalizes pose so the recognition model sees a canonical
112x112 face (ArcFace convention).
"""
from __future__ import annotations

import cv2
import numpy as np

from ai.face.schemas import FaceDetection, FaceEmbedding

# Canonical ArcFace 5-point alignment template for a 112x112 output.
_ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)

_OUTPUT_SIZE = 112


def normalize_embedding(vector: list[float] | np.ndarray) -> FaceEmbedding:
    """L2-normalize a raw embedding vector before storage/comparison."""
    arr = np.asarray(vector, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        raise ValueError("embedding vector is empty")
    norm = float(np.linalg.norm(arr))
    if norm < 1e-12:
        raise ValueError("embedding vector has zero norm")
    normalized = (arr / norm).tolist()
    return FaceEmbedding(vector=normalized, dim=arr.size, l2_norm=round(norm, 6))


def align_face(
    image: np.ndarray, detection: FaceDetection
) -> np.ndarray | None:
    """Align a detected face to the canonical template via similarity transform.

    Falls back to a center square crop when fewer than 5 landmarks are present
    or the transform cannot be estimated; returns ``None`` for an empty crop.
    """
    h, w = image.shape[:2]
    landmarks = detection.landmarks
    if len(landmarks) == 5:
        try:
            source = np.array(landmarks, dtype=np.float32)
            transform, _ = cv2.estimateAffinePartial2D(source, _ARCFACE_TEMPLATE)
            if transform is not None:
                return cv2.warpAffine(
                    image,
                    transform,
                    (_OUTPUT_SIZE, _OUTPUT_SIZE),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                )
        except cv2.error:
            pass

    x1, y1, x2, y2 = [int(v) for v in (detection.bbox or [0, 0, w, h])]
    x1, y1 = max(x1, 0), max(y1, 0)
    x2, y2 = min(x2, w), min(y2, h)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    crop = image[y1:y2, x1:x2]
    return cv2.resize(crop, (_OUTPUT_SIZE, _OUTPUT_SIZE), interpolation=cv2.INTER_LINEAR)


def face_embedding(
    aligned_face: np.ndarray,
    recognition_callable,
) -> FaceEmbedding | None:
    """Produce a normalized embedding from an aligned face crop.

    ``recognition_callable`` receives the 112x112 BGR face and returns a raw
    (unnormalized or pre-normalized) embedding vector, or ``None`` on failure.
    """
    if aligned_face is None or aligned_face.size == 0:
        return None
    raw = recognition_callable(aligned_face)
    if raw is None:
        return None
    return normalize_embedding(raw)


def embed_document_face(
    image: np.ndarray,
    detection: FaceDetection,
    recognition_callable,
) -> FaceEmbedding | None:
    """Full single-face embedding path: align -> recognize -> normalize."""
    aligned = align_face(image, detection)
    if aligned is None:
        return None
    embedding = face_embedding(aligned, recognition_callable)
    if embedding is None:
        return None
    # Guard: re-normalize in case the model already normalized (idempotent).
    return embedding
