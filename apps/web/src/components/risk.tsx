import { Badge } from "./ui";
import { RISK_STYLES } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types";

export function RiskBadge({ level }: { level: RiskLevel | null }) {
  const normalized: RiskLevel = level ?? "UNKNOWN";
  return <Badge className={RISK_STYLES[normalized]}>{normalized}</Badge>;
}

export function RiskGauge({ score, level }: { score: number; level: RiskLevel }) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);

  const color = {
    LOW: "text-emerald-600",
    MEDIUM: "text-amber-600",
    HIGH: "text-orange-600",
    CRITICAL: "text-red-600",
    UNKNOWN: "text-slate-500",
  }[level];

  const bar = {
    LOW: "bg-emerald-500",
    MEDIUM: "bg-amber-500",
    HIGH: "bg-orange-500",
    CRITICAL: "bg-red-500",
    UNKNOWN: "bg-slate-400",
  }[level];

  return (
    <div className="flex items-center gap-4">
      <div
        className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 ${color} border-current text-2xl font-bold`}
      >
        {pct}
      </div>
      <div className="flex-1">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-medium text-slate-700">Risk score</span>
          <span className={`font-bold ${color}`}>{level}</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${bar}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-slate-400">
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