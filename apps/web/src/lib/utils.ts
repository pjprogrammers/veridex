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
  LOW: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  MEDIUM: "bg-neutral-400/70 text-neutral-100 ring-neutral-500/40",
  HIGH: "bg-neutral-700/80 text-white ring-neutral-800/40",
  CRITICAL: "bg-black text-white ring-neutral-800/60",
  UNKNOWN: "bg-neutral-100 text-neutral-500 ring-neutral-300",
};

export const RISK_BAR: Record<RiskLevel, string> = {
  LOW: "bg-neutral-400",
  MEDIUM: "bg-neutral-500",
  HIGH: "bg-neutral-700",
  CRITICAL: "bg-black",
  UNKNOWN: "bg-neutral-300",
};

export const STATUS_STYLES: Record<CaseStatus, string> = {
  in_review: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  under_examination: "bg-neutral-400/70 text-neutral-100 ring-neutral-500/40",
  cleared: "bg-neutral-100 text-neutral-600 ring-neutral-300",
  flagged: "bg-black text-white ring-neutral-800/60",
  closed: "bg-neutral-100 text-neutral-400 ring-neutral-300",
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
