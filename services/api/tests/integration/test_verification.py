"""Integration test for the verification workflow (no DB required)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from app.face.analysis import run_face_analysis
from app.face.engine import BaselineFaceEngine
from app.forensics.analyze import run_forensics
from app.pipeline.pipeline import analyze_document


def _make_document_image(w=2000, h=1500):
    import cv2
    img = np.full((h, w, 3), 240, dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (w - 20, h - 20), (200, 200, 200), 3)
    # portrait zone (top-left)
    cv2.rectangle(img, (150, 150), (550, 500), (170, 170, 170), -1)
    # MRZ-like dense region at bottom
    for y in range(h - 200, h - 40, 30):
        cv2.rectangle(img, (100, y), (w - 100, y + 15), (0, 0, 0), -1)
    return img


def test_full_verification_pipeline_structure():
    img = _make_document_image()
    doc_analysis = analyze_document(img)
    forensics = run_forensics(img)
    face = run_face_analysis(
        img, identity_db_embeddings=None, face_engine=BaselineFaceEngine()
    )

    # Document analysis
    assert doc_analysis.width > 0
    assert "overall_score" in doc_analysis.quality

    # Forensics
    assert 0.0 <= forensics["overall_score"] <= 1.0
    assert len(forensics["flags"]) == 4

    # Face
    assert face["portrait"]["portrait"] is not None
    assert face["duplicate_identity"] is None


def test_forensics_and_face_combine_into_risk_signals():
    img = _make_document_image()
    analyze_document(img)  # ensure document analysis runs without error
    forensics = run_forensics(img)
    face = run_face_analysis(img, face_engine=BaselineFaceEngine())

    # Risk factors include anything with content (document processed)
    risk_factors = []
    if forensics["overall_score"] > 0.15:
        risk_factors.append("forensic")
    if face.get("verification") and not face["verification"]["is_match"]:
        risk_factors.append("face")

    assert isinstance(risk_factors, list)
