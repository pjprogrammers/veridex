"""Tests for field validation rules."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.validation.fields import (
    validate_country_code,
    validate_date_yyyymmdd,
    validate_document_number,
    validate_expiry,
    validate_fields,
    validate_sex_code,
)


def test_valid_date():
    r = validate_date_yyyymmdd("900101")
    assert r["verdict"] == "PASS"


def test_invalid_date_format():
    r = validate_date_yyyymmdd("90-01")
    assert r["verdict"] == "FAIL"


def test_impossible_date():
    r = validate_date_yyyymmdd("991331")
    assert r["verdict"] == "FAIL"


def test_future_date_warn():
    # yy=36 -> 2036 (future relative to 2026)
    r = validate_date_yyyymmdd("360101")
    assert r["verdict"] == "WARN"


def test_valid_document_number():
    r = validate_document_number("A1234567")
    assert r["verdict"] == "PASS"


def test_invalid_document_number_short():
    r = validate_document_number("A1")
    assert r["verdict"] == "FAIL"


def test_document_number_lowercase_rejected():
    r = validate_document_number("a1234567")
    assert r["verdict"] == "FAIL"


def test_sex_code_valid():
    assert validate_sex_code("M")["verdict"] == "PASS"
    assert validate_sex_code("F")["verdict"] == "PASS"
    assert validate_sex_code("X")["verdict"] == "PASS"


def test_sex_code_invalid():
    assert validate_sex_code("Q")["verdict"] == "FAIL"


def test_country_code_valid():
    assert validate_country_code("USA")["verdict"] == "PASS"


def test_country_code_invalid():
    assert validate_country_code("US")["verdict"] == "FAIL"


def test_expiry_past():
    r = validate_expiry("200101")
    assert r["verdict"] == "FAIL"
    assert r["reason"] == "document_expired"


def test_expiry_future():
    # yy=36 -> 2036, a future expiry
    r = validate_expiry("360101")
    assert r["verdict"] == "PASS"


def test_validate_fields_missing():
    r = validate_fields({})
    assert r["date_of_birth"]["verdict"] == "WARN"
    assert r["date_of_birth"]["reason"] == "missing_field"
