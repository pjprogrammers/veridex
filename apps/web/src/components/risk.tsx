import { Badge } from "./ui";
import { RISK_STYLES } from "@/lib/utils";
import { useCountUp } from "@/lib/use-count-up";
import type { RiskLevel } from "@/lib/types";

export function RiskBadge({ level }: { level: RiskLevel | null }) {
  const normalized: RiskLevel = level ?? "UNKNOWN";
  return <Badge className={RISK_STYLES[normalized]}>{normalized}</Badge>;
}

export function RiskGauge({ score, level }: { score: number; level: RiskLevel }) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);

  const color = {
    LOW: "text-neutral-500",
    MEDIUM: "text-neutral-600",
    HIGH: "text-neutral-800",
    CRITICAL: "text-black",
    UNKNOWN: "text-neutral-400",
  }[level];

  const bar = {
    LOW: "bg-neutral-400",
    MEDIUM: "bg-neutral-500",
    HIGH: "bg-neutral-700",
    CRITICAL: "bg-black",
    UNKNOWN: "bg-neutral-300",
  }[level];

  const shown = useCountUp(pct);

  return (
    <div className="flex items-center gap-4">
      <div
        className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 ${color} border-current text-2xl font-bold bg-[var(--card)]`}
      >
        {shown}
      </div>
      <div className="flex-1">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-medium text-[var(--muted)]">Risk score</span>
          <span className={`font-bold ${color}`}>{level}</span>
        </div>
        <div className="progress-track h-2.5">
          <div className="h-full" style={{ width: `${pct}%` }}>
            <div className={`progress-fill micro-grow-x h-full rounded-full ${bar}`} />
          </div>
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-[var(--muted)]">
          <span>0</span>
          <span>0.25</span>
          <span>0.5</span>
          <span>0.75</span>
          <span>1</span>
        </div>
      </div>
    </div>
  );
}
