"""Evidence fusion for forensic detectors.

Combines per-detector anomaly scores into a single tampering indicator. The
fuser is *not* a blind average: it applies configurable per-detector weights,
then blends a small max-boost so a single very strong signal is not diluted by
many clean detectors. All output is a "potential manipulation indicator"
score, never a claim of forgery.

Production-evidence integrity
----------------------------
A ``forensic_status`` guards the fused score:

* ``"sufficient_evidence"`` — at least one *production* or *conditional*
  detector produced an explicit positive signal, so a numerical
  ``tampering_score`` is meaningful.
* ``"insufficient_evidence"`` — only experimental/unvalidated detectors ran
  (or none fired). Their outputs are retained for research/debugging but must
  NOT be conflated with a production tampering score, so
  ``tampering_score`` is ``None``.

Experimental detector scores are still computed and returned in
``weighted_components`` for research/visualization, but they never drive a
production tampering score by themselves.
"""
from __future__ import annotations

from app.forensics.detectors import ForensicFinding

# Default configurable weights (sum ~= 1.0). Overridable per pipeline/request.
# NOTE: these weights only apply when a production/conditional detector fires.
# They are NOT redistributed to make experimental evidence look meaningful.
DEFAULT_WEIGHTS = {
    "ela": 0.25,
    "copy_move": 0.20,
    "compression": 0.20,
    "metadata": 0.10,
    "portrait": 0.15,
    "text": 0.10,
}

# Blending factor for the strongest single detector (avoids blind averaging).
MAX_BOOST = 0.3

# Detector statuses that may legitimately drive a production tampering score.
PRODUCTION_STATUSES = ("production", "conditional")


def derive_weights(weights: dict | None) -> dict:
    """Return a validated weight mapping merged over defaults."""
    merged = dict(DEFAULT_WEIGHTS)
    if weights:
        merged.update({k: float(v) for k, v in weights.items() if k in merged})
    return merged


def fuse(
    findings: list[ForensicFinding],
    weights: dict | None = None,
) -> dict:
    """Fuse findings into a tampering indicator score and assessment.

    Returns a dict with ``forensic_status``, ``tampering_score``, ``level``,
    ``weighted_components`` and a cautious ``explanation``.

    ``tampering_score`` is ``None`` when no production/conditional detector
    provides explicit evidence (``forensic_status = "insufficient_evidence"``).
    Experimental findings are still surfaced in ``weighted_components`` for
    research/debugging/visualization.
    """
    w = derive_weights(weights)
    by_id = {f.detector_id: f for f in findings}

    weighted_sum = 0.0
    weight_total = 0.0
    components: list[dict] = []
    scores: list[float] = []
    production_fired = False
    for detector_id, weight in w.items():
        finding = by_id.get(detector_id)
        score = finding.score if finding else 0.0
        # Only weight detectors that actually ran (produced a finding).
        if finding is not None:
            status = finding.detector_status
            weighted_sum += score * weight
            weight_total += weight
            scores.append(score)
            components.append(
                {
                    "detector_id": detector_id,
                    "name": finding.detector_name,
                    "score": finding.score,
                    "weight": weight,
                    "severity": finding.severity,
                    "detector_status": status,
                }
            )
            # Conditional detectors count only when they actually produced an
            # explicit positive signal (score > 0), so "no metadata present"
            # does NOT become evidence of tampering — absence of editing
            # metadata is never authenticity evidence.
            if status in PRODUCTION_STATUSES and score > 0.0:
                production_fired = True

    if weight_total <= 0 or not scores:
        return {
            "forensic_status": "insufficient_evidence",
            "tampering_score": None,
            "level": "NONE",
            "weighted_components": components,
            "explanation": (
                "No forensic detector produced a signal. This is not a proof "
                "of authenticity; manual review remains prudent."
            ),
        }

    if not production_fired:
        # Experimental/unvalidated detectors are preserved for research and
        # debugging, but they are NOT permitted to drive a production score.
        explanation = _explain_insufficient(components)
        return {
            "forensic_status": "insufficient_evidence",
            "tampering_score": None,
            "level": "NONE",
            "weighted_components": components,
            "explanation": explanation,
        }

    weighted_mean = weighted_sum / weight_total
    max_score = max(scores)
    tampering_score = (1.0 - MAX_BOOST) * weighted_mean + MAX_BOOST * max_score
    tampering_score = round(float(min(1.0, tampering_score)), 4)

    level = _level(tampering_score)
    explanation = _explain(level, tampering_score, components)
    return {
        "forensic_status": "sufficient_evidence",
        "tampering_score": tampering_score,
        "level": level,
        "weighted_components": components,
        "explanation": explanation,
    }


def _level(score: float) -> str:
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    if score >= 0.15:
        return "LOW"
    return "NONE"


def _explain(level: str, score: float, components: list[dict]) -> str:
    top = sorted(components, key=lambda c: c["score"], reverse=True)[:3]
    if not top:
        return (
            "No significant tampering indicators detected. This is not a proof "
            "of authenticity; manual review remains prudent."
        )
    parts = []
    for c in top:
        parts.append(f"{c['name'].lower()} ({c['score']:.2f})")
    return (
        f"Tampering indicator level: {level} (score {score:.2f}). "
        f"Principal supporting signals: {', '.join(parts)}. "
        "These are potential-manipulation indicators, not a determination of "
        "forgery. Manual review is required."
    )


def _explain_insufficient(components: list[dict]) -> str:
    """Explanation when only experimental signals are present."""
    if not components:
        return (
            "No forensic detector produced a signal. This is not a proof of "
            "authenticity; manual review remains prudent."
        )
    top = sorted(components, key=lambda c: c["score"], reverse=True)[:3]
    parts = []
    for c in top:
        parts.append(f"{c['name'].lower()} ({c['score']:.2f})")
    return (
        "Forensic evidence is currently insufficient to report a tampering "
        f"score (detectors are experimental/unvalidated). "
        f"Raw experimental signals: {', '.join(parts)}. "
        "This is NOT a statement of authenticity."
    )
