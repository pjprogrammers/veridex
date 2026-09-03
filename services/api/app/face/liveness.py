"""Liveness / presentation-attack heuristic checks.

A heuristic baseline that estimates whether a presented face is a live person
or a printed/photo presentation. NOTE: This is NOT a certified PAD (presentation
attack detection) system — it only provides weak indicators and always defaults
to recommending manual review when suspicious.
"""
import cv2
import numpy as np


def liveness_heuristic(image: np.ndarray) -> dict:
    """Estimate presentation-attack likelihood from a single face image.

    Heuristic signals:
      - Extremely low noise / over-flat regions suggest a printed photo.
      - Moiré / screen-capture artifacts raise suspicion.
      - Unnatural uniform texture in the skin region.
    All are weak and combined into a bounded suspicion score (0-1).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.size == 0:
        return {"score": 0.5, "verdict": "uncertain", "signals": []}

    signals: list[dict[str, str | float]] = []

    # 1. Noise level (printed photos are often low-noise / over-smoothed)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(laplacian.var())
    # Very low sharpness -> potential print
    if sharpness < 50:
        signals.append({"name": "low_texture_noise", "score": 0.7})
    elif sharpness < 120:
        signals.append({"name": "low_texture_noise", "score": 0.3})

    # 2. Uniformity of skin regions (over-flat -> print)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # We only use low variance as a weak cue
    std = float(np.std(gray))
    if std < 25:
        signals.append({"name": "low_contrast_flat", "score": 0.4})

    # 3. Moiré / periodic screen artifact proxy (frequency band energy)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.log(np.abs(fshift) + 1.0)
    sz = gray.shape
    center = magnitude[
        sz[0] // 2 - 4:sz[0] // 2 + 5, sz[1] // 2 - 4:sz[1] // 2 + 5
    ]
    dc_energy = float(np.mean(center))
    total_energy = float(np.mean(magnitude)) + 1e-6
    peakness = dc_energy / total_energy
    if peakness > 6.0:
        signals.append({"name": "periodic_artifact_moire", "score": 0.6})

    if not signals:
        score = 0.15  # baseline low suspicion
    else:
        score_total = sum(float(s["score"]) for s in signals)
        score = min(1.0, 0.3 + score_total / (len(signals) + 1))

    verdict = (
        "manual_review_recommended"
        if score >= 0.5
        else "no_strong_liveness_concerns"
    )

    return {
        "score": round(float(np.clip(score, 0.0, 1.0)), 4),
        "verdict": verdict,
        "signals": signals,
    }
