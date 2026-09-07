"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Fingerprint, Scale } from "lucide-react";
import { api, errorFn } from "@/lib/api";
import type {
  AuditEntry,
  AuditVerifyResponse,
  CaseDetail,
  CaseStatus,
  VerificationReport,
} from "@/lib/types";
import { RiskBadge, RiskGauge } from "@/components/risk";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Select,
  Skeleton,
  Spinner,
} from "@/components/ui";
import {
  cn,
  formatBytes,
  formatDate,
  STATUS_LABELS,
} from "@/lib/utils";

const STATUSES: CaseStatus[] = [
  "in_review",
  "under_examination",
  "cleared",
  "flagged",
  "closed",
];

export default function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = params.caseId;

  const [data, setData] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [auditVerify, setAuditVerify] = useState<AuditVerifyResponse | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [verification, setVerification] = useState<VerificationReport | null>(null);
  const [liveFace, setLiveFace] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const detail = await api<CaseDetail>(`/cases/${caseId}`);
      setData(detail);
      setSelectedDocId((cur) => {
        if (cur && detail.documents.some((d) => d.id === cur)) return cur;
        return detail.documents[0]?.id ?? null;
      });
      setAudit(await api<AuditEntry[]>(`/audit?case_id=${caseId}&limit=200`));
    } catch (e) {
      setError(errorFn(e));
    }
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  const selectedDoc = data?.documents.find((d) => d.id === selectedDocId) ?? null;

  async function changeStatus(status: CaseStatus) {
    setStatusBusy(true);
    setError(null);
    try {
      await api(`/cases/${caseId}/status`, {
        method: "PATCH",
        json: { status },
      });
      await load();
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setStatusBusy(false);
    }
  }

  async function uploadDocument(file: File) {
    setBusy("upload");
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api(`/cases/${caseId}/documents`, { method: "POST", formData: fd });
      await load();
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setBusy(null);
    }
  }

  async function runFullVerify() {
    if (!selectedDoc) return;
    setBusy("verify");
    setVerification(null);
    setError(null);
    try {
      const fd = new FormData();
      if (liveFace) fd.append("live_face", liveFace);
      fd.append("check_registry", "true");
      const res = await api<{ success: boolean; verification: VerificationReport }>(
        `/verification/${selectedDoc.id}/full?check_registry=true`,
        { method: "POST", formData: fd },
      );
      setVerification(res.verification);
      await load();
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setBusy(null);
    }
  }

  async function verifyAuditChain() {
    setBusy("audit");
    setError(null);
    try {
      setAuditVerify(await api<AuditVerifyResponse>(`/audit/verify/${caseId}`));
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setBusy(null);
    }
  }

  if (error && !data) {
    return (
      <div className="mx-auto max-w-4xl">
        <Alert title="Could not load case">{error}</Alert>
        <Link
          href="/cases"
          className="mt-4 inline-block text-sm text-indigo-600 hover:text-indigo-500"
        >
          ← Back to cases
        </Link>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <Skeleton className="h-10 w-56" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href="/cases"
            className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
          >
            ← All cases
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            {data.case_number}
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {data.description || "No description"} · created{" "}
            {formatDate(data.created_at)}
          </p>
          <div className="mt-2">
            <Link
              href={`/cases/${caseId}/forensics`}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-500"
            >
              <Fingerprint className="h-3.5 w-3.5" aria-hidden />
              Open forensics analysis →
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <RiskBadge level={data.risk_level} />
          <Select
            className="h-9 w-48 text-sm"
            value={data.status}
            onChange={(e) => changeStatus(e.target.value as CaseStatus)}
            disabled={statusBusy}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader title="Risk assessment" action={<RiskBadge level={data.risk_level} />} />
          <div className="p-5">
            {verification ? (
              <RiskGauge
                score={verification.risk?.score ?? data.risk_score ?? 0}
                level={verification.risk?.level ?? data.risk_level ?? "UNKNOWN"}
              />
            ) : data.risk_score != null ? (
              <RiskGauge
                score={data.risk_score}
                level={data.risk_level ?? "UNKNOWN"}
              />
            ) : (
              <p className="text-sm text-slate-500">
                Run full verification to assess risk.
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Documents"
            subtitle="Upload an identity or travel document image"
            action={
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadDocument(f);
                    e.target.value = "";
                  }}
                />
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy === "upload"}
                  onClick={() => fileRef.current?.click()}
                >
                  {busy === "upload" ? <Spinner /> : "Upload document"}
                </Button>
              </>
            }
          />
          {data.documents.length === 0 ? (
            <div className="p-5">
              <EmptyState
                title="No documents uploaded"
                hint="Upload a document, then run the full verification pipeline."
              />
            </div>
          ) : (
            <ul className="divide-y divide-slate-50">
              {data.documents.map((doc) => {
                const active = doc.id === selectedDocId;
                return (
                  <li key={doc.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedDocId(doc.id);
                        setVerification(null);
                      }}
                      className={cn(
                        "flex w-full items-center justify-between gap-4 px-5 py-3 text-left transition-colors",
                        active ? "bg-indigo-50/60" : "hover:bg-slate-50",
                      )}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                          {doc.document_type || "Document"}
                        </div>
                        <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-500">
                          <span>{doc.mime_type}</span>
                          <span>{formatBytes(doc.file_size)}</span>
                        </div>
                      </div>
                      <div className="shrink-0 text-right text-xs">
                        <div className="text-slate-500">
                          quality{" "}
                          {doc.quality_score != null
                            ? `${Math.round(doc.quality_score * 100)}%`
                            : "—"}
                        </div>
                        <Link
                          href={`/cases/${caseId}/forensics?doc=${doc.id}`}
                          className="mt-1 inline-block font-medium text-indigo-600 hover:text-indigo-500"
                        >
                          Forensics →
                        </Link>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      {selectedDoc ? (
        <Card>
          <CardHeader
            title="Verification actions"
            subtitle={
              selectedDoc.document_type || "Document selected, type pending analysis"
            }
            action={<RiskBadge level={data.risk_level} />}
          />
          <div className="flex flex-wrap items-center gap-3 p-4">
            <Button disabled={busy !== null} onClick={runFullVerify}>
              {busy === "verify" ? <Spinner /> : null}
              <Scale className="h-4 w-4" aria-hidden /> Full verification
            </Button>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
              <input
                type="file"
                accept="image/jpeg,image/png"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setLiveFace(f);
                  e.target.value = "";
                }}
              />
              {liveFace ? (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20"
                >
                  live face: {liveFace.name}
                  <button type="button" onClick={() => setLiveFace(null)}>
                    ✕
                  </button>
                </span>
              ) : (
                <span className="text-xs font-medium text-indigo-600 hover:text-indigo-500">
                  + attach live face
                </span>
              )}
            </label>
          </div>
        </Card>
      ) : null}

      {verification ? (
        <Card>
          <CardHeader
            title="Verification summary"
            action={<RiskBadge level={verification.risk?.level ?? "UNKNOWN"} />}
          />
          <div className="grid gap-x-8 gap-y-3 p-5 md:grid-cols-2">
            <span className="text-sm text-slate-600">
              Document:{" "}
              <span className="font-medium text-slate-800">
                {verification.document_type || "—"}
              </span>
            </span>
            <span className="text-sm text-slate-600">
              OCR confidence:{" "}
              <span className="font-medium text-slate-800">
                {verification.ocr_confidence != null
                  ? `${(verification.ocr_confidence * 100).toFixed(0)}%`
                  : "—"}
              </span>
            </span>
            <span className="text-sm text-slate-600">
              Recommendation:{" "}
              <span className="font-medium text-slate-800">
                {verification.recommendation || "—"}
              </span>
            </span>
            <span className="text-sm text-slate-600">
              Face match:{" "}
              <span className="font-medium text-slate-800">
                {String(
                  (
                    ((verification.face ?? {}) as Record<string, unknown>)
                      .verification as Record<string, unknown> | undefined
                  )?.verdict ?? "not performed",
                )}
              </span>
            </span>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Audit trail"
          subtitle="Tamper-evident SHA-256 chained log"
          action={
            <Button size="sm" variant="secondary" onClick={verifyAuditChain}>
              {busy === "audit" ? <Spinner /> : "Verify chain integrity"}
            </Button>
          }
        />
        {auditVerify ? (
          <div
            className={cn(
              "border-b px-5 py-3",
              auditVerify.valid
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800",
            )}
          >
            <div className="text-sm font-semibold">
              {auditVerify.valid ? "Chain integrity confirmed" : "Chain VIOLATED"}
            </div>
            <div className="text-xs opacity-90">{auditVerify.message}</div>
            {auditVerify.integrity_issues.length > 0 ? (
              <pre className="mt-2 font-mono text-[11px]">
                {JSON.stringify(auditVerify.integrity_issues, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}
        {!audit ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : audit.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No audit entries yet" />
          </div>
        ) : (
          <ul className="divide-y divide-slate-50">
            {audit.map((entry) => (
              <li key={entry.id} className="px-5 py-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-slate-100 text-slate-700 ring-slate-500/20">
                      #{entry.id}
                    </Badge>
                    <span className="text-sm font-medium text-slate-900">
                      {entry.action}
                    </span>
                    {entry.actor_role ? (
                      <Badge className="bg-indigo-50 text-indigo-700 ring-indigo-600/20">
                        {entry.actor_role}
                      </Badge>
                    ) : null}
                  </div>
                  <span className="text-xs text-slate-400">
                    {formatDate(entry.timestamp)}
                  </span>
                </div>
                {Object.keys(entry.payload ?? {}).length > 0 ? (
                  <pre className="mt-1.5 whitespace-pre-wrap font-mono text-[11px] text-slate-500">
                    {JSON.stringify(entry.payload, null, 2)}
                  </pre>
                ) : null}
                <div className="mt-1.5 flex items-center gap-3 font-mono text-[10px] text-slate-400">
                  <span>prev: {entry.previous_hash ?? "—"}</span>
                  <span>cur: {entry.current_hash?.slice(0, 16)}…</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
