"""Deterministic tests for the ai.face sub-package.

Face detection decision logic, quality assessment, embedding normalization,
cosine similarity and the face verification decision table — all exercised
with synthetic inputs and no real InsightFace/ONNX model weights.
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai import config
from ai.face.detector import face_situation, select_document_face
from ai.face.embedding import align_face, normalize_embedding
from ai.face.engine import compute_face_similarity
from ai.face.quality import assess_face_quality
from ai.face.schemas import (
    FaceDetection,
)
from ai.face.verification import (
    cosine_similarity,
    decide,
    verify_faces,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_face_image(w=400, h=500):
    img = np.full((h, w, 3), 180, dtype=np.uint8)
    img[100:350, 120:280] = 160
    return img


def _sharper_image():
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[50:150, 50:150] = 200
    img[60:140, 60:140] = 40
    return img


def _blurrier_image():
    img = np.full((200, 200, 3), 120, dtype=np.uint8)
    cv2.GaussianBlur(img, (31, 31), 0, img)
    return img


def _detection(bbox=None, conf=0.98, landmarks=None):
    return FaceDetection(
        bbox=bbox or [100, 100, 300, 350],
        confidence=conf,
        landmarks=landmarks or [],
    )


# ===========================================================================
# COSINE SIMILARITY / EMBEDDING NORMALIZATION
# ===========================================================================

def test_cosine_identical():
    a = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(a, a) - 1.0) < 1e-6


def test_cosine_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_empty():
    assert cosine_similarity([], []) == 0.0


def test_cosine_different_length():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_normalize_embedding_raises_on_empty():
    with pytest.raises(ValueError):
        normalize_embedding([])


def test_normalize_embedding_raises_on_zero():
    with pytest.raises(ValueError):
        normalize_embedding([0.0, 0.0, 0.0])


def test_normalize_embedding_norm_is_one():
    vec = [3.0, -4.0, 0.0, 12.0]
    emb = normalize_embedding(vec)
    assert abs(np.linalg.norm(emb.vector) - 1.0) < 1e-6
    assert emb.dim == 4


def test_normalize_embedding_numpy_array():
    arr = np.array([1.0, 2.0, 3.0])
    emb = normalize_embedding(arr)
    assert emb.dim == 3
    assert abs(emb.l2_norm - float(np.linalg.norm(arr))) < 0.001


def test_compute_face_similarity_shorthand():
    a = np.random.default_rng(0).normal(size=64)
    a = (a / np.linalg.norm(a)).tolist()
    b = a[:]
    assert abs(compute_face_similarity(a, b) - 1.0) < 1e-6


# ===========================================================================
# FACE SITUATION / DETECTOR DECISION
# ===========================================================================

def test_face_situation_no_face():
    assert face_situation(0) == "NO_FACE"


def test_face_situation_single():
    assert face_situation(1) == "SINGLE_FACE"


def test_face_situation_multi():
    assert face_situation(2) == "MULTIPLE_FACES"
    assert face_situation(5) == "MULTIPLE_FACES"


def test_select_document_face_empty():
    assert select_document_face([], (500, 600)) is None


def test_select_document_face_single():
    dets = [_detection(bbox=[120, 80, 280, 300], conf=0.95)]
    best = select_document_face(dets, (500, 600))
    assert best is not None


def test_select_document_face_prefers_upper():
    upper = _detection(bbox=[120, 50, 280, 200], conf=0.9)
    lower = _detection(bbox=[120, 350, 280, 480], conf=0.95)
    best = select_document_face([upper, lower], (500, 600))
    assert best.bbox == [120, 50, 280, 200]


# ===========================================================================
# FACE QUALITY
# ===========================================================================

def test_quality_sharp_face():
    img = _sharper_image()
    det = _detection(bbox=[50, 50, 150, 150])
    q = assess_face_quality(img, det)
    assert q.blur < 0.5
    assert q.score > 0.3


def test_quality_blurry_face():
    img = _blurrier_image()
    det = _detection(bbox=[10, 10, 190, 190])
    q = assess_face_quality(img, det)
    assert q.blur > 0.3


def test_quality_too_small_face():
    img = _make_face_image(600, 800)
    det = _detection(bbox=[10, 10, 14, 14])
    q = assess_face_quality(img, det)
    assert q.size_ok is False
    assert "face_too_small" in q.reasons


def test_quality_empty_crop():
    img = _make_face_image()
    det = _detection(bbox=[0, 0, 0, 0])
    q = assess_face_quality(img, det)
    assert q.score == 0.0
    assert "face_crop_empty" in q.reasons


def test_quality_score_bounded():
    img = _make_face_image()
    det = _detection(bbox=[100, 100, 300, 350])
    q = assess_face_quality(img, det)
    assert 0.0 <= q.score <= 1.0
    assert 0.0 <= q.blur <= 1.0


def test_quality_pose_out_of_range_flagged():
    img = _make_face_image()
    # Nose placed far off the eye-midpoint axis -> strong yaw.
    extreme_landmarks = [[100, 100], [300, 100], [10, 130], [180, 260], [240, 260]]
    det = _detection(bbox=[0, 0, 400, 400], landmarks=extreme_landmarks)
    q = assess_face_quality(img, det)
    assert q.pose_ok is False
    assert "pose_out_of_range" in q.reasons


# ===========================================================================
# ALIGNMENT
# ===========================================================================

def test_align_face_no_landmarks_fallback():
    img = _make_face_image(400, 500)
    det = _detection(bbox=[50, 80, 280, 350], landmarks=[])
    aligned = align_face(img, det)
    assert aligned is not None
    assert aligned.shape == (112, 112, 3)


def test_align_face_5_landmarks():
    img = _make_face_image(400, 500)
    # 5-point landmarks (eye, eye, nose, mouth, mouth)
    lm = [[150, 180], [240, 180], [200, 260], [160, 310], [240, 310]]
    det = _detection(bbox=[120, 100, 280, 380], landmarks=lm)
    aligned = align_face(img, det)
    assert aligned is not None
    assert aligned.shape == (112, 112, 3)


# ===========================================================================
# DECISION TABLE
# ===========================================================================

def test_decide_match():
    q = 0.7
    assert decide(0.76, 0.55, q, q) == "MATCH"


def test_decide_no_match():
    q = 0.7
    assert decide(0.30, 0.55, q, q) == "NO_MATCH"


def test_decide_low_quality_hard_floor():
    q = config.FACE_MIN_QUALITY_HARD - 0.01
    assert decide(0.80, 0.55, q, q) == "LOW_QUALITY"


def test_decide_inconclusive_soft_floor():
    q = (config.FACE_MIN_QUALITY_SOFT + config.FACE_MIN_QUALITY_HARD) / 2
    assert decide(0.80, 0.55, q, q) == "INCONCLUSIVE"


def test_decide_no_quality_embedding_missing():
    assert decide(None, 0.55, None, None) == "INCONCLUSIVE"


# ===========================================================================
# verify_faces (selection logic — no models)
# ===========================================================================

def test_verify_no_face_on_document():
    result = verify_faces([], [_detection()], None, None, threshold=0.55)
    assert result.result == "NO_FACE"


def test_verify_no_face_on_live():
    result = verify_faces([_detection()], [], None, None, threshold=0.55)
    assert result.result == "NO_FACE"


def test_verify_multiple_faces_document():
    result = verify_faces(
        [_detection(), _detection()],
        [_detection()],
        None,
        None,
        threshold=0.55,
    )
    assert result.result == "MULTIPLE_FACES"


def test_verify_multiple_faces_live():
    result = verify_faces(
        [_detection()],
        [_detection(), _detection()],
        None,
        None,
        threshold=0.55,
    )
    assert result.result == "MULTIPLE_FACES"


def test_verify_match():
    rng = np.random.default_rng(42)
    vec = rng.normal(size=128)
    vec = (vec / np.linalg.norm(vec)).tolist()
    emb = normalize_embedding(vec)
    q = 0.80
    result = verify_faces(
        [_detection()],
        [_detection()],
        emb,
        emb,
        threshold=0.55,
        document_face_quality=q,
        live_face_quality=q,
    )
    assert result.result == "MATCH"
    assert result.similarity is not None
    assert abs(result.similarity - 1.0) < 1e-4


def test_verify_no_match():
    rng = np.random.default_rng(0)
    a = normalize_embedding(rng.normal(size=128))
    b = normalize_embedding(rng.normal(size=128))
    q = 0.80
    result = verify_faces(
        [_detection()],
        [_detection()],
        a,
        b,
        threshold=0.99,
        document_face_quality=q,
        live_face_quality=q,
    )
    assert result.result == "NO_MATCH"


def test_verify_threshold_in_result():
    rng = np.random.default_rng(1)
    vec = normalize_embedding(rng.normal(size=128))
    q = 0.70
    result = verify_faces(
        [_detection()],
        [_detection()],
        vec,
        vec,
        threshold=0.60,
        document_face_quality=q,
        live_face_quality=q,
    )
    assert result.threshold == 0.60


def test_verify_latency_present():
    rng = np.random.default_rng(2)
    vec = normalize_embedding(rng.normal(size=128))
    q = 0.70
    result = verify_faces(
        [_detection()],
        [_detection()],
        vec,
        vec,
        threshold=0.55,
        document_face_quality=q,
        live_face_quality=q,
    )
    assert result.latency_ms is not None
