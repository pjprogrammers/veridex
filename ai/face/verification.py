"""Face-to-face verification: similarity and decision logic.

Cosine similarity compares L2-normalized embeddings. The match threshold is
configurable (``FACE_MATCH_THRESHOLD``) and must be calibrated against the
chosen model and representative validation data — it is never treated as a
universal truth.

Decision table (spec §15): no face -> NO_FACE; multiple faces -> MULTIPLE_FACES;
poor quality -> INCONCLUSIVE (below the hard floor: LOW_QUALITY);
similarity >= threshold -> MATCH; else NO_MATCH.
"""
from __future__ import annotations

import numpy as np

from ai import config
from ai.face.detector import face_situation
from ai.face.schemas import FaceDetection, FaceEmbedding, FaceVerificationResult


def cosine_similarity(
    a: list[float] | np.ndarray, b: list[float] | np.ndarray
) -> float:
    """Cosine similarity between two equal-length vectors.

    Embeddings are L2-normalized before storage, so this trivially equals their
    dot product; the implementation still guards against zero-norm inputs.
    """
    va = np.asarray(a, dtype=np.float64).reshape(-1)
    vb = np.asarray(b, dtype=np.float64).reshape(-1)
    if va.shape != vb.shape or va.size == 0:
        return 0.0
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-9
    return float(np.dot(va, vb) / denom)


def decide(
    similarity: float | None,
    threshold: float,
    document_face_quality: float | None,
    live_face_quality: float | None,
) -> str:
    """Map similarity + quality into a face-verification verdict."""
    for quality in (document_face_quality, live_face_quality):
        if quality is None:
            # A missing embedding implies the face path could not run.
            return "INCONCLUSIVE"
        if quality < config.FACE_MIN_QUALITY_HARD:
            return "LOW_QUALITY"
    for quality in (document_face_quality, live_face_quality):
        if quality is None:
            return "INCONCLUSIVE"
        if quality < config.FACE_MIN_QUALITY_SOFT:
            return "INCONCLUSIVE"
    if similarity is None:
        return "INCONCLUSIVE"
    if similarity >= threshold:
        return "MATCH"
    return "NO_MATCH"


def verify_faces(
    document_detections: list[FaceDetection],
    live_detections: list[FaceDetection],
    document_embedding: FaceEmbedding | None,
    live_embedding: FaceEmbedding | None,
    *,
    threshold: float | None = None,
    document_face_quality: float | None = None,
    live_face_quality: float | None = None,
) -> FaceVerificationResult:
    """Run the decision logic over detections/embeddings/qualities."""
    threshold = threshold if threshold is not None else config.FACE_MATCH_THRESHOLD
    doc_count = len(document_detections)
    live_count = len(live_detections)

    # Hard preconditions — never silently pick a face.
    if face_situation(doc_count) == "NO_FACE" or face_situation(live_count) == "NO_FACE":
        return FaceVerificationResult(
            face_detected_document=doc_count > 0,
            face_detected_live=live_count > 0,
            document_face_count=doc_count,
            live_face_count=live_count,
            document_face_quality=document_face_quality,
            live_face_quality=live_face_quality,
            threshold=threshold,
            result="NO_FACE",
        )
    if face_situation(doc_count) == "MULTIPLE_FACES" or face_situation(live_count) == "MULTIPLE_FACES":
        return FaceVerificationResult(
            face_detected_document=True,
            face_detected_live=True,
            document_face_count=doc_count,
            live_face_count=live_count,
            document_face_quality=document_face_quality,
            live_face_quality=live_face_quality,
            threshold=threshold,
            result="MULTIPLE_FACES",
        )

    similarity = None
    if document_embedding is not None and live_embedding is not None:
        similarity = round(
            cosine_similarity(document_embedding.vector, live_embedding.vector), 6
        )

    return FaceVerificationResult(
        face_detected_document=True,
        face_detected_live=True,
        document_face_count=doc_count,
        live_face_count=live_count,
        document_face_quality=document_face_quality,
        live_face_quality=live_face_quality,
        similarity=similarity,
        threshold=float(threshold),
        result=decide(similarity, threshold, document_face_quality, live_face_quality),
    )
