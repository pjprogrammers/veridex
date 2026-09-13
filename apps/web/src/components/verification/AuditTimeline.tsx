"use client";

import { useEffect, useState } from "react";
import { Activity, Boxes, Hash } from "lucide-react";
import type { DemoCase } from "@/data/demo/verificationCases";
import { demoTxId, sha256Hex } from "@/data/demo/demoAudit";
import { Badge } from "@/components/ui";

function formatClock(baseIso: string, offsetSeconds: number): string {
  const d = new Date(new Date(baseIso).getTime() + offsetSeconds * 1000);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function AuditTimeline({
  demoCase,
  createdAt,
}: {
  demoCase: DemoCase;
  createdAt: string;
}) {
  const [auditHash, setAuditHash] = useState<string>("computing…");

  useEffect(() => {
    let cancelled = false;
    const payload = JSON.stringify({
      case_id: demoCase.id,
      subject: demoCase.document.name,
      document: demoCase.document.passportNumber,
      decision: demoCase.result.decision.verdict,
      risk_score: demoCase.result.risk.score,
      generated_at: createdAt,
    });
    sha256Hex(payload).then((h) => {
      if (!cancelled) setAuditHash(h);
    });
    return () => {
      cancelled = true;
    };
  }, [demoCase, createdAt]);

  const txId = demoTxId(auditHash);
  const block = demoCase.audit.blockchain;

  return (
    <div>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-neutral-500" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-[var(--text)]">
              Audit Trail
            </div>
            <div className="text-xs text-[var(--muted)]">
              Deterministic demonstration timestamps
            </div>
          </div>
        </div>
        <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
          IMMUTABLE · DEMO
        </Badge>
      </div>

      <div className="space-y-5 p-5">
        <ol className="relative space-y-3 border-l border-[var(--border)] pl-5">
          {demoCase.audit.events.map((e, i) => (
            <li key={i} className="relative">
              <span
                className="absolute -left-[26px] top-1 flex h-3 w-3 items-center justify-center rounded-full border-2 border-[var(--border)] bg-[var(--card)]"
                aria-hidden
              />
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-sm font-medium text-[var(--text)]">
                  {e.action}
                </span>
                <span className="font-mono text-xs tabular-nums text-[var(--muted)]">
                  {formatClock(createdAt, e.offsetSeconds)}
                </span>
              </div>
              {e.detail ? (
                <p className="text-xs text-[var(--muted)]">{e.detail}</p>
              ) : null}
            </li>
          ))}
        </ol>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
                <Hash className="h-4 w-4 text-neutral-500" aria-hidden />
                Audit Hash — DEMO
              </span>
              <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
                SHA-256
              </Badge>
            </div>
            <p className="mt-2 break-all font-mono text-[11px] leading-5 text-[var(--muted)]">
              {auditHash}
            </p>
            <p className="mt-2 text-[11px] leading-4 text-[var(--muted)]">
              Computed locally in the browser over the static verification JSON.
              No server call is made.
            </p>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
                <Boxes className="h-4 w-4 text-neutral-500" aria-hidden />
                Permissioned Blockchain
              </span>
              <Badge className="bg-neutral-200/70 text-neutral-700 ring-neutral-400/40">
                RECORD SIMULATED
              </Badge>
            </div>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted)]">Network</dt>
                <dd className="font-medium text-[var(--text)]">{block.network}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted)]">Channel</dt>
                <dd className="font-mono text-xs text-[var(--text)]">
                  {block.channel}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted)]">Status</dt>
                <dd className="font-medium text-[var(--text)]">{block.status}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted)]">Block</dt>
                <dd className="font-mono text-xs text-[var(--text)]">
                  #{block.blockNumber.toLocaleString()}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="shrink-0 text-[var(--muted)]">Tx</dt>
                <dd className="break-all text-right font-mono text-[11px] text-[var(--text)]">
                  {txId}
                </dd>
              </div>
            </dl>
            <p className="mt-2 text-[11px] leading-4 text-[var(--muted)]">
              Hyperledger Fabric is displayed as a simulated target. The
              prototype does not contact a ledger node.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
