"""Tests for MRZ region detection and line assembly from OCR word boxes."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.pipeline.mrz_region import (
    _assemble_line,
    cluster_rows,
    detect_mrz_region,
    extract_mrz_from_words,
)


def _word(text, x, y, w=40, h=14):
    """Build an OCR word dict with a box centered near (x, y)."""
    return {
        "text": text,
        "confidence": 0.98,
        "box": [
            [x - w // 2, y - h // 2],
            [x + w // 2, y - h // 2],
            [x + w // 2, y + h // 2],
            [x - w // 2, y + h // 2],
        ],
    }


def _mrz_word_row(line, y, block_w=400, char_w=12):
    """Split a fixed MRZ text into word boxes spaced across a block."""
    words = []
    text = line
    # Simulate the OCR splitting the line into several adjacent chunks
    # (real MRZ characters are tightly packed, so chunks abut with no gap).
    chunks = [text[i : i + 11] for i in range(0, len(text), 11)]
    left0 = 120
    x = left0
    for ch in chunks:
        w = len(ch) * char_w
        words.append(_word(ch, x + w / 2, y, w=w))
        x += w
    return words


def test_empty_words_not_detected():
    r = detect_mrz_region([])
    assert r.detected is False
    assert "no_words" in r.warnings


def test_sparse_text_not_detected():
    # Some ordinary printed text, not dense enough to be an MRZ zone.
    words = [_word("PASSPORT", 100, 50), _word("NAME", 100, 90)]
    r = detect_mrz_region(words)
    assert r.detected is False


def test_dense_mrz_rows_detected():
    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    line2 = "L898902C<3UTO6908061F9406236ZE184226B<<<<<14"
    words = _mrz_word_row(line1, 520) + _mrz_word_row(line2, 545)
    r = detect_mrz_region(words)
    assert r.detected is True
    assert len(r.lines) >= 2
    # Assembled lines should be uppercase and contain the row characters.
    joined = "".join(r.lines)
    assert "UTOERIKSSON" in joined
    assert "L898902C" in joined


def test_assemble_line_joins_without_space_loss():
    words = _mrz_word_row("P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<", 300)
    rows = cluster_rows(words)
    line = _assemble_line(rows[0]).replace("<", "")
    assert line.startswith("PUTOERIKSSONANNAMARIA")


def test_low_density_not_detected():
    # A long string of spaces/gutters should not pass density.
    words = _mrz_word_row("P<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", 400)
    r = detect_mrz_region(words)
    assert r.detected is False


def test_extract_mrz_from_words_wrapper():
    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    line2 = "L898902C<3UTO6908061F9406236ZE184226B<<<<<14"
    words = _mrz_word_row(line1, 520) + _mrz_word_row(line2, 545)
    r = extract_mrz_from_words(words)
    assert r.detected is True
