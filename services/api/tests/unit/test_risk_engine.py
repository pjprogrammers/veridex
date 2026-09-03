"""Tests for the explainable risk engine."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.risk.engine import RISK_LEVELS, RiskEngine


def _engine():
    return RiskEngine()


def test_no_signals_low_risk():
    r = _engine().compute()
    assert r.score == 0.0
    assert r.level == "LOW"
    assert len(r.factors) == 0


def test_face_mismatch_raises_risk():
    r = _engine().compute(
        face={"verification": {"is_match": False, "similarity": 0.1}}
    )
    assert r.score > 0.5
    assert r.level in ("HIGH", "CRITICAL")


def test_registry_stolen_critical():
    r = _engine().compute(registry={"status": "reported_stolen"})
    assert r.level in ("HIGH", "CRITICAL")
    assert r.score >= 0.7


def test_risk_levels_valid():
    r = _engine().compute(forensics={"overall_score": 0.6})
    assert r.level in RISK_LEVELS


def test_explanation_nonempty_with_factors():
    r = _engine().compute(face={"verification": {"is_match": False, "similarity": 0.1}})
    assert r.explanation
    assert "decision-support" in r.explanation.lower() or "manual review" in r.explanation.lower()


def test_recommendations_present_for_high_risk():
    r = _engine().compute(registry={"status": "blacklisted"})
    assert r.recommendations
    assert any("manual review" in rec.lower() for rec in r.recommendations)


def test_score_bounded():
    for signal in [0.0, 0.3, 0.6, 0.9, 1.0]:
        r = _engine().compute(forensics={"overall_score": signal})
        assert 0.0 <= r.score <= 1.0


def test_face_mismatch_and_registry_both_contribute():
    r = _engine().compute(
        face={"verification": {"is_match": False, "similarity": 0.1}},
        registry={"status": "reported_stolen"},
    )
    ids = {f["id"] for f in r.factors}
    assert "face_no_match" in ids
    assert "registry_alert" in ids
