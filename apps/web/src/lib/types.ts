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
  factors: string[];
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