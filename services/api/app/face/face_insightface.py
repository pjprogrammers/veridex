"""InsightFace engine adapter.

Isolated so `insightface` (heavy, requires the AI Docker image) is only
imported when `FACE_ENGINE=insightface`. Uses ArcFace for embeddings and
the bundled SCRFD detector.
"""
import os
from typing import Optional

import numpy as np

from app.face.engine import FaceEngine

# Model download directory (models fetched on first run or seeded)
MODELS_DIR = os.environ.get("FACE_MODELS_DIR", "/app/models")


class InsightFaceEngine(FaceEngine):
    name = "insightface"

    def __init__(self):
        import insightface

        self._app = insightface.app.FaceAnalysis(
            name="buffalo_l",
            root=MODELS_DIR,
            allowed_modules=["detection", "recognition"],
        )
        self._app.prepare(ctx_id=-1)  # CPU

    def detect_face(self, image_bgr: np.ndarray) -> Optional[dict]:
        faces = self._app.get(image_bgr)
        if not faces:
            return None
        face = faces[0]
        bbox = face.bbox.astype(int).tolist()
        return {
            "bbox": bbox,
            "detector": self.name,
            "det_score": float(face.det_score),
            "landmarks": face.kps.tolist() if face.kps is not None else None,
        }

    def get_embedding(self, image_bgr: np.ndarray) -> Optional[list[float]]:
        faces = self._app.get(image_bgr)
        if not faces:
            return None
        vec = faces[0].normed_embedding
        return vec.tolist()
