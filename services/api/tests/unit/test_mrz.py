"""Tests for MRZ parsing and ICAO check-digit validation.

Uses intentionally-constructed synthetic TD3 strings (built with correct
check digits) plus deliberately corrupted variants to exercise validation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.pipeline.mrz import (
    mrz_check_digit,
    parse_mrz,
    parse_td3,
    validate_mrz_checksum,
)

# ---------------------------------------------------------------------------
# Check digit computation
# ---------------------------------------------------------------------------

def test_mrz_check_digit_numeric():
    # '015' (weights 7,3,1) -> 0*7 + 1*3 + 5*1 = 8
    assert mrz_check_digit("015") == 8


def test_check_digit_alphabet_mapping():
    # 'A' = 10; 'A00' -> 10*7 = 70 -> 0
    assert mrz_check_digit("A00") == 0
    # '0A0' -> A at index 1, weight 3 -> 10*3 = 30 -> 0
    assert mrz_check_digit("0A0") == 0


def test_check_digit_fill_char_zero():
    # '<' maps to 0
    assert mrz_check_digit("<<<") == 0


def test_validate_checksum_valid():
    assert validate_mrz_checksum("015", "8") is True


def test_validate_checksum_invalid():
    assert validate_mrz_checksum("015", "9") is False


def test_check_digit_roundtrip():
    # The computed check digit must validate.
    field = "AB12345"
    digit = str(mrz_check_digit(field))
    assert validate_mrz_checksum(field, digit) is True


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
    """Build a valid (or intentionally corrupted) TD3 line 2 (44 chars).

    Layout: passport(9) check(1) nationality(3) dob(6) dobcd(1) sex(1)
    expiry(6) expcd(1) personal(8) personalcd(1) optional(5) final(1) spare(1).
    """
    def cd_or(corrupt, field):
        return corrupt if corrupt is not None else str(mrz_check_digit(field))

    passport_padded = passport.ljust(9, "<")
    passport_cd = cd_or(corrupt_passport_cd, passport_padded)
    dob_cd = cd_or(corrupt_dob_cd, dob)
    expiry_cd = cd_or(corrupt_expiry_cd, expiry)
    personal_padded = personal.ljust(8, "<")
    personal_cd = cd_or(corrupt_personal_cd, personal_padded)
    optional_padded = optional.ljust(5, "<")
    # Composite final check digit covers line2 indices 2:42, which begins
    # part-way through the passport number (index 2) through the optional data.
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
    assert result.mrz_detected is True
    assert result.mrz_valid is True
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
    assert p["final_check_digit"]  # present
    assert all(v is True for v in result.check_digits.values())


def test_parse_td3_raw_lines_preserved():
    lines = _build_td3()
    result = parse_td3(lines)
    assert result.raw_mrz == [ln.upper() for ln in lines]


# ---------------------------------------------------------------------------
# Corrupted MRZ strings (validation catches each)
# ---------------------------------------------------------------------------

def test_corrupt_passport_number():
    lines = _build_td3(passport="L898902C", corrupt_passport_cd="0")
    result = parse_mrz(lines)
    assert result.mrz_detected is True
    assert result.mrz_valid is False
    assert result.check_digits["passport_number"] is False


def test_corrupt_date_of_birth():
    lines = _build_td3(corrupt_dob_cd="0")
    result = parse_mrz(lines)
    assert result.mrz_valid is False
    assert result.check_digits["date_of_birth"] is False


def test_corrupt_expiry_date():
    lines = _build_td3(corrupt_expiry_cd="0")
    result = parse_mrz(lines)
    assert result.mrz_valid is False
    assert result.check_digits["expiry_date"] is False


def test_corrupt_personal_number():
    # Corrupt the personal number check digit to a wrong value but keep the
    # composite final check digit consistent with the TRUE personal digit, so
    # only the personal-number check fails.
    lines = _build_td3(corrupt_personal_cd="9")
    result = parse_mrz(lines)
    assert result.mrz_valid is False
    assert result.check_digits["personal_number"] is False


def test_corrupt_final_check_digit():
    lines = _build_td3(corrupt_final_cd="0")
    result = parse_mrz(lines)
    assert result.mrz_valid is False
    assert result.check_digits["final"] is False


def test_corrupt_document_code():
    lines = _build_td3(corrupt_document_code=True)
    result = parse_mrz(lines)
    assert result.mrz_detected is True
    # Document code not starting with P produces a warning but check digits
    # remain valid.
    assert "non_passport_document_code" in result.warnings
    assert result.mrz_valid is True


# ---------------------------------------------------------------------------
# Format / error handling
# ---------------------------------------------------------------------------

def test_parse_mrz_rejects_short_lines():
    result = parse_mrz(["SHORT", "LINES"])
    assert result.mrz_detected is False
    assert "unrecognized_mrz_format" in result.warnings


def test_parse_mrz_empty():
    result = parse_mrz([])
    assert result.mrz_detected is False
    assert "empty_mrz" in result.warnings


def test_parse_mrz_requires_exact_length():
    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    result = parse_mrz([line1, "TOO SHORT"])
    assert result.mrz_detected is False


def test_mrz_not_detected_structure():
    result = parse_mrz([])
    assert result.mrz_detected is False
    assert result.check_digits == {}
    assert result.parsed_fields == {}
