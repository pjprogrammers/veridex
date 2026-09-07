"""Configurable rule-based OCR field extraction.

Loads per-document-type YAML rule files and applies them to OCR word boxes
to extract structured identity fields.  This replaces the hardcoded ``_LABELS``
dict in ``field_parser.py`` with a data-driven approach that can be extended
to new document types by adding a YAML file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

_RULES_DIR = Path(__file__).parent / "ocr_rules"


@dataclass
class ExtractedField:
    """A single extracted field with its confidence and bounding box."""

    field_name: str
    value: str
    confidence: float
    bbox: list[list[float]] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of rule-based field extraction."""

    fields: list[ExtractedField] = field(default_factory=list)
    document_type: str = "unknown"
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "fields": [
                {
                    "field_name": f.field_name,
                    "value": f.value,
                    "confidence": round(f.confidence, 4),
                    "bbox": f.bbox,
                }
                for f in self.fields
            ],
            "raw_text": self.raw_text,
        }


def _norm(text: str) -> str:
    """Uppercase and strip non-alphanumeric for label matching."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _cluster_rows(words: list[dict]) -> list[list[dict]]:
    """Group OCR words into visual rows by y-center bucket."""
    rows: dict[int, list[dict]] = {}
    for w in words:
        box = w.get("box")
        text = w.get("text", "")
        if not box or len(box) < 2 or not text:
            continue
        yc = sum(p[1] for p in box[:4]) / 4
        key = int(yc) // 12
        rows.setdefault(key, []).append(w)
        xc = sum(p[0] for p in box[:4]) / 4
        w["_xc"] = xc
    return [sorted(ws, key=lambda w: w["_xc"]) for ws in rows.values()]


def _match_label(row: list[dict], label_norm: str) -> int:
    """Return index just after the matched label sequence, else -1.

    Supports single-token and multi-token label matching (e.g. "DATE"
    followed by "OF" followed by "BIRTH" matching "DATEOFBIRTH").
    """
    tokens = [w["_norm"] for w in row]
    for i in range(len(tokens)):
        if tokens[i] == label_norm:
            return i + 1
        joined = ""
        end = i
        while end < len(tokens) and len(joined) < len(label_norm) + 2:
            joined += tokens[end]
            if joined == label_norm:
                return end + 1
            end += 1
    return -1


def _read_value(row: list[dict], start: int, max_words: int = 3) -> tuple[str, list[dict]]:
    """Collect value words starting just after a matched label.

    Returns (value_text, matched_words) where matched_words preserves
    bounding boxes for the extracted value.
    """
    parts: list[str] = []
    matched: list[dict] = []
    all_label_norms: set[str] | None = None  # lazy
    for j in range(start, min(start + max_words, len(row))):
        text = row[j].get("text", "").strip()
        if not text:
            continue
        if all_label_norms is None:
            all_label_norms = set()
        if row[j]["_norm"] in all_label_norms:
            break
        parts.append(text)
        matched.append(row[j])
    return " ".join(parts).strip(), matched


def _parse_date(raw: str) -> str:
    """Convert DD-MM-YYYY or YYYY-MM-DD to YYMMDD for MRZ compatibility."""
    digits = re.sub(r"[^0-9]", "", raw)

    def _valid(d: int, m: int, y: int) -> bool:
        return 1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2099

    if len(digits) == 8:
        d1, m1, y1 = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
        if _valid(d1, m1, y1):
            return f"{y1 % 100:02d}{m1:02d}{d1:02d}"
        y2, m2, d2 = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _valid(d2, m2, y2):
            return f"{y2 % 100:02d}{m2:02d}{d2:02d}"
    elif len(digits) == 6:
        return digits
    return ""


def _uppercase_3char(v: str) -> str:
    cleaned = re.sub(r"[^A-Z]", "", v.upper())
    return cleaned[:3] if cleaned else ""


_NORMALIZERS: dict[str, Any] = {
    "uppercase": lambda v: v.upper(),
    "alphanumeric_uppercase": lambda v: re.sub(r"[^A-Z0-9]", "", v.upper()),
    "uppercase_3char": _uppercase_3char,
    "date_to_yymmdd": _parse_date,
    "raw": lambda v: v.strip(),
}


def load_rules(document_type: str) -> dict[str, Any] | None:
    """Load YAML extraction rules for a document type.

    Returns the parsed YAML dict, or ``None`` if no rules file exists.
    """
    path = _RULES_DIR / f"{document_type}.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def extract_fields(
    words: list[dict],
    document_type: str,
    raw_text: str = "",
) -> ExtractionResult:
    """Extract structured fields from OCR words using YAML rules.

    Parameters
    ----------
    words:
        OCR word boxes ``[{text, confidence, box}, ...]``.
    document_type:
        Document type key matching a YAML file name (e.g. ``"passport"``).
    raw_text:
        Full OCR text for storage.

    Returns
    -------
    ExtractionResult
        Extracted fields with per-field confidence and bounding boxes.
    """
    rules = load_rules(document_type)
    if not rules or not words:
        return ExtractionResult(document_type=document_type, raw_text=raw_text)

    field_rules = rules.get("fields", {})
    rows = _cluster_rows(words)
    for row in rows:
        for w in row:
            w["_norm"] = _norm(w.get("text", ""))

    extracted: list[ExtractedField] = []

    for field_name, rule in field_rules.items():
        labels = rule.get("labels", [])
        max_words = rule.get("max_words", 3)
        normalizer_name = rule.get("normalize", "raw")
        normalizer = _NORMALIZERS.get(normalizer_name, lambda v: v)
        allowed = rule.get("allowed_values")

        for label_text in labels:
            label_norm = _norm(label_text)
            matched = False
            for row in rows:
                idx = _match_label(row, label_norm)
                if idx < 0:
                    continue
                raw_value, matched_words = _read_value(row, idx, max_words)
                if not raw_value:
                    continue

                value = normalizer(raw_value)
                if allowed and value not in allowed:
                    continue

                avg_conf = (
                    sum(w.get("confidence", 0.0) for w in matched_words) / len(matched_words)
                    if matched_words
                    else 0.0
                )
                bbox = [w.get("box", []) for w in matched_words if w.get("box")]

                extracted.append(
                    ExtractedField(
                        field_name=field_name,
                        value=value,
                        confidence=round(avg_conf, 4),
                        bbox=bbox,
                    )
                )
                matched = True
                break
            if matched:
                break

    return ExtractionResult(
        fields=extracted,
        document_type=document_type,
        raw_text=raw_text,
    )
