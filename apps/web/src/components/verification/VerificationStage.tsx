"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react";
import type { DemoStageDefinition } from "@/data/demo/verificationCases";
import type { StageResult } from "@/data/demo/demoResults";
import { cn } from "@/lib/utils";

export type PipelineState =
  | "pending"
  | "processing"
  | "completed"
  | "warning"
  | "failed";

export const PIPELINE_STYLES: Record<
  PipelineState,
  { label: string; badge: string; icon: React.ReactNode }
> = {
  pending: {
    label: "Pending",
    badge: "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]",
    icon: <Circle className="h-4 w-4 text-neutral-300" aria-hidden />,
  },
  processing: {
    label: "Processing",
    badge: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
    icon: <Loader2 className="h-4 w-4 animate-spin text-neutral-500" aria-hidden />,
  },
  completed: {
    label: "Completed",
    badge: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
    icon: <CheckCircle2 className="h-4 w-4 text-neutral-600" aria-hidden />,
  },
  warning: {
    label: "Warning",
    badge: "bg-neutral-400/40 text-neutral-900 ring-neutral-500/40",
    icon: <AlertTriangle className="h-4 w-4 text-neutral-700" aria-hidden />,
  },
  failed: {
    label: "Failed",
    badge: "bg-black text-white ring-neutral-800/60",
    icon: <XCircle className="h-4 w-4 text-black" aria-hidden />,
  },
};

export function stageResultToState(status: StageResult["status"]): PipelineState {
  if (status === "warning") return "warning";
  if (status === "failed") return "failed";
  return "completed";
}

export function VerificationStage({
  definition,
  state,
  result,
  index,
}: {
  definition: DemoStageDefinition;
  state: PipelineState;
  result: StageResult;
  index: number;
}) {
  const [open, setOpen] = useState(false);
  const style = PIPELINE_STYLES[state];
  const hasDetail = Boolean(result.details?.length);

  return (
    <li className="border-b border-[var(--border)] last:border-0">
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        aria-expanded={hasDetail ? open : undefined}
        className={cn(
          "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors",
          hasDetail ? "hover:bg-[#f6f7fb]" : "cursor-default",
        )}
      >
        <span className="mt-0.5 shrink-0">{style.icon}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
              Stage {index + 1}
            </span>
            <span className="text-sm font-medium text-[var(--text)]">
              {definition.title}
            </span>
          </span>
          <span className="mt-0.5 block text-xs text-[var(--muted)]">
            {result.summary}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset",
              style.badge,
            )}
          >
            {style.label}
          </span>
          {hasDetail ? (
            <ChevronDown
              className={cn(
                "h-4 w-4 text-neutral-400 transition-transform",
                open && "rotate-180",
              )}
              aria-hidden
            />
          ) : null}
        </span>
      </button>
      {open && hasDetail ? (
        <div className="px-4 pb-3 pl-11">
          <ul className="space-y-1 rounded-lg bg-[#f6f7fb] px-3 py-2">
            {result.details?.map((d, i) => (
              <li key={i} className="text-xs text-[var(--text)]">
                {d}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}
