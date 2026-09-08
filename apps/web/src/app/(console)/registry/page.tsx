"use client";

import { useCallback, useEffect, useState } from "react";
import { api, errorFn } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  RegistryEntry,
  RegistryListResponse,
  RegistryLookupResponse,
} from "@/lib/types";
import {
  Alert,
  Badge,
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

function statusTone(status: string): string {
  if (status === "valid")
    return "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40";
  if (
    status === "reported_stolen" ||
    status === "blacklisted" ||
    status === "suspended"
  )
    return "bg-neutral-200/80 text-black ring-neutral-400/40";
  return "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40";
}

const REGISTRY_STATUSES = [
  "valid",
  "reported_stolen",
  "blacklisted",
  "expired",
  "suspended",
];

const REGISTRY_STAT_DOTS: Record<string, string> = {
  valid: "bg-neutral-500",
  flagged: "bg-black",
  pending: "bg-neutral-500",
};

const FLAGGED_STATUSES = new Set([
  "reported_stolen",
  "blacklisted",
  "suspended",
]);
const PENDING_STATUSES = new Set(["expired"]);

function registryStats(entries: RegistryEntry[]) {
  const total = entries.length;
  const valid = entries.filter((e) => e.status === "valid").length;
  const flagged = entries.filter((e) => FLAGGED_STATUSES.has(e.status)).length;
  const pending = entries.filter((e) => PENDING_STATUSES.has(e.status)).length;
  return { total, valid, flagged, pending };
}

function RegistryStatCard({
  label,
  value,
  dot,
  sublabel,
}: {
  label: string;
  value: number;
  dot: string;
  sublabel?: string;
}) {
  return (
    <div className="card-hover rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
        {label}
      </p>
      <div className="mt-2 flex items-center gap-2">
        <span className={cn("h-2.5 w-2.5 rounded-full", dot)} />
        <span className="text-3xl font-bold tracking-tight text-[var(--text)] animate-count-up">
          {value.toLocaleString()}
        </span>
      </div>
      {sublabel ? (
        <p className="mt-1 text-[11px] text-[var(--muted)]">{sublabel}</p>
      ) : null}
    </div>
  );
}

function dotFor(entryStatus: string) {
  if (entryStatus === "valid") return REGISTRY_STAT_DOTS.valid;
  if (FLAGGED_STATUSES.has(entryStatus)) return REGISTRY_STAT_DOTS.flagged;
  return REGISTRY_STAT_DOTS.pending;
}

export default function RegistryPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [entries, setEntries] = useState<RegistryEntry[] | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [lookupNumber, setLookupNumber] = useState("");
  const [lookupResult, setLookupResult] = useState<RegistryLookupResponse | null>(null);
  const [lookupBusy, setLookupBusy] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createForm, setCreateForm] = useState({
    registry_type: "police",
    document_number: "",
    status: "valid",
    holder_name: "",
    issuing_country: "",
  });

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api<RegistryListResponse>(
        `/registry?limit=100${
          statusFilter ? `&status_filter=${statusFilter}` : ""
        }`,
      );
      setEntries(res.entries);
    } catch (e) {
      setError(errorFn(e));
      setEntries([]);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function doLookup(e: React.FormEvent) {
    e.preventDefault();
    if (!lookupNumber.trim()) return;
    setLookupBusy(true);
    setError(null);
    try {
      setLookupResult(
        await api<RegistryLookupResponse>(
          `/registry/lookup/${encodeURIComponent(lookupNumber.trim())}`,
        ),
      );
    } catch (err) {
      setError(errorFn(err));
    } finally {
      setLookupBusy(false);
    }
  }

  async function doCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateBusy(true);
    setError(null);
    try {
      await api("/registry", {
        method: "POST",
        json: {
          registry_type: createForm.registry_type,
          document_number: createForm.document_number.trim(),
          status: createForm.status,
          ...(createForm.holder_name ? { holder_name: createForm.holder_name } : {}),
          ...(createForm.issuing_country
            ? { issuing_country: createForm.issuing_country }
            : {}),
        },
      });
      setCreateOpen(false);
      setCreateForm((f) => ({
        ...f,
        document_number: "",
        holder_name: "",
        issuing_country: "",
      }));
      await load();
    } catch (err) {
      setError(errorFn(err));
    } finally {
      setCreateBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Registry</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Synthetic document registry (police / immigration / blacklist).
          </p>
        </div>
        {isAdmin ? (
          <Button onClick={() => setCreateOpen(true)}>Add entry</Button>
        ) : null}
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      {entries ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {(() => {
            const s = registryStats(entries);
            return (
              <>
                <RegistryStatCard label="Total entries" value={s.total} dot="bg-neutral-500" />
                <RegistryStatCard label="Valid" value={s.valid} dot={dotFor("valid")} />
                <RegistryStatCard label="Flagged" value={s.flagged} dot={dotFor("reported_stolen")} sublabel="stolen / blacklisted / suspended" />
                <RegistryStatCard label="Pending" value={s.pending} dot={dotFor("expired")} sublabel="expired" />
              </>
            );
          })()}
        </div>
      ) : null}

      <Card>
        <CardHeader
          title="Lookup document"
          subtitle="Check a document number against registered statuses"
        />
        <form onSubmit={doLookup} className="flex flex-wrap items-end gap-3 p-4">
          <div className="min-w-56 flex-1">
            <Label>Document number</Label>
            <Input
              placeholder="e.g. AB123456X"
              value={lookupNumber}
              onChange={(e) => setLookupNumber(e.target.value)}
              className="font-mono"
              minLength={4}
              required
            />
          </div>
          <Button type="submit" disabled={lookupBusy || !lookupNumber.trim()}>
            {lookupBusy ? <Spinner /> : "Look up"}
          </Button>
        </form>
        {lookupResult ? (
          <div className="border-t border-[var(--border)] px-4 py-3">
            {lookupResult.found ? (
              <div className="space-y-2">
                {(lookupResult.entries ?? []).map((entry) => (
                  <div
                    key={entry.id}
                    className="flex flex-wrap items-center gap-3 rounded-lg bg-[#f6f7fb] px-3 py-2 text-sm"
                  >
                    <Badge className={statusTone(entry.status)}>
                      {entry.status}
                    </Badge>
                    <span className="font-medium text-[var(--text)]">
                      {entry.registry_type}
                    </span>
                    <span className="font-mono text-[var(--text)]">
                      {entry.document_number}
                    </span>
                    <span className="text-xs text-[var(--muted)]">
                      {entry.holder_name ?? "no holder"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-[var(--text)]">{lookupResult.message}</div>
            )}
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader
          title="Registry entries"
          subtitle={`${entries?.length ?? 0} listed`}
          action={
            <Select
              className="h-9 w-44 text-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              {REGISTRY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          }
        />
        {!entries ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : entries.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="No registry entries"
              hint={
                isAdmin
                  ? "Add an entry to seed the synthetic registry."
                  : "Ask an admin to seed entries."
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[#f6f7fb]">
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Type</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Document number</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Status</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Holder</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Country</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {entries.map((entry, idx) => (
                  <tr
                    key={entry.id}
                    className={cn(
                      "table-row-alt transition-colors hover:bg-neutral-100/70",
                      idx % 2 === 1 && "bg-[#f8f9fc]",
                    )}
                  >
                    <td className="px-6 py-3.5 text-[var(--text)]">
                      {entry.registry_type}
                    </td>
                    <td className="px-6 py-3.5 font-mono text-[var(--text)]">
                      {entry.document_number}
                    </td>
                    <td className="px-6 py-3.5">
                      <Badge className={statusTone(entry.status)}>
                        {entry.status}
                      </Badge>
                    </td>
                    <td className="px-6 py-3.5 text-[var(--text)]">
                      {entry.holder_name ?? "—"}
                    </td>
                    <td className="px-6 py-3.5 text-[var(--text)]">
                      {entry.issuing_country ?? "—"}
                    </td>
                    <td className="px-6 py-3.5 text-xs text-[var(--muted)]">
                      {formatDate(entry.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {createOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--dark)]/50 p-4">
          <form
            onSubmit={doCreate}
            className="w-full max-w-md rounded-2xl bg-[var(--card)] p-6 shadow-2xl text-[var(--text)] border border-[var(--border)]"
          >
            <h2 className="text-lg font-semibold text-[var(--text)]">
              Add registry entry
            </h2>
            <div className="mt-4 space-y-4">
              <div>
                <Label>Registry type</Label>
                <Select
                  value={createForm.registry_type}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      registry_type: e.target.value,
                    }))
                  }
                >
                  <option value="police">police</option>
                  <option value="immigration">immigration</option>
                  <option value="blacklist">blacklist</option>
                </Select>
              </div>
              <div>
                <Label>Document number</Label>
                <Input
                  className="font-mono"
                  placeholder="AB123456X"
                  minLength={4}
                  maxLength={20}
                  value={createForm.document_number}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      document_number: e.target.value,
                    }))
                  }
                  required
                />
              </div>
              <div>
                <Label>Status</Label>
                <Select
                  value={createForm.status}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, status: e.target.value }))
                  }
                >
                  {REGISTRY_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Holder name (optional)</Label>
                <Input
                  value={createForm.holder_name}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, holder_name: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="secondary"
                type="button"
                disabled={createBusy}
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createBusy}>
                {createBusy ? <Spinner /> : "Add entry"}
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
