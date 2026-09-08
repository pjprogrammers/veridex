"""Face quality assessment.

Evaluates a face detection before any embedding is produced, so a degraded
face never yields a confident MATCH. Components (spec §12):

* detection confidence      — detector score
* face size                 — bounding box relative to the image
* blur                      — Laplacian variance of the face crop
* exposure                  — mean brightness of the crop
* pose                      — geometric yaw/pitch heuristic from landmarks
* occlusion / completeness  — clipping at image edges and dark-region share
"""
from __future__ import annotations

import cv2
import numpy as np

from ai import config
from ai.face.schemas import FaceDetection, FaceQuality


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _crop(image: np.ndarray, bbox: list[int]) -> np.ndarray | None:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(int(x1), 0)
    y1 = max(int(y1), 0)
    x2 = min(int(x2), w)
    y2 = min(int(y2), h)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return image[y1:y2, x1:x2]


def _pos_from_landmarks(detection: FaceDetection) -> dict[str, float]:
    """Estimate yaw/pitch deviation from the standard 5-point landmark set."""
    pts = detection.landmarks
    out = {"yaw": 0.0, "pitch": 0.0}
    if not pts or len(pts) < 3:
        out.update({"yaw": 0.5, "pitch": 0.5})
        return out
    left_eye, right_eye, nose = pts[0], pts[1], pts[2]
    eye_mid_x = (left_eye[0] + right_eye[0]) / 2.0
    eye_mid_y = (left_eye[1] + right_eye[1]) / 2.0
    eye_width = max(abs(right_eye[0] - left_eye[0]), 1e-6)
    yaw = abs(nose[0] - eye_mid_x) / eye_width
    pitch = abs(nose[1] - eye_mid_y) / max(eye_width, 1e-6)
    if len(pts) >= 5:
        mouth_mid_y = (pts[3][1] + pts[4][1]) / 2.0
        pitch = min(pitch, abs(mouth_mid_y - nose[1]) / max(eye_width, 1e-6))
    out["yaw"] = _clamp(yaw)
    out["pitch"] = _clamp(pitch)
    return out


def assess_face_quality(
    image: np.ndarray,
    detection: FaceDetection,
) -> FaceQuality:
    """Assess the quality of one face detection in ``image`` (BGR)."""
    reasons: list[str] = []
    h, w = image.shape[:2]
    image_area = max(float(h * w), 1.0)

    crop = _crop(image, detection.bbox or [])
    if crop is None or crop.size == 0:
        return FaceQuality(
            score=0.0, blur=1.0, pose_ok=False, size_ok=False,
            exposure_ok=False, occlusion_ok=False, crop_complete=False,
            reasons=["face_crop_empty"],
        )

    # --- blur (Laplacian variance) ---
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    clarity = _clamp(variance / 700.0)  # 700 is a nominal "good" variance floor
    blur = 1.0 - clarity

    # --- exposure ---
    mean_brightness = float(np.mean(gray))
    exposure_score = 1.0 - abs(mean_brightness - 128.0) / 128.0
    exposure_ok = 35.0 <= mean_brightness <= 225.0

    # --- size ---
    crop_area = float(crop.shape[0] * crop.shape[1])
    area_ratio = crop_area / image_area
    diagonal = float(np.hypot(w, h))
    face_diag = float(np.hypot(crop.shape[1], crop.shape[0]))
    size_score = _clamp(area_ratio / 0.03)  # nominal 3% frame coverage
    min_side = min(crop.shape[0], crop.shape[1])
    size_ok = min_side >= 32 and area_ratio >= 0.001
    size_ok = size_ok and face_diag >= config.FACE_MIN_SIZE_RATIO * diagonal

    # --- pose ---
    pose = _pos_from_landmarks(detection)
    pose_score = 1.0 - max(pose["yaw"], pose["pitch"])
    pose_ok = pose["yaw"] <= 0.5 and pose["pitch"] <= 0.5

    # --- occlusion / completeness ---
    dark_share = float(np.mean(gray < 45))
    occlusion_score = _clamp(1.0 - dark_share * 1.6)
    occlusion_ok = dark_share < 0.25
    if detection.landmarks and len(detection.landmarks) < 3:
        occlusion_ok = False
        occlusion_score = min(occlusion_score, 0.5)

    x1, y1, x2, y2 = detection.bbox
    margin = 4
    touches_edge = (
        x1 <= margin or y1 <= margin or x2 >= w - margin or y2 >= h - margin
    )
    crop_complete = not touches_edge
    completeness_score = 0.0 if touches_edge else 1.0

    if not pose_ok:
        reasons.append("pose_out_of_range")
    if not size_ok:
        reasons.append("face_too_small")
    if not exposure_ok:
        reasons.append("bad_exposure")
    if not occlusion_ok:
        reasons.append("possible_occlusion")
    if not crop_complete:
        reasons.append("face_cropped")
    if blur >= 0.7:
        reasons.append("excessive_blur")

    score = (
        0.30 * clarity
        + 0.25 * exposure_score
        + 0.20 * size_score
        + 0.15 * pose_score
        + 0.07 * occlusion_score
        + 0.03 * completeness_score
    )
    score = float(_clamp(score))
    return FaceQuality(
        score=round(score, 4),
        blur=round(float(_clamp(blur)), 4),
        pose_ok=pose_ok,
        size_ok=size_ok,
        exposure_ok=exposure_ok,
        occlusion_ok=occlusion_ok,
        crop_complete=crop_complete,
        reasons=reasons,
    )
