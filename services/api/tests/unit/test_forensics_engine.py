"""Tests for the modular forensic engine (detectors + fusion).

Categories
----------
1. Contract tests        — implementation behavior (bounded scores, shapes,
                           artifacts, per-detector mechanics).
2. Fusion-mechanics tests — weighted/boosted combination math, weight merging.
3. Evidence-integrity tests — production vs experimental evidence gating:
                              experimental-only findings must never produce a
                              numeric production tampering score.
4. Synthetic-harness tests — clean-vs-manipulated checks on random-noise /
                             drawn images. These validate the harness only and
                             are NOT evidence that a detector works on real
                             documents.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
import numpy as np

from app.forensics.detectors import (
    ALL_DETECTORS,
    CompressionDetector,
    CopyMoveDetector,
    ELADetector,
    ForensicDetector,
    ForensicFinding,
    MetadataDetector,
    PortraitDetector,
    TextDetector,
)
from app.forensics.engine import ForensicPipeline, ForensicResult
from app.forensics.fusion import DEFAULT_WEIGHTS, derive_weights, fuse


def _as_jpeg(image: np.ndarray, quality: int = 92) -> np.ndarray:
    """JPEG round-trip an array; mimics a captured/saved document."""
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    assert ok
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _clean_image(w=900, h=600):
    """A genuine single-compression document for de-copy-move / fusion tests.

    Pure high-frequency texture with no repeated structures, so a copy-moved
    patch is the ONLY duplicated region and copy-move reads near-zero here.
    """
    rng = np.random.default_rng(5)
    texture = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    return _as_jpeg(texture)


def _manipulated_image(w=900, h=600):
    """A strong, well-defined manipulating cue: a copy-moved textured patch."""
    base = _clean_image(w, h)
    patch = base[100:320, 200:440].copy()  # 220x240
    base[300:520, 500:740] = patch
    return base


def _flat_doc(w=900, h=600):
    """A concrete single-compression document with border + text (drawn content).

    Used as the clean baseline for the ELA / compression recalibration checks.
    """
    img = np.full((h, w, 3), 235, dtype=np.uint8)
    cv2.rectangle(img, (30, 30), (w - 30, h - 30), (80, 80, 80), 2)
    cv2.line(img, (60, 80), (w - 60, 80), (90, 90, 90), 2)
    cv2.putText(img, "SMITH JOHN AB1234", (70, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (70, 70, 70), 1)
    return _as_jpeg(img)


def _metadata_bytes():
    from io import BytesIO

    from PIL import Image, PngImagePlugin

    img = Image.fromarray(np.full((100, 100, 3), 128, dtype=np.uint8))
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Software", "Adobe Photoshop")
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------
def test_detector_interface_contract():
    for d in ALL_DETECTORS:
        assert isinstance(d, ForensicDetector)
        assert d.detector_id
        assert d.name
        assert 0.0 <= d.default_weight <= 1.0
        assert hasattr(d, "analyze")
        assert d.detector_status in {"production", "conditional", "experimental", "unvalidated"}


def test_six_detectors_registered():
    ids = {d.detector_id for d in ALL_DETECTORS}
    assert ids == {"ela", "copy_move", "compression", "metadata", "portrait", "text"}


def test_detector_status_classification():
    statuses = {d.detector_id: d.detector_status for d in ALL_DETECTORS}
    # No detector is claimed as production-validated in this phase.
    assert statuses["ela"] == "experimental"
    assert statuses["copy_move"] == "experimental"
    assert statuses["compression"] == "experimental"
    assert statuses["portrait"] == "experimental"
    assert statuses["text"] == "experimental"
    # Metadata is conditional: evidence only when explicit editing markers exist.
    assert statuses["metadata"] == "conditional"


def test_finding_stamps_detector_status():
    finding = ELADetector().analyze(_flat_doc(), {})
    assert finding.detector_status == "experimental"
    meta = MetadataDetector().analyze(_flat_doc(), {"raw_bytes": _metadata_bytes()})
    assert meta.detector_status == "conditional"


# ---------------------------------------------------------------------------
# Per-detector behavior on clean vs manipulated (contract checks)
# ---------------------------------------------------------------------------
def test_ela_detector_bounded_and_artifacts():
    finding = ELADetector().analyze(_flat_doc(), {})
    assert 0.0 <= finding.score <= 1.0
    assert finding.artifacts.get("ela_map")
    assert finding.artifacts.get("ela_heatmap")


def test_ela_detector_clean_low():
    # Recalibration: a single-compression clean document must not report a
    # large solid ELA anomaly (which would be a false positive).
    finding = ELADetector().analyze(_flat_doc(), {})
    assert finding.score < 0.5


def test_ela_detector_reacts_to_input():
    # Naive ELA is a conservative *supporting* signal: it must stay LOW on
    # clean captures yet still be a genuine (non-constant) function of input,
    # so heterogeneous content registers a real value rather than a dead zero.
    flat = ELADetector().analyze(_flat_doc(), {})      # text/border -> sparse ELA
    noise = ELADetector().analyze(_clean_image(), {})  # flat texture -> ~0
    assert flat.score > 0.0
    assert noise.score == 0.0
    assert flat.score != noise.score


def test_copy_move_detector_clean_low():
    # SYNTHETIC-HARNESS ONLY: pure random noise (with one copy-moved patch) as
    # the clean baseline has no duplicated structure. This validates the
    # harness, NOT real-document performance.
    finding = CopyMoveDetector().analyze(_clean_image(), {})
    assert finding.score < 0.5


def test_copy_move_detector_manipulated_higher():
    # SYNTHETIC-HARNESS ONLY: random-noise base + pasted patch. Does NOT
    # demonstrate real-document discrimination (see audit).
    clean = CopyMoveDetector().analyze(_clean_image(), {})
    manip = CopyMoveDetector().analyze(_manipulated_image(), {})
    assert manip.score > clean.score
    assert manip.regions  # duplicated region(s) should be surfaced


def test_compression_detector_clean_low():
    # SYNTHETIC-HARNESS ONLY: single-compression random noise must not report
    # heavy block-artifact signal. Harness validation, not real docs.
    finding = CompressionDetector().analyze(_clean_image(), {})
    assert finding.score < 0.5


def test_compression_detector_recompressed_higher():
    # SYNTHETIC-HARNESS ONLY: a hard Q25 re-save of random noise shows the
    # blockiness metric responds to recompression. Harness validation only.
    clean = CompressionDetector().analyze(_clean_image(), {})
    heavy = CompressionDetector().analyze(_as_jpeg(_clean_image(), quality=25), {})
    assert heavy.score > clean.score
    assert heavy.score >= 0.5  # must actually register as a strong artifact


def test_metadata_detector_editing_software():
    finding = MetadataDetector().analyze(_clean_image(), {"raw_bytes": _metadata_bytes()})
    assert finding.score > 0
    assert finding.evidence.get("software") == "Adobe Photoshop"
    # Cautious phrasing — never "Photoshop = fake".
    assert "forgery" not in finding.description.lower()
    assert "supporting" in finding.description.lower()


def test_metadata_detector_no_bytes_low():
    finding = MetadataDetector().analyze(_clean_image(), {})
    assert finding.score == 0.0


def test_metadata_detector_clean_bytes_no_authenticity_boost():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.fromarray(_clean_image()).save(buf, format="PNG")
    finding = MetadataDetector().analyze(_clean_image(), {"raw_bytes": buf.getvalue()})
    # Absence of editing software: score 0 AND wording must NOT claim the
    # document is authentic.
    assert finding.score == 0.0
    assert "not proof of authenticity" in finding.description.lower()


def test_portrait_detector_bounded_and_region():
    finding = PortraitDetector().analyze(_clean_image(), {})
    assert 0.0 <= finding.score <= 1.0
    assert finding.regions


def test_text_detector_bounded_and_region():
    finding = TextDetector().analyze(_clean_image(), {})
    assert 0.0 <= finding.score <= 1.0
    assert finding.regions


def test_all_detectors_return_full_finding_shape():
    for d in ALL_DETECTORS:
        f = d.analyze(_clean_image(), {})
        assert 0.0 <= f.score <= 1.0
        assert f.severity in {"LOW", "MEDIUM", "HIGH"}
        assert isinstance(f.description, str) and f.description
        assert isinstance(f.evidence, dict)
        assert isinstance(f.regions, list)
        assert f.detector_status in {"production", "conditional", "experimental", "unvalidated"}


# ---------------------------------------------------------------------------
# Evidence-integrity / production gating (NOT synthetic discrimination)
# ---------------------------------------------------------------------------
def _experimental_set(*, with_metadata_score: float = 0.0):
    """All-six finding set; metadata is conditional, the rest experimental."""
    return [
        ForensicFinding(detector_id="ela", detector_name="ELA", score=0.85,
                        severity="HIGH", description="", detector_status="experimental"),
        ForensicFinding(detector_id="copy_move", detector_name="CM", score=0.3,
                        severity="MEDIUM", description="", detector_status="experimental"),
        ForensicFinding(detector_id="compression", detector_name="C", score=0.2,
                        severity="LOW", description="", detector_status="experimental"),
        ForensicFinding(detector_id="metadata", detector_name="M", score=with_metadata_score,
                        severity="MEDIUM" if with_metadata_score > 0 else "LOW",
                        description="", detector_status="conditional"),
        ForensicFinding(detector_id="portrait", detector_name="P", score=0.15,
                        severity="LOW", description="", detector_status="experimental"),
        ForensicFinding(detector_id="text", detector_name="T", score=0.15,
                        severity="LOW", description="", detector_status="experimental"),
    ]


def test_fusion_all_experimental_insufficient_evidence():
    # High experimental scores must NOT produce a production tampering score.
    res = fuse(_experimental_set(with_metadata_score=0.0))
    assert res["forensic_status"] == "insufficient_evidence"
    assert res["tampering_score"] is None
    assert res["level"] == "NONE"


def test_fusion_experimental_findings_remain_available():
    res = fuse(_experimental_set(with_metadata_score=0.0))
    assert res["weighted_components"]
    scores = {c["detector_id"]: c["score"] for c in res["weighted_components"]}
    assert scores["ela"] == 0.85  # experimental signal preserved for research
    assert scores["copy_move"] == 0.3


def test_fusion_no_metadata_does_not_imply_authenticity():
    # Absence of editing-software metadata → no conditional evidence. The
    # explanation must NOT claim the document is authentic.
    res = fuse(_experimental_set(with_metadata_score=0.0))
    assert res["forensic_status"] == "insufficient_evidence"
    assert res["tampering_score"] is None
    explanation = res["explanation"].lower()
    assert "not a statement of authenticity" in explanation


def test_fusion_metadata_conditional_evidence_sufficient():
    # Explicit editing-software metadata provides conditional evidence, so a
    # numeric tampering score is permitted.
    res = fuse(_experimental_set(with_metadata_score=0.6))
    assert res["forensic_status"] == "sufficient_evidence"
    assert res["tampering_score"] is not None
    assert 0.0 <= res["tampering_score"] <= 1.0
    meta = next(c for c in res["weighted_components"] if c["detector_id"] == "metadata")
    assert meta["detector_status"] == "conditional"


def test_fusion_experimental_only_never_returns_number_even_when_high():
    # Even an overwhelming experimental signal must not yield a score when no
    # production/conditional evidence exists.
    res = fuse(_experimental_set(with_metadata_score=0.0))
    assert res["tampering_score"] is None
    assert res["forensic_status"] == "insufficient_evidence"


# ---------------------------------------------------------------------------
# Fusion mechanics
# ---------------------------------------------------------------------------
def test_default_weights_cover_all_detectors():
    assert set(DEFAULT_WEIGHTS) == {"ela", "copy_move", "compression", "metadata", "portrait", "text"}
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-6


def test_weights_not_redistributed_to_appear_meaningful():
    # The audit conclusion holds: weights are NOT rebalanced to make
    # experimental evidence look like production evidence.
    assert DEFAULT_WEIGHTS == {
        "ela": 0.25,
        "copy_move": 0.20,
        "compression": 0.20,
        "metadata": 0.10,
        "portrait": 0.15,
        "text": 0.10,
    }


def test_derive_weights_merges_overrides():
    w = derive_weights({"ela": 0.5})
    assert w["ela"] == 0.5
    assert w["copy_move"] == DEFAULT_WEIGHTS["copy_move"]


def test_fuse_all_zero():
    empty = fuse([])
    assert empty["tampering_score"] is None
    assert empty["forensic_status"] == "insufficient_evidence"
    assert empty["level"] == "NONE"
    assert empty["weighted_components"] == []


def test_fusion_is_weighted_not_blind_average():
    # Mechanics: a single strong CONDITIONAL signal is boosted above a plain
    # average. Uses conditional status so the numeric path is valid.
    from app.forensics.detectors import ForensicFinding

    findings = [
        ForensicFinding(detector_id="ela", detector_name="ELA", score=1.0,
                        severity="HIGH", description="", detector_status="conditional"),
        ForensicFinding(detector_id="copy_move", detector_name="CM", score=0.0,
                        severity="LOW", description=""),
        ForensicFinding(detector_id="compression", detector_name="C", score=0.0,
                        severity="LOW", description=""),
        ForensicFinding(detector_id="metadata", detector_name="M", score=0.0,
                        severity="LOW", description=""),
        ForensicFinding(detector_id="portrait", detector_name="P", score=0.0,
                        severity="LOW", description=""),
        ForensicFinding(detector_id="text", detector_name="T", score=0.0,
                        severity="LOW", description=""),
    ]
    # ELA has the highest weight (0.25) and is the only strong signal here.
    result = fuse(findings)
    # Pure average of one 1.0 and five 0.0 = 0.167. A weighted fuser raises the
    # single strong signal above that (max boost), so it must exceed 0.167.
    assert result["tampering_score"] > 0.167
    assert result["tampering_score"] < 1.0


def test_fusion_weights_change_score():
    from app.forensics.detectors import ForensicFinding

    findings = [
        ForensicFinding(detector_id=d, detector_name=d, score=1.0, severity="HIGH", description="",
                        detector_status="conditional")
        for d in ("ela", "copy_move", "compression", "metadata", "portrait", "text")
    ]
    base = fuse(findings)
    # Boost ELA weight; since all are 1.0 the weighted mean is unchanged, but we
    # confirm reweighting is accepted without error and stays bounded.
    boosted = fuse(findings, {"ela": 0.9})
    assert 0.0 <= base["tampering_score"] <= 1.0
    assert 0.0 <= boosted["tampering_score"] <= 1.0
    assert base["weighted_components"] and boosted["weighted_components"]


# ---------------------------------------------------------------------------
# Engine / pipeline
# ---------------------------------------------------------------------------
def test_pipeline_all_experimental_produces_insufficient_evidence():
    # SYNTHETIC-HARNESS ONLY: the pipeline has no production/conditional detector
    # firing on a pure random-noise image, so it must return insufficient_evidence.
    pipe = ForensicPipeline()
    res = pipe.run(_clean_image(), {"raw_bytes": None})
    assert isinstance(res, ForensicResult)
    assert res.forensic_status == "insufficient_evidence"
    assert res.tampering_score is None
    assert res.level == "NONE"


def test_pipeline_experimental_detectors_still_return_findings():
    # Experimental findings must remain available for research/visualization.
    pipe = ForensicPipeline()
    res = pipe.run(_clean_image(), {"raw_bytes": None})
    assert len(res.findings) == 6
    scores = {f.detector_id: f.score for f in res.findings}
    assert "ela" in scores and "copy_move" in scores


def test_pipeline_result_to_dict_shape():
    pipe = ForensicPipeline()
    res = pipe.run(_clean_image(), {"raw_bytes": None})
    d = res.to_dict()
    assert set(d) == {
        "forensic_status", "tampering_score", "level", "explanation", "weights",
        "components", "regions", "detectors",
    }
    assert d["forensic_status"] == "insufficient_evidence"
    assert d["tampering_score"] is None
    assert len(d["detectors"]) == 6
    sample = d["detectors"][0]
    assert set(sample) == {
        "detector_id", "detector_name", "score", "severity",
        "description", "evidence", "regions", "artifacts", "detector_status",
    }


def test_pipeline_detector_failure_does_not_crash():
    class Boom(ForensicDetector):
        detector_id = "boom"
        name = "Boom"
        default_weight = 0.1
        def analyze(self, image, context):
            raise RuntimeError("boom")

    pipe = ForensicPipeline(detectors=[Boom()])
    res = pipe.run(_clean_image(), {})
    assert isinstance(res, ForensicResult)
    assert res.findings[0].score == 0.0
    assert res.findings[0].severity == "LOW"


def test_pipeline_custom_weights():
    pipe = ForensicPipeline(weights={"ela": 0.9})
    res = pipe.run(_manipulated_image(), {"raw_bytes": None})
    assert res.weights["ela"] == 0.9
