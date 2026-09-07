"""Rule-based document validation engine — rule abstraction and rule library.

Every ``ValidationRule`` evaluates a portion of the extracted data plus its
context (MRZ, document type, current date, registry, other documents) and
produces a single :class:`ValidationFinding` carrying:

    rule_id, severity, passed, message, evidence, risk_contribution

Findings describe whether a check passed and how severe a failure is, but they
never hardcode numeric risk scores. ``risk_contribution`` is a semantic factor
identifier (e.g. ``"expired_document"``) that the Risk Engine will later map to
a weight — keeping scoring policy out of the validation layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from app.validation.fields import (
    validate_country_code,
    validate_date_yyyymmdd,
    validate_document_number,
    validate_names,
    validate_sex_code,
)
from app.validation.mrz_compare import fuzzy_equal

# Severity levels, low-to-high. INFO / LOW / MEDIUM / HIGH / CRITICAL.
INFO = "INFO"
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
CRITICAL = "CRITICAL"

SEVERITY_RANK = {INFO: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4}


# ---------------------------------------------------------------------------
# Abstractions
# ---------------------------------------------------------------------------
@dataclass
class ValidationFinding:
    """A single rule evaluation result."""

    rule_id: str
    severity: str
    passed: bool
    message: str
    evidence: dict = field(default_factory=dict)
    risk_contribution: str = "none"


@dataclass
class ValidationContext:
    """The inputs a rule evaluates a document against."""

    extracted_data: dict = field(default_factory=dict)
    mrz: dict = field(default_factory=dict)
    document_type: Optional[str] = None
    document_country: Optional[str] = None
    current_date: date = field(default_factory=date.today)
    registry: Optional[list[dict]] = None
    other_documents: Optional[list[dict]] = None


class ValidationRule:
    """Base class for a validation rule.

    Subclasses set ``rule_id``, ``name`` and ``severity`` (the severity applied
    when the rule fails) and implement :meth:`run` returning a
    :class:`ValidationFinding`.
    """

    rule_id: str = ""
    name: str = ""
    severity: str = MEDIUM

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------
def field_value(extracted_data: dict, key: str) -> str:
    """Read a value from ``extracted_data`` handling nested or flat shapes."""
    if not extracted_data:
        return ""
    val = extracted_data.get(key)
    if isinstance(val, dict):
        return str(val.get("value") or "")
    return str(val) if val is not None else ""


def mrz_field(mrz: dict, key: str) -> str:
    """Read a field from the MRZ ``parsed_fields`` dict."""
    if not mrz:
        return ""
    parsed = mrz.get("parsed_fields") or {}
    val = parsed.get(key)
    return str(val) if val is not None else ""


def _norm(value) -> str:
    if not value:
        return ""
    return str(value).upper().replace("<", "").replace(" ", "").replace("-", "").strip()


def norm_date(value) -> str:
    """Normalize a date to YYMMDD for comparison where possible."""
    raw = _norm(value)
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 8:
        # YYYYMMDD or DDMMYYYY
        try:
            if 1900 <= int(digits[0:4]) <= 2099:
                return digits[2:4] + digits[4:6] + digits[6:8]
            if 1900 <= int(digits[4:8]) <= 2099:
                return digits[6:8] + digits[2:4] + digits[0:2]
        except ValueError:
            pass
        return digits
    if len(digits) == 6:
        return digits
    return raw


def _parse_yymmdd(value: str) -> Optional[date]:
    """Parse a YYMMDD (or more explicit) date string into a date."""
    raw = _norm(value)
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 8:
        try:
            for first in (digits[0:4], digits[4:8]):
                if 1900 <= int(first) <= 2099:
                    return datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
            return None
    if len(digits) == 6:
        res = validate_date_yyyymmdd(digits)
        parsed_str = res.get("parsed")
        if not parsed_str:
            return None
        try:
            return datetime.strptime(parsed_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    try:
        parsed = datetime.strptime(_norm(value), "%Y-%m-%d").date()
        return parsed
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 1. Required fields
# ---------------------------------------------------------------------------
class RequiredFieldsRule(ValidationRule):
    """Ensure mandatory identity fields are present for the document type."""

    rule_id = "required_fields"
    name = "Required identity fields present"
    severity = HIGH
    REQUIRED = {
        "passport": ["passport_number", "full_name", "date_of_birth", "nationality"],
        "national_id": ["document_number", "full_name", "date_of_birth"],
        "drivers_license": ["document_number", "full_name", "date_of_birth"],
        "residence_permit": ["document_number", "full_name", "date_of_birth", "nationality"],
        "immigration": ["document_number", "full_name", "date_of_birth", "nationality"],
    }

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        doc_type = (ctx.document_type or "").lower()
        if doc_type not in self.REQUIRED:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=INFO,
                passed=True,
                message=f"No required-field profile defined for document type '{doc_type}'.",
                evidence={"document_type": ctx.document_type},
            )
        required = self.REQUIRED.get(doc_type, ["full_name"])
        missing = [k for k in required if not field_value(ctx.extracted_data, k)]
        if missing:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message=f"Missing required identity field(s): {', '.join(missing)}.",
                evidence={"missing": missing, "document_type": ctx.document_type},
                risk_contribution="missing_identity_fields",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="All required identity fields are present.",
            evidence={"fields": required},
        )


# ---------------------------------------------------------------------------
# 2. Field format
# ---------------------------------------------------------------------------
class FieldFormatRule(ValidationRule):
    """Validate format of document number, sex, nationality and names."""

    rule_id = "field_format"
    name = "Field format validation"
    severity = MEDIUM

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        doc_number = field_value(ctx.extracted_data, "passport_number") or field_value(
            ctx.extracted_data, "document_number"
        )
        sex = field_value(ctx.extracted_data, "sex")
        nationality = field_value(ctx.extracted_data, "nationality")
        surname = field_value(ctx.extracted_data, "full_name")

        problems: list[str] = []
        if doc_number:
            res = validate_document_number(doc_number)
            if res["verdict"] in ("FAIL",):
                problems.append(f"document_number={res.get('reason')}")
        if sex:
            res = validate_sex_code(sex)
            if res["verdict"] == "FAIL":
                problems.append(f"sex={res.get('reason')}")
        if nationality:
            res = validate_country_code(nationality)
            if res["verdict"] == "FAIL":
                problems.append(f"nationality={res.get('reason')}")
        if surname:
            res = validate_names(surname, "")
            if res["verdict"] == "FAIL":
                problems.append(f"name={res.get('reason')}")

        if problems:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message="One or more fields failed format validation.",
                evidence={"problems": problems},
                risk_contribution="invalid_field_format",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Field formats are valid.",
        )


# ---------------------------------------------------------------------------
# 3. Date validation
# ---------------------------------------------------------------------------
class DateFormatRule(ValidationRule):
    """Validate that DOB / expiry are well-formed YYMMDD dates."""

    rule_id = "date_format"
    name = "Date format validation"
    severity = MEDIUM

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        problems: list[str] = []
        dob = field_value(ctx.extracted_data, "date_of_birth")
        expiry = field_value(ctx.extracted_data, "date_of_expiry")
        for label, val in (("date_of_birth", dob), ("date_of_expiry", expiry)):
            if not val:
                continue
            res = validate_date_yyyymmdd(val)
            if res["verdict"] == "FAIL":
                problems.append(f"{label} -> {res.get('reason')}")
        if problems:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message="One or more dates are malformed or impossible.",
                evidence={"problems": problems},
                risk_contribution="invalid_date",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Dates are well-formed.",
        )


# ---------------------------------------------------------------------------
# 4. DOB cannot be in the future
# ---------------------------------------------------------------------------
class DOBNotFutureRule(ValidationRule):
    """A date of birth in the future is impossible for a living holder."""

    rule_id = "dob_not_future"
    name = "Date of birth not in the future"
    severity = HIGH

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        dob = field_value(ctx.extracted_data, "date_of_birth")
        if not dob:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=LOW,
                passed=True,
                message="Date of birth not provided; nothing to check.",
                evidence={"date_of_birth": ""},
            )
        d = _parse_yymmdd(dob)
        if d is None:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=LOW,
                passed=True,
                message="Date of birth could not be parsed; skipped.",
                evidence={"date_of_birth": dob},
            )
        if d > ctx.current_date:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message="Date of birth is in the future — impossible.",
                evidence={"date_of_birth": dob, "parsed": d.isoformat()},
                risk_contribution="future_dob",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Date of birth is not in the future.",
            evidence={"parsed": d.isoformat()},
        )


# ---------------------------------------------------------------------------
# 5. Expiry after issue date
# ---------------------------------------------------------------------------
class ExpiryAfterIssueRule(ValidationRule):
    """Where both exist, expiry should come after the issue date."""

    rule_id = "expiry_after_issue"
    name = "Expiry date after issue date"
    severity = MEDIUM

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        expiry = field_value(ctx.extracted_data, "date_of_expiry")
        issue = field_value(ctx.extracted_data, "date_of_issue")
        if not expiry or not issue:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=INFO,
                passed=True,
                message="Issue date not available; this check is not applicable.",
                evidence={"has_issue_date": bool(issue), "has_expiry": bool(expiry)},
            )
        exp = _parse_yymmdd(expiry)
        iss = _parse_yymmdd(issue)
        if exp is None or iss is None:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=LOW,
                passed=True,
                message="Issue/expiry dates could not be parsed; skipped.",
                evidence={"issue_date": issue, "expiry_date": expiry},
            )
        if exp <= iss:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message="Expiry date is not after the issue date.",
                evidence={"issue_date": iss.isoformat(), "expiry_date": exp.isoformat()},
                risk_contribution="expiry_before_issue",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Expiry date is after the issue date.",
            evidence={"issue_date": iss.isoformat(), "expiry_date": exp.isoformat()},
        )


# ---------------------------------------------------------------------------
# 6. Expired document detection
# ---------------------------------------------------------------------------
class ExpiredDocumentRule(ValidationRule):
    """Detect documents whose expiry date has passed the current date."""

    rule_id = "document_expired"
    name = "Document not expired"
    severity = HIGH

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        expiry = field_value(ctx.extracted_data, "date_of_expiry") or mrz_field(
            ctx.mrz, "expiry_date"
        )
        if not expiry:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=INFO,
                passed=True,
                message="No expiry date available; expiry could not be assessed.",
                evidence={"expiry_date": ""},
            )
        d = _parse_yymmdd(expiry)
        if d is None:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=LOW,
                passed=True,
                message="Expiry date could not be parsed; skipped.",
                evidence={"expiry_date": expiry},
            )
        if d < ctx.current_date:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message=f"Document is expired as of {d.isoformat()}.",
                evidence={"expiry_date": d.isoformat()},
                risk_contribution="expired_document",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Document is not expired.",
            evidence={"expiry_date": d.isoformat()},
        )


# ---------------------------------------------------------------------------
# 7. MRZ check-digit validation
# ---------------------------------------------------------------------------
class MRZCheckDigitsRule(ValidationRule):
    """Validate MRZ ICAO check digits when an MRZ was detected."""

    rule_id = "mrz_check_digits"
    name = "MRZ check-digit validation"
    severity = HIGH

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        if not ctx.mrz or not ctx.mrz.get("mrz_detected"):
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=LOW,
                passed=True,
                message="No MRZ detected; check-digit validation not applicable.",
                evidence={"mrz_detected": False},
            )
        check_digits = ctx.mrz.get("check_digits") or {}
        failed = [k for k, v in check_digits.items() if v is False]
        if failed:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message=f"MRZ check digit(s) failed: {', '.join(failed)}.",
                evidence={"failed": failed, "check_digits": check_digits},
                risk_contribution="mrz_check_failed",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="MRZ check digits are valid.",
            evidence={"check_digits": check_digits},
        )


# ---------------------------------------------------------------------------
# OCR vs MRZ consistency (aggregate + per-field)
# ---------------------------------------------------------------------------
_VISUAL_TO_MRZ = {
    "passport_number": "passport_number",
    "full_name": "name",
    "date_of_birth": "date_of_birth",
    "nationality": "nationality",
    "date_of_expiry": "expiry_date",
}


def _consistency_check(extracted_data: dict, mrz: dict, visual_key: str) -> tuple[bool, str, dict]:
    """Compare one visual field against its MRZ counterpart.

    Returns (consistent, verdict, evidence).
    """
    visual = field_value(extracted_data, visual_key)
    mrz_key = _VISUAL_TO_MRZ[visual_key]
    if mrz_key == "name":
        given = mrz_field(mrz, "given_names")
        surname = mrz_field(mrz, "surname")
        mrz_val = f"{given} {surname}".strip()
    else:
        mrz_val = mrz_field(mrz, mrz_key)
    if not visual and not mrz_val:
        return True, "UNAVAILABLE", {"visual": "", "mrz": ""}
    if not visual or not mrz_val:
        return True, "UNAVAILABLE", {"visual": visual, "mrz": mrz_val}
    a = visual
    b = mrz_val
    if mrz_key in ("date_of_birth", "expiry_date"):
        a, b = norm_date(visual), norm_date(mrz_val)
    elif mrz_key != "name":
        # Names are compared on raw, space-preserved values so word reordering
        # can be fuzzy-matched; everything else is normalized (strips '<' etc.).
        a, b = _norm(visual), _norm(mrz_val)
    match_field = "name" if mrz_key == "name" else mrz_key
    consistent = fuzzy_equal(a, b, match_field)
    return consistent, ("MATCH" if consistent else "MISMATCH"), {
        "visual": visual,
        "mrz": mrz_val,
    }


class OCRMRZConsistencyRule(ValidationRule):
    """Aggregate OCR-vs-MRZ consistency across all comparable identity fields."""

    rule_id = "ocr_mrz_consistency"
    name = "OCR vs MRZ consistency"
    severity = MEDIUM

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        if not ctx.mrz or not ctx.mrz.get("mrz_detected"):
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=INFO,
                passed=True,
                message="No MRZ available; OCR-vs-MRZ consistency not applicable.",
                evidence={"mrz_detected": False},
            )
        mismatches: list[dict] = []
        details = {}
        for visual_key in _VISUAL_TO_MRZ:
            consistent, verdict, ev = _consistency_check(
                ctx.extracted_data, ctx.mrz, visual_key
            )
            details[visual_key] = verdict
            if verdict == "MISMATCH":
                mismatches.append({"field": visual_key, **ev})
        if mismatches:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message=(
                    f"{len(mismatches)} field(s) differ between visual OCR and "
                    f"MRZ: {', '.join(m['field'] for m in mismatches)}."
                ),
                evidence={"mismatches": mismatches, "per_field": details},
                risk_contribution="ocr_mrz_mismatch",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Visual OCR fields are consistent with the MRZ.",
            evidence={"per_field": details},
        )


def _make_consistency_rule(
    rule_id: str, name: str, visual_key: str, severity: str = MEDIUM
) -> type[ValidationRule]:
    field_name = visual_key
    rid = rule_id
    rule_name = name
    rule_severity = severity

    class _Rule(ValidationRule):
        rule_id = rid
        name = rule_name
        severity = rule_severity

        def run(self, ctx: "ValidationContext") -> ValidationFinding:
            if not ctx.mrz or not ctx.mrz.get("mrz_detected"):
                return ValidationFinding(
                    rule_id=self.rule_id,
                    severity=INFO,
                    passed=True,
                    message=f"MRZ not available; {rule_name.lower()} not applicable.",
                    evidence={"mrz_detected": False},
                )
            consistent, verdict, ev = _consistency_check(
                ctx.extracted_data, ctx.mrz, field_name
            )
            if verdict == "UNAVAILABLE":
                return ValidationFinding(
                    rule_id=self.rule_id,
                    severity=LOW,
                    passed=True,
                    message=f"{rule_name} could not be compared (value missing on one side).",
                    evidence=ev,
                )
            if consistent:
                return ValidationFinding(
                    rule_id=self.rule_id,
                    severity=INFO,
                    passed=True,
                    message=f"{rule_name} is consistent between visual OCR and MRZ.",
                    evidence=ev,
                )
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message=f"{rule_name} differs between visual OCR and MRZ.",
                evidence=ev,
                risk_contribution="ocr_mrz_mismatch",
            )

    _Rule.__name__ = f"{'_'.join(p.capitalize() for p in rule_id.split('_'))}Rule"
    return _Rule


PassportNumberConsistencyRule = _make_consistency_rule(
    "passport_number_consistency",
    "Passport number",
    "passport_number",
    severity=HIGH,
)
NameConsistencyRule = _make_consistency_rule(
    "name_consistency", "Name", "full_name", severity=MEDIUM
)
DOBConsistencyRule = _make_consistency_rule(
    "dob_consistency", "Date of birth", "date_of_birth", severity=MEDIUM
)
ExpiryConsistencyRule = _make_consistency_rule(
    "expiry_consistency", "Expiry date", "date_of_expiry", severity=MEDIUM
)


# ---------------------------------------------------------------------------
# 13. Cross-document consistency
# ---------------------------------------------------------------------------
class CrossDocumentConsistencyRule(ValidationRule):
    """Compare identity fields across documents claimed to be the same holder."""

    rule_id = "cross_document_consistency"
    name = "Cross-document consistency"
    severity = HIGH

    def run(self, ctx: "ValidationContext") -> ValidationFinding:
        others = ctx.other_documents or []
        if not others:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=INFO,
                passed=True,
                message="No other documents available for cross-document comparison.",
                evidence={"compared_documents": 0},
            )
        problems: list[dict] = []
        compared = 0
        for other in others:
            other_fields = other.get("fields") or {}
            for field_name in ["full_name", "date_of_birth", "nationality"]:
                mine = field_value(ctx.extracted_data, field_name)
                theirs = field_value(other_fields, field_name)
                if not mine or not theirs:
                    continue
                compared += 1
                a = mine if field_name == "full_name" else norm_date(mine)
                b = theirs if field_name == "full_name" else norm_date(theirs)
                match_field = "name" if field_name == "full_name" else field_name
                if not fuzzy_equal(a, b, match_field):
                    problems.append(
                        {
                            "field": field_name,
                            "current": mine,
                            "other": theirs,
                            "other_document_id": other.get("id"),
                        }
                    )
        if problems:
            return ValidationFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                passed=False,
                message=(
                    f"Identity fields differ across documents: "
                    f"{', '.join(p['field'] for p in problems)}."
                ),
                evidence={"inconsistencies": problems, "compared": compared},
                risk_contribution="cross_document_inconsistent",
            )
        return ValidationFinding(
            rule_id=self.rule_id,
            severity=INFO,
            passed=True,
            message="Identity fields are consistent across all submitted documents.",
            evidence={"compared": compared, "compared_documents": len(others)},
        )


ALL_RULES: list[ValidationRule] = [
    RequiredFieldsRule(),
    FieldFormatRule(),
    DateFormatRule(),
    DOBNotFutureRule(),
    ExpiryAfterIssueRule(),
    ExpiredDocumentRule(),
    MRZCheckDigitsRule(),
    OCRMRZConsistencyRule(),
    PassportNumberConsistencyRule(),
    NameConsistencyRule(),
    DOBConsistencyRule(),
    ExpiryConsistencyRule(),
    CrossDocumentConsistencyRule(),
]


def build_default_rules() -> list[ValidationRule]:
    return list(ALL_RULES)
