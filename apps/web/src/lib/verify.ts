"use client";

import { api } from "./api";
import type {
  CaseDetail,
  ClassificationResult,
  ForensicResult,
  MRZExtractionResponse,
  OCRExtractionResult,
  ProcessingStage,
  VerificationReport,
  DocumentType,
} from "./types";

/**
 * Upload a document to an existing case (legacy endpoint).
 * Returns the document record as reported by the backend.
 */
export async function uploadDocument(caseId: string, file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return api<{
    document_id: string;
    case_id: string;
    document_type: string;
    storage_key: string;
    content_hash: string;
    quality_score: number;
    message: string;
  }>(`/cases/${caseId}/documents`, { method: "POST", formData: fd });
}

/** Standalone document upload (Phase 3 ingestion). Accepts optional caseId. */
export async function uploadDocumentStandalone(
  file: File,
  caseId?: string | null,
) {
  const fd = new FormData();
  fd.append("file", file);
  const qs = caseId ? `?case_id=${encodeURIComponent(caseId)}` : "";
  return api<DocumentUploadResult>(`/documents/upload${qs}`, {
    method: "POST",
    formData: fd,
  });
}

/** Preprocess a document image (Phase 3). Returns the document with preprocessing metadata. */
export async function preprocessDocument(documentId: string) {
  return api<DocumentUploadResult>(`/documents/${documentId}/preprocess`, {
    method: "POST",
  });
}

/** Fetch document metadata (Phase 3). */
export async function getDocument(documentId: string) {
  return api<DocumentUploadResult>(`/documents/${documentId}`, { method: "GET" });
}

/** Classify a document image (Phase 4). Returns the document with classification data. */
export async function classifyDocument(documentId: string) {
  return api<DocumentUploadResult>(`/documents/${documentId}/classify`, {
    method: "POST",
  });
}

/** Run OCR extraction on a stored document (Phase 5). */
export async function extractOCR(documentId: string) {
  return api<OCRExtractionResult>(`/ocr/v1/extract`, {
    method: "POST",
    json: { document_id: documentId },
  });
}

/** Run MRZ extraction + visual-vs-MRZ comparison on a stored document (Phase 6). */
export async function extractMRZ(documentId: string) {
  return api<MRZExtractionResponse>(`/documents/${documentId}/mrz`, {
    method: "POST",
  });
}

/** Run the modular forensic engine over a stored document (Phase 8). */
export async function runForensics(documentId: string) {
  return api<ForensicResult>(`/documents/${documentId}/forensics`, {
    method: "POST",
  });
}

/** Document upload result from the Phase 3 ingestion endpoint. */
export interface DocumentUploadResult {
  id: string;
  case_id: string | null;
  status: string;
  original_filename: string | null;
  mime_type: string | null;
  file_size: number | null;
  content_hash: string;
  quality_score: number | null;
  document_type: string | null;
  preprocess: Record<string, unknown>;
  classification: ClassificationResult | null;
  ocr_extracted_fields: {
    fields?: OCRExtractionResult["fields"];
    raw_text?: string;
    processing_time_ms?: number;
  } | null;
  original_key: string | null;
  processed_key: string | null;
  preview_key: string | null;
  processing_error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Run the document analysis pipeline (classify, preprocess, extract, validate). */
export async function analyzeDocument(caseId: string, documentId: string) {
  return api<{
    success: boolean;
    analysis: Record<string, unknown> & {
      document_type?: DocumentType;
      ocr?: { confidence?: number };
      quality?: { overall_score?: number };
      extracted_fields?: Record<string, unknown>;
      mrz?: Record<string, unknown>;
    };
  }>(`/cases/${caseId}/documents/${documentId}/analyze`, { method: "POST" });
}

/** Run the full verification pipeline against a document. */
export async function runFullVerification(
  documentId: string,
  options: { liveFace?: File | null; checkRegistry?: boolean } = {},
) {
  const fd = new FormData();
  if (options.liveFace) fd.append("live_face", options.liveFace);
  fd.append("check_registry", String(options.checkRegistry ?? true));
  return api<{ success: boolean; verification: VerificationReport }>(
    `/verification/${documentId}/full?check_registry=${options.checkRegistry ?? true}`,
    { method: "POST", formData: fd },
  );
}

/** Fetch a previously stored verification report without re-running the pipeline. */
export async function getVerificationReport(documentId: string): Promise<
  | { verified: false; document_id: string }
  | { verified: true; document_id: string; verification: VerificationReport }
> {
  return api(
    `/verification/${documentId}/report`,
    { method: "GET" },
  );
}

export interface FreshDocument {
  id: string;
  document_id: string;
  document_type: string;
  content_hash: string;
  mime_type: string | null;
  file_size: number | null;
  quality_score: number | null;
  created_at: string | null;
}

export async function getCaseQuick(caseId: string): Promise<CaseDetail> {
  return api<CaseDetail>(`/cases/${caseId}`);
}

/**
 * The ordered processing stages for the verify flow. The CLI-driven
 * progression walks through each stage before completing.
 */
export const VERIFY_STAGES: ProcessingStage[] = [
  "UPLOADED",
  "CLASSIFYING",
  "PREPROCESSING",
  "EXTRACTING",
  "VALIDATING",
  "FORENSIC_ANALYSIS",
  "FACE_VERIFICATION",
  "RISK_ASSESSMENT",
  "COMPLETED",
];

/** Convenience: derive a document type label. */
export function documentTypeLabel(type: DocumentType | null | undefined): string {
  if (!type || type === "unknown") return "Unknown document";
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
