import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

export interface RiskFactorItem {
  label?: string;
  detail?: string;
  [key: string]: unknown;
}

export function RiskReasons({
  factors,
  className,
  title = "Reasons",
}: {
  factors: RiskFactorItem[];
  className?: string;
  title?: string;
}) {
  if (factors.length === 0) return null;
  return (
    <div className={className}>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {title}
      </div>
      <ul className="micro-stagger space-y-1.5">
        {factors.map((f, i) => {
          const label = String(f.label ?? f.detail ?? `Factor ${i + 1}`);
          const detail = f.detail ? String(f.detail) : null;
          const hasDetail = Boolean(f.label && f.detail);
          return (
            <li
              key={i}
              style={{ "--i": i } as CSSProperties}
              className="flex items-start gap-2 rounded-lg bg-[#f6f7fb] px-3 py-2 text-sm text-[var(--text)]"
            >
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-neutral-300/40 text-[10px] font-bold text-neutral-800">
                {i + 1}
              </span>
              <span>
                {label}
                {hasDetail ? (
                  <span className="ml-1 text-[var(--muted)]">— {detail}</span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function RiskRecommendations({
  recommendations,
  explanation,
  className,
}: {
  recommendations: string[];
  explanation?: string | null;
  className?: string;
}) {
  if (recommendations.length === 0 && !explanation) return null;
  return (
    <div className={cn("mt-4 space-y-3", className)}>
      {explanation ? (
        <div className="rounded-lg bg-[#f6f7fb] p-3 text-sm text-[var(--text)]">
          {explanation}
        </div>
      ) : null}
      {recommendations.length > 0 ? (
        <div className="rounded-lg border border-neutral-300 bg-neutral-200/60 p-3 text-sm text-neutral-800">
          <span className="font-semibold">Recommendations: </span>
          {recommendations.join(". ")}
        </div>
      ) : null}
    </div>
  );
}