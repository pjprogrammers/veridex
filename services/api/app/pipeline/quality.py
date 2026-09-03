"""Image quality assessment for document images.

Produces bounded scores (0.0 - 1.0) for resolution, sharpness (blur),
brightness, and contrast. All deterministic, no AI dependencies.
"""
import cv2
import numpy as np


def _score_resolution(image: np.ndarray, ideal_width: int = 2000) -> float:
    """Score based on image width relative to an ideal scanning resolution."""
    h, w = image.shape[:2]
    ratio = min(w / ideal_width, 1.0)
    return round(float(ratio), 4)


def _score_sharpness(image: np.ndarray) -> float:
    """Estimate sharpness via the variance of the Laplacian (Variance of Laplacian / blur metric).

    Higher VoL = sharper. Normalize with a saturating curve.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.size == 0:
        return 0.0
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    vol = float(laplacian.var())
    # VoL ranges ~100 (very blurry) to ~2000+ (sharp). Sigmoid-ish normalization.
    score = 1.0 - np.exp(-vol / 600.0)
    return round(float(np.clip(score, 0.0, 1.0)), 4)


def _score_brightness(image: np.ndarray) -> float:
    """Score brightness. Ideal documents are well-lit, not under/over-exposed."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))
    # Ideal around 128 (0-255 scale). Penalize very dark or very bright.
    distance = abs(mean_brightness - 128.0) / 128.0
    score = 1.0 - distance
    return round(float(np.clip(score, 0.1, 1.0)), 4)


def _score_contrast(image: np.ndarray) -> float:
    """Score contrast via standard deviation of pixel intensities."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    std = float(np.std(gray))
    # Ideal std ~60-70 for good docs. Saturating curve.
    score = 1.0 - np.exp(-std / 45.0)
    return round(float(np.clip(score, 0.1, 1.0)), 4)


def assess_image_quality(image: np.ndarray) -> dict:
    """Assess document image quality and return component + overall scores."""
    if image is None or image.size == 0:
        return {
            "resolution_score": 0.0,
            "sharpness_score": 0.0,
            "brightness_score": 0.0,
            "contrast_score": 0.0,
            "overall_score": 0.0,
            "quality_label": "POOR",
        }

    resolution = _score_resolution(image)
    sharpness = _score_sharpness(image)
    brightness = _score_brightness(image)
    contrast = _score_contrast(image)

    # Weighted overall (resolution & sharpness matter most for OCR).
    overall = (
        0.35 * resolution
        + 0.35 * sharpness
        + 0.15 * brightness
        + 0.15 * contrast
    )
    overall = round(float(np.clip(overall, 0.0, 1.0)), 4)

    if overall >= 0.75:
        label = "EXCELLENT"
    elif overall >= 0.5:
        label = "GOOD"
    elif overall >= 0.3:
        label = "FAIR"
    else:
        label = "POOR"

    return {
        "resolution_score": resolution,
        "sharpness_score": sharpness,
        "brightness_score": brightness,
        "contrast_score": contrast,
        "overall_score": overall,
        "quality_label": label,
    }
