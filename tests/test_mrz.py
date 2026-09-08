"""Tests for MRZ parsing and ICAO check-digit validation (ai.ocr.mrz).

Uses intentionally-constructed synthetic TD3 strings (built with correct
check digits) plus deliberately corrupted variants to exercise validation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.ocr.mrz import (
    compute_check_digit,
    detect_mrz_lines,
    normalize_mrz_line,
    parse_mrz,
    parse_td3,
    validate_check_digit,
)
from ai.ocr.schemas import TextBlock

# ---------------------------------------------------------------------------
# Check digit computation
# ---------------------------------------------------------------------------

def test_check_digit_numeric():
    assert compute_check_digit("015") == 8


def test_check_digit_alphabet_mapping():
    assert compute_check_digit("A00") == 0
    assert compute_check_digit("0A0") == 0


def test_check_digit_fill_char_zero():
    assert compute_check_digit("<<<") == 0


def test_validate_checksum_valid():
    assert validate_check_digit("015", "8") is True


def test_validate_checksum_invalid():
    assert validate_check_digit("015", "9") is False


def test_check_digit_roundtrip():
    field = "AB12345"
    digit = str(compute_check_digit(field))
    assert validate_check_digit(field, digit) is True


# ---------------------------------------------------------------------------
# Normalize / detection helpers
# ---------------------------------------------------------------------------

def test_normalize_mrz_line():
    assert normalize_mrz_line(" P<INDDOE<<JOHN ") == "P<INDDOE<<JOHN"
    assert normalize_mrz_line("P<INDDOE<<JOHN") == "P<INDDOE<<JOHN"


# ---------------------------------------------------------------------------
# Synthetic TD3 helpers
# ---------------------------------------------------------------------------

def _build_line2(
    passport="L898902C",
    nationality="UTO",
    dob="690806",
    sex="F",
    expiry="940623",
    personal="ZE184226",
    optional="B",
    corrupt_passport_cd=None,
    corrupt_dob_cd=None,
    corrupt_expiry_cd=None,
    corrupt_personal_cd=None,
    corrupt_final_cd=None,
):
    def cd_or(corrupt, field):
        return corrupt if corrupt is not None else str(compute_check_digit(field))

    passport_padded = passport.ljust(9, "<")
    passport_cd = cd_or(corrupt_passport_cd, passport_padded)
    dob_cd = cd_or(corrupt_dob_cd, dob)
    expiry_cd = cd_or(corrupt_expiry_cd, expiry)
    personal_padded = personal.ljust(8, "<")
    personal_cd = cd_or(corrupt_personal_cd, personal_padded)
    optional_padded = optional.ljust(5, "<")
    composite = (
        passport_padded[2:9] + passport_cd + nationality
        + dob + dob_cd + sex + expiry + expiry_cd
        + personal_padded + personal_cd + optional_padded
    )
    final_cd = cd_or(corrupt_final_cd, composite)
    line = (
        passport_padded + passport_cd + nationality
        + dob + dob_cd + sex + expiry + expiry_cd
        + personal_padded + personal_cd + optional_padded + final_cd + "<"
    )
    assert len(line) == 44, len(line)
    return line


def _build_td3(
    line1="P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
    corrupt_document_code=False,
    **line2_kwargs,
):
    if corrupt_document_code:
        line1 = "A<" + line1[2:]
    line2 = _build_line2(**line2_kwargs)
    assert len(line1) == 44, len(line1)
    assert len(line2) == 44, len(line2)
    return [line1, line2]


# ---------------------------------------------------------------------------
# Valid MRZ
# ---------------------------------------------------------------------------

def test_parse_td3_valid():
    lines = _build_td3()
    result = parse_mrz(lines)
    assert result.detected is True
    assert result.valid is True
    assert result.format == "TD3"
    p = result.parsed_fields
    assert p["document_code"] == "P<"
    assert p["issuing_state"] == "UTO"
    assert p["surname"] == "ERIKSSON"
    assert p["given_names"] == "ANNA MARIA"
    assert p["passport_number"] == "L898902C<"
    assert p["nationality"] == "UTO"
    assert p["date_of_birth"] == "690806"
    assert p["sex"] == "F"
    assert p["expiry_date"] == "940623"
    assert p["personal_number"] == "ZE184226"
    assert result.check_digits.document_number is True
    assert result.check_digits.date_of_birth is True
    assert result.check_digits.expiry_date is True
    assert result.check_digits.composite is True


def test_parse_td3_raw_lines_preserved():
    lines = _build_td3()
    result = parse_td3(lines)
    assert result.lines == [ln.upper() for ln in lines]


# ---------------------------------------------------------------------------
# Corrupted check digits
# ---------------------------------------------------------------------------

def test_corrupt_passport_number():
    lines = _build_td3(corrupt_passport_cd="0")
    result = parse_mrz(lines)
    assert result.detected is True
    assert result.valid is False
    assert result.check_digits.document_number is False


def test_corrupt_date_of_birth():
    lines = _build_td3(corrupt_dob_cd="0")
    result = parse_mrz(lines)
    assert result.valid is False
    assert result.check_digits.date_of_birth is False


def test_corrupt_expiry_date():
    lines = _build_td3(corrupt_expiry_cd="0")
    result = parse_mrz(lines)
    assert result.valid is False
    assert result.check_digits.expiry_date is False


def test_corrupt_personal_number():
    lines = _build_td3(corrupt_personal_cd="9")
    result = parse_mrz(lines)
    assert result.valid is False
    assert result.check_digits.personal_number is False


def test_corrupt_final_check_digit():
    lines = _build_td3(corrupt_final_cd="0")
    result = parse_mrz(lines)
    assert result.valid is False
    assert result.check_digits.composite is False


def test_corrupt_document_code():
    lines = _build_td3(corrupt_document_code=True)
    result = parse_mrz(lines)
    assert result.detected is True
    assert "non_passport_document_code" in result.warnings
    assert result.valid is True


# ---------------------------------------------------------------------------
# Format / error handling
# ---------------------------------------------------------------------------

def test_parse_mrz_rejects_short_lines():
    result = parse_mrz(["SHORT", "LINES"])
    assert result.detected is False
    assert "unrecognized_mrz_format" in result.warnings


def test_parse_mrz_empty():
    result = parse_mrz([])
    assert result.detected is False
    assert "empty_mrz" in result.warnings


def test_parse_mrz_requires_exact_length():
    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    result = parse_mrz([line1, "TOO SHORT"])
    assert result.detected is False


def test_mrz_not_detected_structure():
    result = parse_mrz([])
    assert result.detected is False
    assert result.check_digits.document_number is None


# ---------------------------------------------------------------------------
# detect_mrz_lines from TextBlocks
# ---------------------------------------------------------------------------

def test_detect_mrz_lines_from_blocks():
    lines = _build_td3()
    blocks = [
        TextBlock(text="PASSPORT", confidence=0.9, bbox=[[10, 10], [200, 10], [200, 40], [10, 40]]),
        TextBlock(text="JOHN DOE", confidence=0.88, bbox=[[10, 50], [200, 50], [200, 80], [10, 80]]),
        TextBlock(text=lines[0], confidence=0.92, bbox=[[10, 400], [300, 400], [300, 420], [10, 420]]),
        TextBlock(text=lines[1], confidence=0.93, bbox=[[10, 422], [300, 422], [300, 442], [10, 442]]),
    ]
    detected = detect_mrz_lines(blocks)
    assert detected is not None
    assert len(detected) == 2


def test_detect_mrz_lines_no_mrz():
    blocks = [
        TextBlock(text="PASSPORT", confidence=0.9, bbox=[[10, 10], [200, 10], [200, 40], [10, 40]]),
        TextBlock(text="JOHN DOE", confidence=0.88, bbox=[[10, 50], [200, 50], [200, 80], [10, 80]]),
    ]
    assert detect_mrz_lines(blocks) is None


# ---------------------------------------------------------------------------
# Inconsistent MRZ (mixed valid / invalid check digits → valid=False)
# ---------------------------------------------------------------------------

def test_partially_corrupted_valid_false():
    lines = _build_td3(corrupt_dob_cd="0", corrupt_expiry_cd="0")
    result = parse_mrz(lines)
    assert result.valid is False
    assert result.check_digits.date_of_birth is False
    assert result.check_digits.expiry_date is False


def test_detect_mrz_lines_skips_blocks_without_bbox():
    """Long candidate lines with no corner box must not crash pairing."""
    from ai.ocr.schemas import TextBlock as TB

    blocks = [
        TB(text="SMITH<<JORDAN<<<<<<<<<<<<<<<<<<<<<<", confidence=0.9, bbox=[]),
        TB(text="PASSPORT", confidence=0.9, bbox=[[10, 10], [200, 10], [200, 40], [10, 40]]),
    ]
    assert detect_mrz_lines(blocks) is None
