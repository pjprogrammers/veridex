"""Structured document field extraction from OCR text blocks.

The extraction layer never relies on raw OCR text order alone. Blocks are first
placed into 2D spatial order (rows), then a document-specific parser locates
printed field labels and reads the value that follows — mirroring how MRZ
fields are normalized so the visual-OCR / MRZ cross-validator can compare them.

Every extracted field retains its source OCR confidence and bounding box.
Romanized/printed labels are matched after uppercasing and stripping
punctuation; the first label that matches wins.
"""
from __future__ import annotations

import re

from ai.config import PADDLEOCR_LOW_CONFIDENCE
from ai.ocr.schemas import FieldValue, TextBlock

DOCUMENT_TYPES = (
    "passport",
    "visa",
    "aadhaar",
    "pan",
    "driving_licence",
    "identity_card",
    "generic",
)

_MONTHS = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

# field -> candidate printed labels (normalized, first wins)
_LABELS: dict[str, list[list[str]]] = {
    "document_number": [
        ["DOCUMENTNUMBER"], ["DOCUMENTNO"], ["DOCUMENTNR"], ["IDNUMBER"],
        ["PASSPORTNO"], ["PASSPORTNUMBER"], ["DRIVINGLICENSENO"], ["LICENSENO"],
        ["AADHAARNUMBER"], ["PERMANENTACCOUNTNUMBER"], ["PAN"],
    ],
    "passport_number": [["PASSPORTNO"], ["PASSPORTNUMBER"]],
    "surname": [["SURNAME"]],
    "given_names": [["GIVENNAMES"], ["GIVENNAME"]],
    "full_name": [["NAME"], ["FULLNAME"], ["APPLICANTNAME"], ["HOLDERNAME"]],
    "father_name": [["FATHERSNAME"], ["FATHERNAME"]],
    "date_of_birth": [["DATEOFBIRTH"], ["DOB"], ["BIRTHDATE"], ["YEAROFBIRTH"]],
    "expiry_date": [
        ["DATEOFEXPIRY"], ["EXPIRYDATE"], ["VALIDUNTIL"],
        ["VALIDTILL"], ["VALIDUPTO"], ["EXPIRY"],
    ],
    "nationality": [["NATIONALITY"]],
    "sex": [["SEX"], ["GENDER"]],
    "address": [["ADDRESS"]],
}

# Explicit per-document-type field lists (documents otherwise share all labels).
_DOC_TYPE_FIELDS: dict[str, list[str]] = {
    "passport": [
        "document_number", "surname", "given_names",
        "date_of_birth", "expiry_date", "nationality", "sex",
    ],
    "visa": [
        "document_number", "passport_number", "surname", "given_names",
        "date_of_birth", "expiry_date", "nationality", "sex",
    ],
    "aadhaar": ["document_number", "full_name", "date_of_birth", "sex", "address"],
    "pan": ["document_number", "full_name", "father_name", "date_of_birth"],
    "driving_licence": [
        "document_number", "full_name", "date_of_birth", "expiry_date",
    ],
    "identity_card": [
        "document_number", "full_name", "date_of_birth",
        "expiry_date", "nationality", "address",
    ],
    "generic": [
        "document_number", "full_name", "date_of_birth",
        "expiry_date", "nationality", "sex",
    ],
}


_FULLWIDTH: dict[str, str | int | None] = {
    **{chr(0xFF10 + i): str(i) for i in range(10)},
    **{chr(0xFF21 + i): chr(0x41 + i) for i in range(26)},
    **{chr(0xFF41 + i): chr(0x61 + i) for i in range(26)},
}


def asciify(text: str) -> str:
    """Map fullwidth (CJK-width) forms back to ASCII — common OCR output."""
    return text.translate(str.maketrans(_FULLWIDTH))


def _norm(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", asciify(text).upper())


def _bbox_center(block: TextBlock) -> tuple[float, float]:
    pts = block.bbox
    if len(pts) < 4:
        return 0.0, 0.0
    xs = [p[0] for p in pts[:4]]
    ys = [p[1] for p in pts[:4]]
    return sum(xs) / 4.0, sum(ys) / 4.0


def spatial_order(blocks: list[TextBlock]) -> list[list[TextBlock]]:
    """Group blocks into visual rows (top->bottom) then sort left->right.

    Rows are formed by y-center proximity relative to the median block height;
    blocks are never reordered within an unrecognized row.
    """
    usable = [b for b in blocks if b.bbox and len(b.bbox) >= 2 and b.text.strip()]
    if not usable:
        return []
    # median height from y-spans
    y_spans = []
    for b in usable:
        ys = [p[1] for p in b.bbox[:4]]
        y_spans.append(max(ys) - min(ys))
    median_height = float(sorted(y_spans)[len(y_spans) // 2]) if y_spans else 12.0
    gap = max(median_height * 0.6, 4.0)

    ordered = sorted(usable, key=lambda b: _bbox_center(b)[1])
    rows: list[list[TextBlock]] = []
    current: list[TextBlock] = []
    last_y: float | None = None
    for b in ordered:
        _, yc = _bbox_center(b)
        if last_y is None or yc - last_y <= gap:
            current.append(b)
        else:
            rows.append(current)
            current = [b]
        last_y = yc
    if current:
        rows.append(current)
    return [sorted(row, key=lambda b: _bbox_center(b)[0]) for row in rows]


def _match_label(
    row: list[TextBlock], label_tokens: list[str]
) -> tuple[int, int] | None:
    """Return the (start, end) block span of a label within a row, else None."""
    tokens = [_norm(b.text) for b in row]
    expected = _norm("".join(label_tokens))
    for i in range(len(tokens)):
        if tokens[i] == expected:
            return i, i + 1
        joined = ""
        j = i
        while j < len(tokens) and len(joined) < len(expected) + 2:
            joined += tokens[j]
            if joined == expected:
                return i, j + 1
            j += 1
    return None


def _read_value(
    row: list[TextBlock], start: int, max_blocks: int = 4
) -> tuple[str, float, list[list[int]] | None]:
    """Collect value blocks following a matched label in the same row."""
    texts: list[str] = []
    confs: list[float] = []
    points: list[list[int]] = []
    all_labels = {
        _norm(tok)
        for variants in _LABELS.values()
        for variant in variants
        for tok in variant
    }
    for b in row[start:start + max_blocks]:
        if _norm(b.text) in all_labels:
            break
        texts.append(b.text.strip())
        confs.append(b.confidence)
        points.extend(b.bbox[:4])
    if not texts:
        return "", 0.0, None
    value = " ".join(t for t in texts if t)
    confidence = sum(confs) / len(confs)
    return value, confidence, points or None


def _read_value_column(
    row: list[TextBlock], start: int, span: tuple[float, float], max_blocks: int = 8
) -> tuple[str, float, list[list[int]] | None]:
    """Collect value blocks that stay inside a label's column on a below row."""
    lx0, lx1 = span
    tolerance = 20.0
    texts: list[str] = []
    confs: list[float] = []
    points: list[list[int]] = []
    all_labels = {
        _norm(tok)
        for variants in _LABELS.values()
        for variant in variants
        for tok in variant
    }
    for b in row[start:start + max_blocks]:
        if not b.bbox:
            break
        xs = [p[0] for p in b.bbox[:4]]
        if min(xs) < lx0 - tolerance or max(xs) > lx1 + tolerance:
            break
        if _norm(b.text) in all_labels:
            break
        texts.append(b.text.strip())
        confs.append(b.confidence)
        points.extend(b.bbox[:4])
    if not texts:
        return "", 0.0, None
    value = " ".join(t for t in texts if t)
    confidence = sum(confs) / len(confs)
    return value, confidence, points or None


def normalize_date(raw: str) -> str:
    """Best-effort normalize a printed date to MRZ YYMMDD; '' if unparseable."""
    text = asciify(raw.strip()).upper()
    m = re.match(r"^(\d{1,2})[/\-.\s]+(\d{1,2})[/\-.\s]+(\d{2,4})$", text)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        y = (f"20{y}" if len(y) == 2 else y)
        if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12:
            return f"{int(y) % 100:02d}{int(mo):02d}{int(d):02d}"
    m2 = re.match(r"^(\d{1,2})\s+([A-Z]{3})\s+(\d{4})$", text)
    if m2:
        d, mon, y = m2.group(1), _MONTHS.get(m2.group(2)), m2.group(3)
        if mon:
            return f"{int(y) % 100:02d}{mon}{int(d):02d}"
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) == 8:
        d1, m1, y1 = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
        if 1 <= d1 <= 31 and 1 <= m1 <= 12 and 1900 <= y1 <= 2099:
            return f"{y1 % 100:02d}{m1:02d}{d1:02d}"
        year2, mon2, day2 = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if 1 <= day2 <= 31 and 1 <= mon2 <= 12 and 1900 <= year2 <= 2099:
            return f"{year2 % 100:02d}{mon2:02d}{day2:02d}"
    if len(digits) == 6:
        return digits
    return ""


def _finalize(field: str, value: str, confidence: float, bbox: list[list[int]] | None) -> FieldValue:
    value = asciify(value)
    if field in ("document_number", "passport_number"):
        value = re.sub(r"[^A-Z0-9<]", "", value.upper())
    elif field in ("surname", "given_names", "full_name", "father_name"):
        value = " ".join(value.split()).upper()
    elif field in ("date_of_birth", "expiry_date"):
        value = normalize_date(value)
    elif field == "nationality":
        value = re.sub(r"[^A-Z]", "", value.upper())
    elif field == "sex":
        norm = _norm(value)
        value = norm if norm in ("M", "F", "X") else value.strip()
    return FieldValue(
        value=value,
        confidence=round(float(confidence), 4),
        bbox=bbox,
        low_confidence=confidence < PADDLEOCR_LOW_CONFIDENCE,
    )


def _build_full_name(fields: dict[str, FieldValue]) -> dict[str, FieldValue]:
    surname = fields.get("surname")
    given = fields.get("given_names")
    if not surname and not given:
        return fields
    both = bool(surname and given)
    parts = [surname.value if surname else "", given.value if given else ""]
    name = " ".join(p for p in parts if p).upper()
    if not name:
        return fields
    conf = min((surname.confidence if surname else 1.0), (given.confidence if given else 1.0)) if both else (
        surname.confidence if surname else given.confidence if given else 0.0
    )
    bbox = None
    if both and surname and given:
        allp = (surname.bbox or []) + (given.bbox or [])
        bbox = allp or None
    elif surname and surname.bbox:
        bbox = surname.bbox
    elif given and given.bbox:
        bbox = given.bbox
    fields["full_name"] = FieldValue(
        value=name,
        confidence=round(float(conf), 4),
        bbox=bbox,
        low_confidence=conf < PADDLEOCR_LOW_CONFIDENCE,
    )
    return fields


def _row_span(blocks: list[TextBlock]) -> tuple[float, float] | None:
    """Horizontal x-range (min, max) covered by a row's blocks with a bbox."""
    xs = [p[0] for b in blocks for p in b.bbox if b.bbox]
    if not xs:
        return None
    return min(xs), max(xs)


def _index_below_value(label_row: list[TextBlock], below_row: list[TextBlock]) -> int:
    """Index into ``below_row`` of the value printed under a same-column label.

    Metric passport layouts print the label above its value, sharing a column.
    Returns the leftmost aligned (and non-label) block, falling back to the
    leftmost usable block of the row. ``-1`` when alignment can't be judged.
    """
    span = _row_span(label_row)
    if span is None:
        return -1
    lx0, lx1 = span
    all_labels = {
        _norm(tok)
        for variants in _LABELS.values()
        for variant in variants
        for tok in variant
    }
    best = -1
    for i, b in enumerate(below_row):
        if _norm(b.text) in all_labels:
            continue
        if not b.bbox:
            continue
        xs = [p[0] for p in b.bbox[:4]]
        cx = (min(xs) + max(xs)) / 2.0
        if lx0 - 20 <= cx <= lx1 + 20 and best < 0:
            best = i
            break
    if best < 0:
        for i, b in enumerate(below_row):
            if _norm(b.text) in all_labels:
                continue
            best = i
            break
    return best


def extract_fields(blocks: list[TextBlock], document_type: str = "generic") -> dict[str, FieldValue]:
    """Extract normalized document fields from OCR text blocks.

    ``document_type`` selects the fields considered; the generic label set is
    always available as a fallback so fields are never silently dropped.
    """
    if document_type not in DOCUMENT_TYPES:
        document_type = "generic"
    rows = spatial_order(blocks)
    if not rows:
        return {}

    wanted = _DOC_TYPE_FIELDS.get(document_type, _DOC_TYPE_FIELDS["generic"])
    fields: dict[str, FieldValue] = {}

    for field in wanted:
        for label_tokens in _LABELS.get(field, []):
            for ri, row in enumerate(rows):
                matched = _match_label(row, label_tokens)
                if matched is None:
                    continue
                start, end = matched
                value, conf, bbox = _read_value(row, end)
                if value.strip():
                    fields[field] = _finalize(field, value, conf, bbox)
                    break
                # Same-row match with no value to the right: metric layouts
                # print the value on the row directly below, same column.
                if ri + 1 < len(rows):
                    span = _row_span(row[start:end])
                    if span is not None:
                        vidx = _index_below_value(row[start:end], rows[ri + 1])
                        if vidx >= 0:
                            value, conf, bbox = _read_value_column(
                                rows[ri + 1], vidx, span
                            )
                            if value.strip():
                                fields[field] = _finalize(field, value, conf, bbox)
                                break
            if field in fields:
                break

    if document_type == "passport":
        fields = _build_full_name(fields)
    return fields
