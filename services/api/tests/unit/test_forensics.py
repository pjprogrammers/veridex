"""Tests for forensic tampering heuristics."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from app.forensics.analyze import (
    compute_ela,
    copy_move_anomaly_score,
    edge_density_anomaly,
    ela_anomaly_score,
    noise_anomaly_score,
    run_forensics,
)


def _make_image(w=1200, h=900, value=200):
    img = np.full((h, w, 3), value, dtype=np.uint8)
    return img


def test_ela_map_shape():
    img = _make_image()
    ela = compute_ela(img, quality=90)
    assert ela.shape == img.shape[:2]


def test_ela_anomaly_scores_bounded():
    img = _make_image()
    result = ela_anomaly_score(img)
    assert 0.0 <= result["score"] <= 1.0


def test_noise_anomaly_scores_bounded():
    img = _make_image()
    result = noise_anomaly_score(img)
    assert 0.0 <= result["score"] <= 1.0


def test_copy_move_anomaly_scores_bounded():
    img = _make_image()
    result = copy_move_anomaly_score(img)
    assert 0.0 <= result["score"] <= 1.0
    assert result["total_tiles"] > 0


def test_edge_density_anomaly():
    img = _make_image()
    result = edge_density_anomaly(img)
    assert 0.0 <= result["score"] <= 1.0


def test_run_forensics_structure():
    img = _make_image()
    result = run_forensics(img)
    # Evidence-integrity fields
    assert result["forensic_status"] == "insufficient_evidence"
    assert result["tampering_score"] is None
    # Research/visualization fields (experimental, not production evidence)
    assert "overall_score" in result
    assert 0.0 <= result["overall_score"] <= 1.0
    assert len(result["flags"]) == 4
    for flag in result["flags"]:
        assert flag["severity"] in {"LOW", "MEDIUM", "HIGH"}
    assert "summary" in result
    # Evidence note must be present to clarify experimental status
    assert result["evidence_note"]
    assert "experimental" in result["evidence_note"].lower()
