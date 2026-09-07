"""Tests for visual-vs-MRZ field comparison and severity scoring."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.validation.mrz_compare import (
    _normalize_date,
    compare_visual_mrz,
    fuzzy_equal,
)


def _full_match_visual():
    return {
        "passport_number": "L898902C",
        "full_name": "ERIKSSON ANNA MARIA",
        "date_of_birth": "1969-08-06",
        "nationality": "UTO",
        "date_of_expiry": "1994-06-23",
    }


def _full_match_mrz():
    return {
        "passport_number": "L898902C",
        "name": "ANNA MARIA ERIKSSON",
        "date_of_birth": "690806",
        "nationality": "UTO",
        "expiry_date": "940623",
    }


def test_all_match():
    vis = _full_match_visual()
    mrz = _full_match_mrz()
    res = compare_visual_mrz(vis, mrz)
    assert all(c.verdict == "MATCH" for c in res.comparisons)
    assert res.severity_score == 0.0
    assert res.severities["level"] == "NONE"


def test_date_normalization_yyyymmdd_vs_yymmdd():
    assert _normalize_date("1969-08-06") == "690806"


def test_date_normalization_ddmmyyyy_vs_yymmdd():
    assert _normalize_date("06-08-1969") == "690806"


def test_passport_number_mismatch_scores_high():
    vis = _full_match_visual()
    mrz = _full_match_mrz()
    mrz["passport_number"] = "X0000000"
    res = compare_visual_mrz(vis, mrz)
    assert res.severity_score >= 0.7
    assert res.severities["level"] == "HIGH"


def test_expiry_mismatch_scores_low():
    vis = _full_match_visual()
    mrz = _full_match_mrz()
    mrz["expiry_date"] = "950101"
    res = compare_visual_mrz(vis, mrz)
    assert 0 < res.severity_score < 0.35
    assert res.severities["level"] == "LOW"


def test_unavailable_field_not_penalized():
    vis = _full_match_visual()
    vis["date_of_birth"] = ""
    mrz = _full_match_mrz()
    res = compare_visual_mrz(vis, mrz)
    dob = next(c for c in res.comparisons if c.field_name == "date_of_birth")
    assert dob.verdict == "UNAVAILABLE"
    # Remaining fields match -> NONE severity.
    assert res.severities["level"] == "NONE"


def test_ocr_confusable_still_matches():
    # '0' vs 'O' IS confusable -> should match; differing chars -> no match.
    assert fuzzy_equal("MO123", "M0123", "passport_number") is True
    assert fuzzy_equal("L898902C", "L8989020", "passport_number") is False


def test_mrz_absent_all_unavailable():
    vis = _full_match_visual()
    res = compare_visual_mrz(vis, {})
    assert all(c.verdict == "UNAVAILABLE" for c in res.comparisons)
    assert res.severity_score == 0.0
    assert res.severities["level"] == "NONE"


def test_name_reorder_matches():
    assert fuzzy_equal("ERIKSSON ANNA MARIA", "ANNA MARIA ERIKSSON", "name") is True


def test_mismatch_reasons_listed():
    vis = _full_match_visual()
    mrz = _full_match_mrz()
    mrz["date_of_birth"] = "700101"
    mrz["nationality"] = "GBR"
    res = compare_visual_mrz(vis, mrz)
    assert "date_of_birth" in res.severities["reasons"]
    assert "nationality" in res.severities["reasons"]
