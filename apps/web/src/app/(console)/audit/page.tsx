"use client";

import { useCallback, useEffect, useState } from "react";
import { ScrollText, ShieldCheck } from "lucide-react";
import { api, errorFn, withQuery } from "@/lib/api";
import type { AuditEntry, AuditVerifyResponse } from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Input,
  Label,
  Select,
  Skeleton,
  Spinner,
} from "@/components/ui";
import { cn, formatDate } from "@/lib/utils";

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState("");
  const [caseFilter, setCaseFilter] = useState("");
  const [verifyBusy, setVerifyBusy] = useState<string | null>(null);
  const [verifyResults, setVerifyResults] = useState<
    Record<string, AuditVerifyResponse>
  >({});

  const load = useCallback(async () => {
    setError(null);
    try {
      const path = withQuery("/audit", {
        limit: 200,
        action: actionFilter || null,
        case_id: caseFilter || null,
      });
      setEntries(await api<AuditEntry[]>(path));
    } catch (e) {
      setError(errorFn(e));
      setEntries([]);
    }
  }, [actionFilter, caseFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const uniqueCases = Array.from(
    new Set((entries ?? []).map((e) => e.case_id).filter(Boolean) as string[]),
  );
  const actions = Array.from(
    new Set((entries ?? []).map((e) => e.action)),
  ).sort();

  async function verifyChain(caseId: string) {
    setVerifyBusy(caseId);
    setError(null);
    try {
      const res = await api<AuditVerifyResponse>(`/audit/verify/${caseId}`);
      setVerifyResults((prev) => ({ ...prev, [caseId]: res }));
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setVerifyBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 animate-fade-in-up">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Audit Trail</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Tamper-evident, SHA-256 chained log of all system activity.
        </p>
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      <Card>
        <CardHeader
          title="Filters"
          subtitle="Refine the audit log view"
        />
        <div className="flex flex-wrap items-end gap-4 p-5">
          <div>
            <Label>Action</Label>
            <Select
              className="w-48"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
            >
              <option value="">All actions</option>
              {actions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Case ID</Label>
            <Input
              className="w-64 font-mono"
              placeholder="UUID of a case"
              value={caseFilter}
              onChange={(e) => setCaseFilter(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {/* Chain integrity per case */}
      {uniqueCases.length > 0 ? (
        <Card>
          <CardHeader
            title="Chain integrity"
            subtitle="Verify the audit hash chain per case"
          />
          <ul className="divide-y divide-[var(--border)]">
            {uniqueCases.map((caseId) => {
              const result = verifyResults[caseId];
              return (
                <li
                  key={caseId}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-xs text-[var(--text)]">{caseId}</div>
                    {result ? (
                      <div
                        className={
                          result.valid
                            ? "mt-1 text-xs font-medium text-neutral-600"
                            : "mt-1 text-xs font-medium text-black"
                        }
                      >
                        {result.valid
                          ? `Integrity confirmed (${result.total_entries} entries)`
                          : `Chain VIOLATED — ${result.message}`}
                      </div>
                    ) : null}
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={verifyBusy === caseId}
                    onClick={() => verifyChain(caseId)}
                  >
                    {verifyBusy === caseId ? <Spinner /> : <ShieldCheck className="h-4 w-4" aria-hidden />}
                    Verify chain
                  </Button>
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Log entries"
          subtitle={`${entries?.length ?? 0} showing`}
        />
        {!entries ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : entries.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="No audit entries"
              hint="System activity is logged here as it happens."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[#f6f7fb]">
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">#</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Action</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Actor</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Case</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Timestamp</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {entries.map((e, idx) => (
                  <tr
                    key={e.id}
                    className={cn(
                      "table-row-alt transition-colors hover:bg-neutral-100/70",
                      idx % 2 === 1 && "bg-[#f8f9fc]",
                    )}
                  >
                    <td className="px-6 py-3.5 text-xs text-[var(--muted)]">#{e.id}</td>
                    <td className="px-6 py-3.5">
                      <span className="inline-flex items-center gap-1.5 font-medium text-[var(--text)]">
                        <ScrollText className="h-3.5 w-3.5 text-[var(--muted)]" aria-hidden />
                        {e.action}
                      </span>
                      {Object.keys(e.payload ?? {}).length > 0 ? (
                        <div className="mt-0.5 max-w-xs truncate font-mono text-[10px] text-[var(--muted)]">
                          {JSON.stringify(e.payload)}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-6 py-3.5">
                      <span className="text-[var(--text)]">{e.actor_role ?? "—"}</span>
                    </td>
                    <td className="px-6 py-3.5 font-mono text-[11px] text-[var(--muted)]">
                      {e.case_id ? e.case_id.slice(0, 8) : "—"}
                    </td>
                    <td className="px-6 py-3.5 text-xs text-[var(--muted)]">
                      {formatDate(e.timestamp)}
                    </td>
                    <td className="px-6 py-3.5 font-mono text-[10px] text-[var(--muted)]">
                      {e.current_hash?.slice(0, 12)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
