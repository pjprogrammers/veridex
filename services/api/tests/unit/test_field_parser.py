"""Tests for the deterministic OCR field parser (visual fields vs MRZ)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.pipeline.field_parser import (
    _yy_mm_dd_from_printed,
    extract_fields_from_words,
)


def _row(y, pairs):
    """Build OCR word boxes for a single visual row of (x, text) pairs."""
    words = []
    for xc, text in pairs:
        words.append(
            {
                "text": text,
                "confidence": 0.99,
                "box": [[xc, y], [xc + 40, y], [xc + 40, y + 20], [xc, y + 20]],
            }
        )
    return words


def _passport_words():
    """Simulate PaddleOCR-style word boxes for a passport face."""
    words = []
    words += _row(150, [(80, "NATIONALITY"), (400, "GBR"), (700, "SEX"), (760, "M")])
    words += _row(180, [(80, "DOCUMENT"), (210, "NO"), (320, "P12345678")])
    words += _row(265, [(80, "SURNAME"), (400, "SMITH")])
    words += _row(341, [(80, "GIVEN"), (190, "NAME"), (400, "JORDAN")])
    words += _row(417, [(80, "DATE"), (170, "OF"), (240, "BIRTH"), (400, "15-04-1991")])
    words += _row(493, [(80, "DATE"), (170, "OF"), (240, "EXPIRY"), (400, "15-04-2036")])
    return words


def test_empty_words():
    assert extract_fields_from_words([]) == {}


def test_extract_passport_fields():
    fields = extract_fields_from_words(_passport_words())
    assert fields["document_number"] == "P12345678"
    assert fields["surname"] == "SMITH"
    assert fields["given_names"] == "JORDAN"
    assert fields["date_of_birth"] == "910415"
    assert fields["expiry_date"] == "360415"
    assert fields["sex"] == "M"
    assert fields["nationality"] == "GBR"


def test_extract_national_id_fields():
    words = []
    words += _row(110, [(80, "SURNAME"), (400, "JOHNSON")])
    words += _row(174, [(80, "GIVEN"), (190, "NAME"), (400, "ALEX")])
    words += _row(238, [(80, "DATE"), (170, "OF"), (240, "BIRTH"), (400, "23-02-1987")])
    words += _row(302, [(80, "SEX"), (200, "F")])
    words += _row(366, [(80, "ID"), (140, "NUMBER"), (300, "N87654321")])
    words += _row(430, [(80, "VALID"), (170, "UNTIL"), (400, "23-02-2031")])
    fields = extract_fields_from_words(words)
    assert fields["surname"] == "JOHNSON"
    assert fields["given_names"] == "ALEX"
    assert fields["date_of_birth"] == "870223"
    assert fields["sex"] == "F"
    assert fields["document_number"] == "N87654321"
    assert fields["expiry_date"] == "310223"


def test_labels_split_across_multiple_words():
    fields = extract_fields_from_words(_passport_words())
    # "DATE OF BIRTH" spans three tokens; value must still be found.
    assert fields["date_of_birth"] == "910415"


def test_missing_fields_omitted():
    words = _row(100, [(80, "SURNAME"), (400, "SMITH")])
    fields = extract_fields_from_words(words)
    assert fields == {"surname": "SMITH"}


def test_national_id_birth_before_1970_uses_two_digit_year_no_century_logic():
    # DDMMYYYY -> YYMMDD
    assert _yy_mm_dd_from_printed("15-04-1991") == "910415"
    assert _yy_mm_dd_from_printed("23-02-1987") == "870223"
    assert _yy_mm_dd_from_printed("1991-04-15") == "910415"
    assert _yy_mm_dd_from_printed("910415") == "910415"
    assert _yy_mm_dd_from_printed("not a date") == ""
