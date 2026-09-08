"""Face detection.

Wraps the InsightFace SCRFD detector (buffalo_l) and provides the pure decision
logic around it:

* 0 faces   -> NO_FACE
* 1 face    -> SINGLE_FACE
* >1 faces  -> MULTIPLE_FACES

A multi-face image is flagged, never silently reduced to an arbitrary face —
that decision is left to the caller (portrait selection vs strict verification).
"""
from __future__ import annotations

import numpy as np

from ai.face.schemas import FACE_SITUATION, FaceDetection


def face_situation(count: int) -> FACE_SITUATION:
    """Classify a face count into a situation level (spec §11)."""
    if count <= 0:
        return "NO_FACE"
    if count == 1:
        return "SINGLE_FACE"
    return "MULTIPLE_FACES"


def insightface_detect(app, image: np.ndarray) -> list[FaceDetection]:
    """Run InsightFace detection and normalize to :class:`FaceDetection`."""
    faces = app.get(image)
    detections: list[FaceDetection] = []
    for face in faces:
        bbox = face.bbox.astype(int).tolist() if face.bbox is not None else []
        kps = face.kps.tolist() if face.kps is not None else []
        detections.append(
            FaceDetection(
                bbox=bbox,
                confidence=float(getattr(face, "det_score", 0.0) or 0.0),
                landmarks=[[float(x), float(y)] for x, y in kps],
            )
        )
    return detections


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def select_document_face(
    detections: list[FaceDetection],
    image_shape: tuple[int, int],
) -> FaceDetection | None:
    """Select the face most likely to be the document portrait.

    Passport portraits occupy the top zone of the page (for TD3 layout) and are
    reasonably large. This is used by the portrait path — strict verification
    still refuses MULTIPLE_FACES outright.
    """
    if not detections:
        return None
    h, w = image_shape
    image_area = max(float(h * w), 1.0)

    def score(d: FaceDetection) -> float:
        x1, y1, x2, y2 = d.bbox
        bw, bh = max(x2 - x1, 0), max(y2 - y1, 0)
        area_ratio = (bw * bh) / image_area
        cy = (y1 + y2) / 2.0
        # Portrait zone favors upper-half placement.
        vertical_ok = 0.0 if cy < h * 0.65 else -0.3
        return _clamp(d.confidence, 0.0, 1.0) + area_ratio + vertical_ok

    return max(detections, key=score)


def best_detection(
    detections: list[FaceDetection],
    image_shape: tuple[int, int],
) -> FaceDetection | None:
    """Return the single usable face for embedding, or ``None`` when ambiguous."""
    situation = face_situation(len(detections))
    if situation != "SINGLE_FACE":
        return None
    return detections[0]
