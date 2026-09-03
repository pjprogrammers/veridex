"""Tests for cross-validation (OCR vs MRZ, cross-document)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.validation.cross_validate import (
    compare_field,
    cross_validate_documents,
    cross_validate_ocr_mrz,
)


def test_compare_field_match():
    r = compare_field("A1234567", "A1234567", "document_number")
    assert r["verdict"] == "PASS"


def test_compare_field_mismatch():
    r = compare_field("A1234567", "B9999999", "document_number")
    assert r["verdict"] == "MISMATCH"


def test_compare_field_confusable_match():
    # O vs 0 and I vs 1 are common OCR confusions
    r = compare_field("A1B2C3D4", "AIBZC3D4", "document_number")
    assert r["verdict"] == "PASS"


def test_compare_field_mrz_missing():
    r = compare_field("A1234567", "", "document_number")
    assert r["verdict"] == "WARN"


def test_cross_validate_ocr_mrz_overall_pass():
    ocr = {"surname": "SMITH", "document_number": "A1234567"}
    mrz = {"surname": "SMITH", "document_number": "A1234567"}
    r = cross_validate_ocr_mrz(ocr, mrz)
    assert r["overall"] == "PASS"
    assert r["mismatches"] == 0


def test_cross_validate_ocr_mrz_overall_mismatch():
    ocr = {"surname": "SMITH", "document_number": "A1234567"}
    mrz = {"surname": "JONES", "document_number": "A1234567"}
    r = cross_validate_ocr_mrz(ocr, mrz)
    assert r["overall"] == "MISMATCH"
    assert r["mismatches"] == 1


def test_cross_validate_documents_consistent():
    doc_a = {"surname": "SMITH", "given_names": "JOHN", "date_of_birth": "900101",
             "document_number": "A1111"}
    doc_b = {"surname": "SMITH", "given_names": "JOHN", "date_of_birth": "900101",
             "document_number": "B2222"}
    r = cross_validate_documents(doc_a, doc_b)
    assert r["consistent"] is True


def test_cross_validate_documents_inconsistent():
    doc_a = {"surname": "SMITH", "given_names": "JOHN", "date_of_birth": "900101",
             "document_number": "A1111"}
    doc_b = {"surname": "JONES", "given_names": "JOHN", "date_of_birth": "900101",
             "document_number": "B2222"}
    r = cross_validate_documents(doc_a, doc_b)
    assert r["consistent"] is False
    assert r["overall"] == "INCONSISTENT"
