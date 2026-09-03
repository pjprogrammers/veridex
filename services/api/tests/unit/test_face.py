"""Tests for the face verification module (baseline engine)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from app.face.analysis import run_face_analysis
from app.face.engine import BaselineFaceEngine, cosine_similarity
from app.face.liveness import liveness_heuristic
from app.face.portrait import encode_portrait_jpeg, extract_portrait


def _make_face_image(w=400, h=500):
    img = np.full((h, w, 3), 180, dtype=np.uint8)
    # Central "face" blob
    img[100:350, 120:280] = 160
    return img


def test_cosine_similarity_identical():
    a = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(a, a) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_baseline_embedding_same_face_high_similarity():
    engine = BaselineFaceEngine()
    img1 = _make_face_image()
    img2 = img1.copy()
    emb1 = engine.get_embedding(img1)
    emb2 = engine.get_embedding(img2)
    assert emb1 and emb2
    sim = cosine_similarity(emb1, emb2)
    assert sim > 0.99


def test_baseline_embedding_different_faces_low_similarity():
    engine = BaselineFaceEngine()
    img1 = _make_face_image()
    img2 = np.full((500, 400, 3), 120, dtype=np.uint8)
    emb1 = engine.get_embedding(img1)
    emb2 = engine.get_embedding(img2)
    assert emb1 and emb2
    sim = cosine_similarity(emb1, emb2)
    assert sim < 0.99


def test_verify_threshold():
    engine = BaselineFaceEngine()
    img = _make_face_image()
    emb = engine.get_embedding(img)
    assert emb
    result = engine.verify(emb, emb, threshold=0.5)
    assert result["is_match"] is True


def test_extract_portrait_detection():
    img = _make_face_image(600, 700)
    result = extract_portrait(img, face_engine=BaselineFaceEngine())
    assert result["portrait"] is not None
    assert result["method"] == "face_detection"


def test_encode_portrait_jpeg():
    img = _make_face_image()
    result = extract_portrait(img, face_engine=BaselineFaceEngine())
    blob = encode_portrait_jpeg(result["portrait"])
    assert blob is not None
    assert len(blob) > 0


def test_encode_portrait_jpeg_none():
    assert encode_portrait_jpeg(None) is None


def test_liveness_heuristic_bounded():
    img = _make_face_image()
    result = liveness_heuristic(img)
    assert 0.0 <= result["score"] <= 1.0
    assert "verdict" in result


def test_run_face_analysis_no_identity_db():
    img = _make_face_image(600, 700)
    result = run_face_analysis(img, face_engine=BaselineFaceEngine())
    assert "portrait" in result
    assert result["duplicate_identity"] is None


def test_run_face_analysis_duplicate_detection():
    engine = BaselineFaceEngine()
    img = _make_face_image(600, 700)
    # Extract portrait the same way the analysis does, and embed it,
    # so the identity DB contains an embedding of the document's portrait.
    from app.face.portrait import extract_portrait as _extract

    pr = _extract(img, face_engine=engine)
    portrait_emb = engine.get_embedding(pr["portrait"])
    identity_db = [
        {"identity_id": "synth-1", "embedding": portrait_emb},
        {"identity_id": "synth-2", "embedding": [0.0] * 512},
    ]
    result = run_face_analysis(
        img, identity_db_embeddings=identity_db, face_engine=engine
    )
    dups = result["duplicate_identity"]
    assert dups["flagged"] is True
    assert dups["matches_found"] >= 1
