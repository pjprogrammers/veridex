"""Static demo responses for the VERIDEX SIH prototype.

Every scenario below returns a deterministic (canned) verification result so
the prototype behaves identically on every run without depending on the heavy
ML pipeline (OCR / MRZ / forensics / face models).

Two families of static responses exist:

* ``aadhaar``  — the synthetic Piyush Verma Aadhaar card (``piyush.jpeg``),
  a genuine CLEAR example.
* passport cases — the sample cases from the SIH pitch:
  Suresh Kumar (CLEAR), Rajesh Sharma (EXPIRED), Amit Singh (MANUAL REVIEW),
  Priya Verma (CLEAR), Neha Gupta (MRZ mismatch), Rohit Mehta (face mismatch),
  Anil Kapoor (tampering detected), Kavita Sharma (registry unknown).

All data is DEMO / SYNTHETIC and must never be mistaken for real identities.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

DISCLAIMER = (
    "This is a decision-support analysis. It does not prove authenticity or "
    "fraud. Manual review by an officer is required before any enforcement "
    "action."
    " DEMO / SYNTHETIC DATA — NOT A REAL DOCUMENT."
)

# SHA-256 of the synthetic Aadhaar image (data/synthetic/piyush.jpeg).
AADHAAR_IMAGE_HASH = "1072d5bb8a09d59b5ec4456297bd505ebc707d4690469941ab270937caffa148"

# ---------------------------------------------------------------------------
# ICAO 9303 TD3 MRZ helpers (prototype check-digit generation)
# ---------------------------------------------------------------------------
_WEIGHTS = (7, 3, 1)


def _check_digit(value: str) -> str:
    total = 0
    for i, ch in enumerate(value):
        if ch == "<":
            v = 0
        elif ch.isdigit():
            v = int(ch)
        elif ch.isalpha():
            v = ord(ch.upper()) - 55
        else:
            v = 0
        total += v * _WEIGHTS[i % 3]
    return str(total % 10)


def _mrz_line1(nationality: str, surname: str, given_names: str) -> str:
    body = f"{surname}<<{given_names}"[:36]
    return f"P<{nationality}{body}"[:44].ljust(44, "<")


def _mrz_line2(
    number: str, dob: str, sex: str, expiry: str, nationality: str = "IND"
) -> str:
    number = number[:9].ljust(9, "<")
    dob_cd = _check_digit(dob)
    exp_cd = _check_digit(expiry)
    optional = "<" * 16
    return (
        f"{number}{_check_digit(number)}{nationality}"
        f"{dob}{dob_cd}{sex}{expiry}{exp_cd}{optional}"
    )


def _mrz_payload(number: str, surname: str, given: str, dob: str, sex: str,
                 expiry: str, dob_mrz: str) -> dict:
    line1 = _mrz_line1("IND", surname, given)
    line2 = _mrz_line2(number, dob_mrz, sex, expiry.replace("-", ""))
    parsed = {
        "passport_number": number,
        "surname": surname,
        "given_names": given,
        "date_of_birth": dob_mrz,
        "sex": sex,
        "nationality": "IND",
        "date_of_expiry": expiry.replace("-", ""),
        "issuing_state": "IND",
    }
    check_digits = {k: True for k in (
        "passport_number", "date_of_birth", "date_of_expiry", "composite")}
    return {
        "mrz_detected": True,
        "mrz_valid": True,
        "check_digits": check_digits,
        "parsed_fields": parsed,
        "raw_mrz": [line1, line2],
        "warnings": [],
    }


def _no_mrz() -> dict:
    return {
        "mrz_detected": False,
        "mrz_valid": False,
        "check_digits": {},
        "parsed_fields": {},
        "raw_mrz": [],
        "warnings": ["No dense MRZ region detected (Aadhaar has no MRZ)."],
    }


# ---------------------------------------------------------------------------
# Forensic helper builders
# ---------------------------------------------------------------------------
def _low_forensics() -> dict:
    return {
        "forensic_status": "insufficient_evidence",
        "tampering_score": None,
        "level": "NONE",
        "explanation": (
            "No manipulation indicators exceeded threshold. ELA residual is "
            "uniform across the surface (σ < 0.02) and the compression profile "
            "is consistent with a single in-camera capture."
        ),
        "weights": {
            "ela": 0.02, "copy_move": 0.03, "metadata": 0.0,
            "template_consistency": 0.04, "splice": 0.0,
        },
        "detectors": [
            _detector("ela", "ELA (error-level analysis)", 0.02, "LOW",
                      "ELA residual is uniform (σ < 0.02); no region deviates "
                      "more than 1.1× the surface baseline."),
            _detector("copy_move", "Copy-move", 0.03, "LOW",
                      "Maximum block self-similarity 0.41 — below the 0.80 "
                      "duplication threshold; no cloned regions."),
            _detector("metadata", "Metadata analysis", 0.0, "LOW",
                      "EXIF is consistent with a single-sensor capture; no "
                      "editor tag, no post-capture timestamp."),
            _detector("template_consistency", "Template consistency", 0.04, "LOW",
                      "Guilloche pattern, MRZ baseline and portrait window all "
                      "match the expected TD3 template within tolerance."),
        ],
    }


def _high_forensics() -> dict:
    return {
        "forensic_status": "sufficient_evidence",
        "tampering_score": 0.81,
        "level": "HIGH",
        "explanation": (
            "Strong copy-move and ELA evidence indicates the portrait region "
            "was replaced and locally re-saved. These are supporting signals "
            "only — the physical document must be examined before any verdict."
        ),
        "weights": {
            "ela": 0.74, "copy_move": 0.88, "metadata": 0.61,
            "template_consistency": 0.55,
        },
        "detectors": [
            _detector("ela", "ELA (error-level analysis)", 0.74, "HIGH",
                      "ELA residual is 4.1× the document baseline across a "
                      "190×120 px block over the surname field — consistent "
                      "with a locally re-saved region.",
                      regions=[{"x": 0.42, "y": 0.18, "w": 0.3, "h": 0.12,
                                "reason": "re-saved region"}]),
            _detector("copy_move", "Copy-move", 0.88, "HIGH",
                      "23 duplicated 32×32 px blocks across the data page "
                      "(max correlation 0.94); portrait background cloned "
                      "into the ghost-image patch.",
                      regions=[{"x": 0.1, "y": 0.24, "w": 0.2, "h": 0.2,
                                "reason": "copy-move block"}]),
            _detector("metadata", "Metadata analysis", 0.61, "MEDIUM",
                      "EXIF editor marker 'Adobe Photoshop 24.7' present; "
                      "DateTime postdates the printed issue date and no "
                      "capture device is recorded."),
            _detector("template_consistency", "Template consistency", 0.55, "MEDIUM",
                      "Guilloche security pattern is interrupted under the "
                      "given-name field; hologram patch missing from the "
                      "top-right quadrant."),
        ],
    }


def _manual_forensics() -> dict:
    return {
        "forensic_status": "insufficient_evidence",
        "tampering_score": None,
        "level": "LOW",
        "explanation": (
            "Weak, non-conclusive manipulation signals were observed around "
            "the portrait. They are below the validated-confidence band, so "
            "physical inspection is recommended before any decision."
        ),
        "weights": {
            "ela": 0.31, "copy_move": 0.24, "metadata": 0.4,
            "template_consistency": 0.35,
        },
        "detectors": [
            _detector("ela", "ELA (error-level analysis)", 0.31, "MEDIUM",
                      "ELA residual is 2.6× the surface baseline across a "
                      "96×96 px block over the portrait — a borderline "
                      "re-save trace."),
            _detector("copy_move", "Copy-move", 0.24, "LOW",
                      "No duplicated 32×32 px blocks above threshold (max "
                      "correlation 0.71)."),
            _detector("metadata", "Metadata analysis", 0.4, "MEDIUM",
                      "EXIF Software tag 'GIMP 2.10' present while DateTime "
                      "and camera Make/Model are missing — inconsistent with "
                      "an in-camera capture."),
            _detector("template_consistency", "Template consistency", 0.35, "LOW",
                      "Portrait-window aspect ratio differs from the TD3 "
                      "template by 4.2%; MRZ baseline sits 3 px low."),
        ],
    }


def _detector(detector_id: str, name: str, score: float, severity: str,
              description: str, regions: Optional[list] = None) -> dict:
    return {
        "detector_id": detector_id,
        "detector_name": name,
        "score": score,
        "severity": severity,
        "description": description,
        "evidence": {"signals": [description]},
        "regions": regions or [],
        "detector_status": "experimental",
    }


# ---------------------------------------------------------------------------
# Face helpers
# ---------------------------------------------------------------------------
def _face_match(similarity: float = 0.84) -> dict:
    return {
        "verification": {"verdict": "match", "similarity": similarity},
        "liveness": {"verdict": "pass", "score": 0.97},
        "duplicate_identity": {"matches_found": 0},
        "portrait_bbox": [0.18, 0.26, 0.24, 0.3],
    }


def _face_mismatch() -> dict:
    return {
        "verification": {"verdict": "mismatch", "similarity": 0.31},
        "liveness": {"verdict": "pass", "score": 0.96},
        "duplicate_identity": {"matches_found": 0},
        "portrait_bbox": [0.18, 0.26, 0.24, 0.3],
    }


def _face_not_performed() -> dict:
    return {
        "verification": {"verdict": "not_performed"},
        "liveness": None,
        "duplicate_identity": {"matches_found": 0},
        "portrait_bbox": None,
    }


# ---------------------------------------------------------------------------
# Scenario catalog
# ---------------------------------------------------------------------------
def _risk(score: float, level: str, factors: list[dict], explanation: str,
          recommendations: Optional[list[str]] = None) -> dict:
    return {
        "score": score,
        "level": level,
        "factors": factors,
        "explanation": explanation,
        "recommendations": recommendations or [],
    }


CLEAR_RECOMMENDATIONS = [
    "Complete the standard checkpoint checks and release the traveler."
]


def _passport_clear_factors(number: str, expiry: str, similarity: float) -> list[dict]:
    """Positive, document-specific reasons for a CLEAR passport decision."""
    return [
        {"label": "MRZ check digits",
         "detail": f"TD3 number, DOB, expiry and composite check digits all "
                   f"pass for {number}"},
        {"label": "Visual / MRZ agreement",
         "detail": "Surname, given names, DOB, sex and expiry match between "
                   "the printed data page and the MRZ"},
        {"label": "Document validity",
         "detail": f"Within validity period (expires {expiry})"},
        {"label": "Image integrity",
         "detail": "ELA residual uniform; no copy-move or editor metadata "
                   "markers above threshold"},
        {"label": "Face verification",
         "detail": f"Portrait-to-live similarity {similarity:.0%} exceeds the "
                   "85% operating threshold"},
        {"label": "Registry / watchlist",
         "detail": "Registry returns VALID and no watchlist match was found"},
    ]

PASSPORT_QUALITY = {"overall_score": 0.93, "brightness_ok": True,
                    "contrast_ok": True, "resolution_ok": True,
                    "sharpness_ok": True}

AADHAAR_QUALITY = {"overall_score": 0.9, "brightness_ok": True,
                   "contrast_ok": True, "resolution_ok": True,
                   "sharpness_ok": True}


def _registry_valid(number: str, holder: str, registry_type: str = "passport") -> dict:
    return {
        "count": 1, "match": "valid", "alert": False,
        "checked": True,
        "entries": [
            {"registry_type": registry_type, "document_number": number,
             "status": "valid", "holder_name": holder},
        ],
    }


def _registry_unknown(number: str) -> dict:
    return {
        "count": 0, "match": "not_found", "alert": True,
        "checked": True,
        "entries": [],
        "message": "Document number not present in the registry.",
    }


def _registry_not_checked() -> dict:
    return {"count": 0, "match": "not_checked", "alert": False,
            "checked": False, "entries": []}


# ---------------------------------------------------------------------------
# The scenario payloads
# ---------------------------------------------------------------------------
def _aadhaar_payload() -> dict:
    extracted = {
        "document_number": "5457 0950 4811",
        "full_name": "पीयूष वर्मा",
        "name_romanized": "PIYUSH VERMA",
        "date_of_birth": "18/12/2007",
        "sex": "MALE / पुरुष",
        "cid/VID": "9103 2996 4131 2258",
        "issue_date": "09/10/2013",
    }
    return {
        "label": "Aadhaar (genuine)",
        "signal": "expect CLEAR · genuine Aadhaar",
        "description": "Synthetic Aadhaar card (piyush.jpeg) — genuine demo example.",
        "doc_file": "piyush.jpeg",
        "live_face_file": None,
        "registry": True,
        "forensics": True,
        "document": {
            "document_type": "aadhaar",
            "quality": AADHAAR_QUALITY,
            "ocr_confidence": 0.89,
            "extracted_fields": extracted,
            "mrz": _no_mrz(),
            "forensics": _low_forensics(),
            "face": _face_match(0.82),
            "field_validation": {
                "document_number": {"verdict": "PASS"},
                "date_of_birth": {"verdict": "PASS", "reason": "age_consistent"},
                "issue_date": {"verdict": "PASS"},
            },
            "cross_validation": {"overall": "PASS", "checked": 5, "passed": 5,
                                 "mismatches": []},
            "registry": _registry_valid("5457 0950 4811", "Piyush Verma", "aadhaar"),
            "risk": _risk(
                0.06, "LOW",
                [
                    {"label": "Aadhaar number checksum",
                     "detail": "5457 0950 4811 passes the Verhoeff (mod-10) "
                               "check digit used by UIDAI"},
                    {"label": "VID format",
                     "detail": "9103 2996 4131 2258 is a well-formed 16-digit "
                               "Aadhaar VID"},
                    {"label": "Demographic consistency",
                     "detail": "पीयूष वर्मा / PIYUSH VERMA, DOB 18/12/2007 and "
                               "gender MALE / पुरुष agree across the data page"},
                    {"label": "Template & layout",
                     "detail": "Government of India header, tricolour motif and "
                               "issue date 09/10/2013 match the Aadhaar card "
                               "template (aadhaar_v1)"},
                    {"label": "Image integrity",
                     "detail": "ELA residual is uniform (σ < 0.02) and no region "
                               "exceeds the surface baseline — single-capture "
                               "compression profile"},
                    {"label": "Registry match",
                     "detail": "Aadhaar record found and returned status VALID "
                               "for the holder"},
                ],
                "Aadhaar data page is internally consistent: the number passes "
                "its Verhoeff checksum, VID/DOB/gender fields cross-validate, "
                "compression is uniform and registry lookup returns VALID.",
                CLEAR_RECOMMENDATIONS,
            ),
            "recommendation": (
                "Genuine document. No significant risk indicators found."
            ),
        },
        "classification": {
            "document_type": "aadhaar", "confidence": 0.97,
            "method": "heuristic", "template_id": "aadhaar_v1", "warnings": [],
        },
        "ocr_extracted_fields": {
            "fields": [
                {"field_name": "document_number", "value": "5457 0950 4811",
                 "confidence": 0.97, "bbox": []},
                {"field_name": "full_name", "value": "पीयूष वर्मा",
                 "confidence": 0.96, "bbox": []},
                {"field_name": "name_romanized", "value": "PIYUSH VERMA",
                 "confidence": 0.92, "bbox": []},
                {"field_name": "date_of_birth", "value": "18/12/2007",
                 "confidence": 0.95, "bbox": []},
                {"field_name": "sex", "value": "MALE / पुरुष",
                 "confidence": 0.9, "bbox": []},
                {"field_name": "cid/VID", "value": "9103 2996 4131 2258",
                 "confidence": 0.93, "bbox": []},
                {"field_name": "issue_date", "value": "09/10/2013",
                 "confidence": 0.94, "bbox": []},
            ],
            "raw_text": (
                "भारत सरकार Government of India आधार "
                "Issue Date: 09/10/2013 पीयूष वर्मा Piyush Verma "
                "जन्म तिथि/DOB: 18/12/2007 पुरुष / MALE 5457 0950 4811 "
                "VID: 9103 2996 4131 2258 मेरा आधार, मेरी पहचान"
            ),
            "processing_time_ms": 812,
        },
    }


def _passport_payload(
    *,
    scenario_key: str,
    label: str,
    signal: str,
    description: str,
    doc_file: str,
    live_face_file: Optional[str],
    number: str,
    surname: str,
    given: str,
    dob: str,
    dob_mrz: str,
    sex: str,
    place_of_birth: str,
    issue: str,
    expiry: str,
    status: str,
    registry: dict,
    forensics: dict,
    face: dict,
    risk: dict,
    mrz_valid: bool = True,
    mrz_override: Optional[dict] = None,
    field_validation: Optional[dict] = None,
    cross_validation: Optional[dict] = None,
    ocr_fields_extra: Optional[list[dict]] = None,
) -> dict:
    ocr_fields = [
        {"field_name": "document_number", "value": number,
         "confidence": 0.98, "bbox": []},
        {"field_name": "full_name", "value": f"{given} {surname}",
         "confidence": 0.96, "bbox": []},
        {"field_name": "surname", "value": surname, "confidence": 0.97, "bbox": []},
        {"field_name": "given_names", "value": given, "confidence": 0.95, "bbox": []},
        {"field_name": "date_of_birth", "value": dob, "confidence": 0.96, "bbox": []},
        {"field_name": "date_of_expiry", "value": expiry, "confidence": 0.94, "bbox": []},
        {"field_name": "date_of_issue", "value": issue, "confidence": 0.93, "bbox": []},
        {"field_name": "nationality", "value": "IND", "confidence": 0.99, "bbox": []},
        {"field_name": "sex", "value": sex, "confidence": 0.98, "bbox": []},
        {"field_name": "place_of_birth", "value": place_of_birth,
         "confidence": 0.9, "bbox": []},
    ]
    if ocr_fields_extra:
        ocr_fields.extend(ocr_fields_extra)

    mrz = _mrz_payload(number, surname, given, dob, sex, expiry, dob_mrz)
    if mrz_override:
        mrz.update(mrz_override)

    extracted = {
        "document_number": number,
        "full_name": f"{given} {surname}",
        "surname": surname,
        "given_names": given,
        "date_of_birth": dob,
        "date_of_expiry": expiry,
        "date_of_issue": issue,
        "nationality": "IND",
        "sex": sex,
        "place_of_birth": place_of_birth,
        "status": status,
    }
    return {
        "label": label,
        "signal": signal,
        "description": description,
        "doc_file": doc_file,
        "live_face_file": live_face_file,
        "registry": True,
        "forensics": True,
        "document": {
            "document_type": "passport",
            "quality": PASSPORT_QUALITY,
            "ocr_confidence": 0.94,
            "extracted_fields": extracted,
            "mrz": mrz,
            "forensics": forensics,
            "face": face,
            "field_validation": field_validation or {
                "document_number": {"verdict": "PASS"},
                "date_of_expiry": {"verdict": "PASS"},
                "date_of_issue": {"verdict": "PASS"},
                "sex": {"verdict": "PASS"},
            },
            "cross_validation": cross_validation or {
                "overall": "PASS", "checked": 5, "passed": 5, "mismatches": [],
            },
            "registry": registry,
            "risk": risk,
            "recommendation": risk["explanation"],
        },
        "classification": {
            "document_type": "passport", "confidence": 0.98,
            "method": "heuristic", "template_id": "passport_td3_v1", "warnings": [],
        },
        "ocr_extracted_fields": {
            "fields": ocr_fields,
            "raw_text": (
                f"P<IND{surname}<<{given} "
                f"{number} IND {dob} {sex} {expiry} {status}"
            ),
            "processing_time_ms": 964,
        },
    }


STATIC_SCENARIOS: dict[str, dict[str, Any]] = {
    "aadhaar": _aadhaar_payload(),
    "suresh": _passport_payload(
        scenario_key="suresh",
        label="Suresh Kumar",
        signal="expect CLEAR · valid passport",
        description="Synthetic passport, valid MRZ, registry-clear.",
        doc_file="genuine_passport.png",
        live_face_file=None,
        number="Z0000001", surname="KUMAR", given="SURESH",
        dob="18/04/1996", dob_mrz="960418", sex="M",
        place_of_birth="SIRSA", issue="2024-06-10", expiry="2034-06-09",
        status="VALID",
        registry=_registry_valid("Z0000001", "Suresh Kumar"),
        forensics=_low_forensics(),
        face=_face_match(0.86),
        risk=_risk(
            0.08, "LOW",
            _passport_clear_factors("Z0000001", "2034-06-09", 0.86),
            "TD3 check digits, visual/MRZ cross-check, portrait and registry "
            "all pass; no manipulation indicator exceeded threshold.",
            CLEAR_RECOMMENDATIONS,
        ),
    ),
    "rajesh": _passport_payload(
        scenario_key="rajesh",
        label="Rajesh Sharma",
        signal="expect EXPIRED · registry alert",
        description="Passport whose status is reported as EXPIRED.",
        doc_file="expired_passport.png",
        live_face_file=None,
        number="Z0000002", surname="SHARMA", given="RAJESH",
        dob="27/11/1992", dob_mrz="921127", sex="M",
        place_of_birth="JAIPUR", issue="2023-02-15", expiry="2033-02-14",
        status="EXPIRED",
        registry=_registry_valid("Z0000002", "Rajesh Sharma", "passport"),
        forensics=_low_forensics(),
        face=_face_match(0.83),
        field_validation={
            "document_number": {"verdict": "PASS"},
            "date_of_expiry": {"verdict": "FAIL", "reason": "document_expired"},
            "date_of_issue": {"verdict": "PASS"},
        },
        risk=_risk(
            0.86, "HIGH",
            [
                {"label": "Registry record closed (EXPIRED)",
                 "detail": "booklet Z0000002 reported surrendered and re-issued; "
                           "record closed 2026-02-14"},
                {"label": "Printed vs registry discrepancy",
                 "detail": "data page reads expiry 2033-02-14 but the underlying "
                           "booklet record is no longer active"},
                {"label": "Operational risk",
                 "detail": "expired/surrendered booklet is not valid for travel "
                           "under ICAO Doc 9303"},
            ],
            "The issuance registry shows this booklet as EXPIRED/surrendered "
            "(record closed on 2026-02-14). Although the printed data page "
            "appears valid, an expired or surrendered booklet is not a valid "
            "travel document under ICAO Doc 9303.",
            ["Refer the traveler to the on-site supervisor.",
             "Hold the document until identity is re-verified."],
        ),
    ),
    "amit": _passport_payload(
        scenario_key="amit",
        label="Amit Singh",
        signal="expect MANUAL REVIEW · tamper signal",
        description="Synthetic passport with altered document area.",
        doc_file="tampered_passport.png",
        live_face_file=None,
        number="Z0000003", surname="SINGH", given="AMIT",
        dob="05/07/1998", dob_mrz="980705", sex="M",
        place_of_birth="DELHI", issue="2025-01-20", expiry="2035-01-19",
        status="MANUAL_REVIEW",
        registry=_registry_valid("Z0000003", "Amit Singh", "passport"),
        forensics=_manual_forensics(),
        face=_face_match(0.71),
        field_validation={
            "document_number": {"verdict": "PASS"},
            "date_of_expiry": {"verdict": "WARN", "reason": "template_consistency"},
            "tamper_detection": {"verdict": "WARN", "reason": "SUSPICIOUS"},
        },
        risk=_risk(
            0.7, "MEDIUM",
            [
                {"label": "ELA anomaly",
                 "detail": "residual 2.6× the surface baseline across a 96×96 px "
                           "block over the portrait (score 0.31)"},
                {"label": "Copy-move region",
                 "detail": "12 duplicated 32×32 px blocks between portrait "
                           "background and stamp area (max correlation 0.71)"},
                {"label": "Metadata inconsistency",
                 "detail": "EXIF Software tag 'GIMP 2.10' while DateTime and "
                           "camera Make/Model are absent"},
                {"label": "Template deviation",
                 "detail": "portrait-window aspect differs from TD3 by 4.2%; "
                           "MRZ baseline sits 3 px low"},
            ],
            "Portrait-region compression and metadata markers deviate from the "
            "capture profile expected for this data page. Escalate for physical "
            "inspection under UV and a lens check on the portrait window.",
            ["Escalate to a supervisor for physical document review.",
             "Cross-check the traveler against the national ID."],
        ),
    ),
    "priya": _passport_payload(
        scenario_key="priya",
        label="Priya Verma",
        signal="expect CLEAR · valid passport",
        description="Synthetic passport, valid MRZ, registry-clear.",
        doc_file="genuine_passport.png",
        live_face_file=None,
        number="Z0000004", surname="VERMA", given="PRIYA",
        dob="22/03/1995", dob_mrz="950322", sex="F",
        place_of_birth="CHANDIGARH", issue="2022-07-11", expiry="2032-07-10",
        status="VALID",
        registry=_registry_valid("Z0000004", "Priya Verma", "passport"),
        forensics=_low_forensics(),
        face=_face_match(0.88),
        risk=_risk(
            0.07, "LOW",
            _passport_clear_factors("Z0000004", "2032-07-10", 0.88),
            "TD3 check digits, visual/MRZ cross-check, portrait and registry "
            "all pass; no manipulation indicator exceeded threshold.",
            CLEAR_RECOMMENDATIONS,
        ),
    ),
    "neha": _passport_payload(
        scenario_key="neha",
        label="Neha Gupta",
        signal="expect MRZ mismatch · review",
        description="Passport with a visual-vs-MRZ mismatch.",
        doc_file="genuine_passport.png",
        live_face_file=None,
        number="Z0000005", surname="GUPTA", given="NEHA",
        dob="14/09/1997", dob_mrz="970914", sex="F",
        place_of_birth="MUMBAI", issue="2023-04-03", expiry="2033-04-02",
        status="MRZ_MISMATCH",
        registry=_registry_valid("Z0000005", "Neha Gupta", "passport"),
        forensics=_low_forensics(),
        face=_face_match(0.79),
        mrz_override={
            "mrz_valid": False,
            "check_digits": {"passport_number": False, "date_of_birth": True,
                             "date_of_expiry": True, "composite": False},
            "parsed_fields": {
                **_mrz_payload("Z0000005", "GUPTA", "NEHA", "14/09/1997",
                               "F", "2033-04-02", "970914")["parsed_fields"],
                "passport_number": "Z00000S",
            },
            "warnings": ["Passport number check digit failed."],
        },
        cross_validation={
            "overall": "FAIL", "checked": 5, "passed": 4,
            "mismatches": [
                {"field_name": "passport_number", "visual": "Z0000005",
                 "mrz": "Z00000S", "verdict": "MISMATCH"},
            ],
            "severity": "HIGH",
        },
        field_validation={
            "document_number": {"verdict": "MISMATCH", "reason": "MRZ_mismatch"},
            "date_of_expiry": {"verdict": "PASS"},
        },
        risk=_risk(
            0.78, "HIGH",
            [
                {"label": "Visual / MRZ number mismatch",
                 "detail": "printed 'Z0000005' vs MRZ 'Z00000S'"},
                {"label": "MRZ check digit failure",
                 "detail": "document-number and composite check digits fail "
                           "(expected 5, read as S)"},
                {"label": "Inconsistency type",
                 "detail": "digit/alpha substitution consistent with a data-page "
                           "relamination or OCR misread"},
            ],
            "Visual OCR reads the passport number as Z0000005 but the MRZ "
            "reads Z00000S. The final symbol is a digit on the printed data "
            "page and an alpha 'S' in the machine-readable zone — consistent "
            "with a data-page relamination, although an OCR misread cannot be "
            "fully excluded.",
            ["Verify the passport under UV light.",
             "Escalate to the supervisor for manual MRZ inspection."],
        ),
    ),
    "rohit": _passport_payload(
        scenario_key="rohit",
        label="Rohit Mehta",
        signal="expect face mismatch",
        description="Document portrait does not match the live face.",
        doc_file="genuine_passport.png",
        live_face_file="live_other.png",
        number="Z0000006", surname="MEHTA", given="ROHIT",
        dob="09/06/1993", dob_mrz="930609", sex="M",
        place_of_birth="AHMEDABAD", issue="2021-11-19", expiry="2031-11-18",
        status="VALID",
        registry=_registry_valid("Z0000006", "Rohit Mehta", "passport"),
        forensics=_low_forensics(),
        face=_face_mismatch(),
        risk=_risk(
            0.64, "MEDIUM",
            [
                {"label": "Portrait does not match provided face",
                 "detail": "similarity 0.31 vs 0.55 operating threshold"},
                {"label": "Geometry mismatch",
                 "detail": "inter-ocular distance and jawline differ markedly "
                           "from the data-page portrait"},
                {"label": "Liveness",
                 "detail": "liveness passed — a live person is present, but not "
                           "the document holder"},
            ],
            "Portrait-to-live similarity is 0.31, far below the 0.55 operating "
            "threshold. Inter-ocular distance and jawline geometry differ "
            "markedly, consistent with a substituted portrait or an "
            "impersonator.",
            ["Interview the traveler and verify biometrics with a supervisor.",
             "Check for additional identity documents."],
        ),
    ),
    "anil": _passport_payload(
        scenario_key="anil",
        label="Anil Kapoor",
        signal="expect tampering detected · high risk",
        description="Passport with strong tampering signals.",
        doc_file="tampered_passport.png",
        live_face_file=None,
        number="Z0000007", surname="KAPOOR", given="ANIL",
        dob="01/12/1990", dob_mrz="901201", sex="M",
        place_of_birth="LUCKNOW", issue="2024-09-16", expiry="2034-09-15",
        status="VALID",
        registry=_registry_valid("Z0000007", "Anil Kapoor", "passport"),
        forensics=_high_forensics(),
        face=_face_match(0.8),
        field_validation={
            "document_number": {"verdict": "PASS"},
            "date_of_expiry": {"verdict": "PASS"},
            "tamper_detection": {"verdict": "WARN",
                                 "reason": "copy_move DETECTED"},
        },
        risk=_risk(
            0.82, "HIGH",
            [
                {"label": "Copy-move detected",
                 "detail": "23 duplicated 32×32 px blocks across the data page "
                           "(max correlation 0.94)"},
                {"label": "ELA anomaly",
                 "detail": "residual 4.1× baseline across a 190×120 px block "
                           "over the surname field (score 0.74)"},
                {"label": "Editor metadata",
                 "detail": "EXIF Software 'Adobe Photoshop 24.7' with no capture "
                           "device recorded"},
                {"label": "Template interruption",
                 "detail": "guilloche pattern interrupted under the given-name "
                           "field; hologram patch missing top-right"},
            ],
            "Strong copy-move and ELA evidence indicates the portrait region "
            "was replaced and locally re-saved. Seize the booklet for "
            "laboratory examination and notify the issuing authority.",
            ["Seize the document for lab analysis.",
             "Report the incident to the officer in charge."],
        ),
    ),
    "kavita": _passport_payload(
        scenario_key="kavita",
        label="Kavita Sharma",
        signal="expect registry unknown · review",
        description="Document number not found in the registry.",
        doc_file="blacklisted_passport.png",
        live_face_file=None,
        number="Z0000008", surname="SHARMA", given="KAVITA",
        dob="17/08/1994", dob_mrz="940817", sex="F",
        place_of_birth="KOLKATA", issue="2022-05-05", expiry="2032-05-04",
        status="NOT_IN_REGISTRY",
        registry=_registry_unknown("Z0000008"),
        forensics=_low_forensics(),
        face=_face_not_performed(),
        risk=_risk(
            0.58, "MEDIUM",
            [
                {"label": "Registry status unknown",
                 "detail": "no issuance record for Z0000008 in the passport "
                           "registry"},
                {"label": "No revocation record",
                 "detail": "number is not listed as active, expired or revoked — "
                           "it does not correspond to an issued booklet"},
                {"label": "Number format",
                 "detail": "Z0000008 is well-formed; failure is at the registry "
                           "lookup, not at the format level"},
            ],
            "Passport number Z0000008 is absent from the issuance registry; no "
            "active, expired or revoked record exists. The number is "
            "well-formed but does not correspond to an issued booklet.",
            ["Query the issuing authority directly.",
             "Hold the document until registry lookup is resolved."],
        ),
    ),
}


def known_scenario(key: Optional[str]) -> Optional[dict]:
    if not key:
        return None
    return STATIC_SCENARIOS.get(str(key))


async def scenario_for_document(db, document) -> Optional[str]:
    """Resolve the static demo scenario for a document.

    Returns ``None`` to run the real pipeline when no demo scenario applies.

    Priority: case metadata (demo flow) > content hash (raw Aadhaar image
    upload).
    """
    if hasattr(document, "case_id") and document.case_id:
        from app.models.models import VerificationCase

        case = await db.get(VerificationCase, document.case_id)
        if case:
            meta = dict(case.case_metadata or {})
            scenario = meta.get("scenario")
            if scenario and known_scenario(scenario):
                return str(scenario)
    content_hash = str(getattr(document, "content_hash", "") or "")
    if content_hash == AADHAAR_IMAGE_HASH:
        return "aadhaar"
    return None


def delivery(scenario: dict, document_id: str | None = None) -> dict:
    """Clone the canned document payload under a fresh id where relevant."""
    payload = {**scenario["document"]}
    if document_id is not None:
        payload["document_id"] = document_id
    payload["demo"] = True
    payload["disclaimer"] = DISCLAIMER
    return payload


def static_verification(scenario: dict, document_id: str) -> dict:
    return delivery(scenario, document_id)


def canonical_result_hash(result: dict) -> str:
    """Deterministic SHA-256 over a verification payload.

    Used to anchor the *actual extracted values and result* of a run into the
    tamper-evident audit chain (the prototype's permissioned-ledger analogue).
    """
    canonical = json.dumps(result, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def static_analysis(scenario: dict, document_id: str) -> dict:
    doc = scenario["document"]
    return {
        "document_id": document_id,
        "document_type": doc["document_type"],
        "type_confidence": scenario["classification"]["confidence"],
        "quality": doc["quality"],
        "dimensions": {"width": 1254, "height": 794},
        "ocr": {"engine": "paddleocr", "confidence": doc["ocr_confidence"]},
        "mrz": doc["mrz"],
        "extracted_fields": doc["extracted_fields"],
        "preprocessing_stages": [
            "orientation_correction", "boundary_detection", "perspective_crop",
            "denoise", "contrast_enhance", "adaptive_sharpen",
        ],
    }


def static_classification(scenario: dict) -> dict:
    return {**scenario["classification"], "demo": True}


def static_mrz(scenario: dict, document_id: str) -> dict:
    doc = scenario["document"]
    fields = {f["field_name"]: f["value"] for f in scenario["ocr_extracted_fields"]["fields"]}
    return {
        "document_id": document_id,
        "document_type": doc["document_type"],
        "mrz": doc["mrz"],
        "visual_fields": {
            "passport_number": fields.get("document_number", ""),
            "full_name": fields.get("full_name", ""),
            "date_of_birth": fields.get("date_of_birth", ""),
            "nationality": fields.get("nationality", ""),
            "date_of_expiry": fields.get("date_of_expiry", ""),
        },
        "comparison": _comparison_payload(scenario),
    }


def _comparison_payload(scenario: dict):
    doc = scenario["document"]
    cross = doc.get("cross_validation") or {}
    if doc["document_type"] != "passport":
        return None
    mismatch_fields = {
        m.get("field_name"): m
        for m in (cross.get("mismatches") or [])
    }
    fields = {f["field_name"]: f["value"] for f in scenario["ocr_extracted_fields"]["fields"]}
    comparisons = []
    for name in ("document_number", "full_name", "date_of_birth", "nationality", "date_of_expiry"):
        m = mismatch_fields.get(name)
        visual = m["visual"] if m else fields.get(name, "")
        mrz = m["mrz"] if m else doc["mrz"]["parsed_fields"].get(
            "passport_number" if name == "document_number" else name, "")
        verdict = "MISMATCH" if m else "MATCH"
        comparisons.append({
            "field_name": name, "visual_value": visual, "mrz_value": mrz,
            "verdict": verdict,
        })
    severity = cross.get("severity")
    if cross.get("overall") == "FAIL":
        return {
            "comparisons": comparisons,
            "severity_score": 0.8,
            "severity": severity or "HIGH",
            "severity_reasons": [
                m.get("field_name", "field") for m in (cross.get("mismatches") or [])
            ],
        }
    return {
        "comparisons": comparisons,
        "severity_score": 0.0,
        "severity": "NONE",
        "severity_reasons": [],
    }


def static_record_payload(scenario: dict) -> dict:
    """Column values to persist on a DocumentRecord for a static scenario."""
    doc = scenario["document"]
    return {
        "document_type": doc["document_type"],
        "quality_score": doc["quality"]["overall_score"],
        "mrz_data": doc["mrz"],
        "extracted_fields": doc["extracted_fields"],
        "classification_data": scenario["classification"],
        "ocr_extracted_fields": scenario["ocr_extracted_fields"],
        "forensic_data": _legacy_forensic_payload(doc["forensics"]),
    }


def _legacy_forensic_payload(forensics: dict) -> dict:
    return {
        "forensic_status": forensics["forensic_status"],
        "tampering_score": forensics["tampering_score"],
        "overall_score": forensics.get("tampering_score"),
        "summary": forensics["explanation"],
        "flags": [
            {"side": d["detector_id"], "signal": d["description"], "score": d["score"],
             "severity": d["severity"]}
            for d in forensics["detectors"]
        ],
    }


def static_forensics(scenario: dict, document_id: str) -> dict:
    forensics = scenario["document"]["forensics"]
    detectors = [
        {k: v for k, v in d.items() if k != "regions"}
        | {"regions": d.get("regions", [])}
        for d in forensics["detectors"]
    ]
    return {
        "document_id": document_id,
        "forensic_status": forensics["forensic_status"],
        "tampering_score": forensics["tampering_score"],
        "level": forensics["level"],
        "explanation": forensics["explanation"],
        "weights": forensics["weights"],
        "components": [
            {"detector_id": d["detector_id"], "score": d["score"], "weight": 0.25}
            for d in forensics["detectors"]
        ],
        "regions": [
            r for d in forensics["detectors"] for r in d.get("regions", [])
        ],
        "detectors": detectors,
        "artifact_keys": {},
    }
