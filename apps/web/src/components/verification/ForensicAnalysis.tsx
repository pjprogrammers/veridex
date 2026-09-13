"use client";

import { Radar, ShieldAlert } from "lucide-react";
import type { DemoForensics } from "@/data/demo/demoResults";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/utils";

function tone(status: string): string {
  const s = status.toUpperCase();
  if (
    s === "PASS" ||
    s === "NOT DETECTED" ||
    s === "CONSISTENT" ||
    s === "NO MATCH"
  ) {
    return "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40";
  }
  if (s === "WARNING" || s === "INCONSISTENT") {
    return "bg-neutral-400/40 text-neutral-900 ring-neutral-500/40";
  }
  return "bg-black text-white ring-neutral-800/60";
}

export function ForensicAnalysis({ forensics }: { forensics: DemoForensics }) {
  const suspicious = forensics.overall !== "PASS";
  return (
    <div>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-center gap-2">
          <Radar className="h-4 w-4 text-neutral-500" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-[var(--text)]">
              Forensic Analysis
            </div>
            <div className="text-xs text-[var(--muted)]">
              Simulated tamper-detection signals
            </div>
          </div>
        </div>
        <Badge className={tone(forensics.overall)}>
          Overall · {forensics.overall}
        </Badge>
      </div>

      <div className="space-y-4 p-5">
        <div
          className={cn(
            "flex items-start gap-3 rounded-xl border p-4",
            suspicious
              ? "border-neutral-400 bg-[#f8f9fc]"
              : "border-[var(--border)] bg-[var(--card)]",
          )}
        >
          <ShieldAlert
            className={cn(
              "mt-0.5 h-5 w-5 shrink-0",
              suspicious ? "text-black" : "text-neutral-500",
            )}
            aria-hidden
          />
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Overall tamper assessment
            </div>
            <div className="text-sm font-semibold text-[var(--text)]">
              {forensics.overall}
            </div>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {forensics.explanation}
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {forensics.detectors.map((d) => (
            <div
              key={d.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3.5"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-[var(--text)]">
                  {d.label}
                </span>
                <Badge className={tone(d.status)}>{d.status}</Badge>
              </div>
              {d.score != null ? (
                <div className="mt-2 flex items-center gap-2">
                  <div className="progress-track h-2 flex-1">
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
                  <span className="w-10 text-right text-xs font-semibold tabular-nums text-[var(--text)]">
                    {d.score.toFixed(2)}
                  </span>
                </div>
              ) : null}
              <p className="mt-2 text-xs text-[var(--muted)]">{d.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
