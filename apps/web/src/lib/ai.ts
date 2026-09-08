"use client";

import { api } from "./api";

// ---------------------------------------------------------------------------
// AI / CV showcase layer — types mirror ai/ocr/schemas.py + ai/face/schemas.py
// ---------------------------------------------------------------------------

export interface AIStackStatus {
  name: string;
  available: boolean;
  version?: string;
  reason?: string;
  components?: Record<string, string>;
  models?: Record<
    string,
    { path: string; present: boolean }
  >;
}

export interface TextBlock {
  text: string;
  confidence: number;
  bbox: number[][];
  low_confidence: boolean;
}

export interface FieldValue {
  value: string;
  confidence: number;
  bbox: number[][] | null;
  low_confidence: boolean;
}

export interface CheckDigits {
  document_number: boolean | null;
  date_of_birth: boolean | null;
  expiry_date: boolean | null;
  composite: boolean | null;
  personal_number: boolean | null;
}

export interface MRZResult {
  detected: boolean;
  format: string;
  valid: boolean;
  lines: string[];
  check_digits: CheckDigits;
  parsed_fields: Record<string, string>;
  warnings: string[];
}

export interface ConsistencyEntry {
  visual: string | null;
  mrz: string | null;
  match: boolean | null;
}

export interface OCREngineResult {
  document_id: string;
  engine: string;
  engine_version: string;
  image_width: number;
  image_height: number;
  fields: Record<string, FieldValue>;
  text_blocks: TextBlock[];
  mrz: MRZResult | null;
  consistency: Record<string, ConsistencyEntry>;
  overall_confidence: number;
  latency_ms: Record<string, number>;
  error: string | null;
  error_detail: string | null;
}

export type FaceVerdict =
  | "MATCH"
  | "NO_MATCH"
  | "INCONCLUSIVE"
  | "NO_FACE"
  | "MULTIPLE_FACES"
  | "LOW_QUALITY";

export interface FaceVerificationResult {
  face_detected_document: boolean;
  face_detected_live: boolean;
  document_face_count: number;
  live_face_count: number;
  document_face_quality: number | null;
  live_face_quality: number | null;
  similarity: number | null;
  threshold: number;
  result: FaceVerdict;
  latency_ms: Record<string, number>;
  error: string | null;
  error_detail: string | null;
}

export const OCR_DOCUMENT_TYPES = [
  "generic",
  "passport",
  "visa",
  "aadhaar",
  "pan",
  "driving_licence",
  "identity_card",
] as const;

export function getAiStatus() {
  return api<AIStackStatus>("/ai/status", { method: "GET" });
}

export function runAiOcr(file: File, documentType: string) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("document_type", documentType);
  return api<OCREngineResult>("/ai/ocr/upload", {
    method: "POST",
    formData: fd,
  });
}

export function runAiFaceVerify(
  documentImage: File,
  liveImage: File,
  threshold?: number,
) {
  const fd = new FormData();
  fd.append("document_image", documentImage);
  fd.append("live_image", liveImage);
  if (threshold != null) fd.append("threshold", String(threshold));
  return api<FaceVerificationResult>("/ai/face/verify", {
    method: "POST",
    formData: fd,
  });
}

export function formatMs(ms?: number): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

export function pct(value?: number): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}