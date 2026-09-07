"""Visual-vs-MRZ field comparison with severity scoring.

Compares identity fields read from the printed (visual) face of a document
against the values encoded in the machine-readable zone (MRZ). Produces a
per-field verdict of MATCH / MISMATCH / UNAVAILABLE and an aggregate
mismatch severity score.

IMPORTANT: A visual-vs-MRZ mismatch is a *signal for review*, not proof of
forgery. OCR errors, degraded captures, and genuine document variability all
produce false mismatches.
"""
from __future__ import annotations

from dataclasses import dataclass

# Fields compared between the visual face and the MRZ.
_COMPARABLE_FIELDS = [
    ("passport_number", "passport_number"),
    ("full_name", "name"),
    ("date_of_birth", "date_of_birth"),
    ("nationality", "nationality"),
    ("date_of_expiry", "expiry_date"),
]

# Relative weighting of each field in the mismatch severity score.
_FIELD_WEIGHTS = {
    "passport_number": 0.35,
    "name": 0.25,
    "date_of_birth": 0.20,
    "nationality": 0.10,
    "expiry_date": 0.10,
}

# The confusable OCR characters used for fuzzy matching.
_CONFUSABLE = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}


def _norm(value) -> str:
    if not value:
        return ""
    return str(value).upper().replace("<", "").replace(" ", "").replace("-", "").strip()


def _normalize_date(value) -> str:
    """Normalize a date for comparison (DD-MM-YYYY -> YYMMDD, etc.)."""
    raw = _norm(value)
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 8 and not raw.isalpha():
        # Assume either YYYYMMDD or DDMMYYYY; convert YYYYMMDD form.
        if 1900 <= int(digits[0:4]) <= 2099:
            return digits[2:4] + digits[4:6] + digits[6:8]
        if 1900 <= int(digits[4:8]) <= 2099:
            return digits[6:8] + digits[2:4] + digits[0:2]
    return digits if len(digits) == 6 else raw


def fuzzy_equal(a: str, b: str, field_name: str) -> bool:
    """Fuzzy comparison tolerant of OCR confusion characters."""
    if field_name == "name":
        return _name_similarity(a, b)
    if a == b:
        return True
    if len(a) != len(b):
        return False
    matches = sum(1 for ca, cb in zip(a, b) if _CONFUSABLE.get(ca, ca) == _CONFUSABLE.get(cb, cb))
    return matches / len(a) >= 0.9


def _name_similarity(a: str, b: str) -> bool:
    """Names may be reordered/abbreviated; check token overlap.

    Tokens are delimited by spaces or the MRZ fill character '<'. The input
    strings should be normalized (upper-cased) but may still contain '<'
    separators. Any stray spaces are treated like '<'.
    """
    set_a = {t for t in a.replace(" ", "<").split("<") if t}
    set_b = {t for t in b.replace(" ", "<").split("<") if t}
    if not set_a or not set_b:
        return False
    return len(set_a & set_b) / max(len(set_a), len(set_b)) >= 0.5


@dataclass
class FieldComparison:
    """A single field comparison result."""

    field_name: str
    visual_value: str
    mrz_value: str
    verdict: str  # MATCH | MISMATCH | UNAVAILABLE
    weight: float


def _compare_field(field_key: str, visual: str, mrz: str, field_name: str) -> FieldComparison:
    weight = _FIELD_WEIGHTS.get(field_name, 0.0)

    if not visual and not mrz:
        return FieldComparison(field_key, visual, mrz, "UNAVAILABLE", weight)

    if not visual or not mrz:
        return FieldComparison(field_key, visual, mrz, "UNAVAILABLE", weight)

    # Name fields: compare on the raw, space-preserved values so that word
    # reordering (MRZ surname<<given) can be fuzzy-matched.
    if field_name == "name":
        matched = _name_similarity(str(visual).upper(), str(mrz).upper())
    else:
        a = _normalize_date(visual) if field_name in ("date_of_birth", "expiry_date") else _norm(visual)
        b = _normalize_date(mrz) if field_name in ("date_of_birth", "expiry_date") else _norm(mrz)
        matched = fuzzy_equal(a, b, field_name)

    if matched:
        return FieldComparison(field_key, visual, mrz, "MATCH", weight)
    return FieldComparison(field_key, visual, mrz, "MISMATCH", weight)


@dataclass
class MRZComparisonResult:
    """Overall visual-vs-MRZ comparison result."""

    comparisons: list[FieldComparison]
    severity_score: float  # 0.0 (no mismatch) to 1.0 (critical mismatch)
    severities: dict

    def to_dict(self) -> dict:
        return {
            "comparisons": [
                {
                    "field_name": c.field_name,
                    "visual_value": c.visual_value,
                    "mrz_value": c.mrz_value,
                    "verdict": c.verdict,
                }
                for c in self.comparisons
            ],
            "severity_score": round(self.severity_score, 4),
            "severity": self.severities.get("level", "NONE"),
            "severity_reasons": self.severities.get("reasons", []),
        }


# Field-key -> human label mapping for the API surface, keyed by MRZ field.
def compare_visual_mrz(visual_fields: dict, mrz_fields: dict) -> MRZComparisonResult:
    """Compare visual (printed) fields against MRZ-encoded fields.

    ``visual_fields`` uses the printed-field names (passport_number,
    full_name, date_of_birth, nationality, date_of_expiry) as produced by
    the rule-based OCR extractor. ``mrz_fields`` uses MRZ field names
    (passport_number, name, date_of_birth, nationality, expiry_date).
    """
    comparisons: list[FieldComparison] = []

    for field_key, mrz_field in _COMPARABLE_FIELDS:
        visual = visual_fields.get(field_key, "")
        mrz = mrz_fields.get(mrz_field, "")
        comparisons.append(_compare_field(field_key, visual, mrz, mrz_field))

    return _aggregate(comparisons)


def _aggregate(comparisons: list[FieldComparison]) -> MRZComparisonResult:
    """Compute the mismatch severity level.

    The passport number is the strongest forgery signal, so a passport-number
    mismatch alone is treated as HIGH severity. Otherwise severity scales with
    the number/proportion of remaining mismatches.
    """
    mismatches = [c for c in comparisons if c.verdict == "MISMATCH"]
    reasons = [c.field_name for c in mismatches]

    if any(c.field_name == "passport_number" for c in mismatches):
        level = "HIGH"
    elif len(mismatches) >= 2:
        level = "MEDIUM"
    elif len(mismatches) == 1:
        level = "LOW"
    else:
        level = "NONE"

    # Numeric severity score in [0, 1] for display/ranking.
    total_weight = sum(c.weight for c in comparisons if c.verdict != "UNAVAILABLE")
    if total_weight <= 0:
        score = 0.0
    else:
        score = sum(c.weight for c in mismatches) / total_weight
        # Ensure a passport mismatch always registers a meaningful score.
        if any(c.field_name == "passport_number" for c in mismatches):
            score = max(score, 0.8)

    return MRZComparisonResult(
        comparisons=comparisons,
        severity_score=round(score, 4),
        severities={"level": level, "reasons": reasons},
    )
