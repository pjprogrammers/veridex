"""ICAO 9303 MRZ processing: detection, TD3 parsing, check-digit validation.

MRZ processing is fully independent from the visual-zone OCR path: raw OCR
lines are fed in, MRZ lines are detected, TD3 fields parsed, and check digits
validated against the ICAO algorithm. Visual-OCR / MRZ consistency is computed
separately and reported as an anomaly signal — not proof of fraud.
"""
from __future__ import annotations

import re

from ai.ocr.parser import asciify
from ai.ocr.schemas import ConsistencyEntry, MRZCheckDigits, MRZResult, TextBlock

_WEIGHTS = [7, 3, 1]


def _char_value(ch: str) -> int:
    if ch == "<":
        return 0
    if ch.isdigit():
        return int(ch)
    if ch.isalpha():
        return ord(ch.upper()) - ord("A") + 10
    return 0


def compute_check_digit(field: str) -> int:
    """ICAO 9303 check digit for a character sequence."""
    total = 0
    for i, ch in enumerate(field):
        total += _char_value(ch) * _WEIGHTS[i % 3]
    return total % 10


def validate_check_digit(field: str, check: str) -> bool:
    """Validate ``field`` against the single-character check digit ``check``."""
    if len(check) != 1 or not check.isdigit():
        return False
    return compute_check_digit(field) == int(check)


def normalize_mrz_line(line: str) -> str:
    """Uppercase and guarantee the ICAO field separator is ``<``."""
    return re.sub(r"[^A-Z0-9<]", "", asciify(line).upper())


def is_mrz_candidate(line: str) -> bool:
    """True when a line looks like an MRZ line (dense filler / digits)."""
    line = normalize_mrz_line(line)
    if len(line) < 20:
        return False
    letters = sum(c.isalpha() for c in line)
    digits = sum(c.isdigit() for c in line)
    fillers = sum(c == "<" for c in line)
    return letters + digits >= len(line) * 0.7 or fillers >= len(line) * 0.15


def detect_mrz_lines(blocks: list[TextBlock]) -> list[str] | None:
    """Detect the MRZ from OCR text blocks.

    Selects blocks that meet length/content MRZ heuristics and sit close
    together vertically near the bottom of the page. Returns the two
    (or one, if only one is legible) normalized lines, else ``None``.
    """
    candidates: list[tuple[float, TextBlock]] = []
    for b in blocks:
        norm = normalize_mrz_line(b.text)
        if not is_mrz_candidate(norm):
            continue
        # Blocks without a 4-corner box can't be positioned for pairing.
        if len(b.bbox) < 4:
            continue
        ys = [p[1] for p in b.bbox[:4]]
        yc = (min(ys) + max(ys)) / 2.0
        candidates.append((yc, b))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])

    # Greedy adjacent pairing: merge near-vertical neighbors into lines.
    pairs: list[list[TextBlock]] = []
    current: list[TextBlock] = []
    last_y: float | None = None
    for yc, b in candidates:
        if last_y is None or yc - last_y <= 20:
            current.append(b)
        else:
            pairs.append(current)
            current = [b]
        last_y = yc
    if current:
        pairs.append(current)

    best: list[str] = []
    for group in pairs:
        group.sort(key=lambda b: min(p[0] for p in b.bbox[:4]))
        text = "".join(normalize_mrz_line(b.text) for b in group)
        valid_chars = sum(
            1 for c in text
            if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        if len(text) >= 20 and valid_chars >= len(text) * 0.6:
            best = [text]
            break
    if not best:
        return None
    # Prefer a valid TD3 pair; otherwise return the longest candidate line.
    top_lines = sorted(
        (normalize_mrz_line(b.text) for yc, b in candidates),
        key=len,
        reverse=True,
    )
    for l1 in top_lines:
        for l2 in top_lines:
            if l1 is l2:
                continue
            candidate = [l1, l2]
            parsed = parse_mrz(candidate)
            if parsed.detected and parsed.valid:
                return candidate
    return best


# ---------------------------------------------------------------------------
# TD3 parsing
# ---------------------------------------------------------------------------


def _parse_name_block(block: str) -> tuple[str, str]:
    parts = block.split("<<")
    surname = parts[0].replace("<", " ").strip() if parts else ""
    given_names = " ".join(p.replace("<", " ").strip() for p in parts[1:]).strip() if len(parts) > 1 else ""
    return surname, given_names


def parse_td3(lines: list[str]) -> MRZResult:
    """Parse a 2x44 TD3 passport MRZ with complete check-digit validation."""
    if len(lines) != 2 or len(lines[0]) != 44 or len(lines[1]) != 44:
        return MRZResult(detected=False, warnings=["td3_length_mismatch"])

    line1 = lines[0].upper()
    line2 = lines[1].upper()

    document_code = line1[0:2]
    issuing_state = line1[2:5]
    surname, given_names = _parse_name_block(line1[5:44])

    passport_number = line2[0:9]
    passport_number_cd = line2[9]
    nationality = line2[10:13]
    date_of_birth = line2[13:19]
    date_of_birth_cd = line2[19]
    sex = line2[20]
    expiry_date = line2[21:27]
    expiry_date_cd = line2[27]
    personal_number = line2[28:36]
    personal_number_cd = line2[36]
    optional_data = line2[37:42]
    final_cd = line2[42]

    check_digits = MRZCheckDigits(
        document_number=validate_check_digit(passport_number, passport_number_cd),
        date_of_birth=validate_check_digit(date_of_birth, date_of_birth_cd),
        expiry_date=validate_check_digit(expiry_date, expiry_date_cd),
        personal_number=(
            None if personal_number_cd == "<"
            else validate_check_digit(personal_number, personal_number_cd)
        ),
        composite=validate_check_digit(line2[2:42], final_cd),
    )

    warnings: list[str] = []
    if not re.fullmatch(r"\d{6}", date_of_birth):
        warnings.append("invalid_date_of_birth_format")
    if not re.fullmatch(r"\d{6}", expiry_date):
        warnings.append("invalid_expiry_date_format")
    if not document_code.startswith("P"):
        warnings.append("non_passport_document_code")

    checks = [
        check_digits.document_number,
        check_digits.date_of_birth,
        check_digits.expiry_date,
        check_digits.personal_number,
        check_digits.composite,
    ]
    valid = all(v is not False for v in checks)

    return MRZResult(
        detected=True,
        valid=valid,
        format="TD3",
        lines=[line1, line2],
        check_digits=check_digits,
        parsed_fields={
            "document_code": document_code,
            "issuing_state": issuing_state,
            "surname": surname,
            "given_names": given_names,
            "full_name": (given_names + " " + surname).strip().upper(),
            "passport_number": passport_number,
            "nationality": nationality,
            "date_of_birth": date_of_birth,
            "sex": sex,
            "expiry_date": expiry_date,
            "personal_number": personal_number,
            "optional_data": optional_data,
        },
        warnings=warnings,
    )


def parse_mrz(lines: list[str]) -> MRZResult:
    """Parse MRZ lines, rejecting blank/invalid input and detecting TD3."""
    cleaned = [normalize_mrz_line(line) for line in lines if line.strip()]
    if not cleaned:
        return MRZResult(detected=False, warnings=["empty_mrz"])
    if len(cleaned) == 2 and len(cleaned[0]) == 44 and len(cleaned[1]) == 44:
        return parse_td3(cleaned)
    return MRZResult(detected=False, warnings=["unrecognized_mrz_format"], lines=cleaned)


# ---------------------------------------------------------------------------
# Visual-OCR / MRZ consistency
# ---------------------------------------------------------------------------


def _compare(visual, mrz) -> ConsistencyEntry:
    if visual is None and mrz is None:
        return ConsistencyEntry(visual="", mrz="", match=None)
    if visual is None or mrz is None:
        return ConsistencyEntry(
            visual=str(visual or ""), mrz=str(mrz or ""), match=None
        )
    return ConsistencyEntry(
        visual=str(visual),
        mrz=str(mrz),
        match=_normalize_for_compare(str(visual)) == _normalize_for_compare(str(mrz)),
    )


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _date_to_yy_mm_dd(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) == 6:
        return digits
    if len(digits) == 8:
        y, m, d = digits[0:4], digits[4:6], digits[6:8]
        if 1900 <= int(y) <= 2099:
            return f"{int(y) % 100:02d}{m}{d}"
    return digits or value


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------


def compare_visual_mrz(
    visual_fields: dict, mrz_fields: dict
) -> dict[str, ConsistencyEntry]:
    """Compare normalized visual-OCR fields against parsed MRZ fields.

    ``visual_fields`` is a mapping of field-name -> str or FieldValue; an
    unfound field on either side yields ``match=None`` (inconclusive, not
    fraud).
    """
    def v(field: str) -> str | None:
        item = visual_fields.get(field)
        if item is None:
            return None
        if hasattr(item, "value"):
            return str(item.value)
        return str(item)

    def m(field: str) -> str | None:
        return mrz_fields.get(field)

    dob_visual: str | None
    dob_mrz: str | None
    if mrz_fields.get("date_of_birth"):
        dob_visual = _date_to_yy_mm_dd(v("date_of_birth") or "")
        dob_mrz = _date_to_yy_mm_dd(m("date_of_birth") or "")
    else:
        dob_visual = v("date_of_birth")
        dob_mrz = m("date_of_birth")
    expiry_visual = _date_to_yy_mm_dd(v("expiry_date") or "") if v("expiry_date") else None
    expiry_mrz = _date_to_yy_mm_dd(m("expiry_date") or "") if m("expiry_date") else None

    visual_name = v("full_name")
    if not visual_name:
        surname = v("surname") or ""
        given = v("given_names") or ""
        visual_name = (given + " " + surname).strip().upper() or None
    mrz_name = m("full_name")

    return {
        "passport_number": _compare(v("document_number") or v("passport_number"), m("passport_number")),
        "name": _compare(visual_name, mrz_name),
        "date_of_birth": _compare(dob_visual, dob_mrz),
        "expiry_date": _compare(expiry_visual, expiry_mrz),
        "nationality": _compare(v("nationality"), m("nationality")),
    }
