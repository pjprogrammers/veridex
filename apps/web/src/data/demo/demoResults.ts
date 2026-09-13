// VERIDEX SIH demonstration — static verification results.
//
// Every value in this module is SYNTHETIC DEMO DATA. Nothing here is produced
// by a real OCR / MRZ / forensics / face / blockchain engine. The three
// passport cases (VX-DEMO-0001..0003) are deterministic canned results used to
// demonstrate the frontend workflow. No network calls are made.

import type { RiskLevel } from "@/lib/types";

/** Demo decision vocabulary surfaced to the officer. */
export type DemoDecision = "CLEAR" | "ALERT" | "MANUAL_REVIEW";

/** Final state of a pipeline stage in the static demo. */
export type StageStatus = "completed" | "warning" | "failed";

export type DemoStageId =
  | "capture"
  | "classification"
  | "preprocessing"
  | "ocr"
  | "validation"
  | "face_detect"
  | "face_verify"
  | "tamper"
  | "registry"
  | "risk"
  | "decision"
  | "case"
  | "hash"
  | "blockchain";

export interface StageResult {
  status: StageStatus;
  summary: string;
  details?: string[];
}

export interface RiskFactorDetail {
  id: string;
  label: string;
  /** Points contributed to the 0–100 risk score. */
  contribution: number;
  /** Human-readable detection result, e.g. "+70", "0", "SUSPICIOUS". */
  result: string;
  explanation: string;
  /** Optional document region that the factor relates to. */
  region?: string;
}

export interface ForensicDetector {
  id: string;
  label: string;
  status: string;
  score?: number;
  detail: string;
}

export interface DemoForensics {
  overall: string;
  explanation: string;
  detectors: ForensicDetector[];
}

export interface DemoFace {
  detection: string;
  liveness: string;
  embedding: string;
  similarity: number;
  threshold: number;
  match: string;
}

export interface DemoDecisionBlock {
  verdict: DemoDecision;
  title: string;
  reasons: string[];
  note?: string;
}

export interface DemoVerificationResult {
  classification: { documentType: string; confidence: number };
  imageQuality: string;
  ocr: { status: string; confidence: number };
  mrzExtraction: { status: string };
  fieldValidation: { status: string; detail?: string };
  mrzCheckDigits: { status: string };
  tamperDetection: { status: string };
  forensics: DemoForensics;
  face: DemoFace;
  registry: { status: string; detail: string };
  expiry: { status: string };
  watchlist: { status: string };
  risk: {
    score: number;
    level: RiskLevel;
    decision: DemoDecision;
    factors: RiskFactorDetail[];
  };
  decision: DemoDecisionBlock;
  stageResults: Record<DemoStageId, StageResult>;
}

export type DemoCaseId = "VX-DEMO-0001" | "VX-DEMO-0002" | "VX-DEMO-0003";

// ---------------------------------------------------------------------------
// Shared stage scaffolding
// ---------------------------------------------------------------------------

const STAGE_DEFAULTS: Record<DemoStageId, StageResult> = {
  capture: {
    status: "completed",
    summary: "Document frame captured and normalized to a flat scan.",
  },
  classification: {
    status: "completed",
    summary: "Document classified as a machine-readable passport.",
  },
  preprocessing: {
    status: "completed",
    summary: "Orientation, crop, denoise and contrast normalization applied.",
  },
  ocr: {
    status: "completed",
    summary: "Visual fields and MRZ lines extracted.",
  },
  validation: {
    status: "completed",
    summary: "Field rules and ICAO 9303 MRZ check digits evaluated.",
  },
  face_detect: {
    status: "completed",
    summary: "Portrait detected; liveness challenge passed.",
  },
  face_verify: {
    status: "completed",
    summary: "Document portrait compared against the live capture.",
  },
  tamper: {
    status: "completed",
    summary: "Forensic detectors fused into a tamper assessment.",
  },
  registry: {
    status: "completed",
    summary: "Issuance registry and watchlist queried.",
  },
  risk: {
    status: "completed",
    summary: "Explainable risk score generated from verified signals.",
  },
  decision: {
    status: "completed",
    summary: "Decision-support recommendation produced.",
  },
  case: {
    status: "completed",
    summary: "Verification case opened and case number assigned.",
  },
  hash: {
    status: "completed",
    summary: "Deterministic audit hash computed locally in the browser.",
  },
  blockchain: {
    status: "completed",
    summary: "Ledger record simulated (no real network connection).",
  },
};

function stages(
  overrides: Partial<Record<DemoStageId, StageResult>> = {},
): Record<DemoStageId, StageResult> {
  return { ...STAGE_DEFAULTS, ...overrides };
}

// ---------------------------------------------------------------------------
// CASE 1 — Suresh Kumar — CLEAR
// ---------------------------------------------------------------------------

const SURESH_RESULT: DemoVerificationResult = {
  classification: { documentType: "PASSPORT", confidence: 99.2 },
  imageQuality: "GOOD",
  ocr: { status: "SUCCESS", confidence: 98.7 },
  mrzExtraction: { status: "SUCCESS" },
  fieldValidation: { status: "PASS" },
  mrzCheckDigits: { status: "PASS" },
  tamperDetection: { status: "PASS" },
  forensics: {
    overall: "PASS",
    explanation:
      "No manipulation indicator exceeded threshold. ELA residual is uniform (σ < 0.02) and the compression profile is consistent with a single in-camera capture.",
    detectors: [
      { id: "ela", label: "ELA Analysis", status: "PASS", score: 0.04, detail: "ELA residual is uniform; no region deviates more than 1.1× the surface baseline." },
      { id: "copy_move", label: "Copy-Move Detection", status: "NOT DETECTED", detail: "Maximum block self-similarity 0.41 — below the 0.80 duplication threshold." },
      { id: "text", label: "Text Consistency", status: "CONSISTENT", detail: "Guilloche line continuity, typeface weight and MRZ baseline match the template." },
      { id: "photo", label: "Photo Integrity", status: "CONSISTENT", detail: "Portrait boundary, quantization tables and ghost image align with the data page." },
      { id: "metadata", label: "Metadata", status: "CONSISTENT", detail: "EXIF consistent with a single-sensor capture; no editor tag or post-capture timestamp." },
      { id: "template", label: "Template Match", status: "PASS", detail: "Layout, hologram position and MRZ geometry match the expected TD3 template." },
    ],
  },
  face: {
    detection: "DETECTED",
    liveness: "PASS",
    embedding: "Generated (demo vector)",
    similarity: 96.8,
    threshold: 85,
    match: "MATCH",
  },
  registry: { status: "VALID", detail: "Document number found and marked valid in the issuance registry." },
  expiry: { status: "VALID" },
  watchlist: { status: "NO MATCH" },
  risk: {
    score: 12,
    level: "LOW",
    decision: "CLEAR",
    factors: [
      {
        id: "validity",
        label: "Document validity",
        contribution: 0,
        result: "0",
        explanation: "Document is within its validity period (expires 2034-06-09).",
        region: "Expiry field",
      },
      {
        id: "mrz",
        label: "MRZ validation",
        contribution: 0,
        result: "0",
        explanation: "MRZ structure is valid and all ICAO 9303 check digits pass.",
        region: "Machine-readable zone",
      },
      {
        id: "tamper",
        label: "Tamper indicators",
        contribution: 0,
        result: "0",
        explanation: "ELA, copy-move and metadata checks are all within the clean-capture band.",
        region: "Full document",
      },
      {
        id: "face",
        label: "Face verification",
        contribution: 0,
        result: "0",
        explanation: "Portrait similarity 96.8% exceeds the 85% operating threshold.",
        region: "Portrait",
      },
      {
        id: "registry",
        label: "Registry / watchlist",
        contribution: 0,
        result: "0",
        explanation: "Registry reports VALID; no watchlist match.",
      },
      {
        id: "consistency",
        label: "Data consistency",
        contribution: 12,
        result: "12",
        explanation:
          "A small baseline weight is retained for residual uncertainty; it is far below the action threshold.",
      },
    ],
  },
  decision: {
    verdict: "CLEAR",
    title: "DOCUMENT CLEARED",
    reasons: [
      "Passport fields are internally consistent.",
      "MRZ structure is valid and all ICAO 9303 check digits pass.",
      "No image manipulation indicators exceeded threshold.",
      "Face similarity exceeds the configured operating threshold.",
      "Document is within its validity period.",
      "No watchlist or registry conflict exists.",
    ],
    note: "No critical verification anomaly detected.",
  },
  stageResults: stages(),
};

// ---------------------------------------------------------------------------
// CASE 2 — Rajesh Sharma — EXPIRED / HIGH-RISK ALERT
// ---------------------------------------------------------------------------

const RAJESH_RESULT: DemoVerificationResult = {
  classification: { documentType: "PASSPORT", confidence: 99.1 },
  imageQuality: "GOOD",
  ocr: { status: "SUCCESS", confidence: 98.4 },
  mrzExtraction: { status: "SUCCESS" },
  fieldValidation: { status: "PASS" },
  mrzCheckDigits: { status: "PASS" },
  tamperDetection: { status: "PASS" },
  forensics: {
    overall: "PASS",
    explanation:
      "No image-manipulation indicators. The data page is a clean capture; the flag is registry-driven, not tamper-driven.",
    detectors: [
      { id: "ela", label: "ELA Analysis", status: "PASS", score: 0.05, detail: "ELA residual is uniform; no re-compression anomaly." },
      { id: "copy_move", label: "Copy-Move Detection", status: "NOT DETECTED", detail: "Maximum block self-similarity 0.44 — no cloned regions." },
      { id: "text", label: "Text Consistency", status: "CONSISTENT", detail: "Guilloche continuity and printed fields match the template." },
      { id: "photo", label: "Photo Integrity", status: "CONSISTENT", detail: "Portrait boundary and inversion region are intact." },
      { id: "metadata", label: "Metadata", status: "CONSISTENT", detail: "EXIF capture profile is uniform; no editor markers." },
      { id: "template", label: "Template Match", status: "PASS", detail: "Layout and MRZ geometry match the expected TD3 template." },
    ],
  },
  face: {
    detection: "DETECTED",
    liveness: "PASS",
    embedding: "Generated (demo vector)",
    similarity: 94.1,
    threshold: 85,
    match: "MATCH",
  },
  registry: {
    status: "EXPIRED",
    detail:
      "Issuance registry shows the booklet as EXPIRED/surrendered (record closed on 2026-02-14) even though the printed data page appears valid.",
  },
  expiry: { status: "EXPIRED" },
  watchlist: { status: "NO MATCH" },
  risk: {
    score: 91,
    level: "CRITICAL",
    decision: "ALERT",
    factors: [
      {
        id: "validity",
        label: "Document validity",
        contribution: 70,
        result: "+70",
        explanation:
          "The issuance registry closed this booklet (EXPIRED/surrendered); an expired booklet is not valid for travel under ICAO Doc 9303.",
        region: "Expiry field",
      },
      {
        id: "registry",
        label: "Registry status",
        contribution: 15,
        result: "+15",
        explanation:
          "The printed data page appears valid, but the registry record for this booklet is closed and no longer authorises travel.",
      },
      {
        id: "mrz",
        label: "MRZ validation",
        contribution: 0,
        result: "0",
        explanation: "MRZ structure and check digits pass.",
      },
      {
        id: "tamper",
        label: "Tamper indicators",
        contribution: 0,
        result: "0",
        explanation: "ELA, copy-move and metadata checks are clean.",
      },
      {
        id: "face",
        label: "Face verification",
        contribution: 0,
        result: "0",
        explanation: "Portrait similarity 94.1% exceeds the 85% operating threshold.",
      },
      {
        id: "watchlist",
        label: "Watchlist",
        contribution: 0,
        result: "0",
        explanation: "No watchlist match.",
      },
      {
        id: "other",
        label: "Other",
        contribution: 6,
        result: "+6",
        explanation: "Operational risk of an expired travel document at a border checkpoint.",
      },
    ],
  },
  decision: {
    verdict: "ALERT",
    title: "ALERT — EXPIRED DOCUMENT",
    reasons: [
      "Registry reports expired.",
      "Travel document validity requirement failed.",
      "Secondary inspection required.",
    ],
    note: "Invalid / expired document — not necessarily physically forged.",
  },
  stageResults: stages({
    registry: {
      status: "warning",
      summary: "Registry record closed (EXPIRED/surrendered) — printed data page still appears valid.",
      details: ["Registry status: EXPIRED (closed 2026-02-14)", "Booklet reported surrendered and re-issued"],
    },
    decision: {
      status: "warning",
      summary: "High-risk alert raised: expired travel document.",
      details: ["Decision-support only — requires secondary inspection."],
    },
  }),
};

// ---------------------------------------------------------------------------
// CASE 3 — Amit Singh — TAMPERED / SUSPICIOUS → MANUAL REVIEW
// ---------------------------------------------------------------------------

const AMIT_RESULT: DemoVerificationResult = {
  classification: { documentType: "PASSPORT", confidence: 98.9 },
  imageQuality: "GOOD",
  ocr: { status: "SUCCESS", confidence: 97.1 },
  mrzExtraction: { status: "SUCCESS" },
  fieldValidation: { status: "WARNING", detail: "Guilloche continuity and portrait-window aspect deviate from the TD3 template." },
  mrzCheckDigits: { status: "PASS" },
  tamperDetection: { status: "SUSPICIOUS" },
  forensics: {
    overall: "SUSPICIOUS",
    explanation:
      "Multiple independent forensic indicators were detected. The document should be manually inspected before accepting the identity.",
    detectors: [
      { id: "ela", label: "ELA Analysis", status: "SUSPICIOUS", score: 0.82, detail: "ELA residual is 2.6× the surface baseline across a 96×96 px block over the portrait — a borderline re-save trace." },
      { id: "copy_move", label: "Copy-Move Detection", status: "DETECTED", detail: "12 duplicated 32×32 px blocks detected between the portrait background and the stamp area (translation offset 2 px, 214 px)." },
      { id: "text", label: "Text Consistency", status: "WARNING", detail: "Guilloche line pattern is interrupted beneath the given-name field; MICR weight differs ~8% from the template." },
      { id: "photo", label: "Photo Integrity", status: "SUSPICIOUS", detail: "Portrait boundary shows a 2 px halo and JPEG quantization tables that differ from the surrounding guilloche print." },
      { id: "metadata", label: "Metadata", status: "INCONSISTENT", detail: "EXIF Software tag 'GIMP 2.10' present while DateTime and camera Make/Model are missing — inconsistent with an in-camera capture." },
      { id: "template", label: "Template Match", status: "WARNING", detail: "Portrait-window aspect ratio differs from the TD3 template by 4.2%; MRZ baseline sits 3 px low." },
    ],
  },
  face: {
    detection: "DETECTED",
    liveness: "PASS",
    embedding: "Generated (demo vector)",
    similarity: 91.7,
    threshold: 85,
    match: "MATCH",
  },
  registry: { status: "VALID", detail: "Document number found and marked valid in the issuance registry." },
  expiry: { status: "VALID" },
  watchlist: { status: "NO MATCH" },
  risk: {
    score: 78,
    level: "HIGH",
    decision: "MANUAL_REVIEW",
    factors: [
      {
        id: "ela",
        label: "ELA anomaly",
        contribution: 18,
        result: "+18",
        explanation:
          "ELA residual is 2.6× the surface baseline across a 96×96 px block over the portrait (score 0.82) — consistent with a locally re-saved region.",
        region: "Photograph region",
      },
      {
        id: "copy_move",
        label: "Copy-move detection",
        contribution: 22,
        result: "+22",
        explanation:
          "12 duplicated 32×32 px blocks match between the portrait background and the stamp area (max correlation 0.87).",
        region: "Neighbouring stamp area",
      },
      {
        id: "photo",
        label: "Photo inconsistency",
        contribution: 18,
        result: "+18",
        explanation:
          "Portrait boundary shows a 2 px halo and JPEG quantization tables that differ from the surrounding guilloche print — consistent with portrait replacement/splicing.",
        region: "Photograph region",
      },
      {
        id: "metadata",
        label: "Metadata inconsistency",
        contribution: 10,
        result: "+10",
        explanation:
          "EXIF Software tag 'GIMP 2.10' is present while DateTime and camera Make/Model are missing — inconsistent with an in-camera capture.",
      },
      {
        id: "template",
        label: "Template mismatch",
        contribution: 10,
        result: "+10",
        explanation:
          "Portrait-window aspect ratio differs from the TD3 template by 4.2% and the MRZ baseline sits 3 px low.",
        region: "Full document",
      },
      {
        id: "mrz",
        label: "MRZ validation",
        contribution: 0,
        result: "0",
        explanation: "MRZ structure and check digits pass.",
        region: "Machine-readable zone",
      },
      {
        id: "face",
        label: "Face verification",
        contribution: 0,
        result: "0",
        explanation: "Portrait similarity 91.7% exceeds the 85% operating threshold.",
        region: "Portrait",
      },
    ],
  },
  decision: {
    verdict: "MANUAL_REVIEW",
    title: "MANUAL REVIEW REQUIRED",
    reasons: [
      "Copy-move anomaly",
      "ELA anomaly",
      "Photo-region inconsistency",
      "Metadata inconsistency",
      "Template mismatch",
      "Multiple forensic signals — several independent indicators contribute to the elevated risk score",
    ],
    note: "Suspicious / requires manual inspection — not absolute proof of forgery.",
  },
  stageResults: stages({
    validation: {
      status: "warning",
      summary: "Field validation completed with warnings.",
      details: ["Template consistency: WARNING"],
    },
    tamper: {
      status: "warning",
      summary: "Multiple forensic signals detected — manual inspection required.",
      details: [
        "ELA: SUSPICIOUS (2.6× baseline, score 0.82)",
        "Copy-move: DETECTED (12 blocks, corr 0.87)",
        "Text region: guilloche interrupted, MICR weight −8%",
        "Photo region: 2 px halo + quantization mismatch",
        "Metadata: EXIF Software=GIMP 2.10, no capture device",
        "Template: portrait aspect −4.2%, MRZ baseline −3 px",
      ],
    },
    decision: {
      status: "warning",
      summary: "Manual review recommended due to multiple forensic indicators.",
      details: ["Suspicious / requires manual inspection."],
    },
  }),
};

export const DEMO_RESULTS: Record<DemoCaseId, DemoVerificationResult> = {
  "VX-DEMO-0001": SURESH_RESULT,
  "VX-DEMO-0002": RAJESH_RESULT,
  "VX-DEMO-0003": AMIT_RESULT,
};

export function getDemoResult(caseId: string): DemoVerificationResult | null {
  return (DEMO_RESULTS as Record<string, DemoVerificationResult>)[caseId] ?? null;
}
