// VERIDEX frontend API types (mirror services/api contracts)

export type CaseStatus =
  | "in_review"
  | "under_examination"
  | "cleared"
  | "flagged"
  | "closed";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";

export interface CaseRecord {
  id: string;
  case_number: string;
  status: CaseStatus;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
  document_hash: string | null;
  case_metadata: Record<string, unknown> | null;
}

export interface CaseListResponse {
  total: number;
  limit: number;
  offset: number;
  cases: CaseRecord[];
}

export interface CaseDocument {
  id: string;
  document_type: string | null;
  content_hash: string;
  mime_type: string | null;
  file_size: number | null;
  quality_score: number | null;
  mrz: Record<string, unknown> | null;
  extracted_fields: Record<string, unknown> | null;
  created_at: string | null;
}

export interface CaseDetail extends CaseRecord {
  documents: CaseDocument[];
}

export interface NewCaseInput {
  case_description?: string;
  verify_face_against?: string;
  check_registry: boolean;
  perform_forensics: boolean;
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuditEntry {
  id: number;
  case_id: string | null;
  action: string;
  actor_id: string | null;
  actor_role: string | null;
  timestamp: string;
  previous_hash: string | null;
  current_hash: string;
  payload: Record<string, unknown>;
}

export interface AuditVerifyResponse {
  case_id: string;
  valid: boolean;
  total_entries: number;
  integrity_issues: { entry_id: number; reason: string }[];
  message: string;
}

export interface RegistryEntry {
  id: string;
  registry_type: string;
  document_number: string;
  status: string;
  holder_name: string | null;
  issuing_country: string | null;
  created_at: string | null;
}

export interface RegistryLookupResponse {
  found: boolean;
  document_number: string;
  message?: string;
  entries?: RegistryEntry[];
}

export interface RegistryListResponse {
  total: number;
  limit: number;
  offset: number;
  entries: RegistryEntry[];
}

export interface RiskAssessment {
  score: number;
  level: RiskLevel;
  factors: Array<{ label?: string; detail?: string; [key: string]: unknown }>;
  explanation: string;
  recommendations?: string[];
}

export interface VerificationResult {
  document_id: string;
  document_type: string | null;
  quality: Record<string, unknown> | null;
  mrz: Record<string, unknown> | null;
  ocr_confidence: number | null;
  forensics: Record<string, unknown> | null;
  face: Record<string, unknown> | null;
  field_validation: Record<string, unknown> | null;
  cross_validation: Record<string, unknown> | null;
  risk: RiskAssessment;
  recommendation: string;
  disclaimer: string;
}

export interface UnknownRecord {
  [key: string]: unknown;
}

export interface HealthStatus {
  status: "ok" | "degraded" | "error";
  version: string;
  services: Record<string, "ok" | "error">;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Officer console / verification pipeline types
// ---------------------------------------------------------------------------

/**
 * Verified document types reported by the backend pipeline.
 */
export type DocumentType =
  | "passport"
  | "national_id"
  | "drivers_license"
  | "residence_permit"
  | "travel_document"
  | "unknown"
  | string;

/**
 * Processing lifecycle of a verification document.
 */
export type ProcessingStage =
  | "UPLOADED"
  | "CLASSIFYING"
  | "PREPROCESSING"
  | "EXTRACTING"
  | "VALIDATING"
  | "FORENSIC_ANALYSIS"
  | "FACE_VERIFICATION"
  | "RISK_ASSESSMENT"
  | "COMPLETED"
  | "FAILED";

export const PROCESSING_LABELS: Record<ProcessingStage, string> = {
  UPLOADED: "Document uploaded",
  CLASSIFYING: "Classifying document",
  PREPROCESSING: "Preprocessing image",
  EXTRACTING: "Extracting fields",
  VALIDATING: "Validating fields",
  FORENSIC_ANALYSIS: "Forensic analysis",
  FACE_VERIFICATION: "Face verification",
  RISK_ASSESSMENT: "Assessing risk",
  COMPLETED: "Complete",
  FAILED: "Failed",
};

/** Decision surfaced to the officer from a verification result. */
export type Verdict =
  | "CLEAR"
  | "MANUAL_REVIEW"
  | "HIGH_RISK_ALERT"
  | "INCONCLUSIVE";

export interface VerificationDecision {
  verdict: Verdict;
  level: RiskLevel;
  score: number;
}

export interface VerificationReport {
  document_id: string;
  document_type: string | null;
  quality: { overall_score?: number } | Record<string, unknown> | null;
  extracted_fields: Record<string, unknown> | null;
  mrz: Record<string, unknown> | null;
  ocr_confidence: number | null;
  field_validation: Record<string, unknown> | null;
  cross_validation: Record<string, unknown> | null;
  forensics: Record<string, unknown> | null;
  face: Record<string, unknown> | null;
  registry: Record<string, unknown> | null;
  risk: {
    score: number;
    level: RiskLevel;
    factors: Array<{ label?: string; detail?: string; [k: string]: unknown }>;
    explanation: string;
    recommendations?: string[];
  };
  recommendation?: string;
  disclaimer?: string;
}

export interface VerificationSummary {
  document_id: string;
  document_type: string | null;
  ocr_confidence: number | null;
  risk: RiskAssessment;
  forensics: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Phase 4 — Document classification types
// ---------------------------------------------------------------------------

export interface ClassificationResult {
  document_type: string;
  confidence: number;
  method: string;
  template_id: string | null;
  warnings: string[];
}

// ---------------------------------------------------------------------------
// Phase 5 — OCR extraction types
// ---------------------------------------------------------------------------

export interface OCRExtractedField {
  field_name: string;
  value: string;
  confidence: number;
  bbox: number[][][];
}

export interface OCRExtractionResult {
  fields: OCRExtractedField[];
  raw_text: string;
  processing_time_ms: number;
  engine: string;
}

// ---------------------------------------------------------------------------
// Phase 6 — MRZ extraction types
// ---------------------------------------------------------------------------

export type MRZCheckDigitState = boolean | null;

export interface MRZExtractionResult {
  mrz_detected: boolean;
  mrz_valid: boolean;
  check_digits: Record<string, MRZCheckDigitState>;
  parsed_fields: Record<string, string>;
  raw_mrz: string[];
  warnings: string[];
}

export interface MRZFieldComparison {
  field_name: string;
  visual_value: string;
  mrz_value: string;
  verdict: "MATCH" | "MISMATCH" | "UNAVAILABLE";
}

export interface MRZComparisonResult {
  comparisons: MRZFieldComparison[];
  severity_score: number;
  severity: "NONE" | "LOW" | "MEDIUM" | "HIGH";
  severity_reasons: string[];
}

export interface MRZExtractionResponse {
  document_id: string;
  document_type: string | null;
  mrz: MRZExtractionResult;
  visual_fields: Record<string, string>;
  comparison: MRZComparisonResult | null;
}

export type ForensicSeverity = "LOW" | "MEDIUM" | "HIGH";
export type ForensicLevel = "NONE" | "LOW" | "MEDIUM" | "HIGH";
export type ForensicStatus = "sufficient_evidence" | "insufficient_evidence";

export interface ForensicDetectorResult {
  detector_id: string;
  detector_name: string;
  score: number;
  severity: ForensicSeverity;
  description: string;
  evidence: Record<string, unknown>;
  regions: Array<Record<string, unknown>>;
  artifacts?: Record<string, unknown>;
  detector_status?: string;
}

export interface ForensicRegion {
  detector_id?: string;
  x: number;
  y: number;
  w: number;
  h: number;
  reason?: string;
}

export interface ForensicResult {
  document_id: string;
  forensic_status: ForensicStatus;
  tampering_score: number | null;
  level: ForensicLevel;
  explanation: string;
  weights: Record<string, number>;
  components: Array<{ detector_id: string; score: number; weight: number }>;
  regions: ForensicRegion[];
  detectors: ForensicDetectorResult[];
  artifact_keys: Record<string, string>;
}
