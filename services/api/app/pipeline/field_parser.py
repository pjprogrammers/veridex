"""Best-effort structured field extraction from visual OCR output.

Human-readable identity fields printed on a document face (name, date of
birth, document number, sex, nationality, expiry) are read by OCR as word
boxes. This module locates those fields by their printed labels and returns
them in the same normalized formats the MRZ parser produces, so the
OCR-vs-MRZ cross-validator can compare them meaningfully.

This is a deterministic baseline: it matches printed field labels and does
not depend on a specific OCR engine. It is intentionally conservative —
unmatched or ambiguous fields are simply omitted so the cross-validator
treats them as "missing" rather than wrong.
"""
import re

# Mapping of MRZ-style field name -> possible printed labels (uppercase,
# whitespace/punctuation removed). The first match wins.
_LABELS: dict[str, list[str]] = {
    "document_number": ["DOCUMENTNO", "DOCUMENTNO.", "DOCUMENTNR", "IDNUMBER", "PASSPORTNO", "PASSPORTNO."],
    "surname": ["SURNAME"],
    "given_names": ["GIVENNAME", "GIVENNAMES", "FIRSTNAME"],
    "date_of_birth": ["DATEOFBIRTH", "DOB", "BIRTHDATE"],
    "expiry_date": ["DATEOFEXPIRY", "VALIDUNTIL", "EXPIRYDATE", "EXPIRY"],
    "sex": ["SEX"],
    "nationality": ["NATIONALITY"],
}


def _norm_word(text: str) -> str:
    """Uppercase and strip spaces/punctuation for label matching."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _cluster_rows(words: list[dict]) -> list[list[dict]]:
    """Group OCR words into visual rows by y-center bucket, sorted left->right."""
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
    return [sorted(words, key=lambda w: w["_xc"]) for words in rows.values()]


def _match_label(words: list[dict], label_norm: str) -> int:
    """Return the index just after the label sequence start+length, else -1."""
    tokens = [w["_norm"] for w in words]
    for i in range(len(tokens)):
        if tokens[i] == label_norm:
            return i + 1
        # A concatenation across a few tokens (e.g. "DATE", "OF", "BIRTH")
        joined = ""
        end = i
        while end < len(tokens) and len(joined) < len(label_norm) + 2:
            joined += tokens[end]
            if joined == label_norm:
                return end + 1
            end += 1
    return -1


def _read_value(
    words: list[dict], start: int, max_words: int = 3
) -> str:
    """Collect the raw value text starting just after a matched label."""
    parts = []
    for j in range(start, min(start + max_words, len(words))):
        text = words[j].get("text", "").strip()
        if not text:
            continue
        # Don't swallow the next label.
        if _norm_word(text) in {tok for labels in _LABELS.values() for tok in labels}:
            break
        parts.append(text)
    return " ".join(parts).strip()


def _yy_mm_dd_from_printed(raw: str) -> str:
    """Convert a printed date (DD-MM-YYYY or YYYY-MM-DD) into MRZ YYMMDD."""
    digits = re.sub(r"[^0-9]", "", raw)

    def is_date(d: int, m: int, y: int) -> bool:
        return 1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2099

    if len(digits) == 8:
        d1, m1, y1 = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
        if is_date(d1, m1, y1):
            # DDMMYYYY
            return f"{y1 % 100:02d}{m1:02d}{d1:02d}"
        y2, m2, d2 = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if is_date(d2, m2, y2):
            # YYYYMMDD
            return f"{y2 % 100:02d}{m2:02d}{d2:02d}"
    elif len(digits) == 6:
        return digits
    return ""


def extract_fields_from_words(words: list[dict]) -> dict:
    """Extract structured identity fields from OCR word boxes.

    Returns a dict keyed by the MRZ-style field names used by the
    cross-validator (document_number, surname, given_names, date_of_birth,
    expiry_date, sex, nationality).
    """
    if not words:
        return {}

    rows = _cluster_rows(words)
    for row in rows:
        for w in row:
            w["_norm"] = _norm_word(w.get("text", ""))

    fields: dict[str, str] = {}

    for field, labels in _LABELS.items():
        matched = False
        for label_norm in labels:
            for row in rows:
                idx = _match_label(row, label_norm)
                if idx < 0:
                    continue
                raw = _read_value(row, idx)
                if not raw:
                    continue
                fields[field] = raw
                matched = True
                break
            if matched:
                break

    result: dict[str, str] = {}

    if "document_number" in fields:
        result["document_number"] = re.sub(r"[^A-Z0-9]", "", fields["document_number"].upper())

    if "surname" in fields:
        result["surname"] = fields["surname"].upper()

    if "given_names" in fields:
        result["given_names"] = fields["given_names"].upper()

    if "date_of_birth" in fields:
        dob = _yy_mm_dd_from_printed(fields["date_of_birth"])
        if dob:
            result["date_of_birth"] = dob

    if "expiry_date" in fields:
        exp = _yy_mm_dd_from_printed(fields["expiry_date"])
        if exp:
            result["expiry_date"] = exp

    if "sex" in fields:
        sex = _norm_word(fields["sex"])
        if sex in ("M", "F", "X"):
            result["sex"] = sex

    if "nationality" in fields:
        nat = re.sub(r"[^A-Z]", "", fields["nationality"].upper())
        if len(nat) == 3:
            result["nationality"] = nat

    return result
