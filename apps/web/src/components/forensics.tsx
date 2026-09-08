"use client";

import { useState } from "react";
import { Radar, RefreshCw, ShieldAlert, ScanSearch } from "lucide-react";
import { errorFn } from "@/lib/api";
import { runForensics } from "@/lib/verify";
import type { ForensicResult, ForensicSeverity } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Spinner, StatDisplay } from "@/components/ui";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES: Record<ForensicSeverity, string> = {
  LOW: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  MEDIUM: "bg-neutral-400/70 text-neutral-100 ring-neutral-500/40",
  HIGH: "bg-black text-white ring-neutral-800/60",
};

const LEVEL_STYLES: Record<ForensicResult["level"], string> = {
  NONE: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  LOW: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  MEDIUM: "bg-neutral-400/70 text-neutral-100 ring-neutral-500/40",
  HIGH: "bg-black text-white ring-neutral-800/60",
};

const STATUS_STYLES: Record<ForensicResult["forensic_status"], string> = {
  sufficient_evidence: "bg-neutral-400/70 text-neutral-100 ring-neutral-500/40",
  insufficient_evidence: "bg-neutral-100 text-neutral-500 ring-neutral-300",
};

export function ForensicsAnalysis({ documentId }: { documentId: string }) {
  const [result, setResult] = useState<ForensicResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await runForensics(documentId);
      setResult(res);
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setLoading(false);
    }
  }

  const tone = (level: string) => {
    const s = LEVEL_STYLES[level as ForensicResult["level"]] ?? LEVEL_STYLES.NONE;
    return s;
  };

  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <Radar className="h-4 w-4 text-neutral-500" aria-hidden />
          Document Forensics
        </h2>
        {result ? (
          <div className="flex items-center gap-2">
            <Badge className={tone(result.level)}>{result.level}</Badge>
            <Button variant="secondary" size="sm" onClick={run} disabled={loading}>
              {loading ? <Spinner /> : <RefreshCw className="h-4 w-4" aria-hidden />}
              Re-run
            </Button>
          </div>
        ) : null}
      </div>

      <div className="space-y-5 p-5">
        {!result ? (
          loading ? (
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <Spinner /> Analyzing the document for manipulation indicators…
            </div>
          ) : (
            <div>
              {error ? <AlertInline tone="error" title="Request failed">{error}</AlertInline> : null}
              <EmptyState
                title="No forensic analysis yet"
                hint="Run the forensic engine to check the document for potential manipulation indicators (re-saved regions, duplicated areas, metadata editing markers)."
              />
              <div className="flex items-center justify-center pb-1">
                <Button onClick={run} disabled={loading}>
                  {loading ? <Spinner /> : <ScanSearch className="h-4 w-4" aria-hidden />}
                  Run forensic analysis
                </Button>
              </div>
            </div>
          )
        ) : (
          <>
            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex h-14 w-14 items-center justify-center rounded-full",
                    result.tampering_score === null
                      ? "bg-neutral-100 text-neutral-400"
                      : result.tampering_score >= 0.55
                        ? "bg-black/10 text-black"
                        : result.tampering_score >= 0.3
                          ? "bg-neutral-500/20 text-neutral-700"
                          : "bg-neutral-200/70 text-neutral-600",
                  )}
                >
                  <ShieldAlert className="h-6 w-6" aria-hidden />
                </div>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                    Tampering indicator
                  </div>
                  {result.tampering_score === null ? (
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold text-[var(--text)]">
                        Insufficient validated evidence
                      </span>
                      <Badge className={STATUS_STYLES[result.forensic_status]}>
                        {result.forensic_status.replace(/_/g, " ")}
                      </Badge>
                    </div>
                  ) : (
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-semibold text-[var(--text)]">
                        {Math.round(result.tampering_score * 100)}%
                      </span>
                      <Badge className={tone(result.level)}>{result.level}</Badge>
                    </div>
                  )}
                </div>
              </div>
              {result.explanation ? (
                <p className="flex-1 text-sm text-[var(--muted)]">{result.explanation}</p>
              ) : null}
            </div>

            {result.detectors.length > 0 ? (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  Detector signals
                </div>
                <div className="space-y-3">
                  {result.detectors.map((d) => (
                    <div
                      key={d.detector_id}
                      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-[var(--text)]">
                            {d.detector_name}
                          </span>
                          <Badge className={SEVERITY_STYLES[d.severity] ?? SEVERITY_STYLES.LOW}>
                            {d.severity}
                          </Badge>
                        </div>
                        <span className="text-sm font-semibold text-[var(--text)]">
                          {Math.round(d.score * 100)}%
                        </span>
                      </div>
                      <div className="progress-track mt-2 h-2">
                        <div
                          className={cn(
                            "progress-fill",
                            d.score >= 0.55
                              ? "bg-black"
                              : d.score >= 0.3
                                ? "bg-neutral-500"
                                : "bg-neutral-400",
                          )}
                          style={{ width: `${Math.round(d.score * 100)}%` }}
                        />
                      </div>
                      {d.description ? (
                        <p className="mt-2 text-sm text-[var(--muted)]">{d.description}</p>
                      ) : null}
                      {d.regions && d.regions.length > 0 ? (
                        <div className="mt-2">
                          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                            Suspicious regions ({d.regions.length})
                          </div>
                          <ul className="mt-1 space-y-1">
                            {d.regions.map((r, i) => (
                              <li key={i} className="text-xs text-[var(--muted)]">
                                {String(r.reason ?? "region")} — x:{coord(r.x)} y:
                                {coord(r.y)} w:{coord(r.w)} h:{coord(r.h)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {Object.keys(result.weights ?? {}).length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-3">
                {Object.entries(result.weights).map(([k, v]) => (
                  <StatDisplay key={k} label={k.replace(/_/g, " ")} value={pct(v)} />
                ))}
              </div>
            ) : null}
          </>
        )}
      </div>
    </Card>
  );
}

function pct(v: unknown): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n * 100)}%`;
}

function coord(v: unknown): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v ?? "—");
  return n.toFixed(2);
}

function AlertInline({
  tone,
  title,
  children,
}: {
  tone: "error" | "info";
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "mb-4 rounded-lg border p-3 text-sm",
        tone === "error"
          ? "border-neutral-300 bg-neutral-100 text-neutral-800"
          : "border-neutral-300 bg-neutral-100 text-neutral-700",
      )}
    >
      <div className="font-semibold">{title}</div>
      <div>{children}</div>
    </div>
  );
}
