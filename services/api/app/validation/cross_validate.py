"""Cross-validation of extracted data across sources and documents.

- OCR vs MRZ consistency: compare the same identity fields read visually
  (OCR) against the MRZ-parsed values.
- Cross-document consistency: compare fields across two documents claimed
  to belong to the same identity.
"""

SPECULATIVE_LETTERS = {"O", "I", "0", "1", "5", "S", "B", "8", "Z", "2", "G", "6"}


def _normalize_text(value: str) -> str:
    """Upper-case and strip fillers for comparison."""
    if not value:
        return ""
    return value.upper().replace("<", "").replace(" ", "").strip()


def _fuzzy_equal(a: str, b: str) -> bool:
    """Equality tolerant of common OCR confusion characters.

    Compares normalized values allowing substitutions among a set of
    easily-confused characters (e.g., O vs 0, I vs 1). Measures as a ratio of
    matching positions after folding the confusable set.
    """
    na, nb = _normalize_text(a), _normalize_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Compare char-by-char allowing confusable folding
    if len(na) != len(nb):
        return False

    def fold(ch: str) -> str:
        mapping = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
        return mapping.get(ch, ch)

    matches = sum(1 for ca, cb in zip(na, nb) if fold(ca) == fold(cb))
    return matches / len(na) >= 0.9


def compare_field(ocr_value: str, mrz_value: str, field_name: str) -> dict:
    """Compare an OCR-read field against its MRZ counterpart."""
    if not mrz_value:
        return {"verdict": "WARN", "reason": "mrz_field_missing", "field": field_name}

    if not ocr_value:
        return {"verdict": "WARN", "reason": "ocr_field_missing", "field": field_name}

    if _fuzzy_equal(ocr_value, mrz_value):
        return {"verdict": "PASS", "reason": None, "field": field_name}
    return {
        "verdict": "MISMATCH",
        "reason": "ocr_mrz_mismatch",
        "field": field_name,
        "ocr": ocr_value,
        "mrz": mrz_value,
    }


def cross_validate_ocr_mrz(ocr_fields: dict, mrz_fields: dict) -> dict:
    """Cross-validate all comparable identity fields between OCR and MRZ."""
    comparable = [
        "document_number",
        "surname",
        "given_names",
        "date_of_birth",
        "expiry_date",
        "sex",
        "nationality",
    ]
    results = []
    for field in comparable:
        ocr_val = ocr_fields.get(field, "")
        mrz_val = mrz_fields.get(field, "")
        # Skip if both empty (field not present in either)
        if not ocr_val and not mrz_val:
            continue
        results.append(compare_field(ocr_val, mrz_val, field))

    mismatches = [r for r in results if r["verdict"] == "MISMATCH"]
    return {
        "checked": len(results),
        "passed": sum(1 for r in results if r["verdict"] == "PASS"),
        "warnings": sum(1 for r in results if r["verdict"] == "WARN"),
        "mismatches": len(mismatches),
        "results": results,
        "overall": "PASS" if not mismatches else "MISMATCH",
    }


def cross_validate_documents(doc_a_fields: dict, doc_b_fields: dict) -> dict:
    """Compare identity fields across two documents for consistency."""
    comparable = ["surname", "given_names", "date_of_birth", "document_number"]
    results = []
    for field in comparable:
        va = doc_a_fields.get(field)
        vb = doc_b_fields.get(field)
        if field == "document_number":
            # Different document numbers are expected across distinct documents.
            continue
        if va and vb:
            verdict = (
                "PASS" if _fuzzy_equal(va, vb) else "INCONSISTENT"
            )
            results.append({"field": field, "verdict": verdict, "doc_a": va, "doc_b": vb})
        else:
            results.append({"field": field, "verdict": "WARN", "reason": "missing_in_one"})

    inconsistencies = [r for r in results if r["verdict"] == "INCONSISTENT"]
    return {
        "checked": len(results),
        "results": results,
        "inconsistencies": len(inconsistencies),
        "consistent": len(inconsistencies) == 0,
        "overall": "CONSISTENT" if not inconsistencies else "INCONSISTENT",
    }
