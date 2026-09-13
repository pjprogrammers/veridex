"use client";

import { AlertTriangle, Scale, ShieldCheck } from "lucide-react";
import type { DemoDecision, DemoDecisionBlock } from "@/data/demo/demoResults";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/utils";

const VERDICT_LABEL: Record<DemoDecision, string> = {
  CLEAR: "CLEAR",
  ALERT: "HIGH-RISK ALERT",
  MANUAL_REVIEW: "MANUAL REVIEW",
};

export function DecisionPanel({
  decision,
  riskScore,
}: {
  decision: DemoDecisionBlock;
  riskScore: number;
}) {
  const dark = decision.verdict !== "CLEAR";
  const Icon =
    decision.verdict === "CLEAR"
      ? ShieldCheck
      : decision.verdict === "ALERT"
        ? AlertTriangle
        : Scale;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border",
        decision.verdict === "CLEAR"
          ? "border-[var(--border)] bg-[var(--card)]"
          : decision.verdict === "ALERT"
            ? "border-neutral-900 bg-black text-white"
            : "border-neutral-700 bg-neutral-800 text-white",
      )}
    >
      <div className="flex flex-wrap items-center gap-4 p-5">
        <div
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-full",
            dark ? "bg-white/10 text-white" : "bg-neutral-200/70 text-neutral-700",
          )}
        >
          <Icon className="h-6 w-6" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div
            className={cn(
              "text-[11px] font-semibold uppercase tracking-wider",
              dark ? "text-white/60" : "text-[var(--muted)]",
            )}
          >
            Final decision · risk score {riskScore}/100
          </div>
          <div className="text-xl font-bold tracking-tight">{decision.title}</div>
        </div>
        <Badge
          className={cn(
            "px-3 py-1 text-xs",
            decision.verdict === "CLEAR"
              ? "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40"
              : decision.verdict === "ALERT"
                ? "bg-white text-black ring-white/40"
                : "bg-white/15 text-white ring-white/40",
          )}
        >
          {VERDICT_LABEL[decision.verdict]}
        </Badge>
      </div>

      <div
        className={cn(
          "border-t px-5 py-4",
          dark ? "border-white/15" : "border-[var(--border)]",
        )}
      >
        <div
          className={cn(
            "mb-2 text-xs font-semibold uppercase tracking-wide",
            dark ? "text-white/60" : "text-[var(--muted)]",
          )}
        >
          Reasons
        </div>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {decision.reasons.map((r, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span
                className={cn(
                  "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                  dark ? "bg-white/70" : "bg-neutral-500",
                )}
                aria-hidden
              />
              <span className={dark ? "text-white/90" : "text-[var(--text)]"}>
                {r}
              </span>
            </li>
          ))}
        </ul>
        {decision.note ? (
          <p
            className={cn(
              "mt-3 rounded-lg px-3 py-2 text-xs",
              dark ? "bg-white/10 text-white/85" : "bg-[#f6f7fb] text-[var(--muted)]",
            )}
          >
            {decision.note}
          </p>
        ) : null}
      </div>

      <div
        className={cn(
          "border-t px-5 py-3 text-[11px]",
          dark
            ? "border-white/15 bg-white/5 text-white/70"
            : "border-[var(--border)] bg-[#f8f9fc] text-[var(--muted)]",
        )}
      >
        Decision-support only — final determination requires authorized officer
        review.
      </div>
    </div>
  );
}
