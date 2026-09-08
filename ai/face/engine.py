"""InsightFace engine and the complete face-verification pipeline.

The heavy InsightFace import (and ONNX Runtime session creation) is deferred
until the first call and the engine is cached per process (spec §19). Model
storage is VERIDEX-owned under ``data/models/insightface`` and uses ONNX Runtime
for inference (CPU by default; GPU optional via ``AI_DEVICE=gpu``).

The machine-detection path is swappable so the test suite can inject a
deterministic detector without loading real weights.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ai import config
from ai.errors import FaceEngineError, InvalidInputError
from ai.face.detector import face_situation, insightface_detect
from ai.face.embedding import embed_document_face, normalize_embedding
from ai.face.quality import assess_face_quality
from ai.face.schemas import FaceDetection, FaceEmbedding, FaceVerificationResult
from ai.face.verification import verify_faces


class FaceRecognitionBackend(ABC):
    """Interface decoupling the recognition model from the pipeline logic."""

    name = "base"

    @abstractmethod
    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        """Return all faces detected in ``image`` (BGR)."""

    @abstractmethod
    def recognize(self, aligned_face: np.ndarray) -> list[float] | None:
        """Return a raw embedding vector for an aligned 112x112 face."""


class InsightFaceBackend(FaceRecognitionBackend):
    """InsightFace SCRFD (buffalo_l) + ArcFace recognition on ONNX Runtime."""

    name = "insightface"

    def __init__(self):
        self._app = None

    def _ensure_app(self):
        if self._app is not None:
            return self._app
        import insightface

        root = str(config.INSIGHTFACE_MODELS_DIR)
        try:
            app = insightface.app.FaceAnalysis(
                name=config.INSIGHTFACE_MODEL_NAME,
                root=root,
                allowed_modules=["detection", "recognition"],
                providers=None if config.AI_USE_GPU else ["CPUExecutionProvider"],
            )
            app.prepare(
                ctx_id=config.AI_CTX_ID,
                det_thresh=config.INSIGHTFACE_DET_THRESHOLD,
                det_size=list(config.INSIGHTFACE_DET_SIZE),
            )
        except Exception as exc:
            raise FaceEngineError(f"InsightFace failed to initialize: {exc}") from exc
        self._app = app
        return app

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        try:
            return insightface_detect(self._ensure_app(), image)
        except Exception as exc:
            raise FaceEngineError(f"Face detection failed: {exc}") from exc

    def recognize(self, aligned_face: np.ndarray) -> list[float] | None:
        try:
            faces = self._ensure_app().get(aligned_face)
        except Exception as exc:
            raise FaceEngineError(f"Face recognition failed: {exc}") from exc
        if not faces:
            return None
        return faces[0].normed_embedding.tolist()


class FaceEngine:
    """Process-wide face engine encapsulating detection, quality, embedding."""

    def __init__(self, backend: FaceRecognitionBackend | None = None):
        self.backend = backend or InsightFaceBackend()

    def warm(self) -> None:
        self.backend.detect(np.zeros((160, 160, 3), dtype=np.uint8))

    # -- single image helpers -------------------------------------------------

    def detect_faces(self, image: np.ndarray) -> list[FaceDetection]:
        image = self._coerce_image(image)
        detections = self.backend.detect(image)
        for d in detections:
            d.quality = assess_face_quality(image, d)
        return detections

    def face_embedding(
        self, image: np.ndarray, detection: FaceDetection | None = None
    ) -> tuple[FaceEmbedding | None, FaceDetection | None]:
        """Embed the single face in ``image`` (using its own detection)."""
        image = self._coerce_image(image)
        if detection is not None:
            dets = [detection]
        else:
            dets = self.detect_faces(image)
        if face_situation(len(dets)) != "SINGLE_FACE":
            return None, None
        chosen = dets[0]
        embedding = embed_document_face(image, chosen, self.backend.recognize)
        return embedding, chosen

    def verify(
        self,
        document_image: np.ndarray,
        live_image: np.ndarray,
        *,
        threshold: float | None = None,
    ) -> FaceVerificationResult:
        """Verify a document portrait against a live/user face (spec §17)."""
        timings: dict[str, float] = {}
        started = time.perf_counter()
        document_image = self._coerce_image(document_image)
        live_image = self._coerce_image(live_image)

        t0 = time.perf_counter()
        doc_detections = self.detect_faces(document_image)
        timings["face_detection_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        live_detections = self.detect_faces(live_image)
        timings["face_detection_latency_ms"] = round(
            (time.perf_counter() - t0) * 1000 + timings["face_detection_latency_ms"], 2
        )

        if face_situation(len(doc_detections)) == "SINGLE_FACE":
            doc_quality = float(doc_detections[0].quality.score) if doc_detections[0].quality else None
            t0 = time.perf_counter()
            doc_embedding = embed_document_face(
                document_image, doc_detections[0], self.backend.recognize
            )
            timings["face_embedding_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        else:
            doc_embedding, doc_quality = None, None

        if face_situation(len(live_detections)) == "SINGLE_FACE":
            live_quality = float(live_detections[0].quality.score) if live_detections[0].quality else None
            t0 = time.perf_counter()
            live_embedding = embed_document_face(
                live_image, live_detections[0], self.backend.recognize
            )
            timings["face_embedding_latency_ms"] = round(
                (time.perf_counter() - t0) * 1000 + timings.get("face_embedding_latency_ms", 0.0), 2
            )
        else:
            live_embedding, live_quality = None, None

        result = verify_faces(
            doc_detections,
            live_detections,
            doc_embedding,
            live_embedding,
            threshold=threshold,
            document_face_quality=doc_quality,
            live_face_quality=live_quality,
        )
        timings["total_ai_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result.latency_ms = timings
        return result

    # -- document portrait selection ------------------------------------------

    def document_portrait_embedding(
        self, document_image: np.ndarray
    ) -> tuple[FaceEmbedding | None, FaceDetection | None]:
        """Embed the best document portrait from the page-level detections."""
        image = self._coerce_image(document_image)
        detections = self.detect_faces(image)
        if face_situation(len(detections)) != "SINGLE_FACE":
            return None, None
        chosen = detections[0]
        return embed_document_face(image, chosen, self.backend.recognize), chosen

    @staticmethod
    def _coerce_image(image) -> np.ndarray:
        if image is None:
            raise InvalidInputError("image is None")
        if isinstance(image, (str, Path)):
            image = Path(image)
            try:
                image = image.read_bytes()
            except OSError:
                raise InvalidInputError("image path could not be read")
        if isinstance(image, bytes):
            from ai.ocr.preprocess import load_image

            loaded = load_image(image)
            if loaded is None:
                raise InvalidInputError("image could not be decoded")
            return loaded
        if not isinstance(image, np.ndarray):
            raise InvalidInputError("image must be a numpy array or bytes")
        if image.ndim == 2:
            import cv2

            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.ndim == 3 and image.shape[2] == 4:
            import cv2

            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        if image.shape[2] not in (1, 3):
            raise InvalidInputError(f"unsupported channel count {image.shape[2]}")
        return image.copy()


_face_engine_singleton: FaceEngine | None = None


def get_face_engine() -> FaceEngine:
    """Return the process-wide face engine (loaded exactly once)."""
    global _face_engine_singleton
    if _face_engine_singleton is None:
        _face_engine_singleton = FaceEngine()
    return _face_engine_singleton


def warm_face() -> None:
    """Eagerly warm the face engine at process startup (spec §19)."""
    get_face_engine().warm()


def normalize_face_embedding(vector) -> FaceEmbedding:
    """Public helper: L2-normalize a raw embedding vector."""
    return normalize_embedding(vector)


def compute_face_similarity(
    a: list[float] | np.ndarray, b: list[float] | np.ndarray
) -> float:
    """Public helper: cosine similarity between two embeddings."""
    from ai.face.verification import cosine_similarity

    return cosine_similarity(a, b)
