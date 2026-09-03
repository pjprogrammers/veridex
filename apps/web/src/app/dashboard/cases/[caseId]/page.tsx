"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, errorFn } from "@/lib/api";
import type {
  AuditEntry,
  AuditVerifyResponse,
  CaseDetail,
  CaseStatus,
  VerificationResult,
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

type Result =
  | { kind: "analysis"; analysis: Record<string, unknown> }
  | { kind: "verification"; verification: VerificationResult };

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 text-sm">
      <span className="shrink-0 text-slate-500">{label}</span>
      <span className="max-w-[60%] text-right font-medium text-slate-800">
        {value}
      </span>
    </div>
  );
}

function VerificationPanel({ result }: { result: VerificationResult }) {
  const risk = result.risk;
  const face = (result.face ?? {}) as Record<string, unknown>;
  const verification = (face.verification ?? {}) as Record<string, unknown>;
  const liveness = (face.liveness ?? {}) as Record<string, unknown>;
  const duplicate = (face.duplicate_identity ?? {}) as Record<string, unknown>;
  const mrz = (result.mrz ?? {}) as Record<string, unknown>;
  const mrzValid = mrz.valid === true || mrz.valid === "true";
  return (
    <div className="space-y-5">
      <Card className="p-5">
        <RiskGauge score={risk.score} level={risk.level} />
        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
          <span className="font-semibold text-slate-800">Explanation: </span>
          {risk.explanation}
        </div>
        {risk.factors.length > 0 ? (
          <div className="mt-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Contributing factors
            </div>
            <ul className="space-y-1.5">
              {risk.factors.map((f, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-slate-700"
                >
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700">
                    {i + 1}
                  </span>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader title="Document analysis" />
        <div className="p-3">
          <DetailRow label="Document type" value={result.document_type ?? "—"} />
          <DetailRow
            label="OCR confidence"
            value={
              result.ocr_confidence != null
                ? `${(result.ocr_confidence * 100).toFixed(0)}%`
                : "—"
            }
          />
          <DetailRow
            label="Quality score"
            value={
              result.quality?.score != null
                ? `${(Number(result.quality.score) * 100).toFixed(0)}%`
                : "—"
            }
          />
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Machine readable zone"
          subtitle="ICAO MRZ as parsed and check-digit validated"
          action={
            mrzValid ? (
              <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">
                valid
              </Badge>
            ) : (
              <Badge className="bg-slate-100 text-slate-600 ring-slate-500/20">
                {Object.keys(mrz).length ? "invalid / unreadable" : "—"}
              </Badge>
            )
          }
        />
        <div className="p-3">
          {Object.keys(mrz).length === 0 ? (
            <div className="text-sm text-slate-500">
              No MRZ detected for this document (only available for travel
              documents with a machine-readable zone).
            </div>
          ) : (
            (() => {
              const rawFields: Array<[string, string]> = [
                ["Format", String(mrz.format ?? "—")],
                ["Document type", String(mrz.document_type ?? "—")],
                ["Document number", String(mrz.document_number ?? "—")],
                ["Issuing country", String(mrz.issuing_country ?? "—")],
                ["Nationality", String(mrz.nationality ?? "—")],
                ["Surname", String(mrz.surname ?? "—")],
                ["Given names", String(mrz.given_names ?? "—")],
                ["Date of birth", String(mrz.date_of_birth ?? "—")],
                ["Sex", String(mrz.sex ?? "—")],
                ["Expiry date", String(mrz.expiry_date ?? "—")],
                [
                  "Check digits",
                  mrz.check_digits_valid === true
                    ? "all valid"
                    : mrz.check_digits_valid === false
                      ? "mismatch"
                      : "—",
                ],
              ];
              const fields = rawFields.filter(
                ([, v]) => v && v !== "—" && v !== "none",
              );
              return (
                <div>
                  <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
                    {fields.map(([label, value]) => (
                      <DetailRow key={label} label={label} value={value} />
                    ))}
                  </div>
                  {Array.isArray(mrz.raw_lines) ? (
                    <div className="mt-3 rounded-lg bg-slate-900 px-4 py-3 font-mono text-xs leading-6 text-emerald-200">
                      {((mrz.raw_lines as unknown[]) ?? []).map((line, i) => (
                        <div key={i}>{String(line)}</div>
                      ))}
                    </div>
                  ) : null}
                  {Array.isArray(mrz.errors) && mrz.errors.length > 0 ? (
                    <p className="mt-2 text-xs text-red-600">
                      {String((mrz.errors as unknown[]).join(", "))}
                    </p>
                  ) : null}
                </div>
              );
            })()
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Forensics" subtitle="Potential tampering signals" />
        <div className="p-4">
          {result.forensics ? (
            <>
              <div className="mb-3">
                <Badge
                  className={
                    (Number(result.forensics.overall_score) ?? 0) > 0.5
                      ? "bg-red-50 text-red-700 ring-red-600/20"
                      : "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                  }
                >
                  Overall signal:{" "}
                  {(Number(result.forensics.overall_score) * 100).toFixed(0)}%
                </Badge>
              </div>
              {Array.isArray(result.forensics.flags) ? (
                (result.forensics.flags as string[]).map((flag, i) => (
                  <div
                    key={i}
                    className="mb-1.5 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700"
                  >
                    {flag}
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-600">
                  {String(result.forensics.summary ?? "No notable signals")}
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-500">Not performed.</div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Face verification" />
        <div className="p-3">
          <DetailRow
            label="Status"
            value={String(verification.status ?? "Not performed")}
          />
          <DetailRow
            label="Similarity"
            value={
              verification.similarity != null
                ? `${(Number(verification.similarity) * 100).toFixed(0)}%`
                : "—"
            }
          />
          <DetailRow
            label="Liveness"
            value={String(liveness.decision ?? "—")}
          />
          <DetailRow
            label="Duplicate identity"
            value={String(duplicate.matched ?? "—")}
          />
        </div>
      </Card>

      {result.field_validation ? (
        <Card>
          <CardHeader title="Field & cross-validation" />
          <div className="space-y-3 p-4">
            <pre className="whitespace-pre-wrap font-mono text-xs text-slate-600">
              {JSON.stringify(result.field_validation, null, 2)}
            </pre>
            {result.cross_validation ? (
              <pre className="whitespace-pre-wrap border-t border-slate-100 pt-3 font-mono text-xs text-slate-600">
                {JSON.stringify(
                  {
                    document_number_match:
                      (result.cross_validation as Record<string, unknown>)
                        ?.document_number ?? null,
                    ...((result.cross_validation as Record<string, unknown>) ?? {}),
                  },
                  null,
                  2,
                )}
              </pre>
            ) : null}
          </div>
        </Card>
      ) : null}

      <Alert tone="info" title="Officer note">
        {result.recommendation} {result.disclaimer}
      </Alert>
    </div>
  );
}

function AnalysisPanel({ analysis }: { analysis: Record<string, unknown> }) {
  return (
    <Card>
      <CardHeader title="Pipeline analysis" />
      <div className="p-4">
        <pre className="whitespace-pre-wrap font-mono text-xs text-slate-600">
          {JSON.stringify(analysis, null, 2)}
        </pre>
      </div>
    </Card>
  );
}

export default function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = params.caseId;

  const [data, setData] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [auditVerify, setAuditVerify] = useState<AuditVerifyResponse | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
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
      setData(await api<CaseDetail>(`/cases/${caseId}/status`, {
        method: "PATCH",
        json: { status },
      }));
      setAudit(await api<AuditEntry[]>(`/audit?case_id=${caseId}&limit=200`));
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

  async function runAnalyze() {
    if (!selectedDoc) return;
    setBusy("analyze");
    setResult(null);
    setError(null);
    try {
      const res = await api<{ success: boolean; analysis: Record<string, unknown> }>(
        `/cases/${caseId}/documents/${selectedDoc.id}/analyze`,
        { method: "POST" },
      );
      setResult({ kind: "analysis", analysis: res.analysis });
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
    setResult(null);
    setError(null);
    try {
      const fd = new FormData();
      if (liveFace) fd.append("live_face", liveFace);
      fd.append("check_registry", "true");
      const res = await api<{ success: boolean; verification: VerificationResult }>(
        `/verification/${selectedDoc.id}/full`,
        { method: "POST", formData: fd },
      );
      setResult({ kind: "verification", verification: res.verification });
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
          href="/dashboard/cases"
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
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href="/dashboard/cases"
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
        </div>
        <div className="flex items-center gap-3">
          <RiskBadge level={data.risk_level} />
          <div className="flex items-center gap-2">
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
            {busy === "audit" ? <Spinner /> : null}
          </div>
        </div>
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      <Card>
        <CardHeader
          title="Documents"
          subtitle="Upload an identity or travel document image"
          action={
            <>
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/tiff,application/pdf"
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
              hint="Upload a document, then run the analysis pipeline and full verification."
            />
          </div>
        ) : (
          <ul className="divide-y divide-slate-50">
            {data.documents.map((doc) => {
              const active = doc.id === selectedDocId;
              return (
                <li key={doc.id}>
                  <button
                    onClick={() => {
                      setSelectedDocId(doc.id);
                      setResult(null);
                    }}
                    className={`flex w-full items-center justify-between gap-4 px-5 py-3 text-left transition-colors ${
                      active ? "bg-indigo-50/60" : "hover:bg-slate-50"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                        {doc.document_type || "Document"}
                        {active ? (
                          <Badge className="bg-indigo-50 text-indigo-700 ring-indigo-600/20">
                            selected
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-500">
                        <span>{doc.mime_type}</span>
                        <span>{formatBytes(doc.file_size)}</span>
                        <span className="font-mono">
                          {doc.content_hash.slice(0, 12)}…
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-xs">
                      <div className="text-slate-500">
                        quality{" "}
                        {doc.quality_score != null
                          ? `${Math.round(doc.quality_score * 100)}%`
                          : "—"}
                      </div>
                      <div className="mt-0.5 text-slate-400">
                        {formatDate(doc.created_at)}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

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
            <Button
              variant="secondary"
              disabled={busy !== null}
              onClick={runAnalyze}
            >
              {busy === "analyze" ? <Spinner /> : null}
              Run document analysis
            </Button>
            <Button disabled={busy !== null} onClick={runFullVerify}>
              {busy === "verify" ? <Spinner /> : null}
              Full verification
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
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                  live face: {liveFace.name}
                  <button onClick={() => setLiveFace(null)}>✕</button>
                </span>
              ) : (
                <span className="text-xs font-medium text-indigo-600 hover:text-indigo-500">
                  + attach live face
                </span>
              )}
            </label>
          </div>
        </Card>
      ) : (
        <EmptyState title="Select a document to begin verification" />
      )}

      {result ? (
        result.kind === "verification" ? (
          <VerificationPanel result={result.verification} />
        ) : (
          <AnalysisPanel analysis={result.analysis} />
        )
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
            className={`border-b px-5 py-3 ${
              auditVerify.valid
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800"
            }`}
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
                  <span title="previous hash">prev: {entry.previous_hash ?? "—"}</span>
                  <span title="current hash">cur: {entry.current_hash.slice(0, 16)}…</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}