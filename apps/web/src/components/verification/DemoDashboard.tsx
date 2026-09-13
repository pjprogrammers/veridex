"use client";

import Link from "next/link";
import { ArrowRight, FlaskConical } from "lucide-react";
import {
  AADHAAR_DEMO,
  DEMO_CASES,
  getDemoStats,
} from "@/data/demo/verificationCases";
import type { DemoDecision } from "@/data/demo/demoResults";
import { Badge, Card, CardHeader } from "@/components/ui";

const DECISION_CLASS: Record<DemoDecision, string> = {
  CLEAR: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  ALERT: "bg-black text-white ring-neutral-800/60",
  MANUAL_REVIEW: "bg-neutral-400/40 text-neutral-900 ring-neutral-500/40",
};

const DECISION_SHORT: Record<DemoDecision, string> = {
  CLEAR: "CLEAR",
  ALERT: "ALERT",
  MANUAL_REVIEW: "REVIEW",
};

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-[var(--text)]">
        {value}
      </div>
    </div>
  );
}

export function DemoDashboard({ showCases = true }: { showCases?: boolean }) {
  const stats = getDemoStats();

  return (
    <Card>
      <CardHeader
        title="SIH Demonstration Mode"
        subtitle="Frontend-only static verification workflow — synthetic data"
        action={
          <Badge className="bg-black text-white ring-neutral-800/60">
            <FlaskConical className="h-3 w-3" aria-hidden />
            DEMO
          </Badge>
        }
      />
      <div className="space-y-5 p-5">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatTile label="Total Demo Cases" value={stats.total} />
          <StatTile label="Clear" value={stats.clear} />
          <StatTile label="Manual Review" value={stats.manualReview} />
          <StatTile label="High Risk / Alert" value={stats.alert} />
          <StatTile label="Aadhaar Demo" value={stats.aadhaar} />
        </div>

        {showCases ? (
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Recent cases
            </div>
            <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
              <table className="w-full border-collapse text-left text-[13px]">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[#f8f9fc] text-[11.5px] font-semibold text-[var(--muted)]">
                    <th className="px-4 py-2.5">Case ID</th>
                    <th className="px-4 py-2.5">Subject</th>
                    <th className="px-4 py-2.5">Document</th>
                    <th className="px-4 py-2.5 text-right">Risk</th>
                    <th className="px-4 py-2.5 text-right">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {DEMO_CASES.map((c) => (
                    <tr
                      key={c.id}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-[#f6f7fb]"
                    >
                      <td className="px-4 py-3 font-mono text-xs font-semibold text-neutral-700">
                        {c.caseInfo.caseId}
                      </td>
                      <td className="px-4 py-3 text-[var(--text)]">
                        {c.caseInfo.subject}
                      </td>
                      <td className="px-4 py-3 text-[var(--muted)]">
                        {c.caseInfo.document}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-[var(--text)]">
                        {c.caseInfo.riskScore}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Badge className={DECISION_CLASS[c.result.decision.verdict]}>
                          {DECISION_SHORT[c.result.decision.verdict]}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  <tr className="hover:bg-[#f6f7fb]">
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-neutral-700">
                      —
                    </td>
                    <td className="px-4 py-3 text-[var(--text)]">
                      {AADHAAR_DEMO.name}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">
                      {AADHAAR_DEMO.document}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[var(--text)]">
                      {AADHAAR_DEMO.riskScore}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Badge className={DECISION_CLASS[AADHAAR_DEMO.expectedDecision]}>
                        CLEAR
                      </Badge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        <div className="flex justify-end">
          <Link
            href="/demo"
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--dark)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--dark-2)]"
          >
            Open demo workflow
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>
      </div>
    </Card>
  );
}
