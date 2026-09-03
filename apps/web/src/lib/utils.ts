import type { RiskLevel, CaseStatus } from "./types";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  MEDIUM: "bg-amber-50 text-amber-700 ring-amber-600/20",
  HIGH: "bg-orange-50 text-orange-700 ring-orange-600/20",
  CRITICAL: "bg-red-50 text-red-700 ring-red-600/20",
  UNKNOWN: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export const RISK_BAR: Record<RiskLevel, string> = {
  LOW: "bg-emerald-500",
  MEDIUM: "bg-amber-500",
  HIGH: "bg-orange-500",
  CRITICAL: "bg-red-500",
  UNKNOWN: "bg-slate-400",
};

export const STATUS_STYLES: Record<CaseStatus, string> = {
  in_review: "bg-blue-50 text-blue-700 ring-blue-600/20",
  under_examination: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  cleared: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  flagged: "bg-red-50 text-red-700 ring-red-600/20",
  closed: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export const STATUS_LABELS: Record<CaseStatus, string> = {
  in_review: "In Review",
  under_examination: "Under Examination",
  cleared: "Cleared",
  flagged: "Flagged",
  closed: "Closed",
};

const RISK_ORDER: Record<RiskLevel, number> = {
  LOW: 0,
  UNKNOWN: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4,
};

export function compareRisk(a: RiskLevel | null, b: RiskLevel | null): number {
  return RISK_ORDER[a ?? "UNKNOWN"] - RISK_ORDER[b ?? "UNKNOWN"];
}