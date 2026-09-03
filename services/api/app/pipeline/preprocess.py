"""Document image preprocessing.

Deterministic OpenCV operations to prepare a document image for OCR:
grayscale conversion, bilateral/median denoising, deskewing, and
adaptive contrast enhancement. No AI dependencies.
"""
import cv2
import numpy as np


def _compute_skew_angle(image: np.ndarray) -> float:
    """Estimate the deskew angle using contour-based minimum area rectangle."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary > 0))
    if coords.shape[0] < 100:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    # Return angle to rotate to correct orientation.
    return -angle


def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def deskew(image: np.ndarray) -> np.ndarray:
    """Correct slight rotation of the document image."""
    angle = _compute_skew_angle(image)
    if abs(angle) < 0.5:
        return image
    return _rotate(image, angle)


def denoise(image: np.ndarray) -> np.ndarray:
    """Apply mild denoising to reduce sensor/scan noise."""
    return cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """Apply CLAHE for adaptive contrast enhancement on a grayscale copy."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def preprocess_document(image: np.ndarray, options: dict | None = None) -> dict:
    """Run the full preprocessing pipeline and return outputs.

    Each stage is toggleable via `options` (e.g. {"deskew": false}).
    Returns processed grayscale image, color image, and stage metadata.
    """
    options = options or {}
    stages = []

    color = image.copy()

    if options.get("deskew", True):
        color = deskew(color)
        stages.append("deskew")

    if options.get("denoise", True):
        color = denoise(color)
        stages.append("denoise")

    if options.get("contrast", True):
        color = enhance_contrast(color)
        stages.append("contrast_enhance")

    gray = to_grayscale(color)

    return {
        "gray": gray,
        "color": color,
        "stages_applied": stages,
    }
