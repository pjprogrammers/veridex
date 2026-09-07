"""MRZ region detection and line assembly from OCR word boxes.

The MRZ zone of a passport is a fixed block of dense, evenly-spaced,
uppercase text. This module:

1. Detects candidate MRZ rows by examining OCR word boxes (y-center
   clustering, character density, and gap consistency).
2. Assembles each detected row into a normalized uppercase string.
3. Returns the assembled candidate lines for the parser.

This is deterministic and engine-agnostic: it consumes the normalized word
box list from any OCR engine (``[{text, confidence, box}, ...]``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

_MIN_ROW_CHARS = 20          # ignore candidates shorter than this
_MIN_ROW_WORDS = 3           # a real MRZ line is split into several words
_ROW_Y_BUCKET = 12           # px tolerance for grouping words on one row
_MAX_ROWS = 4                # MRZ is 2-3 lines; allow a small margin
_MIN_DIAG_CHARS = 30         # combined detection threshold for "dense"


@dataclass
class MRZRegion:
    """Result of MRZ region detection."""

    detected: bool = False
    rows: list[list[dict]] = field(default_factory=list)  # raw word groups
    lines: list[str] = field(default_factory=list)        # assembled lines
    warnings: list[str] = field(default_factory=list)


def _word_center(w: dict) -> tuple[float, float]:
    box = w.get("box") or []
    if len(box) < 4:
        return 0.0, 0.0
    xs = [p[0] for p in box[:4]]
    ys = [p[1] for p in box[:4]]
    return sum(xs) / 4.0, sum(ys) / 4.0


def _row_width(w: dict) -> float:
    box = w.get("box") or []
    if len(box) < 4:
        return 0.0
    xs = [p[0] for p in box[:4]]
    return max(xs) - min(xs)


def cluster_rows(words: list[dict]) -> list[list[dict]]:
    """Group OCR words into visual rows by y-center bucket."""
    rows: dict[int, list[dict]] = {}
    for w in words:
        text = (w.get("text") or "").strip()
        if not text:
            continue
        _, yc = _word_center(w)
        key = int(yc) // _ROW_Y_BUCKET
        rows.setdefault(key, []).append(w)
        w["_xc"] = _word_center(w)[0]
    return [sorted(ws, key=lambda x: x["_xc"]) for ws in rows.values()]


def _assemble_line(row: list[dict]) -> str:
    """Join a row's words into a normalized uppercase MRZ-style string.

    Uses fill characters '<' to represent the blank gutters between word
    boxes so the fixed-width MRZ layout is preserved as closely as possible.
    """
    if not row:
        return ""
    # Sort by x-center (already sorted, but be safe).
    row_sorted = sorted(row, key=lambda w: _word_center(w)[0])
    parts: list[str] = []
    prev_right: float | None = None
    for w in row_sorted:
        text = (w.get("text") or "").strip().upper()
        if not text:
            continue
        xc, _ = _word_center(w)
        width = _row_width(w)
        left = xc - width / 2.0
        if prev_right is not None:
            gap = left - prev_right
            fill = "<" * max(0, int(gap / 10))
            if parts:
                parts.append(fill)
        parts.append(text)
        prev_right = xc + width / 2.0
    return "".join(parts)


def _is_dense_mrz_row(row: list[dict]) -> bool:
    """A candidate MRZ row should be dense and fairly continuous."""
    if len(row) < _MIN_ROW_WORDS:
        return False
    text = "".join((w.get("text") or "") for w in row)
    alnum = sum(1 for c in text if c.isalnum())
    return alnum >= _MIN_ROW_CHARS


def detect_mrz_region(words: list[dict]) -> MRZRegion:
    """Detect the MRZ region and assemble candidate lines from OCR words."""
    if not words:
        return MRZRegion(detected=False, warnings=["no_words"])

    rows = [r for r in cluster_rows(words) if _is_dense_mrz_row(r)]
    if not rows:
        return MRZRegion(detected=False, warnings=["no_dense_rows"])

    # Keep only dense rows, limited count.
    rows = rows[: _MAX_ROWS]
    lines = [_assemble_line(r) for r in rows]

    # Require enough combined density to consider the MRZ present.
    total_alnum = sum(1 for c in "".join(lines) if c.isalnum())
    if total_alnum < _MIN_DIAG_CHARS:
        return MRZRegion(
            detected=False,
            rows=rows,
            lines=lines,
            warnings=["low_density"],
        )

    return MRZRegion(detected=True, rows=rows, lines=lines)


def extract_mrz_from_words(words: list[dict]) -> MRZRegion:
    """Convenience wrapper that detects the region and returns it."""
    return detect_mrz_region(words)
