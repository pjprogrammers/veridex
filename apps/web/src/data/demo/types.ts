/**
 * Shared types for the fully-static VERIDEX SIH demonstration.
 *
 * Everything here is synthetic demo data — nothing is produced by real
 * OCR / face / forensic / ledger engines. The UI must never present these
 * results as genuine government identity verification.
 */

export type DemoStageState =
  | "pending"
  | "processing"
  | "completed"
  | "warning"
  | "failed";

export type DemoStageKey =
  | "upload"
  | "classification"
  | "preprocess"
  | "ocr"
  | "validation"
  | "face_detect"
  | "face_verify"
  | "tamper_fusion"
  | "registry"
  | "risk_engine"
  | "decision"
  | "case_management"
  | "audit_hash"
  | "blockchain";

export type DemoArchGroup =
  | "input"
  | "ai_processing"
  | "verification"
  | "decision"
  | "audit";

export interface DemoStage {
  key: DemoStageKey;
  label: string;
  group: DemoArchGroup;
  /** Optional one-line static result shown when the stage completes. */
  detail?: string;
}

export interface DemoRiskFactor {
  label: string;
  /** Risk points this factor contributes (0 = none). */
  contribution: number;
  /** Short verdict, e.g. "VALID", "EXPIRED", "DETECTED". */
  detection: string;
  /** Human explanation shown when the factor is clicked. */
  explanation: string;
  /** Affected document region, if any (used for highlighting). */
  region?: string;
}

export interface DemoForensicSignal {
  label: string;
  status: "PASS" | "WARNING" | "SUSPICIOUS" | "DETECTED" | "INCONSISTENT";
  score?: number;
  detail?: string;
}

export interface DemoFaceResult {
  detection: string;
  liveness: string;
  embedding: string;
  similarity: number;
  threshold: number;
  result: "MATCH" | "NO_MATCH" | "INCONCLUSIVE";
  note: string;
}

export interface DemoLedgerRecord {
  network: string;
  status: string;
  txId: string;
  blockNumber: string;
  channel: string;
}

export interface DemoAuditEntry {
  time: string;
  label: string;
}

export interface DemoDocumentDetails {
  documentType: string;
  passportNumber: string;
  name: string;
  nationality: string;
  dob: string;
  age: number;
  sex: string;
  placeOfBirth: string;
  issueDate: string;
  expiryDate: string;
  registryStatus: string;
  watchlistStatus: string;
  mrzLines: [string, string];
}

export interface DemoCheck {
  label: string;
  value: string;
  tone?: "pass" | "warn" | "fail" | "neutral";
}

export interface DemoDecision {
  verdict: "CLEAR" | "ALERT" | "MANUAL_REVIEW";
  headline: string;
  tone: "clear" | "alert" | "review";
  summary: string;
  reasons: string[];
  note: string;
}

export interface DemoCaseManagement {
  caseId: string;
  document: string;
  subject: string;
  riskScore: number;
  decision: DemoDecision["verdict"];
  createdAt: string;
  officer: string;
  verificationStatus: string;
}

/**
 * Complete deterministic verification object for one synthetic case.
 */
export interface DemoCase {
  id: string;
  key: string;
  title: string;
  subtitle: string;
  expectedOutcome: string;
  document: DemoDocumentDetails;
  classification: DemoCheck;
  imageQuality: DemoCheck;
  ocr: DemoCheck;
  mrzExtraction: DemoCheck;
  fieldValidation: DemoCheck;
  mrzCheckDigits: DemoCheck;
  tamperDetection: DemoCheck;
  checks: DemoCheck[];
  registry: DemoCheck;
  expiry: DemoCheck;
  watchlist: DemoCheck;
  reasons: string[];
  risk: {
    score: number;
    level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
    decision: string;
    factors: DemoRiskFactor[];
    explanation: string;
  };
  forensics: {
    overall: "PASS" | "SUSPICIOUS";
    tamperAssessment: string;
    explanation: string;
    signals: DemoForensicSignal[];
  };
  face: DemoFaceResult;
  decision: DemoDecision;
  caseManagement: DemoCaseManagement;
  audit: DemoAuditEntry[];
  auditHash: {
    label: string;
    value: string;
  };
  ledger: DemoLedgerRecord;
  /** Per-stage final state overrides (default = completed). */
  stageStateOverrides: Partial<Record<DemoStageKey, DemoStageState>>;
  /** Per-stage result detail overrides (defaults to stage.detail). */
  stageDetailOverrides?: Partial<Record<DemoStageKey, string>>;
}