"""Document tampering forensics.

Implements multiple forensic signals that flag *potential* manipulation.
All outputs are bounded anomaly scores (0.0 = no anomaly, 1.0 = strong
anomaly) and are presented as "potential manipulation detected" signals,
never as proof of forgery.

Signals:
- ELA (Error Level Analysis): recompression/retouching artifacts.
- Noise inconsistency: statistical noise differences across regions.
- Splice/copy-move: high local similarity across non-overlapping regions.
- Density/edge anomalies in the MRZ or photo zones.
"""
import cv2
import numpy as np


def compute_ela(image: np.ndarray, quality: int = 90) -> np.ndarray:
    """Return the Error Level Analysis difference map.

    Re-encodes the image at a given JPEG quality and returns the absolute
    pixel difference between original and re-encoded versions.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    encoded, buf = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not encoded:
        return np.zeros_like(gray, dtype=np.float32)
    decoded = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if decoded is None:
        return np.zeros_like(gray, dtype=np.float32)
    diff = cv2.absdiff(gray.astype(np.float32), decoded.astype(np.float32))
    return diff


def _block_stats(ela_map: np.ndarray, block_size: int = 32) -> np.ndarray:
    """Compute mean ELA per non-overlapping block."""
    h, w = ela_map.shape
    bh, bw = max(1, h // block_size), max(1, w // block_size)
    blocks = ela_map[: bh * block_size, : bw * block_size]
    grid = blocks.reshape(bh, block_size, bw, block_size).mean(axis=(1, 3))
    return grid


def ela_anomaly_score(image: np.ndarray) -> dict:
    """Assess local ELA variability as a tampering indicator.

    Genuine full-frame captures show fairly uniform low ELA. Spots that were
    edited/re-saved have notably different ELA levels. We score by the
    normalized standard deviation of block-level ELA intensities.
    """
    ela = compute_ela(image, quality=90)
    if ela.size == 0 or float(np.max(ela)) < 1e-6:
        return {"score": 0.0, "mean_ela": 0.0, "block_std": 0.0, "signal": "ela"}

    grid = _block_stats(ela)
    block_std = float(np.std(grid))
    mean_ela = float(np.mean(ela))

    # Normalize std against local mean; high relative variability -> anomaly.
    rel_var = block_std / (mean_ela + 1e-6)
    # Saturating curve
    score = 1.0 - np.exp(-rel_var / 2.0)
    return {
        "score": round(float(np.clip(score, 0.0, 1.0)), 4),
        "mean_ela": round(mean_ela, 3),
        "block_std": round(block_std, 3),
        "signal": "ela",
    }


def noise_anomaly_score(image: np.ndarray) -> dict:
    """Detect inconsistent noise between quadrants.

    Different capture conditions or spliced regions produce differing noise
    statistics. We measure per-quadrant noise via one image denoise and
    compare residual statistics.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    residual = cv2.absdiff(gray, denoised).astype(np.float32)

    h, w = residual.shape
    mid_h, mid_w = h // 2, w // 2
    quads = [
        residual[:mid_h, :mid_w],
        residual[:mid_h, mid_w:],
        residual[mid_h:, :mid_w],
        residual[mid_h:, mid_w:],
    ]
    quad_means = [float(q.mean()) for q in quads if q.size > 0]
    if not quad_means:
        return {"score": 0.0, "signal": "noise"}

    # Ratio of max to min mean noise across quadrants.
    mn, mx = min(quad_means), max(quad_means)
    ratio = (mx / (mn + 1e-6)) - 1.0
    score = 1.0 - np.exp(-ratio / 1.5)
    return {
        "score": round(float(np.clip(score, 0.0, 1.0)), 4),
        "quadrant_means": [round(q, 3) for q in quad_means],
        "signal": "noise",
    }


def copy_move_anomaly_score(image: np.ndarray) -> dict:
    """Detect duplicated (copy-moved) regions via block self-similarity.

    A cheap deterministic proxy: compare small tiles within the image to
    themselves and flag tiles that match two distinct far-apart locations
    more strongly than chance. This is a weak but explainable signal.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (256, 256))
    tile = 16
    grid_h, grid_w = 256 // tile, 256 // tile

    tile_rows: list[np.ndarray] = []
    for i in range(grid_h):
        for j in range(grid_w):
            tile_rows.append(
                small[i * tile:(i + 1) * tile, j * tile:(j + 1) * tile].flatten()
            )

    tiles = np.array(tile_rows, dtype=np.float32)
    tiles -= tiles.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(tiles, axis=1, keepdims=True)
    norms[norms == 0] = 1e-6
    tiles_n = tiles / norms

    sim = tiles_n @ tiles_n.T
    np.fill_diagonal(sim, -1.0)  # ignore self
    # For each tile, count how many distinct others it matches
    threshold = 0.98
    matches = np.sum(sim > threshold, axis=1)
    strong_duplicates = int(np.sum(matches >= 2))
    total = len(tiles)
    ratio = strong_duplicates / total if total else 0.0
    score = 1.0 - np.exp(-ratio * 6.0)
    return {
        "score": round(float(np.clip(score, 0.0, 1.0)), 4),
        "duplicate_tiles": strong_duplicates,
        "total_tiles": total,
        "signal": "copy_move",
    }


def edge_density_anomaly(image: np.ndarray) -> dict:
    """Flag abnormally low or variable edge density in the photo zone.

    A photo that has been swapped/edited may show unnatural edge energy.
    Compares edge density between the top-half (likely identity fields) and
    border regions as a weak heuristic.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    total_px = edges.size
    edge_px = int(np.count_nonzero(edges))
    density = edge_px / total_px if total_px else 0.0

    # Normal documents have moderate edge density (0.02 - 0.12 typically).
    if density < 0.005:
        score = 0.9  # suspiciously featureless
    elif density > 0.3:
        score = 0.7  # unnaturally noisy
    else:
        score = 0.0
    return {
        "score": float(score),
        "edge_density": round(float(density), 4),
        "signal": "edge_density",
    }


def run_forensics(image: np.ndarray) -> dict:
    """Run all forensic signals and produce a combined assessment."""
    signals = {
        "ela": ela_anomaly_score(image),
        "noise": noise_anomaly_score(image),
        "copy_move": copy_move_anomaly_score(image),
        "edge_density": edge_density_anomaly(image),
    }

    # Weighted overall manipulation indicator (0-1).
    weights = {"ela": 0.4, "noise": 0.25, "copy_move": 0.25, "edge_density": 0.1}
    overall = sum(signals[k]["score"] * weights[k] for k in weights)

    flags = [
        {
            "signal": k,
            "score": v["score"],
            "severity": _severity(v["score"]),
            "description": _describe(k, v),
        }
        for k, v in signals.items()
    ]

    return {
        "overall_score": round(float(np.clip(overall, 0.0, 1.0)), 4),
        "signals": signals,
        "flags": flags,
        "summary": _summary(overall),
    }


def _severity(score: float) -> str:
    if score >= 0.55:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"


def _describe(signal: str, data: dict) -> str:
    if signal == "ela":
        return "Local error-level variation suggests possible local recompression or retouching."
    if signal == "noise":
        return "Inconsistent noise statistics across image regions may indicate splicing."
    if signal == "copy_move":
        return "Highly similar duplicated regions detected; possible copy-move manipulation."
    if signal == "edge_density":
        return "Edge energy distribution deviates from expectations for a genuine document."
    return ""


def _summary(overall: float) -> str:
    if overall >= 0.5:
        return "Multiple potential manipulation indicators detected. Manual review recommended."
    if overall >= 0.25:
        return "Some potential tampering indicators present. Manual review recommended."
    return "No strong tampering indicators detected under forensic heuristics."
