"""Field-level validation for extracted document data.

Validates format correctness and internal consistency of extracted fields
(such as dates, document numbers, sex codes, and country codes) using
deterministic rules. Outputs are discrete PASS/WARN/FAIL verdicts with
explanations.
"""
import re
from datetime import date, datetime
from typing import Optional

SEX_CODES = {"M", "F", "X"}
COUNTRY_CODES_RE = re.compile(r"^[A-Z]{3}$")


def validate_date_yyyymmdd(value: str) -> dict:
    """Validate an ICAO YYMMDD date string (with century handling).

    Returns PASS/WARN/FAIL. A date in the future is flagged but not fatal
    (birthdates in the future are impossible; expiry so-so).
    """
    if not value or not re.fullmatch(r"\d{6}", value):
        return {"verdict": "FAIL", "reason": "invalid_date_format", "detail": value}
    try:
        yy = int(value[0:2])
        mm = int(value[2:4])
        dd = int(value[4:6])
    except ValueError:
        return {"verdict": "FAIL", "reason": "invalid_date_digits", "detail": value}

    # ICAO: dates in range c. 1940-2039. Choose century.
    full_year = 1900 + yy if yy >= 40 else 2000 + yy
    try:
        parsed = datetime(full_year, mm, dd).date()
    except ValueError:
        return {"verdict": "FAIL", "reason": "impossible_date", "detail": value}

    today = date.today()
    if parsed > today:
        return {
            "verdict": "WARN",
            "reason": "date_in_future",
            "detail": value,
            "parsed": parsed.isoformat(),
        }
    return {
        "verdict": "PASS",
        "reason": None,
        "detail": value,
        "parsed": parsed.isoformat(),
    }


def validate_document_number(value: str) -> dict:
    """Validate a document number: 6-9 alphanumeric (uppercase), may contain '<'."""
    if not value:
        return {"verdict": "FAIL", "reason": "missing_document_number"}
    cleaned = value.replace("<", "")
    if not cleaned:
        return {"verdict": "FAIL", "reason": "empty_document_number"}
    if not re.fullmatch(r"[A-Z0-9]{6,9}", cleaned):
        return {
            "verdict": "FAIL",
            "reason": "invalid_document_number_format",
            "detail": value,
        }
    return {"verdict": "PASS", "reason": None, "detail": value}


def validate_sex_code(value: str) -> dict:
    if not value:
        return {"verdict": "WARN", "reason": "missing_sex_code"}
    if value.upper() not in SEX_CODES:
        return {"verdict": "FAIL", "reason": "invalid_sex_code", "detail": value}
    return {"verdict": "PASS", "reason": None, "detail": value}


def validate_country_code(value: str) -> dict:
    if not value:
        return {"verdict": "WARN", "reason": "missing_country_code"}
    if not COUNTRY_CODES_RE.fullmatch(value):
        return {"verdict": "FAIL", "reason": "invalid_country_code", "detail": value}
    return {"verdict": "PASS", "reason": None, "detail": value}


def validate_names(surname: str, given_names: str) -> dict:
    if not surname:
        return {"verdict": "FAIL", "reason": "missing_surname"}
    # Names should be alphabetic plus spaces/hyphens/apostrophes
    pattern = re.compile(r"^[A-Za-z' \-]+$")
    if not pattern.fullmatch(surname.strip()):
        return {"verdict": "FAIL", "reason": "invalid_surname_chars", "detail": surname}
    return {"verdict": "PASS", "reason": None}


def validate_expiry(expiry_yyyymmdd: str, today: Optional[date] = None) -> dict:
    """Validate an expiry date against the current date."""
    today = today or date.today()
    result = validate_date_yyyymmdd(expiry_yyyymmdd)
    if result["verdict"] == "FAIL":
        return result
    parsed = datetime.strptime(result["parsed"], "%Y-%m-%d").date()
    if parsed < today:
        return {
            "verdict": "FAIL",
            "reason": "document_expired",
            "detail": parsed.isoformat(),
        }
    return {"verdict": "PASS", "reason": None, "detail": parsed.isoformat()}


VALIDATORS = {
    "date_of_birth": lambda v: validate_date_yyyymmdd(v),
    "expiry_date": lambda v: validate_expiry(v),
    "document_number": validate_document_number,
    "sex": validate_sex_code,
    "nationality": validate_country_code,
    "issuing_country": validate_country_code,
}


def validate_fields(fields: dict) -> dict:
    """Run all applicable validators on an extracted-fields dict."""
    results = {}
    for name, validator in VALIDATORS.items():
        value = fields.get(name)
        if value is None or value == "":
            results[name] = {"verdict": "WARN", "reason": "missing_field"}
        else:
            results[name] = validator(value)
    return results
