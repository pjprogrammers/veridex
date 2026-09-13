"use client";

import { ArrowDown } from "lucide-react";
import type { DemoDecision } from "@/data/demo/demoResults";
import { cn } from "@/lib/utils";

interface ArchGroup {
  phase: string;
  subtitle: string;
  items: string[];
}

const ARCHITECTURE: ArchGroup[] = [
  {
    phase: "INPUT",
    subtitle: "Capture",
    items: ["Document Upload & Capture", "Face Capture"],
  },
  {
    phase: "AI PROCESSING",
    subtitle: "Extraction & biometrics",
    items: [
      "Document Classification",
      "Image Preprocessing",
      "OCR + MRZ Extraction",
      "Field & MRZ Validation",
      "Face Detection + Liveness",
      "Face Verification",
    ],
  },
  {
    phase: "VERIFICATION",
    subtitle: "Fusion & policy",
    items: [
      "Tamper Fusion Engine",
      "Registry & Watchlist",
      "Explainable Risk Engine",
    ],
  },
  {
    phase: "DECISION",
    subtitle: "Officer-facing outcome",
    items: ["CLEAR", "MANUAL REVIEW", "ALERT"],
  },
  {
    phase: "AUDIT",
    subtitle: "Integrity",
    items: ["SHA-256 Audit Hash", "Permissioned Blockchain — DEMO"],
  },
];

const DECISION_ITEM: Record<DemoDecision, string> = {
  CLEAR: "CLEAR",
  MANUAL_REVIEW: "MANUAL REVIEW",
  ALERT: "ALERT",
};

export function ArchitectureMap({ decision }: { decision: DemoDecision }) {
  return (
    <div>
      <div className="border-b border-[var(--border)] px-5 py-4">
        <div className="text-sm font-semibold text-[var(--text)]">
          Architecture Mapping
        </div>
        <div className="text-xs text-[var(--muted)]">
          Static frontend pipeline mapped to the VERIDEX architecture diagram
        </div>
      </div>
      <div className="p-5">
        <div className="flex flex-col">
          {ARCHITECTURE.map((group, gi) => (
            <div key={group.phase}>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]">
                <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-2.5">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text)]">
                    {group.phase}
                  </span>
                  <span className="text-[11px] text-[var(--muted)]">
                    {group.subtitle}
                  </span>
                </div>
                <ul className="grid gap-1.5 p-3 sm:grid-cols-2">
                  {group.items.map((item) => {
                    const active =
                      group.phase === "DECISION" &&
                      item === DECISION_ITEM[decision];
                    return (
                      <li
                        key={item}
                        className={cn(
                          "rounded-lg px-3 py-1.5 text-xs",
                          active
                            ? "bg-black font-semibold text-white"
                            : "bg-[#f6f7fb] text-[var(--text)]",
                        )}
                      >
                        {item}
                      </li>
                    );
                  })}
                </ul>
              </div>
              {gi < ARCHITECTURE.length - 1 ? (
                <div className="flex justify-center py-1" aria-hidden>
                  <ArrowDown className="h-3.5 w-3.5 text-neutral-400" />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
