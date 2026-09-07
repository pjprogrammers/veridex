"""Tests for the rule-based document validation engine.

Exercises every rule in the validation library using synthetic passport data
that is intentionally valid or deliberately corrupted to force each rule's
fail path.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.validation.engine import validate  # noqa: E402
from app.validation.rules import (  # noqa: E402
    CRITICAL,
    HIGH,
    INFO,
    LOW,
    MEDIUM,
)


def _fields(**overrides):
    base = {
        "passport_number": "L898902C",
        "full_name": "ERIKSSON ANNA MARIA",
        "date_of_birth": "690806",
        "date_of_issue": "300101",
        "date_of_expiry": "340101",
        "nationality": "UTO",
        "sex": "F",
    }
    base.update(overrides)
    return base


def _mrz(**overrides):
    base = {
        "mrz_detected": True,
        "mrz_valid": True,
        "check_digits": {
            "passport_number": True,
            "date_of_birth": True,
            "expiry_date": True,
            "final": True,
        },
        "parsed_fields": {
            "passport_number": "L898902C",
            "surname": "ERIKSSON",
            "given_names": "ANNA MARIA",
            "date_of_birth": "690806",
            "sex": "F",
            "expiry_date": "340101",
            "nationality": "UTO",
            "issuing_state": "UTO",
        },
    }
    base.update(overrides)
    return base


def _run(fields=None, mrz=None, **kwargs):
    result = validate(
        extracted_data=fields or _fields(),
        mrz=mrz if mrz is not None else _mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
        **kwargs,
    )
    by_id = {f.rule_id: f for f in result.findings}
    return result, by_id


def _finding(by_id, rule_id):
    assert rule_id in by_id, f"rule {rule_id} missing; got {list(by_id)}"
    return by_id[rule_id]


# ---------------------------------------------------------------------------
# 1. Required fields
# ---------------------------------------------------------------------------
def test_required_fields_pass():
    _, by_id = _run()
    f = _finding(by_id, "required_fields")
    assert f.passed is True


def test_required_fields_fail_missing():
    _, by_id = _run(fields=_fields(passport_number=""))
    f = _finding(by_id, "required_fields")
    assert f.passed is False
    assert f.severity == HIGH
    assert "passport_number" in f.evidence["missing"]


def test_required_fields_fail_missing_name():
    _, by_id = _run(fields=_fields(full_name=""))
    f = _finding(by_id, "required_fields")
    assert f.passed is False
    assert "full_name" in f.evidence["missing"]


def test_required_fields_unknown_type_is_info():
    result = validate(
        extracted_data=_fields(),
        mrz=_mrz(),
        document_type="mystery_doc",
        current_date=date(2024, 1, 1),
    )
    f = _finding({r.rule_id: r for r in result.findings}, "required_fields")
    assert f.passed is True
    assert f.severity == INFO


# ---------------------------------------------------------------------------
# 2. Field format
# ---------------------------------------------------------------------------
def test_field_format_pass():
    _, by_id = _run()
    f = _finding(by_id, "field_format")
    assert f.passed is True


def test_field_format_fail_document_number():
    _, by_id = _run(fields=_fields(passport_number="not a number!"))
    f = _finding(by_id, "field_format")
    assert f.passed is False


def test_field_format_fail_country_code():
    _, by_id = _run(fields=_fields(nationality="12"))
    f = _finding(by_id, "field_format")
    assert f.passed is False


# ---------------------------------------------------------------------------
# 3. Date validation
# ---------------------------------------------------------------------------
def test_date_format_pass():
    _, by_id = _run()
    f = _finding(by_id, "date_format")
    assert f.passed is True


def test_date_format_fail_impossible():
    _, by_id = _run(fields=_fields(date_of_birth="991331"))
    f = _finding(by_id, "date_format")
    assert f.passed is False


# ---------------------------------------------------------------------------
# 4. DOB cannot be in the future
# ---------------------------------------------------------------------------
def test_dob_not_future_pass():
    _, by_id = _run()
    f = _finding(by_id, "dob_not_future")
    assert f.passed is True


def test_dob_future_fail():
    # Current date 2024; DOB 20300101 is in the future -> impossible.
    _, by_id = _run(fields=_fields(date_of_birth="300101"))
    f = _finding(by_id, "dob_not_future")
    assert f.passed is False
    assert f.risk_contribution == "future_dob"


# ---------------------------------------------------------------------------
# 5. Expiry after issue date
# ---------------------------------------------------------------------------
def test_expiry_after_issue_pass():
    _, by_id = _run()
    f = _finding(by_id, "expiry_after_issue")
    assert f.passed is True


def test_expiry_after_issue_fail():
    _, by_id = _run(fields=_fields(date_of_issue="340101", date_of_expiry="300101"))
    f = _finding(by_id, "expiry_after_issue")
    assert f.passed is False
    assert f.risk_contribution == "expiry_before_issue"


def test_expiry_after_issue_not_applicable():
    _, by_id = _run(fields=_fields(date_of_issue=""))
    f = _finding(by_id, "expiry_after_issue")
    assert f.passed is True
    assert f.severity == INFO


# ---------------------------------------------------------------------------
# 6. Expired document detection
# ---------------------------------------------------------------------------
def test_expired_document_pass():
    _, by_id = _run()
    f = _finding(by_id, "document_expired")
    assert f.passed is True
    assert f.severity == INFO


def test_expired_document_fail():
    _, by_id = _run(fields=_fields(date_of_expiry="200101"))
    f = _finding(by_id, "document_expired")
    assert f.passed is False
    assert f.severity == HIGH
    assert f.risk_contribution == "expired_document"


def test_expired_document_from_mrz():
    mrz = _mrz()
    mrz["parsed_fields"]["expiry_date"] = "200101"
    _, by_id = _run(fields=_fields(date_of_expiry=""), mrz=mrz)
    f = _finding(by_id, "document_expired")
    assert f.passed is False


# ---------------------------------------------------------------------------
# 7. MRZ check-digit validation
# ---------------------------------------------------------------------------
def test_mrz_check_digits_pass():
    _, by_id = _run()
    f = _finding(by_id, "mrz_check_digits")
    assert f.passed is True


def test_mrz_check_digits_fail():
    mrz = _mrz()
    mrz["check_digits"]["passport_number"] = False
    _, by_id = _run(mrz=mrz)
    f = _finding(by_id, "mrz_check_digits")
    assert f.passed is False
    assert f.risk_contribution == "mrz_check_failed"


def test_mrz_check_digits_not_applicable():
    mrz = {"mrz_detected": False}
    _, by_id = _run(mrz=mrz)
    f = _finding(by_id, "mrz_check_digits")
    assert f.passed is True


# ---------------------------------------------------------------------------
# 8. OCR vs MRZ consistency (aggregate)
# ---------------------------------------------------------------------------
def test_ocr_mrz_consistency_pass():
    _, by_id = _run()
    f = _finding(by_id, "ocr_mrz_consistency")
    assert f.passed is True


def test_ocr_mrz_consistency_fail():
    _, by_id = _run(fields=_fields(passport_number="L898902X"))
    f = _finding(by_id, "ocr_mrz_consistency")
    assert f.passed is False
    assert f.risk_contribution == "ocr_mrz_mismatch"


# ---------------------------------------------------------------------------
# 9-12. Per-field consistency
# ---------------------------------------------------------------------------
def test_passport_number_consistency():
    _, by_id = _run(fields=_fields(passport_number="L898902X"))
    f = _finding(by_id, "passport_number_consistency")
    assert f.passed is False
    assert f.severity == HIGH

    ok, by_id2 = _run()
    assert _finding(by_id2, "passport_number_consistency").passed is True


def test_name_consistency():
    _, by_id = _run(fields=_fields(full_name="SMITH JOHN"))
    f = _finding(by_id, "name_consistency")
    assert f.passed is False
    assert f.severity == MEDIUM


def test_name_consistency_reordered_tokens_pass():
    # MRZ surname<<given vs visual "GIVEN SURNAME" reordering is tolerated.
    result = validate(
        extracted_data=_fields(full_name="ANNA MARIA ERIKSSON"),
        mrz=_mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
    )
    f = _finding({r.rule_id: r for r in result.findings}, "name_consistency")
    assert f.passed is True


def test_dob_consistency():
    _, by_id = _run(fields=_fields(date_of_birth="690807"))
    f = _finding(by_id, "dob_consistency")
    assert f.passed is False
    assert f.severity == MEDIUM

    ok, by_id2 = _run()
    assert _finding(by_id2, "dob_consistency").passed is True


def test_expiry_consistency():
    _, by_id = _run(fields=_fields(date_of_expiry="340102"))
    f = _finding(by_id, "expiry_consistency")
    assert f.passed is False
    assert f.severity == MEDIUM


def test_per_field_consistency_unavailable_when_no_mrz():
    result = validate(
        extracted_data=_fields(),
        mrz={"mrz_detected": False},
        document_type="passport",
        current_date=date(2024, 1, 1),
    )
    by_id = {r.rule_id: r for r in result.findings}
    for rule_id in (
        "ocr_mrz_consistency",
        "passport_number_consistency",
        "name_consistency",
        "dob_consistency",
        "expiry_consistency",
    ):
        assert by_id[rule_id].passed is True


# ---------------------------------------------------------------------------
# 13. Cross-document consistency
# ---------------------------------------------------------------------------
def test_cross_document_pass():
    others = [
        {"id": "11111111-1111-1111-1111-111111111111", "fields": _fields()},
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "fields": _fields(full_name="ERIKSSON ANNA MARIA", date_of_birth="690806"),
        },
    ]
    _, by_id = _run(other_documents=others)
    f = _finding(by_id, "cross_document_consistency")
    assert f.passed is True
    assert f.evidence["compared"] > 0


def test_cross_document_fail():
    others = [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "fields": _fields(full_name="SMITH JOHN", date_of_birth="800101"),
        }
    ]
    _, by_id = _run(other_documents=others)
    f = _finding(by_id, "cross_document_consistency")
    assert f.passed is False
    assert f.risk_contribution == "cross_document_inconsistent"
    assert f.evidence["inconsistencies"]


def test_cross_document_not_applicable():
    _, by_id = _run()
    f = _finding(by_id, "cross_document_consistency")
    assert f.passed is True
    assert f.severity == INFO


# ---------------------------------------------------------------------------
# Registry + summary + response shape
# ---------------------------------------------------------------------------
def test_registry_flag_surfaces_finding():
    result = validate(
        extracted_data=_fields(),
        mrz=_mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
        registry=[{"document_number": "L898902C", "status": "reported_stolen"}],
    )
    f = {r.rule_id: r for r in result.findings}["registry_status"]
    assert f.passed is False
    assert f.severity == HIGH
    assert f.risk_contribution == "registry_alert"


def test_registry_clean_finding():
    result = validate(
        extracted_data=_fields(),
        mrz=_mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
        registry=[{"document_number": "L898902C", "status": "valid"}],
    )
    f = {r.rule_id: r for r in result.findings}["registry_status"]
    assert f.passed is True


def test_summary_shape():
    result = validate(
        extracted_data=_fields(),
        mrz=_mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
    )
    s = result.summary
    assert set(s) == {"overall", "rules_run", "passed", "failed", "max_severity", "by_severity"}
    assert s["overall"] == "PASS"
    assert s["rules_run"] == 13
    assert s["max_severity"] == "INFO"


def test_summary_failed_aggregate_max_severity():
    result = validate(
        extracted_data=_fields(passport_number=""),  # triggers required_fields HIGH
        mrz=_mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
    )
    s = result.summary
    assert s["overall"] == "FAIL"
    assert s["max_severity"] == HIGH


def test_finding_response_shape():
    result = validate(
        extracted_data=_fields(),
        mrz=_mrz(),
        document_type="passport",
        current_date=date(2024, 1, 1),
    )
    d = result.to_dict()
    assert "findings" in d and "summary" in d
    for f in d["findings"]:
        assert set(f) == {
            "rule_id",
            "severity",
            "passed",
            "message",
            "evidence",
            "risk_contribution",
        }


# ---------------------------------------------------------------------------
# Severity constants are part of the public contract
# ---------------------------------------------------------------------------
def test_severity_constants_exist():
    for sev in (INFO, LOW, MEDIUM, HIGH, CRITICAL):
        assert isinstance(sev, str)
