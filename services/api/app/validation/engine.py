"""Rule-based document validation engine.

Orchestrates the validation rules over a document's extracted data plus its
context (MRZ, document type, current date, registry, other documents) and
produces a list of :class:`ValidationFinding` findings together with a summary.

The engine produces *findings*; it does not compute a risk score. Numeric
scoring is out of scope here and is delegated to the Risk Engine, which maps
the ``risk_contribution`` signal each finding carries onto weights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.validation.rules import (
    HIGH,
    INFO,
    SEVERITY_RANK,
    ValidationContext,
    ValidationFinding,
    ValidationRule,
    build_default_rules,
)


@dataclass
class ValidationResult:
    """Aggregate result of running the validation rules."""

    findings: list[ValidationFinding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "passed": f.passed,
                    "message": f.message,
                    "evidence": f.evidence,
                    "risk_contribution": f.risk_contribution,
                }
                for f in self.findings
            ],
            "summary": self.summary,
        }


def summarise(findings: list[ValidationFinding]) -> dict:
    """Derive a compact summary from a set of findings.

    The aggregate severity is the highest severity among *failing* findings, or
    INFO when everything passes. This is a summary of findings, not a risk
    score.
    """
    failed = [f for f in findings if not f.passed]
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    overall = "PASS"
    max_sev_rank = -1
    top_severity = None
    for f in failed:
        rank = SEVERITY_RANK.get(f.severity, 0)
        if rank > max_sev_rank:
            max_sev_rank = rank
            top_severity = f.severity
    if failed:
        overall = "FAIL"

    return {
        "overall": overall,
        "rules_run": len(findings),
        "passed": sum(1 for f in findings if f.passed),
        "failed": len(failed),
        "max_severity": top_severity or "INFO",
        "by_severity": by_severity,
    }


def validate(
    extracted_data: Optional[dict] = None,
    mrz: Optional[dict] = None,
    document_type: Optional[str] = None,
    document_country: Optional[str] = None,
    current_date: Optional[date] = None,
    registry: Optional[list[dict]] = None,
    other_documents: Optional[list[dict]] = None,
    rules: Optional[list[ValidationRule]] = None,
) -> ValidationResult:
    """Run the validation rules and return findings plus a summary.

    ``extracted_data`` is the rule-extracted (visual) field dict, e.g. from
    ``doc.ocr_extracted_fields``. ``mrz`` is the MRZ payload dict with keys
    ``mrz_detected``, ``mrz_valid``, ``check_digits`` and ``parsed_fields``.
    """
    ctx = ValidationContext(
        extracted_data=extracted_data or {},
        mrz=mrz or {},
        document_type=document_type,
        document_country=document_country,
        current_date=current_date or date.today(),
        registry=registry,
        other_documents=other_documents,
    )
    active_rules = rules or build_default_rules()
    findings = [rule.run(ctx) for rule in active_rules]

    if registry:
        findings.append(_registry_finding(registry))

    return ValidationResult(findings=findings, summary=summarise(findings))


def _registry_finding(registry: list[dict]) -> ValidationFinding:
    """Surface registry lookups as an informational finding for the officer.

    Any flagged status is a signal for review/verification, not a determination
    of fraud. Statuses are surfaced verbatim from the (synthetic) registry.
    """
    flagged = [r for r in registry if (r.get("status") or "valid") != "valid"]
    if flagged:
        statuses = ", ".join(f"{r.get('document_number')}={r.get('status')}" for r in flagged)
        return ValidationFinding(
            rule_id="registry_status",
            severity=HIGH,
            passed=False,
            message=(
                "Registry lookup flagged one or more entries (e.g. stolen or "
                "expired). Verify against an authorized secondary source."
            ),
            evidence={"statuses": statuses, "entries": registry},
            risk_contribution="registry_alert",
        )
    return ValidationFinding(
        rule_id="registry_status",
        severity=INFO,
        passed=True,
        message="Registry lookup returned no flags for this document number.",
        evidence={"entries": registry},
    )
