"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ScanLine } from "lucide-react";
import { api, errorFn, withQuery } from "@/lib/api";
import type { CaseListResponse, CaseRecord, NewCaseInput, RiskLevel } from "@/lib/types";
import { RiskBadge } from "@/components/risk";
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
import {
  cn,
  formatDate,
  STATUS_LABELS,
  STATUS_STYLES,
} from "@/lib/utils";

const PAGE_SIZE = 25;

interface CreateForm {
  description: string;
  check_registry: boolean;
  perform_forensics: boolean;
  verify_face_against: string;
  scenario: string;
}

const SCENARIO_OPTIONS: Array<{ key: string; label: string; note: string }> = [
  { key: "aadhaar", label: "Piyush · Aadhaar (default demo)", note: "genuine CLEAR" },
  { key: "", label: "Live / no scenario", note: "Run the real pipeline" },
  { key: "suresh", label: "Suresh Kumar", note: "CLEAR" },
  { key: "rajesh", label: "Rajesh Sharma", note: "EXPIRED" },
  { key: "amit", label: "Amit Singh", note: "MANUAL REVIEW" },
  { key: "priya", label: "Priya Verma", note: "CLEAR" },
  { key: "neha", label: "Neha Gupta", note: "MRZ mismatch" },
  { key: "rohit", label: "Rohit Mehta", note: "face mismatch" },
  { key: "anil", label: "Anil Kapoor", note: "tampering detected" },
  { key: "kavita", label: "Kavita Sharma", note: "registry unknown" },
];

export default function CasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseRecord[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<CreateForm>({
    description: "",
    check_registry: true,
    perform_forensics: true,
    verify_face_against: "",
    scenario: "aadhaar",
  });

  const load = useCallback(async () => {
    setError(null);
    try {
      const path = withQuery("/cases", {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        status_filter: statusFilter || null,
        risk_level: riskFilter || null,
      });
      const res = await api<CaseListResponse>(path);
      setCases(res.cases);
      setTotal(res.total);
    } catch (e) {
      setError(errorFn(e));
      setCases([]);
    }
  }, [page, statusFilter, riskFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function createCase() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: NewCaseInput = {
        case_description: form.description || undefined,
        check_registry: form.check_registry,
        perform_forensics: form.perform_forensics,
        verify_face_against: form.verify_face_against || undefined,
        scenario: form.scenario || undefined,
      };
      const res = await api<CaseRecord>("/cases", { method: "POST", json: payload });
      router.push(`/cases/${res.id}`);
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setSubmitting(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-6xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Cases</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Verification cases opened at the checkpoint.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => router.push("/verify")}>
            <ScanLine className="h-4 w-4" aria-hidden />
            New Verification
          </Button>
          <Button onClick={() => setCreating(true)}>New case</Button>
        </div>
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      <div className="flex flex-wrap items-end gap-4">
        <div>
          <Label>Status</Label>
          <Select
            className="w-48"
            value={statusFilter}
            onChange={(e) => {
              setPage(0);
              setStatusFilter(e.target.value);
            }}
          >
            <option value="">All</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label>Risk level</Label>
          <Select
            className="w-40"
            value={riskFilter}
            onChange={(e) => {
              setPage(0);
              setRiskFilter(e.target.value);
            }}
          >
            <option value="">All</option>
            {(["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"] as RiskLevel[]).map(
              (l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ),
            )}
          </Select>
        </div>
        <div className="text-xs text-[var(--muted)]">{total} case(s)</div>
      </div>

      <Card>
        <CardHeader title="Case list" subtitle="Newest first" />
        {!cases ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : cases.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="No cases match"
              hint="Adjust the filters or start a new verification."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[#f6f7fb]">
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Case</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Status</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Risk</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Created</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)]">Forensics</th>
                  <th className="px-6 py-3 text-[11.5px] font-semibold text-[var(--muted)] text-right">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {cases.map((c, idx) => (
                  <tr
                    key={c.id}
                    className={cn(
                      "table-row-alt transition-colors hover:bg-neutral-100/70",
                      idx % 2 === 1 && "bg-[#f8f9fc]",
                    )}
                  >
                    <td className="px-6 py-3.5">
                      <div className="font-semibold text-[var(--text)]">
                        {c.case_number}
                      </div>
                      <div className="max-w-xs truncate text-xs text-[var(--muted)]">
                        {c.description || "—"}
                      </div>
                    </td>
                    <td className="px-6 py-3.5">
                      <Badge className={STATUS_STYLES[c.status]}>
                        {STATUS_LABELS[c.status]}
                      </Badge>
                    </td>
                    <td className="px-6 py-3.5">
                      <RiskBadge level={c.risk_level} />
                    </td>
                    <td className="px-6 py-3.5 text-xs text-[var(--muted)]">
                      {formatDate(c.created_at)}
                    </td>
                    <td className="px-6 py-3.5 text-xs">
                      <Link
                        href={`/cases/${c.id}/forensics`}
                        className="font-medium text-neutral-500 hover:text-black"
                      >
                        Forensics →
                      </Link>
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      <Link
                        href={`/cases/${c.id}`}
                        className="text-xs font-medium text-neutral-500 hover:text-black"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-[var(--border)] px-5 py-3">
          <span className="text-xs text-[var(--muted)]">
            Showing {cases ? cases.length : 0} of {total}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Prev
            </Button>
            <span className="text-xs text-[var(--muted)]">
              {page + 1} / {totalPages}
            </span>
            <Button
              size="sm"
              variant="secondary"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>

      {creating ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--dark)]/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-[var(--card)] p-6 shadow-2xl text-[var(--text)] border border-[var(--border)]">
            <h2 className="text-lg font-semibold text-[var(--text)]">
              Open a new case
            </h2>
            <div className="mt-4 space-y-4">
              <div>
                <Label>Description</Label>
                <Input
                  placeholder="Synthetic traveler at border checkpoint"
                  value={form.description}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, description: e.target.value }))
                  }
                />
              </div>
              <div>
                <Label>Demo scenario (optional)</Label>
                <Select
                  value={form.scenario}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, scenario: e.target.value }))
                  }
                >
                  {SCENARIO_OPTIONS.map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label} — {o.note}
                    </option>
                  ))}
                </Select>
                {form.scenario ? (
                  <p className="mt-1 text-[11px] text-[var(--muted)]">
                    The pipeline will return the static demonstration result for{" "}
                    {form.scenario}. DEMO / SYNTHETIC DATA.
                  </p>
                ) : null}
              </div>
              <div>
                <Label>Verify face against identity (optional)</Label>
                <Input
                  placeholder="e.g. identity UUID or local identifier"
                  value={form.verify_face_against}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      verify_face_against: e.target.value,
                    }))
                  }
                />
              </div>
              {(
                [
                  {
                    key: "check_registry",
                    label: "Check document against registry",
                  },
                  { key: "perform_forensics", label: "Run forensic analysis" },
                ] as const
              ).map(({ key, label }) => (
                <label
                  key={key}
                    className="flex items-center gap-2 text-sm text-[var(--text)]"
                  >
                  <input
                    type="checkbox"
                    checked={form[key]}
                    onChange={(e) => {
                      const v = e.target.checked;
                      setForm((f) => ({ ...f, [key]: v }));
                    }}
                    className="h-4 w-4 rounded border-[var(--border)] text-neutral-500"
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => setCreating(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button onClick={createCase} disabled={submitting}>
                {submitting ? <Spinner /> : "Create case"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
