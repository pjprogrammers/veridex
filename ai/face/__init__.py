"""VERIDEX AI — Face sub-package (InsightFace detection, quality, embedding)."""
from ai.face.engine import (
    FaceEngine,
    compute_face_similarity,
    get_face_engine,
    warm_face,
)
from ai.face.schemas import (
    FaceDetection,
    FaceEmbedding,
    FaceQuality,
    FaceVerificationResult,
)
from ai.face.verification import (
    cosine_similarity,
    decide,
    verify_faces,
)

__all__ = [
    "FaceDetection",
    "FaceEmbedding",
    "FaceEngine",
    "FaceQuality",
    "FaceVerificationResult",
    "compute_face_similarity",
    "cosine_similarity",
    "decide",
    "get_face_engine",
    "verify_faces",
    "warm_face",
]
