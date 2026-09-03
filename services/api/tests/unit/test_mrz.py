"""Tests for MRZ parsing and check-digit validation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.pipeline.mrz import mrz_check_digit, parse_mrz, validate_mrz_checksum


def test_mrz_check_digit_known_value():
    # ICAO example: 'L898902C' -> ?
    # Verified simple case: document number with known check digit.
    # '015' (weights 7,3,1) -> 0*7 + 1*3 + 5*1 = 8
    assert mrz_check_digit("015") == 8


def test_check_digit_alphabet_mapping():
    # 'A' = 10
    assert mrz_check_digit("A00") == (10 * 7) % 10


def test_validate_checksum_valid():
    # '015' -> 8
    assert validate_mrz_checksum("015", "8") is True


def test_validate_checksum_invalid():
    assert validate_mrz_checksum("015", "9") is False


def test_parse_td3_valid():
    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    # line1 must be 44 chars
    assert len(line1) == 44
    line2 = "L898902C<3UTO6908061F9406236ZE184226B<<<<<14"
    assert len(line2) == 44
    result = parse_mrz([line1, line2])
    assert result.valid is True
    assert result.format == "TD3"
    assert result.surname == "ERIKSSON"
    assert "ANNA" in result.given_names


def test_parse_mrz_rejects_short_lines():
    result = parse_mrz(["SHORT", "LINES"])
    assert result.valid is False
    assert result.errors


def test_parse_mrz_empty():
    result = parse_mrz([])
    assert result.valid is False
