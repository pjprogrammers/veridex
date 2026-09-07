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
import { formatDate } from "@/lib/utils";

function statusTone(status: string): string {
  if (status === "valid")
    return "bg-emerald-50 text-emerald-700 ring-emerald-600/20";
  if (
    status === "reported_stolen" ||
    status === "blacklisted" ||
    status === "suspended"
  )
    return "bg-red-50 text-red-700 ring-red-600/20";
  return "bg-amber-50 text-amber-700 ring-amber-600/20";
}

const REGISTRY_STATUSES = [
  "valid",
  "reported_stolen",
  "blacklisted",
  "expired",
  "suspended",
];

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
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Registry</h1>
          <p className="mt-1 text-sm text-slate-500">
            Synthetic document registry (police / immigration / blacklist).
          </p>
        </div>
        {isAdmin ? (
          <Button onClick={() => setCreateOpen(true)}>Add entry</Button>
        ) : null}
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

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
          <div className="border-t border-slate-100 px-4 py-3">
            {lookupResult.found ? (
              <div className="space-y-2">
                {(lookupResult.entries ?? []).map((entry) => (
                  <div
                    key={entry.id}
                    className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm"
                  >
                    <Badge className={statusTone(entry.status)}>
                      {entry.status}
                    </Badge>
                    <span className="font-medium text-slate-800">
                      {entry.registry_type}
                    </span>
                    <span className="font-mono text-slate-600">
                      {entry.document_number}
                    </span>
                    <span className="text-xs text-slate-500">
                      {entry.holder_name ?? "no holder"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-600">{lookupResult.message}</div>
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
                <tr className="border-b border-slate-100 text-xs text-slate-500">
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Document number</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Holder</th>
                  <th className="px-5 py-3 font-medium">Country</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 text-slate-700">
                      {entry.registry_type}
                    </td>
                    <td className="px-5 py-3 font-mono text-slate-900">
                      {entry.document_number}
                    </td>
                    <td className="px-5 py-3">
                      <Badge className={statusTone(entry.status)}>
                        {entry.status}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {entry.holder_name ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {entry.issuing_country ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
          <form
            onSubmit={doCreate}
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
          >
            <h2 className="text-lg font-semibold text-slate-900">
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
