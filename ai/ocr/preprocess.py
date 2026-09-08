"""OCR image preprocessing.

Independent, deterministic OpenCV stages. The original uploaded image is never
modified in place — every stage returns a new array and the pipeline keeps
``original_image`` and ``preprocessed_image`` separate forever.

Preprocessing is intentionally conservative: aggressive processing destroys
MRZ characters, fine text, security patterns and portrait regions, so the
pipeline only applies the mildest useful operations and every stage can be
toggled off.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ai.config import PREPROCESS_MAX_WIDTH
from ai.errors import InvalidInputError


def load_image(source: str | bytes | Path) -> np.ndarray | None:
    """Decode an image from a path or raw encoded bytes.

    Decoding is the authoritative check — a corrupt/truncated file returns
    ``None`` rather than raising or trusting a file extension.
    """
    if isinstance(source, bytes):
        data = source
    else:
        path = Path(source)
        try:
            data = path.read_bytes()
        except OSError:
            return None
    if not data:
        return None
    buf = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)  # None on any decode failure


def validate_image(image: np.ndarray) -> None:
    """Validate an image for OCR. Raises :class:`InvalidInputError` if unusable."""
    if image is None or not isinstance(image, np.ndarray):
        raise InvalidInputError("image is not a valid numpy array")
    if image.ndim not in (2, 3):
        raise InvalidInputError(f"image has unsupported ndim={image.ndim}")
    h, w = image.shape[:2]
    if h < 20 or w < 20:
        raise InvalidInputError(f"image too small ({w}x{h} < 20x20)")
    if image.size == 0:
        raise InvalidInputError("image is empty")


def to_bgr(image: np.ndarray) -> np.ndarray:
    """Normalize an input array to a 3-channel BGR array (never aliases input)."""
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3:
        channels = image.shape[2]
        if channels == 1:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if channels == 3:
            return image.copy()
        if channels == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR).copy()
    raise InvalidInputError(f"image has unsupported shape {image.shape}")


def resize_image(image: np.ndarray, max_width: int = PREPROCESS_MAX_WIDTH) -> np.ndarray:
    """Downscale so the longest edge matches ``max_width`` (preserves aspect)."""
    h, w = image.shape[:2]
    if w <= max_width:
        return image.copy()
    scale = max_width / float(w)
    return cv2.resize(image, (max_width, int(round(h * scale))), interpolation=cv2.INTER_AREA)


def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def correct_orientation(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Correct gross document rotation (90-degree multiples).

    Chooses the rotation that makes the longer edge horizontal, which matches
    the natural layout of MRZ-less identity documents. Returns the corrected
    image and the applied rotation in degrees.
    """
    h, w = image.shape[:2]
    if h == w:
        return image.copy(), 0.0
    # Try 0/90/180/270 and prefer the alignment with the widest "text axis".
    candidates = [
        (0.0, image),
        (90.0, _rotate(image, 90.0)),
        (180.0, _rotate(image, 180.0)),
        (270.0, _rotate(image, 270.0)),
    ]
    best_angle, best_img = candidates[0]
    best_score = -1.0
    for angle, cand in candidates:
        gray = cv2.cvtColor(to_bgr(cand), cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _h = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        top = sorted(contours, key=cv2.contourArea, reverse=True)[:8]
        hulls = [cv2.convexHull(c, returnPoints=True) for c in top]
        lengths: list[float] = []
        for hull in hulls:
            rect = cv2.minAreaRect(hull)
            (_, _), (bw, bh), _ = rect
            lengths.append(max(bw, bh) / (min(bw, bh) + 1e-6))
        dominance = max(lengths) if lengths else 0.0
        if dominance > best_score:
            best_score, best_angle, best_img = dominance, angle, cand
    return best_img, best_angle


def denoise_image(image: np.ndarray) -> np.ndarray:
    """Mild edge-preserving denoising (never aggressive)."""
    return cv2.bilateralFilter(image, 5, 40, 40)


def normalize_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE adaptive contrast normalization on the L channel of LAB."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order four corner points TL, TR, BR, BL."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _detect_document_boundary(image: np.ndarray) -> tuple[np.ndarray | None, float]:
    """Find the largest rectilinear document quadrilateral + confidence."""
    h, w = image.shape[:2]
    scale = min(1.0, 1600 / max(h, w))
    small = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(gray, 75, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edged = cv2.dilate(edged, kernel, iterations=1)
    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0.0
    frame_area = small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if area / frame_area < 0.20:
                continue
            pts = approx.reshape(4, 2).astype("float32")
            if scale > 0:
                pts = pts / scale
            return _order_points(pts), float(np.clip(area / frame_area, 0.0, 1.0))
    return None, 0.0


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    tl, tr, br, bl = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_width = max(int(width_a), int(width_b))
    max_height = max(int(height_a), int(height_b))
    dst = np.array(
        [[0, 0], [max_width - 1, 0],
         [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height), flags=cv2.INTER_LINEAR)


def correct_perspective(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Optional perspective correction via document boundary detection."""
    pts, confidence = _detect_document_boundary(image)
    if pts is None or confidence < 0.5:
        return image, 0.0
    try:
        return _four_point_transform(image, pts), confidence
    except cv2.error:
        return image, 0.0


def preprocess_for_ocr(image: np.ndarray, options: dict | None = None) -> dict:
    """Run the full OCR preprocessing pipeline.

    Keeps ``original`` (untouched copy) and ``preprocessed`` fully separate, as
    required by the spec. Every stage is togglable via ``options``.
    Returns:

    * ``original``       — exact copy of the decoded input (never mutated).
    * ``preprocessed``   — OCR-ready BGR image.
    * ``metadata``       — dimensions, rotation, applied stages.
    """
    options = options or {}
    validate_image(image)
    bgr = to_bgr(image)
    original = bgr.copy()
    current = bgr
    stages: list[str] = []
    rotation = 0.0
    boundary_conf = 0.0

    if options.get("resize", True):
        current = resize_image(current)
        stages.append("resize")

    if options.get("orientation", True):
        current, rotation = correct_orientation(current)
        stages.append("orientation")

    if options.get("perspective", True):
        current, boundary_conf = correct_perspective(current)
        stages.append("perspective")
        if boundary_conf >= 0.5:
            stages.append("perspective_crop")

    if options.get("denoise", True):
        current = denoise_image(current)
        stages.append("denoise")

    if options.get("contrast", True):
        current = normalize_contrast(current)
        stages.append("contrast")

    h, w = current.shape[:2]
    metadata = {
        "width": int(w),
        "height": int(h),
        "rotation": round(float(rotation), 2),
        "stages_applied": stages,
        "document_boundary_confidence": round(float(boundary_conf), 4),
    }
    return {"original": original, "preprocessed": current, "metadata": metadata}
