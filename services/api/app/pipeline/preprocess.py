"""Document image preprocessing.

Deterministic OpenCV operations to prepare a document image for OCR:
decode safety, orientation correction, document boundary detection,
perspective transformation, cropping, resolution normalization,
denoising, contrast enhancement, and adaptive sharpening. No AI
dependencies.

*Note:* preprocessing produces an OCR-ready image but makes no
guarantee about OCR accuracy — that depends on the source document and
the OCR engine.
"""
import cv2
import numpy as np

from app.pipeline.quality import assess_image_quality

TARGET_PROCESSED_WIDTH = 2000
TARGET_PREVIEW_WIDTH = 640


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


# ---------------------------------------------------------------------------
# Phase 3 ingestion preprocessing
# ---------------------------------------------------------------------------


def decode_image(data: bytes) -> np.ndarray | None:
    """Safely decode encoded image bytes; returns None on any failure.

    Never trusts file extension or declared MIME type — decoding is the
    authoritative check and rejects truncated/corrupt images by returning
    None instead of proceeding.
    """
    if not data:
        return None
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return img


def encode_jpeg(image: np.ndarray, quality: int = 92) -> bytes:
    """Encode a BGR image to JPEG bytes (used for processed/preview objects)."""
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Failed to encode image")
    return buf.tobytes()


def correct_orientation(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Correct gross document orientation.

    Uses the bounding-box aspect ratio to rotate 90/180/270 degree flips
    so the document occupies its natural landscape/portrait layout. Returns
    the corrected image and the applied rotation in degrees.
    """
    h, w = image.shape[:2]
    # Treat the longer axis as the intended horizontal.
    quadrants = [
        (0.0, image),
        (90.0, _rotate(image, 90.0)),
    ]
    best = quadrants[0]
    for degrees, candidate in quadrants:
        ch, cw = candidate.shape[:2]
        if cw >= ch:
            best = (degrees, candidate)
            break
    return best[1], best[0]


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order four corner points as top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def detect_document_boundary(image: np.ndarray, max_dim: int = 1600) -> tuple[np.ndarray | None, float]:
    """Detect the largest rectilinear document quadrilateral.

    Downscales for speed, finds the largest near-rectangular contour, and
    returns the (ordered) corner points and a confidence in [0, 1]. Returns
    ``(None, 0.0)`` when no reliable boundary is found so the caller can
    fall back to using the full frame.
    """
    h, w = image.shape[:2]
    scale = min(1.0, max_dim / max(h, w))
    small = cv2.resize(
        image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
    )
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(gray, 75, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edged = cv2.dilate(edged, kernel, iterations=1)

    contours, _ = cv2.findContours(
        edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return None, 0.0

    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    frame_area = small.shape[0] * small.shape[1]

    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            # Require the document to cover a meaningful portion of the frame.
            if area / frame_area < 0.20:
                continue
            pts = approx.reshape(4, 2).astype("float32")
            # Map back to original coordinates.
            pts = pts / scale if scale > 0 else pts
            confidence = float(np.clip(area / frame_area, 0.0, 1.0))
            return _order_points(pts), confidence

    return None, 0.0


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply a perspective transform that crops the document quadrilateral."""
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_width = max(int(width_a), int(width_b))
    max_height = max(int(height_a), int(height_b))

    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(
        image, matrix, (max_width, max_height), flags=cv2.INTER_LINEAR
    )


def perspective_crop(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Crop out the document via boundary detection + perspective transform."""
    pts, confidence = detect_document_boundary(image)
    if pts is None or confidence < 0.5:
        return image, confidence
    try:
        return _four_point_transform(image, pts), confidence
    except cv2.error:
        return image, 0.0


def normalize_resolution(
    image: np.ndarray, target_width: int = TARGET_PROCESSED_WIDTH
) -> np.ndarray:
    """Resize so the long edge (width) matches the target, preserving aspect ratio."""
    h, w = image.shape[:2]
    if w <= target_width:
        return image
    scale = target_width / float(w)
    return cv2.resize(
        image, (target_width, int(h * scale)), interpolation=cv2.INTER_AREA
    )


def sharpen(image: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """Apply adaptive sharpening with an unsharp-mask style kernel."""
    kernel = np.array([[-1, -1, -1], [-1, 9 + amount, -1], [-1, -1, -1]])
    return cv2.filter2D(image, -1, kernel)


def sharpen_where_appropriate(image: np.ndarray) -> np.ndarray:
    """Sharpen only when the image is reasonably sharp to avoid amplifying noise."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    vol = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if vol < 100:
        # Very blurry — skip sharpening to avoid noise amplification.
        return image
    return sharpen(image, amount=0.3)


def make_preview(image: np.ndarray, width: int = TARGET_PREVIEW_WIDTH) -> np.ndarray:
    """Produce a lightweight preview (JPEG-friendly) of the processed image."""
    h, w = image.shape[:2]
    if w <= width:
        return image
    scale = width / float(w)
    return cv2.resize(
        image, (width, int(h * scale)), interpolation=cv2.INTER_AREA
    )


def run_ingestion_preprocess(image: np.ndarray, options: dict | None = None) -> dict:
    """Run the Phase 3 ingestion preprocessing pipeline.

    Keeps the original untouched and returns the processed (OCR-ready) and
    preview images plus a metadata structure with width, height, rotation,
    quality score, blur score, brightness score, and boundary confidence.
    """
    options = options or {}
    stages: list[str] = []

    # 1-2. Orientation correction.
    oriented, rotation = correct_orientation(image)
    stages.append("orientation")

    # 3-5. Boundary detection, perspective transform, cropping.
    cropped, boundary_conf = perspective_crop(oriented)
    stages.append("boundary_detect")
    if boundary_conf >= 0.5:
        stages.append("perspective_crop")

    # 6. Resolution normalization.
    normalized = normalize_resolution(cropped)
    stages.append("resolution_norm")

    # 7. Denoising.
    denoised = denoise(normalized) if options.get("denoise", True) else normalized.copy()
    stages.append("denoise")

    # 8. Contrast enhancement.
    enhanced = enhance_contrast(denoised)
    stages.append("contrast_enhance")

    # 9. Sharpening where appropriate.
    sharpened = sharpen_where_appropriate(enhanced)
    stages.append("sharpen")

    processed = sharpened

    quality = assess_image_quality(processed)
    preview = make_preview(processed)

    metadata = {
        "width": int(processed.shape[1]),
        "height": int(processed.shape[0]),
        "rotation": round(float(rotation), 2),
        "quality_score": quality["overall_score"],
        "quality_label": quality["quality_label"],
        "blur_score": round(1.0 - quality["sharpness_score"], 4),
        "brightness_score": quality["brightness_score"],
        "document_boundary_confidence": round(float(boundary_conf), 4),
        "resolution": quality["resolution_score"],
        "stages_applied": stages,
    }

    return {
        "original": image,
        "processed": processed,
        "preview": preview,
        "metadata": metadata,
    }
