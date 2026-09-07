"""Explainable risk engine.

Combines validated signals into a bounded risk score (0-1) with a risk level
and a human-readable explanation listing contributing factors. The engine is
a transparent weighted model so every point of the score is attributable —
no opaque "black box" for an officer decision-support tool.

Language is calibrated: outputs use "high-risk indicators", "verification
mismatch", "potential manipulation" — never claims of proof.
"""
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings

settings = get_settings()

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]


@dataclass
class RiskFactor:
    """A single contributory risk signal."""

    id: str
    label: str
    weight: float
    score: float  # 0-1 strength of the signal
    source: str
    detail: str = ""


@dataclass
class RiskResult:
    score: float = 0.0
    level: str = "UNKNOWN"
    factors: list[dict] = field(default_factory=list)
    explanation: str = ""
    recommendations: list[str] = field(default_factory=list)


class RiskEngine:
    def compute(
        self,
        *,
        document_analysis: dict | None = None,
        forensics: dict | None = None,
        face: dict | None = None,
        registry: dict | None = None,
        validation: dict | None = None,
        cross_validation: dict | None = None,
    ) -> RiskResult:
        factors: list[RiskFactor] = []

        # --- Document quality ---
        quality = (document_analysis or {}).get("quality", {})
        q_score = quality.get("overall_score", 0.0)
        if quality and q_score < 0.35:
            factors.append(
                RiskFactor(
                    id="low_quality",
                    label="Poor image quality",
                    weight=0.10,
                    score=0.8,
                    source="document_analysis",
                    detail=f"Quality score {q_score:.2f}",
                )
            )

        # --- MRZ validity ---
        mrz = (document_analysis or {}).get("mrz", {})
        if mrz and mrz.get("mrz_detected"):
            if not mrz.get("mrz_valid"):
                failed = [
                    k for k, v in (mrz.get("check_digits") or {}).items()
                    if v is False
                ]
                factors.append(
                    RiskFactor(
                        id="mrz_check_failed",
                        label="MRZ check-digit validation failed",
                        weight=0.20,
                        score=0.85,
                        source="mrz",
                        detail=",".join(failed) if failed else "invalid_mrz",
                    )
                )
        elif mrz and not mrz.get("mrz_detected"):
            factors.append(
                RiskFactor(
                    id="mrz_unreadable",
                    label="MRZ could not be parsed",
                    weight=0.12,
                    score=0.5,
                    source="mrz",
                )
            )

        # --- Field validation ---
        if validation:
            fails = [
                k for k, v in validation.items() if v.get("verdict") == "FAIL"
            ]
            warns = [
                k for k, v in validation.items() if v.get("verdict") == "WARN"
            ]
            if "expiry_date" in fails and any(
                v.get("reason") == "document_expired"
                for k, v in validation.items()
                if k == "expiry_date"
            ):
                factors.append(
                    RiskFactor(
                        id="expired_document",
                        label="Document is expired",
                        weight=0.30,
                        score=1.0,
                        source="validation",
                    )
                )
            other_fails = [f for f in fails if f != "expiry_date"]
            if other_fails:
                factors.append(
                    RiskFactor(
                        id="invalid_fields",
                        label="Invalid field values detected",
                        weight=0.20,
                        score=0.7,
                        source="validation",
                        detail=",".join(other_fails),
                    )
                )
            if warns:
                factors.append(
                    RiskFactor(
                        id="missing_fields",
                        label="Some identity fields could not be verified",
                        weight=0.08,
                        score=0.4,
                        source="validation",
                        detail=",".join(warns),
                    )
                )

        # --- OCR vs MRZ cross-validation ---
        if cross_validation and cross_validation.get("overall") == "MISMATCH":
            factors.append(
                RiskFactor(
                    id="ocr_mrz_mismatch",
                    label="Verification mismatch between visual OCR and MRZ data",
                    weight=0.35,
                    score=0.9,
                    source="cross_validation",
                    detail=str(cross_validation.get("mismatches")),
                )
            )

        # --- Cross-document consistency ---
        if cross_validation and isinstance(cross_validation, list):
            for cv in cross_validation:
                if cv and cv.get("overall") == "INCONSISTENT":
                    factors.append(
                        RiskFactor(
                            id="cross_doc_inconsistent",
                            label="Inconsistency across submitted documents",
                            weight=0.30,
                            score=0.85,
                            source="cross_document",
                        )
                    )

        # --- Forensics ---
        # Experimental detector outputs are research/debugging signals only.
        # They must NOT silently raise a production risk score. A forensics
        # factor is added ONLY when the forensic subsystem reports
        # sufficient_evidence (i.e. a production/conditional detector fired).
        if forensics:
            f_status = forensics.get("forensic_status")
            # "tampering_score" is the canonical production key produced by the
            # modular engine; fall back to the legacy "overall_score" research
            # aggregate for compatibility with the legacy verify payload.
            f_score = forensics.get(
                "tampering_score", forensics.get("overall_score", 0.0)
            )
            if f_status == "sufficient_evidence" and f_score is not None:
                if f_score >= 0.5:
                    level_label = "strong"
                    weight = 0.30
                elif f_score >= 0.25:
                    level_label = "some"
                    weight = 0.15
                else:
                    level_label = "no"
                    weight = 0.0
                if level_label != "no":
                    factors.append(
                        RiskFactor(
                            id="forensics",
                            label=f"{level_label.capitalize()} potential manipulation indicators",
                            weight=weight,
                            score=min(1.0, f_score),
                            source="forensics",
                            detail=f"overall {f_score:.2f}",
                        )
                    )

        # --- Face verification ---
        if face:
            verification = face.get("verification")
            if verification and not verification.get("is_match"):
                factors.append(
                    RiskFactor(
                        id="face_no_match",
                        label="Portrait does not match provided face",
                        weight=0.45,
                        score=0.95,
                        source="face",
                        detail=f"similarity {verification.get('similarity')}",
                    )
                )
            liveness = face.get("liveness")
            if liveness and liveness.get("score", 0) >= 0.5:
                factors.append(
                    RiskFactor(
                        id="liveness_concern",
                        label="Potential presentation-attack indicators",
                        weight=0.25,
                        score=liveness.get("score", 0.5),
                        source="liveness",
                        detail="Not a certified PAD; manual review recommended",
                    )
                )
            dup = face.get("duplicate_identity")
            if dup and dup.get("flagged"):
                factors.append(
                    RiskFactor(
                        id="duplicate_identity",
                        label="Potential duplicate / multiple identity",
                        weight=0.40,
                        score=0.9,
                        source="face",
                        detail=f"{dup.get('matches_found')} matches in identity database",
                    )
                )

        # --- Registry ---
        if registry:
            status = registry.get("status")
            if status in ("reported_stolen", "blacklisted"):
                factors.append(
                    RiskFactor(
                        id="registry_alert",
                        label=f"Registry flag: {status.replace('_', ' ')}",
                        weight=0.50,
                        score=1.0,
                        source="registry",
                    )
                )
            elif status == "expired":
                factors.append(
                    RiskFactor(
                        id="registry_expired",
                        label="Registry reports document expired",
                        weight=0.25,
                        score=0.7,
                        source="registry",
                    )
                )

        # --- Combine ---
        score = self._combine(factors)
        level = self._level(score)
        explanation = self._explain(level, factors)
        recommendations = self._recommendations(factors, level)

        return RiskResult(
            score=round(score, 4),
            level=level,
            factors=[_factor_dict(f) for f in factors],
            explanation=explanation,
            recommendations=recommendations,
        )

    def _combine(self, factors: list[RiskFactor]) -> float:
        """Weighted logit-style combination bounded to [0,1].

        Uses a softmax-of-weights approach: strong factors dominate but the
        combination never saturates instantly. Baseline 0.0 (no signals).
        """
        if not factors:
            return 0.0
        total_weight = sum(f.weight for f in factors)
        # Weighted mean of factor scores, with the baseline lifted slightly
        weighted = sum(f.weight * f.score for f in factors) / total_weight
        # Blend toward the max factor so a single critical factor stands out
        max_score = max(f.score for f in factors)
        blended = 0.7 * weighted + 0.3 * max_score
        return float(min(1.0, blended))

    def _level(self, score: float) -> str:
        if score >= 0.85:
            return "CRITICAL"
        if score >= settings.RISK_HIGH_THRESHOLD:
            return "HIGH"
        if score >= settings.RISK_MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    def _explain(self, level: str, factors: list[RiskFactor]) -> str:
        if not factors:
            return (
                "No significant risk indicators detected. The document passed "
                "automated checks. Officer discretion still applies."
            )
        top = sorted(factors, key=lambda f: f.weight * f.score, reverse=True)[:3]
        parts = [
            f"Risk level: {level}. Principal contributing indicators: "
            + "; ".join(
                f"{f.label.lower()} ({', '.join(filter(None, [f.detail])) or 'high weight'})"
                for f in top
            )
            + "."
        ]
        parts.append(
            "This is an automated decision-support summary, not a determination "
            "of fraud. Manual review is required before any enforcement action."
        )
        return " ".join(parts)

    def _recommendations(self, factors: list[RiskFactor], level: str) -> list[str]:
        recs: list[str] = []
        if level in ("CRITICAL", "HIGH"):
            recs.append("Manual review by a senior officer required before any action.")
        elif level == "MEDIUM":
            recs.append("Manual review recommended before clearing the traveler.")
        else:
            recs.append("Proceed with standard verification; retain officer discretion.")

        if any(f.id == "face_no_match" for f in factors):
            recs.append("Re-capture a fresh live face image and re-verify.")
        if any(f.id == "duplicate_identity" for f in factors):
            recs.append("Investigate possible multiple-identity usage.")
        if any(f.id == "registry_alert" for f in factors):
            recs.append("Cross-check registry status with an authorized secondary source.")
        return recs


def _factor_dict(f: RiskFactor) -> dict[str, Any]:
    return {
        "id": f.id,
        "label": f.label,
        "weight": f.weight,
        "score": f.score,
        "source": f.source,
        "detail": f.detail,
    }


risk_engine = RiskEngine()
