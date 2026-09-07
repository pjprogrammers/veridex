"use client";

import { useState } from "react";
import { Radar, RefreshCw, ShieldAlert, ScanSearch } from "lucide-react";
import { errorFn } from "@/lib/api";
import { runForensics } from "@/lib/verify";
import type { ForensicResult, ForensicSeverity } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Spinner, StatDisplay } from "@/components/ui";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES: Record<ForensicSeverity, string> = {
  LOW: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  MEDIUM: "bg-amber-50 text-amber-700 ring-amber-600/20",
  HIGH: "bg-red-50 text-red-700 ring-red-600/20",
};

const LEVEL_STYLES: Record<ForensicResult["level"], string> = {
  NONE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  LOW: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  MEDIUM: "bg-amber-50 text-amber-700 ring-amber-600/20",
  HIGH: "bg-red-50 text-red-700 ring-red-600/20",
};

const STATUS_STYLES: Record<ForensicResult["forensic_status"], string> = {
  sufficient_evidence: "bg-amber-50 text-amber-700 ring-amber-600/20",
  insufficient_evidence: "bg-slate-100 text-slate-600 ring-slate-500/20",
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
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Radar className="h-4 w-4 text-indigo-500" aria-hidden />
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
            <div className="flex items-center gap-2 text-sm text-slate-500">
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
            <div className="flex items-center gap-4 rounded-xl border border-slate-100 p-4">
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex h-14 w-14 items-center justify-center rounded-full",
                    result.tampering_score === null
                      ? "bg-slate-100 text-slate-500"
                      : result.tampering_score >= 0.55
                        ? "bg-red-100 text-red-600"
                        : result.tampering_score >= 0.3
                          ? "bg-amber-100 text-amber-600"
                          : "bg-emerald-100 text-emerald-600",
                  )}
                >
                  <ShieldAlert className="h-6 w-6" aria-hidden />
                </div>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Tampering indicator
                  </div>
                  {result.tampering_score === null ? (
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold text-slate-700">
                        Insufficient validated evidence
                      </span>
                      <Badge className={STATUS_STYLES[result.forensic_status]}>
                        {result.forensic_status.replace(/_/g, " ")}
                      </Badge>
                    </div>
                  ) : (
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-semibold text-slate-900">
                        {Math.round(result.tampering_score * 100)}%
                      </span>
                      <Badge className={tone(result.level)}>{result.level}</Badge>
                    </div>
                  )}
                </div>
              </div>
              {result.explanation ? (
                <p className="flex-1 text-sm text-slate-600">{result.explanation}</p>
              ) : null}
            </div>

            {result.detectors.length > 0 ? (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Detector signals
                </div>
                <div className="space-y-3">
                  {result.detectors.map((d) => (
                    <div
                      key={d.detector_id}
                      className="rounded-xl border border-slate-100 p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-slate-800">
                            {d.detector_name}
                          </span>
                          <Badge className={SEVERITY_STYLES[d.severity] ?? SEVERITY_STYLES.LOW}>
                            {d.severity}
                          </Badge>
                        </div>
                        <span className="text-sm font-semibold text-slate-700">
                          {Math.round(d.score * 100)}%
                        </span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            d.score >= 0.55
                              ? "bg-red-500"
                              : d.score >= 0.3
                                ? "bg-amber-500"
                                : "bg-emerald-500",
                          )}
                          style={{ width: `${Math.round(d.score * 100)}%` }}
                        />
                      </div>
                      {d.description ? (
                        <p className="mt-2 text-sm text-slate-600">{d.description}</p>
                      ) : null}
                      {d.regions && d.regions.length > 0 ? (
                        <div className="mt-2">
                          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                            Suspicious regions ({d.regions.length})
                          </div>
                          <ul className="mt-1 space-y-1">
                            {d.regions.map((r, i) => (
                              <li key={i} className="text-xs text-slate-500">
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
          ? "border-red-200 bg-red-50 text-red-700"
          : "border-blue-200 bg-blue-50 text-blue-800",
      )}
    >
      <div className="font-semibold">{title}</div>
      <div>{children}</div>
    </div>
  );
}
