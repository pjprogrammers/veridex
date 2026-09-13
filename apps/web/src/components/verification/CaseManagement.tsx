"use client";

import { useState } from "react";
import { Briefcase, ChevronDown } from "lucide-react";
import type { DemoCase } from "@/data/demo/verificationCases";
import { Badge } from "@/components/ui";
import { cn, formatDate } from "@/lib/utils";

const DECISION_CLASS: Record<string, string> = {
  CLEAR: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  ALERT: "bg-black text-white ring-neutral-800/60",
  MANUAL_REVIEW: "bg-neutral-400/40 text-neutral-900 ring-neutral-500/40",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className="text-[var(--muted)]">{label}</span>
      <span className="text-right font-medium text-[var(--text)]">{value}</span>
    </div>
  );
}

export function CaseManagement({
  demoCase,
  createdAt,
}: {
  demoCase: DemoCase;
  createdAt: string;
}) {
  const [open, setOpen] = useState(false);
  const { caseInfo, result } = demoCase;

  return (
    <div>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-center gap-2">
          <Briefcase className="h-4 w-4 text-neutral-500" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-[var(--text)]">
              Case Management
            </div>
            <div className="text-xs text-[var(--muted)]">
              Static demonstration case record
            </div>
          </div>
        </div>
        <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
          {caseInfo.verificationStatus}
        </Badge>
      </div>

      <div className="grid gap-x-8 gap-y-1 p-5 sm:grid-cols-2">
        <Row label="Case ID" value={<span className="font-mono text-xs">{caseInfo.caseId}</span>} />
        <Row label="Document" value={caseInfo.document} />
        <Row label="Subject" value={caseInfo.subject} />
        <Row label="Risk Score" value={`${caseInfo.riskScore} / 100`} />
        <Row
          label="Decision"
          value={
            <Badge className={DECISION_CLASS[result.decision.verdict]}>
              {result.decision.verdict.replace(/_/g, " ")}
            </Badge>
          }
        />
        <Row label="Created At" value={formatDate(createdAt)} />
        <Row label="Officer" value={caseInfo.officer} />
        <Row label="Verification Status" value={caseInfo.verificationStatus} />
      </div>

      <div className="border-t border-[var(--border)] px-5 py-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex items-center gap-2 text-xs font-semibold text-neutral-600 hover:text-black"
        >
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
            aria-hidden
          />
          {open ? "Hide case details" : "Open case details"}
        </button>

        {open ? (
          <div className="mt-3 grid gap-4 rounded-xl bg-[#f8f9fc] p-4 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                Document
              </div>
              <Row label="Passport number" value={demoCase.document.passportNumber} />
              <Row label="Nationality" value={demoCase.document.nationality} />
              <Row label="Expiry" value={demoCase.document.expiryDate} />
              <Row label="Registry" value={demoCase.document.registryStatus} />
              <Row label="Watchlist" value={demoCase.document.watchlistStatus} />
            </div>
            <div>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                Verification
              </div>
              <Row label="Risk level" value={result.risk.level} />
              <Row label="Face similarity" value={`${result.face.similarity}%`} />
              <Row label="Tamper assessment" value={result.forensics.overall} />
              <Row label="Audit events" value={String(demoCase.audit.events.length)} />
              <Row
                label="Ledger status"
                value={demoCase.audit.blockchain.status}
              />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
