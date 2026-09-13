"use client";

import { useState } from "react";
import { ChevronDown, Radar, ScanSearch } from "lucide-react";
import type {
  DemoDecision,
  RiskFactorDetail,
} from "@/data/demo/demoResults";
import { Badge } from "@/components/ui";
import { RiskBadge } from "@/components/risk";
import { cn, RISK_BAR } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types";

const DECISION_CLASS: Record<DemoDecision, string> = {
  CLEAR: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  ALERT: "bg-black text-white ring-neutral-800/60",
  MANUAL_REVIEW: "bg-neutral-400/40 text-neutral-900 ring-neutral-500/40",
};

function FactorRow({
  factor,
  open,
  onToggle,
}: {
  factor: RiskFactorDetail;
  open: boolean;
  onToggle: () => void;
}) {
  const positive = factor.contribution > 0;
  return (
    <li className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3.5 py-3 text-left transition-colors hover:bg-[#f6f7fb]"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-[var(--text)]">
            {factor.label}
          </span>
          <span className="mt-0.5 block truncate text-xs text-[var(--muted)]">
            {factor.explanation}
          </span>
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold tabular-nums ring-1 ring-inset",
            positive
              ? "bg-[#f6f7fb] text-black ring-neutral-400/50"
              : "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]",
          )}
        >
          {factor.result === "0" ? "0" : factor.result}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-neutral-400 transition-transform",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <div className="border-t border-[var(--border)] bg-[#f8f9fc] px-3.5 py-3">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-[var(--muted)]">Score contribution</dt>
              <dd className="font-medium text-[var(--text)]">
                {positive ? `+${factor.contribution}` : factor.contribution} points
              </dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--muted)]">Detection result</dt>
              <dd className="font-medium text-[var(--text)]">{factor.result}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-[var(--muted)]">Explanation</dt>
              <dd className="text-[var(--text)]">{factor.explanation}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-[var(--muted)]">
                Affected document region
              </dt>
              <dd className="text-[var(--text)]">{factor.region ?? "Not localized"}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </li>
  );
}

export function RiskBreakdown({
  score,
  level,
  decision,
  factors,
}: {
  score: number;
  level: RiskLevel;
  decision: DemoDecision;
  factors: RiskFactorDetail[];
}) {
  const [openId, setOpenId] = useState<string | null>(
    factors.find((f) => f.contribution > 0)?.id ?? null,
  );

  const bar = RISK_BAR[level] ?? "bg-neutral-400";

  return (
    <div>
      <div className="flex items-center gap-4 border-b border-[var(--border)] px-5 py-4">
        <Radar className="h-4 w-4 text-neutral-500" aria-hidden />
        <div className="flex-1">
          <div className="text-sm font-semibold text-[var(--text)]">
            Explainable Risk Engine
          </div>
          <div className="text-xs text-[var(--muted)]">
            Deterministic demo scoring · click a factor for details
          </div>
        </div>
        <Badge className={DECISION_CLASS[decision]}>{decision.replace(/_/g, " ")}</Badge>
      </div>

      <div className="space-y-5 p-5">
        <div className="flex flex-wrap items-center gap-5">
          <div className="flex items-center gap-3">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 border-current bg-[var(--card)] text-2xl font-bold text-[var(--text)]">
              {score}
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                Risk Score
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-[var(--text)]">
                  {score} / 100
                </span>
                <RiskBadge level={level} />
              </div>
            </div>
          </div>
          <div className="min-w-[200px] flex-1">
            <div className="mb-1 flex justify-between text-[10px] text-[var(--muted)]">
              <span>0</span>
              <span>30</span>
              <span>60</span>
              <span>80</span>
              <span>100</span>
            </div>
            <div className="progress-track h-2.5">
              <div
                className={cn("progress-fill micro-grow-x h-full rounded-full", bar)}
                style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
              />
            </div>
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            <ScanSearch className="h-3.5 w-3.5" aria-hidden />
            Risk factors
          </div>
          <ul className="space-y-2">
            {factors.map((f) => (
              <FactorRow
                key={f.id}
                factor={f}
                open={openId === f.id}
                onToggle={() =>
                  setOpenId((cur) => (cur === f.id ? null : f.id))
                }
              />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
