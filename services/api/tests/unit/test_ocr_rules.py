"""Unit tests for configurable rule-based OCR field extraction."""
import pytest

from app.pipeline import ocr_rules


def _word(text: str, x: int, y: int, conf: float = 0.95) -> dict:
    """Build a word dict with a square bbox at (x, y)."""
    return {
        "text": text,
        "confidence": conf,
        "box": [[x, y], [x + 100, y], [x + 100, y + 20], [x, y + 20]],
    }


def _row(texts: list[str], y: int, conf: float = 0.95) -> list[dict]:
    """Build a visual row of words, spaced horizontally."""
    words = []
    x = 0
    for t in texts:
        words.append(_word(t, x, y, conf))
        x += 150
    return words


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------

def test_load_rules_passport():
    rules = ocr_rules.load_rules("passport")
    assert rules is not None
    assert "full_name" in rules["fields"]
    assert "passport_number" in rules["fields"]
    assert "date_of_birth" in rules["fields"]


def test_load_rules_visa():
    rules = ocr_rules.load_rules("visa")
    assert rules is not None
    assert "visa_number" in rules["fields"]
    assert "valid_from" in rules["fields"]
    assert "valid_until" in rules["fields"]


def test_load_rules_unknown_type():
    assert ocr_rules.load_rules("national_id") is None
    assert ocr_rules.load_rules("does_not_exist") is None


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def test_extract_passport_fields():
    words = []
    words += _row(["PASSPORT", "NO.", "AB1234567"], 0)
    words += _row(["NAME", "JOHN", "PAUL", "SMITH"], 40)
    words += _row(["NATIONALITY", "IND"], 120)
    words += _row(["DATE", "OF", "BIRTH", "15-03-1985"], 160)
    words += _row(["SEX", "M"], 200)
    words += _row(["DATE", "OF", "EXPIRY", "01-01-2026"], 240)

    result = ocr_rules.extract_fields(words, "passport", raw_text="\n".join(w["text"] for w in words))

    by_name = {f.field_name: f for f in result.fields}
    assert by_name["passport_number"].value == "AB1234567"
    assert by_name["full_name"].value == "JOHN PAUL SMITH"
    assert by_name["nationality"].value == "IND"
    assert by_name["date_of_birth"].value == "850315"
    assert by_name["sex"].value == "M"
    assert by_name["date_of_expiry"].value == "260101"


def test_extract_visa_fields():
    words = []
    words += _row(["VISA", "NO.", "V12345678"], 0)
    words += _row(["NAME", "JANE", "DOE"], 40)
    words += _row(["PASSPORT", "NO.", "CD9876543"], 80)
    words += _row(["NATIONALITY", "USA"], 120)
    words += _row(["VALID", "FROM", "10-06-2024"], 160)
    words += _row(["VALID", "UNTIL", "09-06-2029"], 200)
    words += _row(["VISA", "TYPE", "B"], 240)

    result = ocr_rules.extract_fields(words, "visa")

    by_name = {f.field_name: f for f in result.fields}
    assert by_name["visa_number"].value == "V12345678"
    assert by_name["name"].value == "JANE DOE"
    assert by_name["passport_number"].value == "CD9876543"
    assert by_name["nationality"].value == "USA"
    assert by_name["valid_from"].value == "240610"
    assert by_name["valid_until"].value == "290609"
    assert by_name["visa_type"].value == "B"


def test_extract_no_match():
    words = _row(["HELLO", "WORLD"], 0)
    result = ocr_rules.extract_fields(words, "passport")
    assert result.fields == []


def test_extract_without_words():
    result = ocr_rules.extract_fields([], "passport", raw_text="empty")
    assert result.fields == []
    assert result.raw_text == "empty"


def test_extract_empty_image_no_doc_type():
    result = ocr_rules.extract_fields([], "unknown")
    assert result.document_type == "unknown"
    assert result.fields == []


# ---------------------------------------------------------------------------
# Bounding boxes preserved
# ---------------------------------------------------------------------------

def test_bbox_preserved():
    words = _row(["PASSPORT", "NO.", "XY999999"], 0)
    result = ocr_rules.extract_fields(words, "passport")
    pn = next(f for f in result.fields if f.field_name == "passport_number")
    assert len(pn.bbox) == 1
    assert pn.bbox[0][0] == [300, 0]
    assert len(pn.bbox[0]) == 4


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def test_normalize_alphanumeric_uppercase():
    words = _row(["PASSPORT", "NO.", "ab-123 456"], 0)
    result = ocr_rules.extract_fields(words, "passport")
    pn = next(f for f in result.fields if f.field_name == "passport_number")
    assert pn.value == "AB123456"


def test_normalize_nationality_3char():
    words = _row(["NATIONALITY", "INDIAN"], 0)
    result = ocr_rules.extract_fields(words, "passport")
    nat = next(f for f in result.fields if f.field_name == "nationality")
    assert nat.value == "IND"


def test_normalize_date_formats():
    assert ocr_rules._parse_date("15-03-1985") == "850315"
    assert ocr_rules._parse_date("1985-03-15") == "850315"
    assert ocr_rules._parse_date("850315") == "850315"
    assert ocr_rules._parse_date("notadate") == ""


def test_confirmed_single_field_confidence():
    words = _row(["PASSPORT", "NO.", "AB1234567"], 0, conf=0.8)
    result = ocr_rules.extract_fields(words, "passport")
    pn = next(f for f in result.fields if f.field_name == "passport_number")
    assert pn.confidence == pytest.approx(0.8, abs=0.001)


def test_allowed_values_filter():
    # "SEX" with invalid value should not produce a sex field
    words = _row(["SEX", "NONBINARY"], 0)
    result = ocr_rules.extract_fields(words, "passport")
    assert not any(f.field_name == "sex" for f in result.fields)


def test_to_dict():
    result = ocr_rules.extract_fields(
        _row(["PASSPORT", "NO.", "AB1234567"], 0), "passport", raw_text="line"
    )
    d = result.to_dict()
    assert d["document_type"] == "passport"
    assert d["raw_text"] == "line"
    assert d["fields"][0]["field_name"] == "passport_number"
    assert "value" in d["fields"][0]
    assert "confidence" in d["fields"][0]
    assert "bbox" in d["fields"][0]
