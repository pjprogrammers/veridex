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
  RiskReasons,
  RiskRecommendations,
  type RiskFactorItem,
} from "@/components/risk-reasons";
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
          className="mt-4 inline-block text-sm text-neutral-500 hover:text-black"
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
    <div className="mx-auto max-w-6xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href="/cases"
            className="text-xs font-medium text-neutral-500 hover:text-black"
          >
            ← All cases
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)]">
            {data.case_number}
          </h1>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            {data.description || "No description"} · created{" "}
            {formatDate(data.created_at)}
          </p>
          <div className="mt-2">
            <Link
              href={`/cases/${caseId}/forensics`}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-500 hover:text-black"
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
              <p className="text-sm text-[var(--muted)]">
                Run full verification to assess risk.
              </p>
            )}
            <RiskReasons factors={riskReasonsFor(data, verification)} className="mt-5" />
            <RiskRecommendations
              recommendations={riskRecommendationsFor(data, verification)}
              explanation={riskExplanationFor(data, verification)}
            />
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
            <ul className="divide-y divide-[var(--border)]">
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
                        active ? "bg-neutral-200/60" : "hover:bg-[#f6f7fb]",
                      )}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
                          {doc.document_type || "Document"}
                        </div>
                        <div className="mt-0.5 flex items-center gap-3 text-xs text-[var(--muted)]">
                          <span>{doc.mime_type}</span>
                          <span>{formatBytes(doc.file_size)}</span>
                        </div>
                      </div>
                      <div className="shrink-0 text-right text-xs">
                        <div className="text-[var(--muted)]">
                          quality{" "}
                          {doc.quality_score != null
                            ? `${Math.round(doc.quality_score * 100)}%`
                            : "—"}
                        </div>
                        <Link
                          href={`/cases/${caseId}/forensics?doc=${doc.id}`}
                          className="mt-1 inline-block font-medium text-neutral-500 hover:text-black"
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
            <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--text)]">
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
                  className="inline-flex items-center gap-1.5 rounded-full bg-neutral-200/70 px-2.5 py-0.5 text-xs font-medium text-neutral-600 ring-1 ring-inset ring-neutral-400/40"
                >
                  live face: {liveFace.name}
                  <button type="button" onClick={() => setLiveFace(null)}>
                    ✕
                  </button>
                </span>
              ) : (
                <span className="text-xs font-medium text-neutral-500 hover:text-black">
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
            <span className="text-sm text-[var(--text)]">
              Document:{" "}
              <span className="font-medium text-[var(--text)]">
                {verification.document_type || "—"}
              </span>
            </span>
            <span className="text-sm text-[var(--text)]">
              OCR confidence:{" "}
              <span className="font-medium text-[var(--text)]">
                {verification.ocr_confidence != null
                  ? `${(verification.ocr_confidence * 100).toFixed(0)}%`
                  : "—"}
              </span>
            </span>
            <span className="text-sm text-[var(--text)]">
              Recommendation:{" "}
              <span className="font-medium text-[var(--text)]">
                {verification.recommendation || "—"}
              </span>
            </span>
            <span className="text-sm text-[var(--text)]">
              Face match:{" "}
              <span className="font-medium text-[var(--text)]">
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
                ? "border-neutral-300 bg-neutral-200/70 text-neutral-600"
                : "border-neutral-700 bg-neutral-900/10 text-black",
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
          <ul className="divide-y divide-[var(--border)]">
            {audit.map((entry) => (
              <li key={entry.id} className="px-5 py-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
                      #{entry.id}
                    </Badge>
                    <span className="text-sm font-medium text-[var(--text)]">
                      {entry.action}
                    </span>
                    {entry.actor_role ? (
                      <Badge className="bg-neutral-200/60 text-neutral-500 ring-neutral-400/40">
                        {entry.actor_role}
                      </Badge>
                    ) : null}
                  </div>
                  <span className="text-xs text-[var(--muted)]">
                    {formatDate(entry.timestamp)}
                  </span>
                </div>
                {Object.keys(entry.payload ?? {}).length > 0 ? (
                  <pre className="mt-1.5 whitespace-pre-wrap font-mono text-[11px] text-[var(--muted)]">
                    {JSON.stringify(entry.payload, null, 2)}
                  </pre>
                ) : null}
                <div className="mt-1.5 flex items-center gap-3 font-mono text-[10px] text-[var(--muted)]">
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

function metadataOf(data: CaseDetail | null): Record<string, unknown> | null {
  return data?.case_metadata ?? null;
}

function isFactorLike(v: unknown): v is RiskFactorItem {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function riskReasonsFor(
  data: CaseDetail | null,
  verification: VerificationReport | null,
): RiskFactorItem[] {
  if (Array.isArray(verification?.risk?.factors)) {
    return verification.risk.factors;
  }
  const stored = metadataOf(data)?.["risk_factors"];
  if (Array.isArray(stored)) {
    return stored.map((f) => (isFactorLike(f) ? f : { detail: String(f) }));
  }
  return [];
}

function riskRecommendationsFor(
  data: CaseDetail | null,
  verification: VerificationReport | null,
): string[] {
  if (Array.isArray(verification?.risk?.recommendations)) {
    return verification.risk.recommendations;
  }
  const stored = metadataOf(data)?.["risk_recommendations"];
  return Array.isArray(stored) ? stored.map(String) : [];
}

function riskExplanationFor(
  data: CaseDetail | null,
  verification: VerificationReport | null,
): string | null {
  const live = verification?.risk?.explanation;
  if (live) return live;
  const stored = metadataOf(data)?.["risk_explanation"];
  return typeof stored === "string" ? stored : null;
}
