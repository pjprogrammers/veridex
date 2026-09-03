"""Document portrait extraction.

Locates and extracts the passport portrait photo from a document image.
Passport photos are typically in the top-left (for TD3) or a defined zone.
Uses a deterministic placement heuristic with optional face-detection
refinement.
"""
from typing import Optional

import cv2
import numpy as np

from app.face.engine import FaceEngine, get_face_engine


def extract_portrait(
    image: np.ndarray, face_engine: Optional[FaceEngine] = None
) -> dict:
    """Extract the portrait region from a document image.

    Strategy:
      1. If the engine detects a face, crop tightly around it.
      2. Otherwise fall back to a deterministic top-left/right zone.

    Returns cropped portrait (BGR) plus metadata. An empty portrait is
    returned if no face and no region can be inferred.
    """
    engine = face_engine or get_face_engine()
    h, w = image.shape[:2]

    # Try face detection first.
    face = engine.detect_face(image)
    face_bbox = face.get("bbox") if face else None
    if face_bbox and not _is_face_region_too_large(face_bbox, h, w):
        box = face_bbox
        pad = 10
        x0 = max(0, box[0] - pad)
        y0 = max(0, box[1] - pad)
        x1 = min(w, box[2] + pad)
        y1 = min(h, box[3] + pad)
        portrait = image[y0:y1, x0:x1]
        return {
            "portrait": portrait,
            "method": "face_detection",
            "bbox": [x0, y0, x1, y1],
        }

    # Deterministic fallback: passport photo zone (top-left, ~25% of height/width).
    if w >= 200 and h >= 250:
        x0, y0 = int(w * 0.06), int(h * 0.12)
        x1, y1 = int(w * 0.30), int(h * 0.48)
        portrait = image[y0:y1, x0:x1]
        return {
            "portrait": portrait,
            "method": "heuristic_zone",
            "bbox": [x0, y0, x1, y1],
        }

    return {"portrait": None, "method": "none", "bbox": None}


def _is_face_region_too_large(bbox: list, h: int, w: int) -> bool:
    if not bbox or len(bbox) != 4:
        return True
    box_w = bbox[2] - bbox[0]
    box_h = bbox[3] - bbox[1]
    return box_w > w * 0.9 or box_h > h * 0.9


def encode_portrait_jpeg(portrait: np.ndarray, quality: int = 85) -> Optional[bytes]:
    """Encode a portrait to JPEG bytes for storage/display."""
    if portrait is None or portrait.size == 0:
        return None
    ok, buf = cv2.imencode(".jpg", portrait, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None
    return buf.tobytes()
