"""Forensic pipeline orchestrator.

Runs the registered detectors over a document image, fuses their findings into
a single "potential manipulation indicator" score, and assembles a complete,
serializable forensic analysis (detector results, scores, bounding boxes,
evidence descriptions and generated artifacts).

The pipeline is modular: detectors implement the :class:`ForensicDetector`
interface and a PyTorch-based detector can be added later without reworking the
fusion or endpoint layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.forensics.detectors import ALL_DETECTORS, ForensicDetector, ForensicFinding
from app.forensics.fusion import fuse


@dataclass
class ForensicResult:
    """Assembled outcome of the forensic pipeline."""

    findings: list[ForensicFinding] = field(default_factory=list)
    forensic_status: str = "insufficient_evidence"
    tampering_score: Optional[float] = None
    level: str = "NONE"
    explanation: str = ""
    components: list[dict] = field(default_factory=list)
    regions: list[dict] = field(default_factory=list)
    weights: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "forensic_status": self.forensic_status,
            "tampering_score": self.tampering_score,
            "level": self.level,
            "explanation": self.explanation,
            "weights": self.weights,
            "components": self.components,
            "regions": self.regions,
            "detectors": [
                {
                    "detector_id": f.detector_id,
                    "detector_name": f.detector_name,
                    "score": f.score,
                    "severity": f.severity,
                    "description": f.description,
                    "evidence": f.evidence,
                    "regions": f.regions,
                    "artifacts": {k: list(v) for k, v in f.artifacts.items()},
                    "detector_status": f.detector_status,
                }
                for f in self.findings
            ],
        }


class ForensicPipeline:
    """Runs detectors then fuses their findings."""

    def __init__(
        self,
        detectors: Optional[list[ForensicDetector]] = None,
        weights: Optional[dict] = None,
    ):
        self.detectors = detectors or ALL_DETECTORS
        self.weights = weights or {}

    def run(self, image: np.ndarray, context: Optional[dict] = None) -> ForensicResult:
        ctx = context or {}
        findings: list[ForensicFinding] = []
        for detector in self.detectors:
            try:
                finding = detector.analyze(image, ctx)
                # Stamp the evidence class so fusion can separate production
                # evidence from experimental/research signals.
                if finding.detector_status != detector.detector_status:
                    finding.detector_status = detector.detector_status
                findings.append(finding)
            except Exception:  # noqa: BLE001
                findings.append(
                    ForensicFinding(
                        detector_id=detector.detector_id,
                        detector_name=detector.name,
                        score=0.0,
                        severity="LOW",
                        description=f"{detector.name} failed; no signal produced.",
                        evidence={"error": True},
                        detector_status=detector.detector_status,
                    )
                )

        fused = fuse(findings, self.weights)

        regions: list[dict] = []
        for f in findings:
            for r in f.regions:
                regions.append({"detector_id": f.detector_id, **r})

        return ForensicResult(
            findings=findings,
            forensic_status=fused["forensic_status"],
            tampering_score=fused["tampering_score"],
            level=fused["level"],
            explanation=fused["explanation"],
            components=fused["weighted_components"],
            regions=regions,
            weights=fused_weight_map(self.weights),
        )


def fused_weight_map(weights: Optional[dict]) -> dict:
    """Return the effective weight map used by the fuser."""
    from app.forensics.fusion import derive_weights
    return derive_weights(weights)


forensic_pipeline = ForensicPipeline()
DEFAULT_WEIGHTS = fused_weight_map(None)
