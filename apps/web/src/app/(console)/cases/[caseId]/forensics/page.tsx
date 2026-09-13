"use client";

import { useCallback, useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Radar, ScanSearch } from "lucide-react";
import { api, errorFn } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Skeleton,
  Spinner,
} from "@/components/ui";
import { cn } from "@/lib/utils";

interface ForensicsResult {
  document_id: string;
  forensics: {
    forensic_status: "sufficient_evidence" | "insufficient_evidence";
    tampering_score: number | null;
    overall_score: number | null;
    signals?: Record<string, unknown>;
    flags?: Array<Record<string, unknown>>;
    summary?: string;
    evidence_note?: string;
  };
}

function severityBadgeCls(severity: string): string {
  const s = severity.toUpperCase();
  if (s === "HIGH") return "bg-neutral-200/80 text-black ring-neutral-400/40";
  if (s === "MEDIUM") return "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40";
  return "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40";
}

export default function ForensicsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-10 w-64" />}>
      <ForensicsInner />
    </Suspense>
  );
}

function ForensicsInner() {
  const params = useParams<{ caseId: string }>();
  const caseId = params.caseId;
  const search = useSearchParams();
  const docParam = search.get("doc");

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(docParam);
  const [result, setResult] = useState<ForensicsResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const detail = await api<CaseDetail>(`/cases/${caseId}`);
      setCaseDetail(detail);
      setSelectedDocId((cur) => {
        if (cur && detail.documents.some((d) => d.id === cur)) return cur;
        return detail.documents[0]?.id ?? null;
      });
    } catch (e) {
      setError(errorFn(e));
    }
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  async function runForensics() {
    if (!selectedDocId) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api<ForensicsResult>(
          `/verification/${selectedDocId}/forensics`,
          { method: "POST" },
        ),
      );
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setBusy(false);
    }
  }

  if (error && !caseDetail) {
    return (
      <div className="mx-auto max-w-4xl">
        <Alert title="Could not load case">{error}</Alert>
        <Link
          href={`/cases/${caseId}`}
          className="mt-4 inline-block text-sm text-neutral-500 hover:text-black"
        >
          ← Back to case
        </Link>
      </div>
    );
  }

  if (!caseDetail) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-36 w-full" />
      </div>
    );
  }

  const forensics = result?.forensics;
  const evidenceStatus =
    forensics?.forensic_status === "sufficient_evidence"
      ? "sufficient_evidence"
      : "insufficient_evidence";
  const flags = forensics?.flags ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 animate-fade-in-up">
      <div>
        <Link
          href={`/cases/${caseId}`}
          className="text-xs font-medium text-neutral-500 hover:text-black"
        >
          ← Back to case
        </Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)]">
          Forensic Analysis — {caseDetail.case_number}
        </h1>
        <p className="mt-0.5 text-sm text-[var(--muted)]">
          Tampering heuristics applied to the selected document image.
        </p>
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      <Card>
        <CardHeader
          title="Select document"
          subtitle="Choose which document to run forensic analysis on"
          action={
            <Button onClick={runForensics} disabled={busy || !selectedDocId}>
              {busy ? <Spinner /> : <ScanSearch className="h-4 w-4" aria-hidden />}
              Run forensics
            </Button>
          }
        />
        {caseDetail.documents.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="No documents"
              hint="Upload a document to this case first."
            />
          </div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {caseDetail.documents.map((doc) => {
              const active = doc.id === selectedDocId;
              return (
                <li key={doc.id}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-center justify-between px-5 py-3 text-left transition-colors",
                      active ? "bg-neutral-200/60" : "hover:bg-[#f6f7fb]",
                    )}
                    onClick={() => {
                      setSelectedDocId(doc.id);
                      setResult(null);
                    }}
                  >
                    <span className="text-sm font-medium text-[var(--text)]">
                      {doc.document_type || "Document"}
                    </span>
                    <span className="text-xs text-[var(--muted)]">{doc.mime_type}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {!result && !busy ? (
        <Card>
          <div className="flex flex-col items-center gap-3 p-8 text-center">
            <Radar className="h-8 w-8 text-[var(--muted)]" aria-hidden />
            <p className="text-sm text-[var(--muted)]">
              Select a document and run forensics to see tamper-evidence here.
            </p>
          </div>
        </Card>
      ) : null}

      {busy ? (
        <Card>
          <div className="flex items-center gap-3 p-6 text-sm text-[var(--muted)]">
            <Spinner /> Running forensic heuristics…
          </div>
        </Card>
      ) : null}

      {forensics ? (
        <Card>
          <CardHeader
            title="Forensic evidence"
            action={
              evidenceStatus === "sufficient_evidence" ? (
                <Badge className="bg-neutral-400/30 text-neutral-800 ring-neutral-400/40">
                  VALIDATED SIGNAL
                </Badge>
              ) : (
                <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
                  EXPERIMENTAL ONLY
                </Badge>
              )
            }
          />
          <div className="p-5">
            <div className="flex items-center gap-4">
              {forensics.tampering_score !== null &&
              forensics.tampering_score !== undefined ? (
                <div
                  className={cn(
                    "flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 text-xl font-bold",
                    forensics.tampering_score > 0.55
                      ? "border-neutral-500 text-neutral-800"
                      : forensics.tampering_score > 0.3
                        ? "border-neutral-500 text-neutral-800"
                        : "border-neutral-500 text-neutral-600",
                  )}
                >
                  {Math.round(forensics.tampering_score * 100)}
                </div>
              ) : (
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 border-[var(--border)] text-xl font-bold text-[var(--muted)]">
                  —
                </div>
              )}
              <div className="flex-1">
                <div className="mb-1 flex justify-between text-xs">
                  <span className="font-medium text-[var(--text)]">Tamper score</span>
                  <span className="text-[var(--muted)]">
                    {evidenceStatus === "sufficient_evidence"
                      ? "validated evidence"
                      : "experimental signal only"}
                  </span>
                </div>
                {forensics.tampering_score !== null &&
                forensics.tampering_score !== undefined ? (
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#f6f7fb]">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        forensics.tampering_score > 0.55
                          ? "bg-neutral-700"
                          : forensics.tampering_score > 0.3
                            ? "bg-neutral-500"
                            : "bg-neutral-500",
                      )}
                      style={{
                        width: `${Math.round(forensics.tampering_score * 100)}%`,
                      }}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-[var(--text)]">
                    No validated forensic evidence is currently available. Raw
                    experimental signals below are for research/debugging only
                    and are not a tampering verdict.
                  </p>
                )}
              </div>
            </div>

            {flags.length > 0 ? (
              <div className="mt-5">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  Suspicious regions / signals
                </div>
                <ul className="space-y-2">
                  {flags.map((f, i) => (
                    <li
                      key={i}
                      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 rounded-lg border border-[var(--border)] bg-[#f6f7fb] px-3 py-2 text-sm"
                    >
                      <div className="min-w-0">
                        <div className="break-words font-medium text-[var(--text)]">
                          {String(f.signal ?? "signal")}
                        </div>
                        {f.description ? (
                          <div className="text-xs text-[var(--muted)]">
                            {String(f.description)}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-xs text-[var(--muted)]">
                          {Math.round(Number(f.score ?? 0) * 100)}%
                        </span>
                        <Badge
                          className={severityBadgeCls(String(f.severity ?? "low"))}
                        >
                          {String(f.severity ?? "low")}
                        </Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {forensics.summary ? (
              <div className="mt-4 rounded-lg bg-[#f6f7fb] p-3 text-sm text-[var(--text)]">
                {forensics.summary}
              </div>
            ) : null}

            {forensics.evidence_note ? (
              <div className="mt-4 rounded-lg border border-neutral-400/40 bg-neutral-300/40 p-3 text-sm text-neutral-300">
                {forensics.evidence_note}
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
