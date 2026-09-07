"""Modular forensic detectors.

Each detector implements the :class:`ForensicDetector` interface and produces a
single :class:`ForensicFinding` for an input image. Detectors are independent
and return *signal* outputs — bounded anomaly scores, suspicious regions,
evidence statistics, and cautious human-readable descriptions. They never
claim definitive forgery; all language is calibrated toward "potential
manipulation indicators".

The architecture is intentionally pluggable: a PyTorch-based detector can be
added later by implementing the same interface and registering it in the
pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.forensics.analyze import compute_ela


def _severity(score: float) -> str:
    if score >= 0.55:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"


def _normalized_bbox(x: int, y: int, w: int, h: int, img_w: int, img_h: int) -> dict:
    """Convert pixel bbox to normalized [0,1] coordinates."""
    return {
        "x": round(max(0.0, x / img_w), 4),
        "y": round(max(0.0, y / img_h), 4),
        "w": round(min(1.0, w / img_w), 4),
        "h": round(min(1.0, h / img_h), 4),
    }


def _norm_to_uint8(src: np.ndarray) -> np.ndarray:
    """Normalize a float map to the 0..255 uint8 range."""
    mn, mx = float(np.min(src)), float(np.max(src))
    if mx - mn < 1e-9:
        out = np.zeros_like(src, dtype=np.uint8)
    else:
        out = ((src - mn) * 255.0 / (mx - mn)).astype(np.uint8)
    return out


def _encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        return b""
    return buf.tobytes()


def _encode_heatmap(ela_map: np.ndarray) -> np.ndarray:
    """Colorize an ELA map as a heatmap image (BGR)."""
    norm = _norm_to_uint8(ela_map)
    return cv2.applyColorMap(norm, cv2.COLORMAP_JET)


@dataclass
class ForensicFinding:
    """Output of a single forensic detector."""

    detector_id: str
    detector_name: str
    score: float  # 0..1 anomaly signal strength
    severity: str  # LOW | MEDIUM | HIGH
    description: str
    evidence: dict = field(default_factory=dict)
    regions: list[dict] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)  # artifact -> encoded bytes
    detector_status: str = "experimental"  # evidence class for production fusion


class ForensicDetector:
    """Base class / interface for a forensic detector.

    Subclasses set ``detector_id``, ``name``, ``default_weight`` and
    ``detector_status`` and implement :meth:`analyze` returning a
    :class:`ForensicFinding`.

    ``detector_status`` classifies the strength of evidence this detector is
    permitted to contribute toward a *production* tampering score:

    * ``"production"``  — validated and permitted to drive a fused score.
    * ``"conditional"`` — evidence-bearing only under explicit preconditions
      (e.g. editing-software metadata explicitly present).
    * ``"experimental"`` — research/debugging/visualization only. Its output
      must NOT silently contribute to a production tampering score.
    * ``"unvalidated"`` — implemented but never assessed.
    """

    detector_id: str = ""
    name: str = ""
    default_weight: float = 0.1
    detector_status: str = "experimental"

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Detector 1: ELA (Error Level Analysis)
# ---------------------------------------------------------------------------
class ELADetector(ForensicDetector):
    detector_id = "ela"
    name = "Error Level Analysis"
    default_weight = 0.25
    detector_status = "experimental"
    BLOCK = 32
    LOCAL_KERNEL = 3
    ELEVATION_THRESHOLD = 1.0   # strong localized ELA elevation to count as abnormal
    FRACTION_FULL = 0.10        # elevated blocks covering >=10% -> score 1.0

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        ela = compute_ela(image, quality=90)
        evidence: dict[str, Any] = {}
        regions: list[dict] = []
        score = 0.0

        if ela.size > 0 and float(np.mean(ela)) > 1e-3:
            grid = _block_grid(ela, block_size=self.BLOCK)
            mean_ela = float(np.mean(ela))
            h, w = ela.shape
            bs = self.BLOCK

            # Localized error-level anomaly: how much each block's ELA deviates
            # from its immediate surroundings, normalized by a floor-guarded
            # global scale. A re-saved/retouched area stands out against its own
            # neighborhood, whereas a uniform capture is locally flat. The
            # denominator carries an absolute floor so a zero-ELA flat
            # background cannot explode the relative ratio.
            scale = max(mean_ela, 0.5)
            local_contrast = _block_local_contrast(
                grid, kernel=self.LOCAL_KERNEL, scale=scale
            )
            max_contrast = float(np.max(local_contrast))
            mean_contrast = float(np.mean(local_contrast))

            # The reliable discriminator is the *spread* of strong localized
            # ELA elevation. Thin content (text strokes, borders) produces a few
            # high-contrast pixel cells but a near-zero elevated-region fraction;
            # a genuinely re-saved/retouched area drives the fraction up.
            elevated = local_contrast > self.ELEVATION_THRESHOLD
            elevated_frac = float(np.mean(elevated))

            # Surface individual abnormal cells as candidate regions when a
            # non-trivial elevated area exists.
            if elevated_frac >= 0.02:
                ys, xs = np.where(elevated)
                top = sorted(zip(ys.tolist(), xs.tolist()), key=lambda rc: -local_contrast[rc[0], rc[1]])[:6]
                for y, x in top:
                    regions.append(
                        {
                            **_normalized_bbox(x * bs, y * bs, bs, bs, w, h),
                            "reason": "locally elevated error level (ELA)",
                            "value": round(float(local_contrast[y, x]), 2),
                        }
                    )

            evidence = {
                "mean_ela": round(mean_ela, 4),
                "max_local_contrast": round(max_contrast, 4),
                "mean_local_contrast": round(mean_contrast, 4),
                "elevated_region_area_fraction": round(elevated_frac, 4),
            }
            # Saturate as the solid elevated-ELA region grows past ~10% of the
            # document; LOW on clean captures where thin content only produces a
            # negligible fraction of elevated blocks.
            score = float(np.clip(elevated_frac / self.FRACTION_FULL, 0.0, 1.0))

        artifacts = {
            "ela_map": _encode_png(_norm_to_uint8(ela)) if ela.size else b"",
            "ela_heatmap": _encode_png(_encode_heatmap(ela)) if ela.size else b"",
        }
        return ForensicFinding(
            detector_id=self.detector_id,
            detector_name=self.name,
            score=round(score, 4),
            severity=_severity(score),
            description=(
                "A region shows locally elevated error level relative to its "
                "neighbourhood, which is consistent with a re-saved or "
                "retouched area; a supporting anomaly signal, not proof "
                "(naive ELA is limited and can miss well-composited edits)."
            ),
            evidence=evidence,
            regions=regions,
            artifacts=artifacts,
            detector_status=self.detector_status,
        )


def _block_local_contrast(grid: np.ndarray, kernel: int, scale: float) -> np.ndarray:
    """Per-block absolute deviation from the local-neighbourhood median ELA.

    ``scale`` is the floor-guarded global ELA magnitude used to normalise the
    deviation so the result is content-invariant and bounded.
    """
    base = _local_median(grid, kernel=kernel)
    return np.abs(grid - base) / max(scale, 1e-6)


def _block_grid(ela_map: np.ndarray, block_size: int = 32) -> np.ndarray:
    h, w = ela_map.shape
    bh, bw = max(1, h // block_size), max(1, w // block_size)
    blocks = ela_map[: bh * block_size, : bw * block_size]
    return blocks.reshape(bh, block_size, bw, block_size).mean(axis=(1, 3))


def _local_median(grid: np.ndarray, kernel: int = 1) -> np.ndarray:
    """Per-cell median of the surrounding kernel x kernel neighbourhood.

    Used as a local baseline: a tampered region stands out against its own
    immediate surroundings, whereas content-driven variation is broad.
    A small kernel with an explicit self-inclusive median via margin tricks.
    """
    pad = kernel // 2
    padded = np.pad(grid, pad, mode="edge")
    out = np.empty_like(grid)
    h, w = grid.shape
    for i in range(h):
        for j in range(w):
            win = padded[i : i + kernel, j : j + kernel]
            out[i, j] = np.median(win)
    return out


def _contiguous_clusters(mask: np.ndarray) -> list[tuple[int, set]]:
    """Return contiguous 8-connected clusters as (label, pixel-coord set)."""
    num, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    clusters: dict[int, set] = {}
    for li in range(1, num):  # skip background
        ys, xs = np.where(labels == li)
        clusters[li] = set(zip(xs.tolist(), ys.tolist()))
        if stats is not None and stats[li, cv2.CC_STAT_AREA] == 0:
            continue
    ordered = sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True)
    return ordered


# ---------------------------------------------------------------------------
# Detector 2: Copy-move / duplicated-region detection
# ---------------------------------------------------------------------------
class CopyMoveDetector(ForensicDetector):
    detector_id = "copy_move"
    name = "Copy-move / duplicated-region"
    default_weight = 0.20
    detector_status = "experimental"
    MIN_SEPARATION = 48.0       # px; closer = same region, not a clone
    MAX_DESCRIPTOR_DIST = 60.0
    DISPLACEMENT_BIN = 8.0      # px quantisation for offset consolidation
    MIN_CONSISTENT = 4          # cloned features sharing one offset to confirm

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        orb = cv2.ORB_create(nfeatures=1500)  # type: ignore[attr-defined]
        kp, des = orb.detectAndCompute(gray, None)
        regions: list[dict] = []
        evidence: dict[str, Any] = {"keypoints": len(kp) if kp else 0, "clones": 0}
        score = 0.0

        if des is not None and kp is not None and len(des) > 4:
            pts = np.array([p.pt for p in kp], dtype=np.float32)
            matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
            # knnMatch k=2: first neighbour is itself, so the second nearest is
            # the best candidate for a duplicated region elsewhere.
            knn = matcher.knnMatch(des, des, k=2)
            candidates: list[tuple[int, int, tuple[float, float]]] = []
            for pair in knn:
                if len(pair) < 2:
                    continue
                nn = pair[1]
                if nn.trainIdx == nn.queryIdx:
                    continue
                if nn.distance > self.MAX_DESCRIPTOR_DIST:
                    continue
                a, b = pts[nn.queryIdx], pts[nn.trainIdx]
                dx, dy = b[0] - a[0], b[1] - a[1]
                if np.hypot(dx, dy) < self.MIN_SEPARATION:
                    continue
                candidates.append((nn.queryIdx, nn.trainIdx, (dx, dy)))

            score = self._cluster_clones(candidates, pts, gray, regions, evidence)

        return ForensicFinding(
            detector_id=self.detector_id,
            detector_name=self.name,
            score=round(score, 4),
            severity=_severity(score),
            description=(
                "Robustly matched features appear in two distinct locations with "
                "a consistent offset; a potential copy-move manipulation signal, "
                "not proof."
            ),
            evidence=evidence,
            regions=regions,
            detector_status=self.detector_status,
        )

    def _cluster_clones(
        self,
        candidates: list[tuple[int, int, tuple[float, float]]],
        pts: np.ndarray,
        gray: np.ndarray,
        regions: list[dict],
        evidence: dict,
    ) -> float:
        """Confirm and locate duplicated regions via a dominant displacement.

        True copy-move produces a *cluster* of feature pairs that all share one
        offset (source -> duplicate). Random noise produces scattered offsets, so
        requiring a consistent dominant offset rejects false positives.
        """
        h, w = gray.shape
        if not candidates:
            return 0.0

        # Bin each candidate by its rounded displacement.
        bins: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for q, t, (dx, dy) in candidates:
            key = (int(round(dx / self.DISPLACEMENT_BIN)), int(round(dy / self.DISPLACEMENT_BIN)))
            bins.setdefault(key, []).append((q, t))

        dominant, pairs = max(bins.items(), key=lambda kv: len(kv[1]))
        evidence["offset_bins"] = len(bins)
        if len(pairs) < self.MIN_CONSISTENT:
            evidence["clones"] = len(pairs)
            evidence["confirmed"] = False
            return 0.0

        evidence["confirmed"] = True
        evidence["clones"] = len(pairs)
        evidence["dominant_displacement"] = {
            "dx": round(dominant[0] * self.DISPLACEMENT_BIN, 1),
            "dy": round(dominant[1] * self.DISPLACEMENT_BIN, 1),
        }
        evidence["dominant_count"] = len(pairs)

        # Two feature clusters (source + duplicate) for the dominant offset.
        queries, trains = zip(*pairs)
        boxes = []
        for idxs in (queries, trains):
            xs = pts[list(idxs)][:, 0]
            ys = pts[list(idxs)][:, 1]
            boxes.append(
                _normalized_bbox(
                    int(xs.min()), int(ys.min()),
                    int(xs.max() - xs.min()), int(ys.max() - ys.min()),
                    w, h,
                )
            )
        for b in boxes[:4]:
            regions.append({"reason": "duplicated feature region", **b})
        evidence["duplicated_regions"] = len(boxes)

        total = evidence.get("keypoints", 0)
        ratio = len(pairs) / max(1, total)
        score = float(np.clip(1.0 - np.exp(-ratio * 25.0), 0.0, 1.0))
        return score


# ---------------------------------------------------------------------------
# Detector 3: Compression / JPEG block-artifact anomaly
# ---------------------------------------------------------------------------
class CompressionDetector(ForensicDetector):
    detector_id = "compression"
    name = "Compression / JPEG block-artifact anomaly"
    default_weight = 0.20
    detector_status = "experimental"

    @staticmethod
    def _blockiness(gray: np.ndarray, grid: int = 8) -> float:
        """Classic JPEG blockiness: boundary vs. mid-block discontinuity.

        Strong compression (or a heavily re-saved region) makes the 8x8
        DCT grid boundaries visible as steps. We measure the mean absolute
        difference across block boundaries minus the mean across mid-block
        locations, for both axes. Negative/near-zero means no visible
        block artifact; large positive means a heavy compression trace.
        """
        g = gray.astype(np.float32)
        h, w = g.shape
        dh = np.abs(np.diff(g, axis=1))   # shape (h, w-1): difference col c, c+1
        idx = np.arange(w - 1)
        bmask = (idx % grid == grid - 1).astype(np.float32)
        imask = (idx % grid == grid // 2).astype(np.float32)
        b = np.sum(dh * bmask[None, :], axis=1) / max(1.0, np.sum(bmask))
        i = np.sum(dh * imask[None, :], axis=1) / max(1.0, np.sum(imask))
        B_h = float(np.mean(b - i))

        dv = np.abs(np.diff(g, axis=0))   # shape (h-1, w)
        idy = np.arange(h - 1)
        bmasky = (idy % grid == grid - 1).astype(np.float32)
        imasky = (idy % grid == grid // 2).astype(np.float32)
        b2 = np.sum(dv * bmasky[:, None], axis=0) / max(1.0, np.sum(bmasky))
        i2 = np.sum(dv * imasky[:, None], axis=0) / max(1.0, np.sum(imasky))
        B_v = float(np.mean(b2 - i2))
        return B_h + B_v

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if gray.size == 0:
            return ForensicFinding(
                self.detector_id, self.name, 0.0, "LOW",
                "Image could not be read for compression analysis.",
                {}, [], {}, self.detector_status,
            )
        blockiness = self._blockiness(gray, grid=8)
        # A single-quality capture shows ~0 block artifact. Heavy recompression
        # or a visibly re-saved region pushes blockiness high.
        score = float(np.clip(1.0 - np.exp(-max(0.0, blockiness) / 8.0), 0.0, 1.0))
        evidence = {
            "blockiness": round(blockiness, 4),
            "grid": 8,
        }
        return ForensicFinding(
            detector_id=self.detector_id,
            detector_name=self.name,
            score=round(score, 4),
            severity=_severity(score),
            description=(
                "Visible JPEG block-grid artifacts suggest the image (or a "
                "region of it) was heavily re-compressed; a potential "
                "re-processing signal, not proof."
            ),
            evidence=evidence,
            detector_status=self.detector_status,
        )


# ---------------------------------------------------------------------------
# Detector 4: Metadata analysis
# ---------------------------------------------------------------------------
class MetadataDetector(ForensicDetector):
    detector_id = "metadata"
    name = "Image metadata"
    default_weight = 0.10
    detector_status = "conditional"

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        raw = context.get("raw_bytes")
        evidence: dict[str, Any] = {
            "software": None,
            "format": None,
            "exif_present": False,
            "comment": None,
        }
        if not raw:
            return ForensicFinding(
                self.detector_id, self.name, 0.0, "LOW",
                "No image bytes available for metadata analysis.", evidence, [], {},
                self.detector_status,
            )
        try:
            from io import BytesIO

            from PIL import Image

            with Image.open(BytesIO(raw)) as img:
                evidence["format"] = img.format
                info = {}
                try:
                    info = img.info
                except Exception:  # noqa: BLE001
                    info = {}
                software = info.get("software") or info.get("Software")
                comment = info.get("comment") or info.get("Comment")
                if software:
                    evidence["software"] = str(software)
                if comment and isinstance(comment, bytes):
                    comment = comment.decode("utf-8", "replace")
                evidence["comment"] = str(comment) if comment else None
                try:
                    if img.getexif() and len(img.getexif()) > 0:
                        evidence["exif_present"] = True
                except Exception:  # noqa: BLE001
                    pass
                evidence["mode"] = img.mode
                evidence["size"] = list(img.size)
        except Exception:  # noqa: BLE001
            evidence["error"] = "metadata unreadable"

        editing_software = bool(evidence.get("software") or evidence.get("comment"))
        score = 0.6 if editing_software else 0.0
        if editing_software:
            description = (
                "Image metadata indicates editing software; this is a "
                "supporting anomaly signal for manual review."
            )
        else:
            description = (
                "No editing-software marker found in metadata. Absence of "
                "metadata is not proof of authenticity either way."
            )
        return ForensicFinding(
            detector_id=self.detector_id,
            detector_name=self.name,
            score=score,
            severity=_severity(score),
            description=description,
            evidence=evidence,
            detector_status=self.detector_status,
        )


# ---------------------------------------------------------------------------
# Detector 5: Portrait-region analysis
# ---------------------------------------------------------------------------
class PortraitDetector(ForensicDetector):
    detector_id = "portrait"
    name = "Portrait-region"
    default_weight = 0.15
    detector_status = "experimental"

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        # Heuristic portrait region: right ~40% and top ~60% of the document.
        h, w = image.shape[:2]
        px0, py0 = int(w * 0.6), int(h * 0.05)
        px1, py1 = int(w * 0.98), int(h * 0.65)
        portrait = image[py0:py1, px0:px1]
        regions: list[dict] = []
        if portrait.size == 0:
            return ForensicFinding(self.detector_id, self.name, 0.0, "LOW",
                                   "Portrait region could not be isolated.", {}, [], {}, self.detector_status)
        # Boundary inconsistency: gradient magnitude at portrait border vs body.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        border = gray[py0:py1, px0:px1]
        body = gray[py0:py1, 0:px0]
        border_edges = np.mean(cv2.Canny(border, 50, 150))
        body_edges = np.mean(cv2.Canny(body, 50, 150)) if body.size else border_edges
        edge_ratio = border_edges / (body_edges + 1e-6)

        # Local compression difference: ELA within portrait vs complement.
        ela = compute_ela(image, quality=90)
        p_ela = float(ela[py0:py1, px0:px1].mean())
        c_ela = float(ela.mean())
        ela_diff = abs(p_ela - c_ela) / (c_ela + 1e-6)

        score = float(np.clip(
            0.5 * (1.0 - np.exp(-max(0.0, float(edge_ratio) - 1.0)))
            + 0.5 * (1.0 - np.exp(-ela_diff / 2.0)),
            0.0, 1.0,
        ))
        regions.append({
            **_normalized_bbox(px0, py0, px1 - px0, py1 - py0, w, h),
            "reason": "portrait region boundary/compression anomaly",
            "edge_ratio": round(float(edge_ratio), 3),
            "ela_diff": round(ela_diff, 3),
        })
        return ForensicFinding(
            detector_id=self.detector_id,
            detector_name=self.name,
            score=round(score, 4),
            severity=_severity(score),
            description=(
                "Boundary and local-compression differences around the portrait "
                "region may indicate photo substitution (supporting signal)."
            ),
            evidence={
                "edge_ratio": round(float(edge_ratio), 3),
                "ela_diff": round(ela_diff, 3),
            },
            regions=regions,
            detector_status=self.detector_status,
        )


# ---------------------------------------------------------------------------
# Detector 6: Text-region analysis
# ---------------------------------------------------------------------------
class TextDetector(ForensicDetector):
    detector_id = "text"
    name = "Text-region"
    default_weight = 0.10
    detector_status = "experimental"

    def analyze(self, image: np.ndarray, context: dict) -> ForensicFinding:
        # Heuristic text/MRZ region: bottom band of the document (~20%).
        h, w = image.shape[:2]
        ty0, tx0 = int(h * 0.80), 0
        text_band = image[ty0:h, :]
        regions: list[dict] = []
        if text_band.size == 0:
            return ForensicFinding(self.detector_id, self.name, 0.0, "LOW",
                                   "Text region could not be isolated.", {}, [], {}, self.detector_status)
        gray = cv2.cvtColor(text_band, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        density = float(np.count_nonzero(edges)) / max(1, edges.size)

        # Background continuity: local variance coherence across the band.
        ela = compute_ela(image, quality=90)
        band_ela = float(ela[ty0:h, :].mean())
        entire_ela = float(ela.mean())
        ela_diff = abs(band_ela - entire_ela) / (entire_ela + 1e-6)

        # Character-region anomaly: very high or very low edge density.
        density_score = 0.0
        if density < 0.005:
            density_score = 0.8  # suspiciously featureless text zone
        elif density > 0.35:
            density_score = 0.6  # unnaturally noisy character area

        score = float(np.clip(
            0.6 * density_score + 0.4 * (1.0 - np.exp(-ela_diff)),
            0.0, 1.0,
        ))
        regions.append({
            **_normalized_bbox(tx0, ty0, w, h - ty0, w, h),
            "reason": "text-region texture / background anomaly",
            "edge_density": round(density, 4),
            "ela_diff": round(ela_diff, 3),
        })
        return ForensicFinding(
            detector_id=self.detector_id,
            detector_name=self.name,
            score=round(score, 4),
            severity=_severity(score),
            description=(
                "Text-region texture or background continuity deviates from "
                "expectation; a possible retouching signal."
            ),
            evidence={
                "edge_density": round(density, 4),
                "ela_diff": round(ela_diff, 3),
            },
            regions=regions,
            detector_status=self.detector_status,
        )


ALL_DETECTORS: list[ForensicDetector] = [
    ELADetector(),
    CopyMoveDetector(),
    CompressionDetector(),
    MetadataDetector(),
    PortraitDetector(),
    TextDetector(),
]
