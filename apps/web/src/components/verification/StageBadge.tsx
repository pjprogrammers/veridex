import type { DemoStageState } from "@/data/demo/types";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Circle,
  Loader2,
  TriangleAlert,
  XCircle,
} from "lucide-react";

export function stageIcon(state: DemoStageState) {
  switch (state) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-neutral-600" aria-hidden />;
    case "processing":
      return <Loader2 className="h-4 w-4 animate-spin text-neutral-500" aria-hidden />;
    case "warning":
      return <TriangleAlert className="h-4 w-4 text-neutral-700" aria-hidden />;
    case "failed":
      return <XCircle className="h-4 w-4 text-black" aria-hidden />;
    default:
      return <Circle className="h-4 w-4 text-[var(--border)]" aria-hidden />;
  }
}

export const STAGE_STYLE: Record<DemoStageState, string> = {
  pending: "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]",
  processing: "bg-neutral-200/80 text-neutral-700 ring-neutral-400/40",
  completed: "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40",
  warning: "bg-neutral-300/60 text-neutral-800 ring-neutral-400/40",
  failed: "bg-black text-white ring-neutral-800/60",
};

export const STAGE_LABEL: Record<DemoStageState, string> = {
  pending: "Pending",
  processing: "Processing",
  completed: "Completed",
  warning: "Warning",
  failed: "Failed",
};

export function StageBadge({ state }: { state: DemoStageState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ring-1 ring-inset",
        STAGE_STYLE[state],
      )}
    >
      {stageIcon(state)}
      {STAGE_LABEL[state]}
    </span>
  );
}