import type {
  DemoCase as LegacyDemoCase,
  DemoDocumentDetails,
} from "./types";
import {
  getDemoResult,
  type DemoDecision,
  type DemoStageId,
  type DemoVerificationResult,
} from "./demoResults";
import { getDemoAudit, type DemoAudit } from "./demoAudit";

/**
 * The synthetic Indian passport demonstration cases plus the genuine Aadhaar
 * demo. All of this is deterministic synthetic data — not real passports, not
 * real people, and not produced by real engines.
 */

const PASSPORT_CASES: LegacyDemoCase[] = [
  {
    id: "VX-DEMO-0001",
    key: "suresh",
    title: "Suresh Kumar",
    subtitle: "Indian Passport · Z0000001",
    expectedOutcome: "expect CLEAR · genuine",
    document: {
      documentType: "Passport",
      passportNumber: "Z0000001",
      name: "Suresh Kumar",
      nationality: "IND",
      dob: "1996-04-18",
      age: 30,
      sex: "M",
      placeOfBirth: "Sirsa",
      issueDate: "2024-06-10",
      expiryDate: "2034-06-09",
      registryStatus: "VALID",
      watchlistStatus: "NO MATCH",
      mrzLines: [
        "P<INDKUMAR<<SURESH<<<<<<<<<<<<<<<<<<<<",
        "Z0000001<IND9604185M3406097<<<<<<<<<<<<",
      ],
    },
    classification: { label: "Document Classification", value: "PASSPORT · 99.2%", tone: "pass" },
    imageQuality: { label: "Image Quality", value: "GOOD", tone: "pass" },
    ocr: { label: "OCR", value: "SUCCESS · 98.7%", tone: "pass" },
    mrzExtraction: { label: "MRZ Extraction", value: "SUCCESS", tone: "pass" },
    fieldValidation: { label: "Field Validation", value: "PASS", tone: "pass" },
    mrzCheckDigits: { label: "MRZ Check Digits", value: "PASS", tone: "pass" },
    tamperDetection: { label: "Tamper Detection", value: "PASS", tone: "pass" },
    checks: [
      { label: "ELA", value: "No suspicious region", tone: "pass" },
      { label: "Copy-Move", value: "Not detected", tone: "pass" },
      { label: "Text Region", value: "Consistent", tone: "pass" },
      { label: "Photo Region", value: "Consistent", tone: "pass" },
      { label: "Metadata", value: "Consistent", tone: "pass" },
      { label: "Template Consistency", value: "PASS", tone: "pass" },
    ],
    registry: { label: "Registry Check", value: "VALID", tone: "pass" },
    expiry: { label: "Expiry Check", value: "VALID", tone: "pass" },
    watchlist: { label: "Watchlist", value: "NO MATCH", tone: "pass" },
    reasons: [
      "Passport fields are internally consistent.",
      "MRZ structure is valid and all ICAO 9303 check digits pass.",
      "No image manipulation indicator exceeded threshold.",
      "Face similarity exceeds the configured operating threshold.",
      "Document is within its validity period.",
      "No watchlist or registry conflict exists.",
    ],
    risk: {
      score: 12,
      level: "LOW",
      decision: "CLEAR",
      factors: [
        {
          label: "Document validity",
          contribution: 0,
          detection: "VALID",
          explanation: "Issue/expiry dates are internally consistent and within the valid period.",
        },
        {
          label: "MRZ validation",
          contribution: 0,
          detection: "PASS",
          explanation: "MRZ structure and ICAO check digits validate cleanly.",
        },
        {
          label: "Tamper indicators",
          contribution: 0,
          detection: "NONE",
          explanation: "ELA residual, copy-move correlation and EXIF checks are all within the clean-capture band.",
        },
        {
          label: "Face verification",
          contribution: 0,
          detection: "MATCH",
          explanation: "Face similarity exceeds the configured operating threshold.",
        },
        {
          label: "Registry / watchlist",
          contribution: 0,
          detection: "CLEAR",
          explanation: "Registry reports VALID and no watchlist match was found.",
        },
        {
          label: "Data consistency",
          contribution: 12,
          detection: "MINOR",
          explanation:
            "A small baseline consistency weight is applied; it is far below the action threshold.",
        },
      ],
      explanation:
        "Overall risk is LOW. All primary signals are clean; the small data-consistency weight is within normal variance.",
    },
    forensics: {
      overall: "PASS",
      tamperAssessment: "PASS",
      explanation:
        "No manipulation indicator exceeded threshold. ELA residual is uniform (σ < 0.02) and the compression profile is consistent with a single in-camera capture.",
      signals: [
        { label: "ELA Analysis", status: "PASS" },
        { label: "Copy-Move Detection", status: "PASS" },
        { label: "Text Consistency", status: "PASS" },
        { label: "Photo Integrity", status: "PASS" },
        { label: "Metadata", status: "PASS" },
        { label: "Template Match", status: "PASS" },
      ],
    },
    face: {
      detection: "DETECTED",
      liveness: "PASS",
      embedding: "demo-embed-v1 · generated",
      similarity: 96.8,
      threshold: 85,
      result: "MATCH",
      note: "Face matching is evidence only — it is not the reason this document is considered genuine.",
    },
    decision: {
      verdict: "CLEAR",
      headline: "DOCUMENT CLEARED",
      tone: "clear",
      summary: "No critical verification anomaly detected.",
      reasons: [
        "Passport fields are internally consistent.",
        "MRZ structure is valid and check digits pass.",
        "No image manipulation indicator exceeded threshold.",
        "Face similarity exceeds the configured operating threshold.",
        "Document is within its validity period.",
        "No watchlist or registry conflict exists.",
      ],
      note: "Decision-support only — final determination requires authorized officer review.",
    },
    caseManagement: {
      caseId: "VX-DEMO-0001",
      document: "Indian Passport",
      subject: "Suresh Kumar",
      riskScore: 12,
      decision: "CLEAR",
      createdAt: "2026-09-13T15:42:00.000Z",
      officer: "Demo Officer · SIHP",
      verificationStatus: "CLEARED",
    },
    audit: [
      { time: "15:42:01", label: "Document uploaded" },
      { time: "15:42:02", label: "Document classified" },
      { time: "15:42:03", label: "OCR completed" },
      { time: "15:42:04", label: "MRZ validated" },
      { time: "15:42:05", label: "Face verification completed" },
      { time: "15:42:06", label: "Forensic analysis completed" },
      { time: "15:42:07", label: "Registry check completed" },
      { time: "15:42:08", label: "Risk score calculated" },
      { time: "15:42:09", label: "Decision generated" },
      { time: "15:42:10", label: "Audit hash generated" },
      { time: "15:42:11", label: "Blockchain record simulated" },
    ],
    auditHash: {
      label: "Audit Hash — DEMO",
      value: "d4e7f1a9c3b25f6a8e1d9c4b7f2a3e5d8c6b1a4f7e9d2c5b8a3f6e1d9c4b7a2f5e8",
    },
    ledger: {
      network: "Hyperledger Fabric — DEMO",
      status: "RECORD SIMULATED",
      txId: "TX-VXDEMO0001-3f8a2d91c4b6e705",
      blockNumber: "Block #000721",
      channel: "veridex-demo-channel",
    },
    stageStateOverrides: {},
  },

  {
    id: "VX-DEMO-0002",
    key: "rajesh",
    title: "Rajesh Sharma",
    subtitle: "Indian Passport · Z0000002",
    expectedOutcome: "expect ALERT · expired",
    document: {
      documentType: "Passport",
      passportNumber: "Z0000002",
      name: "Rajesh Sharma",
      nationality: "IND",
      dob: "1992-11-27",
      age: 33,
      sex: "M",
      placeOfBirth: "Jaipur",
      issueDate: "2023-02-15",
      expiryDate: "2033-02-14",
      registryStatus: "EXPIRED",
      watchlistStatus: "NO MATCH",
      mrzLines: [
        "P<INDSHARMA<<RAJESH<<<<<<<<<<<<<<<<<<<<",
        "Z0000002<IND9211273M3302148<<<<<<<<<<<<",
      ],
    },
    classification: { label: "Document Classification", value: "PASSPORT · 99.1%", tone: "pass" },
    imageQuality: { label: "Image Quality", value: "GOOD", tone: "pass" },
    ocr: { label: "OCR", value: "SUCCESS · 98.4%", tone: "pass" },
    mrzExtraction: { label: "MRZ Extraction", value: "SUCCESS", tone: "pass" },
    fieldValidation: { label: "Field Validation", value: "PASS", tone: "pass" },
    mrzCheckDigits: { label: "MRZ Check Digits", value: "PASS", tone: "pass" },
    tamperDetection: { label: "Tamper Detection", value: "PASS", tone: "pass" },
    checks: [],
    registry: { label: "Registry Check", value: "EXPIRED", tone: "fail" },
    expiry: { label: "Expiry Check", value: "EXPIRED", tone: "fail" },
    watchlist: { label: "Watchlist", value: "NO MATCH", tone: "pass" },
    reasons: [
      "REGISTRY RECORD CLOSED (EXPIRED)",
      "The issuance registry closed this booklet (EXPIRED/surrendered) on 2026-02-14.",
      "PRINTED DATA PAGE APPEARS VALID",
      "The data page reads an expiry of 2033-02-14, but the underlying booklet record is no longer active.",
      "HIGH OPERATIONAL RISK",
      "An expired or surrendered booklet is not valid for travel and requires secondary inspection.",
    ],
    risk: {
      score: 91,
      level: "CRITICAL",
      decision: "HIGH-RISK ALERT",
      factors: [
        {
          label: "Document validity",
          contribution: 70,
          detection: "EXPIRED",
          explanation:
            "The issuance registry closed this booklet (EXPIRED/surrendered); an expired booklet is not valid for travel under ICAO Doc 9303.",
          region: "expiry date",
        },
        {
          label: "Registry status",
          contribution: 15,
          detection: "CONFLICT",
          explanation:
            "The printed data page appears valid, but the registry record for this booklet is closed and no longer authorises travel.",
          region: "registry record",
        },
        {
          label: "MRZ validation",
          contribution: 0,
          detection: "PASS",
          explanation: "MRZ structure and check digits validate cleanly.",
        },
        {
          label: "Tamper indicators",
          contribution: 0,
          detection: "NONE",
          explanation: "ELA, copy-move and metadata checks are clean.",
        },
        {
          label: "Face verification",
          contribution: 0,
          detection: "MATCH",
          explanation: "Face similarity exceeds the 85% operating threshold.",
        },
        {
          label: "Watchlist",
          contribution: 0,
          detection: "CLEAR",
          explanation: "No watchlist match was found.",
        },
        {
          label: "Other",
          contribution: 6,
          detection: "OPERATIONAL",
          explanation:
            "Secondary-inspection burden and operational handling add a small residual weight.",
        },
      ],
      explanation:
        "The primary issue is document expiry. This is an invalid / expired document — not necessarily physically forged.",
    },
    forensics: {
      overall: "PASS",
      tamperAssessment: "PASS",
      explanation:
        "No image-manipulation indicators. The data page is a clean capture; the flag is registry-driven, not tamper-driven.",
      signals: [
        { label: "ELA Analysis", status: "PASS" },
        { label: "Copy-Move Detection", status: "PASS" },
        { label: "Text Consistency", status: "PASS" },
        { label: "Photo Integrity", status: "PASS" },
        { label: "Metadata", status: "PASS" },
        { label: "Template Match", status: "PASS" },
      ],
    },
    face: {
      detection: "DETECTED",
      liveness: "PASS",
      embedding: "demo-embed-v1 · generated",
      similarity: 94.1,
      threshold: 85,
      result: "MATCH",
      note: "The face matches — this is NOT the reason the document is flagged. The alert is due to expiry.",
    },
    decision: {
      verdict: "ALERT",
      headline: "ALERT — EXPIRED DOCUMENT",
      tone: "alert",
      summary:
        "The issuance registry record for this booklet is closed (EXPIRED/surrendered).",
      reasons: [
        "Registry record closed (EXPIRED/surrendered)",
        "Booklet reported surrendered and re-issued",
        "Secondary inspection required",
      ],
      note: "Decision-support only — final determination requires authorized officer review. An expired document is invalid, not necessarily forged.",
    },
    caseManagement: {
      caseId: "VX-DEMO-0002",
      document: "Indian Passport",
      subject: "Rajesh Sharma",
      riskScore: 91,
      decision: "ALERT",
      createdAt: "2026-09-13T15:42:00.000Z",
      officer: "Demo Officer · SIHP",
      verificationStatus: "HIGH-RISK ALERT",
    },
    audit: [
      { time: "15:42:01", label: "Document uploaded" },
      { time: "15:42:02", label: "Document classified" },
      { time: "15:42:03", label: "OCR completed" },
      { time: "15:42:04", label: "MRZ validated" },
      { time: "15:42:05", label: "Face verification completed" },
      { time: "15:42:06", label: "Forensic analysis completed" },
      { time: "15:42:07", label: "Registry check completed" },
      { time: "15:42:08", label: "Risk score calculated" },
      { time: "15:42:09", label: "Decision generated" },
      { time: "15:42:10", label: "Audit hash generated" },
      { time: "15:42:11", label: "Blockchain record simulated" },
    ],
    auditHash: {
      label: "Audit Hash — DEMO",
      value: "9c1e4a7f2d6b8e3a5c7d9f1b4e6a8c2d5f7b1e3a9c4d6f8b2a5e7c1d3f9b4e6a8c2",
    },
    ledger: {
      network: "Hyperledger Fabric — DEMO",
      status: "RECORD SIMULATED",
      txId: "TX-VXDEMO0002-7c2b5e91a4f8d306",
      blockNumber: "Block #000722",
      channel: "veridex-demo-channel",
    },
    stageStateOverrides: {
      registry: "warning",
      risk_engine: "warning",
      decision: "warning",
    },
    stageDetailOverrides: {
      registry: "Registry → EXPIRED · no watchlist match",
      risk_engine: "Risk score 91/100 · CRITICAL",
      decision: "ALERT — EXPIRED DOCUMENT",
    },
  },

  {
    id: "VX-DEMO-0003",
    key: "amit",
    title: "Amit Singh",
    subtitle: "Indian Passport · Z0000003",
    expectedOutcome: "expect MANUAL REVIEW · suspicious",
    document: {
      documentType: "Passport",
      passportNumber: "Z0000003",
      name: "Amit Singh",
      nationality: "IND",
      dob: "1998-07-05",
      age: 28,
      sex: "M",
      placeOfBirth: "Delhi",
      issueDate: "2025-01-20",
      expiryDate: "2035-01-19",
      registryStatus: "VALID",
      watchlistStatus: "NO MATCH",
      mrzLines: [
        "P<INDSINGH<<AMIT<<<<<<<<<<<<<<<<<<<<<<<",
        "Z0000003<IND9807057M3501196<<<<<<<<<<<<",
      ],
    },
    classification: { label: "Document Classification", value: "PASSPORT · 98.9%", tone: "pass" },
    imageQuality: { label: "Image Quality", value: "GOOD", tone: "pass" },
    ocr: { label: "OCR", value: "SUCCESS · 97.1%", tone: "pass" },
    mrzExtraction: { label: "MRZ Extraction", value: "SUCCESS", tone: "pass" },
    fieldValidation: { label: "Field Validation", value: "WARNING", tone: "warn" },
    mrzCheckDigits: { label: "MRZ Check Digits", value: "PASS", tone: "pass" },
    tamperDetection: { label: "Tamper Detection", value: "SUSPICIOUS", tone: "fail" },
    checks: [
      { label: "ELA", value: "SUSPICIOUS · 0.82", tone: "fail" },
      { label: "Copy-Move Detection", value: "DETECTED", tone: "fail" },
      { label: "Text Region Analysis", value: "INCONSISTENT", tone: "warn" },
      { label: "Photo Region Analysis", value: "POTENTIAL REPLACEMENT", tone: "fail" },
      { label: "Metadata", value: "INCONSISTENT", tone: "warn" },
      { label: "Template Consistency", value: "WARNING", tone: "warn" },
    ],
    registry: { label: "Registry Check", value: "VALID", tone: "pass" },
    expiry: { label: "Expiry Check", value: "VALID", tone: "pass" },
    watchlist: { label: "Watchlist", value: "NO MATCH", tone: "pass" },
    reasons: [
      "COPY-MOVE REGION DETECTED",
      "12 duplicated 32×32 px blocks match between the portrait background and the stamp area (max correlation 0.87).",
      "ELA ANOMALY",
      "ELA residual is 2.6× the surface baseline across a 96×96 px block over the portrait — a borderline re-save trace.",
      "PHOTO REGION INCONSISTENCY",
      "Portrait boundary shows a 2 px halo and JPEG quantization tables that differ from the surrounding guilloche print.",
      "METADATA INCONSISTENCY",
      "EXIF Software tag 'GIMP 2.10' present while DateTime and camera Make/Model are missing.",
      "TEMPLATE CONSISTENCY WARNING",
      "Portrait-window aspect ratio differs from the TD3 template by 4.2%; MRZ baseline sits 3 px low.",
      "MULTIPLE FORENSIC SIGNALS",
      "Several independent indicators align on the portrait region and contribute to the elevated risk score.",
    ],
    risk: {
      score: 78,
      level: "HIGH",
      decision: "MANUAL REVIEW",
      factors: [
        {
          label: "ELA anomaly",
          contribution: 18,
          detection: "SUSPICIOUS",
          explanation:
            "ELA residual is 2.6× the surface baseline across a 96×96 px block over the portrait — consistent with a locally re-saved region.",
          region: "photograph region",
        },
        {
          label: "Copy-move detection",
          contribution: 22,
          detection: "DETECTED",
          explanation:
            "12 duplicated 32×32 px blocks match between the portrait background and the stamp area (max correlation 0.87).",
          region: "duplicated region",
        },
        {
          label: "Photo inconsistency",
          contribution: 18,
          detection: "POTENTIAL REPLACEMENT",
          explanation:
            "Portrait boundary shows a 2 px halo and JPEG quantization tables that differ from the surrounding guilloche print.",
          region: "photograph region",
        },
        {
          label: "Metadata inconsistency",
          contribution: 10,
          detection: "INCONSISTENT",
          explanation:
            "EXIF Software tag 'GIMP 2.10' is present while DateTime and camera Make/Model are missing.",
        },
        {
          label: "Template mismatch",
          contribution: 10,
          detection: "WARNING",
          explanation:
            "Portrait-window aspect ratio differs from the TD3 template by 4.2% and the MRZ baseline sits 3 px low.",
        },
        {
          label: "MRZ validation",
          contribution: 0,
          detection: "PASS",
          explanation: "MRZ structure and check digits validate cleanly.",
        },
        {
          label: "Face verification",
          contribution: 0,
          detection: "MATCH",
          explanation: "Face similarity exceeds the 85% operating threshold.",
        },
      ],
      explanation:
        "Multiple independent forensic signals are present. This is suspicious and requires manual inspection — not proof of forgery.",
    },
    forensics: {
      overall: "SUSPICIOUS",
      tamperAssessment: "SUSPICIOUS",
      explanation:
        "Portrait-region compression, copy-move and metadata markers indicate a locally edited data page. Physical inspection under UV is required before accepting the identity.",
      signals: [
        { label: "ELA Analysis", status: "SUSPICIOUS", score: 0.82 },
        { label: "Copy-Move Detection", status: "DETECTED" },
        { label: "Text Consistency", status: "WARNING" },
        { label: "Photo Integrity", status: "SUSPICIOUS" },
        { label: "Metadata", status: "INCONSISTENT" },
        { label: "Template Match", status: "WARNING" },
      ],
    },
    face: {
      detection: "DETECTED",
      liveness: "PASS",
      embedding: "demo-embed-v1 · generated",
      similarity: 91.7,
      threshold: 85,
      result: "MATCH",
      note: "The face matches — face matching is NOT the reason this document is flagged. The suspicion comes from forensic signals.",
    },
    decision: {
      verdict: "MANUAL_REVIEW",
      headline: "MANUAL REVIEW REQUIRED",
      tone: "review",
      summary: "Suspicious / requires manual inspection.",
      reasons: [
        "Copy-move: 12 blocks over portrait/stamp (corr 0.87)",
        "ELA: 2.6× baseline at portrait",
        "Photo region: 2 px halo + quantization mismatch",
        "Metadata: EXIF Software=GIMP 2.10, no capture device",
        "Template: portrait aspect −4.2%, MRZ baseline −3 px",
      ],
      note: "Decision-support only — final determination requires authorized officer review. These are indicators, not proof of forgery.",
    },
    caseManagement: {
      caseId: "VX-DEMO-0003",
      document: "Indian Passport",
      subject: "Amit Singh",
      riskScore: 78,
      decision: "MANUAL_REVIEW",
      createdAt: "2026-09-13T15:42:00.000Z",
      officer: "Demo Officer · SIHP",
      verificationStatus: "MANUAL REVIEW",
    },
    audit: [
      { time: "15:42:01", label: "Document uploaded" },
      { time: "15:42:02", label: "Document classified" },
      { time: "15:42:03", label: "OCR completed" },
      { time: "15:42:04", label: "MRZ validated" },
      { time: "15:42:05", label: "Face verification completed" },
      { time: "15:42:06", label: "Forensic analysis completed" },
      { time: "15:42:07", label: "Registry check completed" },
      { time: "15:42:08", label: "Risk score calculated" },
      { time: "15:42:09", label: "Decision generated" },
      { time: "15:42:10", label: "Audit hash generated" },
      { time: "15:42:11", label: "Blockchain record simulated" },
    ],
    auditHash: {
      label: "Audit Hash — DEMO",
      value: "5b8e3d1a7f2c4e6b8a1d5f9c3e7a2b4d6f8c1e3a5b7d9f2c4e6a8b1d3f5c7e9a2b4d",
    },
    ledger: {
      network: "Hyperledger Fabric — DEMO",
      status: "RECORD SIMULATED",
      txId: "TX-VXDEMO0003-6a1d4c8e2b7f9a35",
      blockNumber: "Block #000723",
      channel: "veridex-demo-channel",
    },
    stageStateOverrides: {
      tamper_fusion: "warning",
      risk_engine: "warning",
      decision: "warning",
    },
    stageDetailOverrides: {
      tamper_fusion: "Tamper fusion → SUSPICIOUS (multiple signals)",
      risk_engine: "Risk score 78/100 · HIGH",
      decision: "MANUAL REVIEW REQUIRED",
    },
  },
];

// ---------------------------------------------------------------------------
// Unified demo model consumed by the /demo workflow components
// ---------------------------------------------------------------------------

export interface DemoIdentityDocument {
  documentType: string;
  passportNumber: string;
  name: string;
  nationality: string;
  dateOfBirth: string;
  age: number;
  sex: string;
  placeOfBirth: string;
  issueDate: string;
  expiryDate: string;
  registryStatus: string;
  watchlistStatus: string;
  mrzLines: string[];
}

export interface DemoCaseInfo {
  caseId: string;
  document: string;
  subject: string;
  riskScore: number;
  decision: DemoDecision;
  createdAt: string;
  officer: string;
  verificationStatus: string;
}

export interface DemoCase {
  id: string;
  key: string;
  name: string;
  signal: string;
  document: DemoIdentityDocument;
  documentFile: string;
  mrz: string[];
  caseInfo: DemoCaseInfo;
  result: DemoVerificationResult;
  audit: DemoAudit;
}

const DOC_FILES: Record<string, string> = {
  suresh: "genuine_passport.png",
  priya: "genuine_passport.png",
  neha: "genuine_passport.png",
  rohit: "genuine_passport.png",
  rajesh: "expired_passport.png",
  amit: "tampered_passport.png",
  anil: "tampered_passport.png",
  kavita: "blacklisted_passport.png",
};

function toIdentityDocument(d: DemoDocumentDetails): DemoIdentityDocument {
  return {
    documentType: d.documentType,
    passportNumber: d.passportNumber,
    name: d.name,
    nationality: d.nationality,
    dateOfBirth: d.dob,
    age: d.age,
    sex: d.sex,
    placeOfBirth: d.placeOfBirth,
    issueDate: d.issueDate,
    expiryDate: d.expiryDate,
    registryStatus: d.registryStatus,
    watchlistStatus: d.watchlistStatus,
    mrzLines: d.mrzLines,
  };
}

/** Passport demo cases joined with their static result and audit record. */
export const DEMO_CASES: DemoCase[] = PASSPORT_CASES.map((c) => {
  const result = getDemoResult(c.id);
  const audit = getDemoAudit(c.id);
  if (!result || !audit) {
    throw new Error(`Demo case ${c.id} is missing result or audit data`);
  }
  return {
    id: c.id,
    key: c.key,
    name: c.title,
    signal: c.expectedOutcome,
    document: toIdentityDocument(c.document),
    documentFile: DOC_FILES[c.key] ?? "genuine_passport.png",
    mrz: c.document.mrzLines,
    caseInfo: {
      caseId: c.caseManagement.caseId,
      document: c.caseManagement.document,
      subject: c.caseManagement.subject,
      riskScore: c.caseManagement.riskScore,
      decision: c.caseManagement.decision,
      createdAt: c.caseManagement.createdAt,
      officer: c.caseManagement.officer,
      verificationStatus: c.caseManagement.verificationStatus,
    },
    result,
    audit,
  };
});

/**
 * The genuine Aadhaar demo. Unlike the passport cases this runs through the
 * live verification page (backend static scenario `aadhaar`).
 */
export const AADHAAR_DEMO = {
  label: "Piyush · Aadhaar",
  name: "Piyush Verma",
  document: "Aadhaar · 5457 0950 4811",
  note: "Genuine Aadhaar — number passes Verhoeff checksum; VID, DOB and gender consistent.",
  href: "/verify",
  riskScore: 6,
  expectedDecision: "CLEAR" as DemoDecision,
};

export function getDemoStats() {
  const clear =
    DEMO_CASES.filter((c) => c.result.decision.verdict === "CLEAR").length + 1;
  const manualReview = DEMO_CASES.filter(
    (c) => c.result.decision.verdict === "MANUAL_REVIEW",
  ).length;
  const alert = DEMO_CASES.filter(
    (c) => c.result.decision.verdict === "ALERT",
  ).length;
  return {
    total: DEMO_CASES.length + 1,
    clear,
    manualReview,
    alert,
    aadhaar: 1,
  };
}

export function getDemoCase(id: string): DemoCase | undefined {
  return DEMO_CASES.find((c) => c.id === id);
}

export function getDemoCaseById(id: string): DemoCase | undefined {
  return getDemoCase(id);
}

export function getDemoCaseByKey(key: string): DemoCase | undefined {
  return DEMO_CASES.find((c) => c.key === key);
}

// ---------------------------------------------------------------------------
// Static pipeline stage definitions (frontend-only demonstration)
// ---------------------------------------------------------------------------

export type DemoPhase = "input" | "ai" | "verification" | "decision" | "audit";

export interface DemoStageDefinition {
  id: DemoStageId;
  title: string;
  phase: DemoPhase;
}

export const PHASE_LABELS: Record<DemoPhase, string> = {
  input: "INPUT · CAPTURE",
  ai: "AI PROCESSING",
  verification: "VERIFICATION",
  decision: "DECISION",
  audit: "AUDIT & LEDGER",
};

export const DEMO_STAGES: DemoStageDefinition[] = [
  { id: "capture", title: "Document Upload & Capture", phase: "input" },
  { id: "classification", title: "Document Classification", phase: "ai" },
  { id: "preprocessing", title: "Image Preprocessing", phase: "ai" },
  { id: "ocr", title: "OCR + MRZ Extraction", phase: "ai" },
  { id: "validation", title: "Field & MRZ Validation", phase: "ai" },
  { id: "face_detect", title: "Face Detection + Liveness", phase: "ai" },
  { id: "face_verify", title: "Face Verification", phase: "ai" },
  { id: "tamper", title: "Tamper Fusion Engine", phase: "verification" },
  { id: "registry", title: "Registry & Watchlist", phase: "verification" },
  { id: "risk", title: "Explainable Risk Engine", phase: "verification" },
  { id: "decision", title: "Decision", phase: "decision" },
  { id: "case", title: "Case Management", phase: "audit" },
  { id: "hash", title: "SHA-256 Audit Hash", phase: "audit" },
  { id: "blockchain", title: "Permissioned Blockchain", phase: "audit" },
];

export type { DemoDecision, DemoStageId, DemoVerificationResult };