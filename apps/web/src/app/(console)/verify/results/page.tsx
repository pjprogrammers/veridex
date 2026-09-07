"use client";

import { useCallback, useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Camera,
  FileSearch,
  Fingerprint,
  Landmark,
  Radar,
  RefreshCw,
  ScanLine,
  ShieldCheck,
  Type,
  UserCheck,
} from "lucide-react";
import { api, errorFn } from "@/lib/api";
import { getVerificationReport, runFullVerification, getDocument, extractMRZ } from "@/lib/verify";
import type {
  CaseDetail,
  ClassificationResult,
  MRZExtractionResponse,
  OCRExtractionResult,
  VerificationReport,
  Verdict,
} from "@/lib/types";
import { RiskBadge, RiskGauge } from "@/components/risk";
import { ForensicsAnalysis } from "@/components/forensics";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Skeleton,
  Spinner,
  StatDisplay,
} from "@/components/ui";
import { cn, formatDate } from "@/lib/utils";

export default function ResultsPage() {
  return (
    <Suspense fallback={<ResultsLoading />}>
      <ResultsInner />
    </Suspense>
  );
}

function ResultsLoading() {
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

function ResultsInner() {
  const params = useSearchParams();
  const caseId = params.get("case") ?? "";
  const docId = params.get("doc") ?? "";

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [classification, setClassification] = useState<ClassificationResult | null>(null);
  const [ocr, setOcr] = useState<OCRExtractionResult | null>(null);
  const [mrz, setMrz] = useState<MRZExtractionResponse | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [mrzLoading, setMrzLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId || !docId) {
      setError("Missing case or document reference in the URL.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const detail = await api<CaseDetail>(`/cases/${caseId}`);
      setCaseDetail(detail);
      // Fetch classification data if available.
      try {
        const doc = await getDocument(docId);
        if (doc.classification) {
          setClassification(doc.classification);
        }
        if (doc.ocr_extracted_fields?.fields) {
          setOcr({
            fields: doc.ocr_extracted_fields.fields,
            raw_text: doc.ocr_extracted_fields.raw_text ?? "",
            processing_time_ms: doc.ocr_extracted_fields.processing_time_ms ?? 0,
            engine: "",
          });
        }
      } catch {
        // Classification may not exist yet — not an error.
      }
      const stored = await getVerificationReport(docId);
      // Keep the existing report when re-running (avoid a flash of empty).
      if (stored.verified) {
        setReport(stored.verification);
        setVerified(true);
      } else {
        setReport(null);
        setVerified(false);
      }
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setLoading(false);
    }
  }, [caseId, docId]);

  useEffect(() => {
    load();
  }, [load]);

  async function runNow() {
    setRunning(true);
    setError(null);
    try {
      const full = await runFullVerification(docId, { checkRegistry: true });
      setReport(full.verification);
      setVerified(true);
      await api(`/cases/${caseId}/status`, {
        method: "PATCH",
        json: { status: deriveCaseStatus(full.verification) },
      }).catch(() => {});
      setCaseDetail(await api<CaseDetail>(`/cases/${caseId}`));
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setRunning(false);
    }
  }

  async function runMrz() {
    setMrzLoading(true);
    setError(null);
    try {
      const result = await extractMRZ(docId);
      setMrz(result);
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setMrzLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Fingerprint className="h-4 w-4 animate-pulse" /> Loading report…
        </div>
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  if (error && !report && verified !== true) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Alert title="Could not load verification results">
          {error}
        </Alert>
        <Link
          href={`/cases/${caseId}`}
          className="inline-flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-500"
        >
          ← Back to case
        </Link>
      </div>
    );
  }

  // No stored report yet — prompt with a clean empty state instead of recomputing.
  if (verified === false && !report) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <Link
            href={`/cases/${caseId}`}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
          >
            ← Back to case {caseDetail?.case_number ?? ""}
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            Verification Results
          </h1>
        </div>
        {error ? <Alert title="Request failed">{error}</Alert> : null}
        <Card>
          <EmptyState
            title="No verification report yet"
            hint="A report has not been generated for this document. Run verification to produce one."
          />
          <div className="flex items-center justify-center gap-3 pb-6">
            <Button onClick={runNow} disabled={running}>
              {running ? <Spinner /> : <ShieldCheck className="h-4 w-4" aria-hidden />}
              Run verification
            </Button>
            <Button variant="secondary" onClick={() => window.history.back()}>
              Cancel
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Alert title="Could not produce verification results">
          {error}
        </Alert>
        <Link
          href="/verify"
          className="inline-flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-500"
        >
          ← New verification
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header + decision */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href={`/cases/${caseId}`}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
          >
            ← Back to case {caseDetail?.case_number ?? ""}
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            Verification Results
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {caseDetail?.case_number} · {formatDate(caseDetail?.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {running ? (
            <span className="inline-flex items-center gap-2 text-sm text-slate-500">
              <Spinner /> Re-running…
            </span>
          ) : null}
          <Button variant="secondary" size="sm" onClick={runNow} disabled={running}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            Re-run verification
          </Button>
          <DecisionBadge decision={deriveDecision(report)} />
        </div>
      </div>

      <RiskSection report={report} />

      {classification ? <ClassificationSection classification={classification} /> : null}

      <div className="grid gap-6 md:grid-cols-2">
        <DocumentSection report={report} />
        <ValidationSection report={report} />
        <ForensicsSection report={report} />
        <BiometricsSection report={report} />
        <RegistrySection report={report} />
      </div>

      {ocr && ocr.fields.length > 0 ? <OCRSection ocr={ocr} /> : null}

      <MRZSection
        result={mrz}
        loading={mrzLoading}
        onRun={runMrz}
      />

      <ForensicsAnalysis documentId={docId} />

      <Alert tone="info" title="Decision-support disclaimer">
        {report.risk?.explanation} This is a decision-support analysis. It does
        not prove authenticity or fraud. Manual review by an officer is required
        before any enforcement action.
      </Alert>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function deriveDecision(report: VerificationReport): Verdict {
  const level = report.risk?.level ?? "UNKNOWN";
  const score = report.risk?.score ?? 0;
  if (level === "CRITICAL") return "HIGH_RISK_ALERT";
  if (level === "HIGH") return "HIGH_RISK_ALERT";
  if (level === "MEDIUM") return "MANUAL_REVIEW";
  if (score > 0.55) return "MANUAL_REVIEW";
  if (level === "LOW") return "CLEAR";
  return "INCONCLUSIVE";
}

function deriveCaseStatus(report: VerificationReport): string {
  const level = report.risk?.level ?? "UNKNOWN";
  if (level === "HIGH" || level === "CRITICAL") return "flagged";
  if (level === "MEDIUM") return "in_review";
  return "in_review";
}

const DECISION_STYLES: Record<Verdict, { label: string; cls: string }> = {
  CLEAR: {
    label: "CLEAR",
    cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  },
  MANUAL_REVIEW: {
    label: "MANUAL REVIEW",
    cls: "bg-amber-50 text-amber-700 ring-amber-600/20",
  },
  HIGH_RISK_ALERT: {
    label: "HIGH-RISK ALERT",
    cls: "bg-red-50 text-red-700 ring-red-600/20",
  },
  INCONCLUSIVE: {
    label: "INCONCLUSIVE",
    cls: "bg-slate-100 text-slate-600 ring-slate-500/20",
  },
};

function DecisionBadge({ decision }: { decision: Verdict }) {
  const s = DECISION_STYLES[decision];
  return (
    <Badge className={cn("px-3 py-1 text-xs font-semibold", s.cls)}>
      {s.label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function SectionCard({
  title,
  icon,
  action,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {icon}
          {title}
        </h2>
        {action}
      </div>
      <div className="flex-1 p-4">{children}</div>
    </Card>
  );
}

function RiskSection({ report }: { report: VerificationReport }) {
  const risk = report.risk;
  const factors = Array.isArray(risk?.factors) ? risk.factors : [];
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Radar className="h-4 w-4 text-indigo-500" aria-hidden />
          Risk Assessment
        </h2>
        <RiskBadge level={risk?.level ?? "UNKNOWN"} />
      </div>
      <div className="p-5">
        <RiskGauge
          score={risk?.score ?? 0}
          level={risk?.level ?? "UNKNOWN"}
        />
        {factors.length > 0 ? (
          <div className="mt-5">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Reasons
            </div>
            <ul className="space-y-1.5">
              {factors.map((f, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700"
                >
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-700">
                    {i + 1}
                  </span>
                  <span>
                    {String(f.label ?? f.detail ?? `Factor ${i + 1}`)}
                    {f.detail && f.label ? (
                      <span className="ml-1 text-slate-500">— {String(f.detail)}</span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {report.risk?.recommendations && report.risk.recommendations.length > 0 ? (
          <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
            <span className="font-semibold">Recommendations: </span>
            {report.risk.recommendations.join(". ")}
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function ClassificationSection({ classification }: { classification: ClassificationResult }) {
  const pct = Math.round(classification.confidence * 100);
  const typeLabel = classification.document_type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <FileSearch className="h-4 w-4 text-indigo-500" aria-hidden />
          Detected Document
        </h2>
        <Badge className="bg-indigo-50 text-indigo-700 ring-indigo-600/20">
          {typeLabel}
        </Badge>
      </div>
      <div className="p-5 space-y-4">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Confidence
          </div>
          <div className="flex items-center gap-3">
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400",
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-sm font-medium text-slate-700">{pct}%</span>
          </div>
        </div>
        <StatDisplay label="Method" value={classification.method} />
        {classification.template_id ? (
          <StatDisplay label="Template" value={classification.template_id} />
        ) : null}
        {classification.warnings.length > 0 ? (
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Warnings
            </div>
            <ul className="space-y-1.5">
              {classification.warnings.map((w, i) => (
                <li
                  key={i}
                  className="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-1.5 text-sm text-amber-700"
                >
                  <span className="font-medium">{w.replace(/_/g, " ")}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function MRZSection({
  result,
  loading,
  onRun,
}: {
  result: MRZExtractionResponse | null;
  loading: boolean;
  onRun: () => void;
}) {
  const validChip = result
    ? result.mrz.mrz_valid
      ? "VALID"
      : result.mrz.mrz_detected
        ? "CHECK FAILED"
        : "NOT DETECTED"
    : null;
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <ScanLine className="h-4 w-4 text-indigo-500" aria-hidden />
          MRZ Analysis
        </h2>
        <div className="flex items-center gap-2">
          {result && validChip ? (
            <Badge
              className={
                result.mrz.mrz_valid
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                  : result.mrz.mrz_detected
                    ? "bg-red-50 text-red-700 ring-red-600/20"
                    : "bg-slate-100 text-slate-600 ring-slate-500/20"
              }
            >
              {validChip}
            </Badge>
          ) : null}
          <Button variant="secondary" size="sm" onClick={onRun} disabled={loading}>
            {loading ? <Spinner /> : null}
            {result ? "Re-run MRZ" : "Run MRZ analysis"}
          </Button>
        </div>
      </div>
      <div className="space-y-5 p-5">
        {!result ? (
          loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Spinner /> Detecting and validating the machine-readable zone…
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              The machine-readable zone (MRZ) has not been extracted yet. Run
              MRZ analysis to detect, parse, and validate the ICAO 9303 zone.
            </p>
          )
        ) : (
          <>
            {!result.mrz.mrz_detected ? (
              <p className="text-sm text-slate-500">
                No dense MRZ region was detected in this document
                {result.mrz.warnings.length > 0
                  ? ` (${result.mrz.warnings.join(", ")})`
                  : ""}
                .
              </p>
            ) : (
              <>
                {result.comparison ? (
                  <VisualMRZComparison comparison={result.comparison} />
                ) : null}

                <div className="grid gap-4 md:grid-cols-2">
                  <Card className="!p-0 shadow-none">
                    <div className="border-b border-slate-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Parsed fields
                    </div>
                    <div className="p-4">
                      <table className="w-full text-sm">
                        <tbody>
                          {Object.entries(result.mrz.parsed_fields).map(([k, v]) => (
                            <tr key={k} className="border-b border-slate-50 last:border-0">
                              <td className="py-1.5 pr-3 text-slate-500">
                                {k.replace(/_/g, " ")}
                              </td>
                              <td className="py-1.5 font-medium text-slate-800">{v || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>

                  <Card className="!p-0 shadow-none">
                    <div className="border-b border-slate-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      ICAO check digits
                    </div>
                    <div className="p-4">
                      <table className="w-full text-sm">
                        <tbody>
                          {Object.entries(result.mrz.check_digits).map(([k, v]) => (
                            <tr key={k} className="border-b border-slate-50 last:border-0">
                              <td className="py-1.5 pr-3 text-slate-500">
                                {k.replace(/_/g, " ")}
                              </td>
                              <td className="py-1.5 text-right">
                                {v === true ? (
                                  <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">
                                    Valid
                                  </Badge>
                                ) : v === false ? (
                                  <Badge className="bg-red-50 text-red-700 ring-red-600/20">
                                    Invalid
                                  </Badge>
                                ) : (
                                  <span className="text-slate-400">—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </div>

                {result.mrz.raw_mrz.length > 0 ? (
                  <details className="group">
                    <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-indigo-600 hover:text-indigo-500">
                      View raw MRZ lines
                    </summary>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                      {result.mrz.raw_mrz.join("\n")}
                    </pre>
                  </details>
                ) : null}
              </>
            )}
          </>
        )}
      </div>
    </Card>
  );
}

function VisualMRZComparison({ comparison }: { comparison: MRZExtractionResponse["comparison"] }) {
  if (!comparison) return null;
  const severityStyles: Record<string, string> = {
    NONE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    LOW: "bg-amber-50 text-amber-700 ring-amber-600/20",
    MEDIUM: "bg-orange-50 text-orange-700 ring-orange-600/20",
    HIGH: "bg-red-50 text-red-700 ring-red-600/20",
  };
  return (
    <div className="rounded-xl border border-slate-100 p-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Visual vs MRZ comparison
        </div>
        <Badge className={severityStyles[comparison.severity] ?? severityStyles.NONE!}>
          {comparison.severity}
        </Badge>
      </div>
      <div className="mt-3 overflow-hidden rounded-lg border border-slate-100">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2 font-semibold">Field</th>
              <th className="px-3 py-2 font-semibold">Visual</th>
              <th className="px-3 py-2 font-semibold">MRZ</th>
              <th className="px-3 py-2 text-right font-semibold">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {comparison.comparisons.map((c) => (
              <tr key={c.field_name} className="border-b border-slate-50 last:border-0">
                <td className="px-3 py-2 text-slate-500">{c.field_name.replace(/_/g, " ")}</td>
                <td className="px-3 py-2 text-slate-700">{c.visual_value || "—"}</td>
                <td className="px-3 py-2 text-slate-700">{c.mrz_value || "—"}</td>
                <td className="px-3 py-2 text-right">
                  {c.verdict === "MATCH" ? (
                    <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">Match</Badge>
                  ) : c.verdict === "MISMATCH" ? (
                    <Badge className="bg-red-50 text-red-700 ring-red-600/20">Mismatch</Badge>
                  ) : (
                    <span className="text-slate-400">N/A</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {comparison.severity_reasons.length > 0 ? (
        <p className="mt-2 text-xs text-slate-500">
          Mismatch on: {comparison.severity_reasons.join(", ")}. Review required —
          OCR error or forgery may be present.
        </p>
      ) : null}
    </div>
  );
}

function OCRSection({ ocr }: { ocr: OCRExtractionResult }) {
  const displayFields = ocr.fields.filter((f) => f.value);
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Type className="h-4 w-4 text-indigo-500" aria-hidden />
          OCR Extraction
        </h2>
        {ocr.engine ? (
          <Badge className="bg-slate-100 text-slate-700 ring-slate-500/20">
            {ocr.engine}
          </Badge>
        ) : null}
      </div>
      <div className="p-5 space-y-5">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
          <div className="min-w-[240px] flex-1">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Average field confidence
            </div>
            <div className="flex items-center gap-3">
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    avgConfPct(ocr) >= 70
                      ? "bg-emerald-500"
                      : avgConfPct(ocr) >= 40
                        ? "bg-amber-500"
                        : "bg-red-400",
                  )}
                  style={{ width: `${avgConfPct(ocr)}%` }}
                />
              </div>
              <span className="text-sm font-medium text-slate-700">
                {avgConfPct(ocr)}%
              </span>
            </div>
          </div>
          {ocr.processing_time_ms > 0 ? (
            <StatDisplay
              label="Processing time"
              value={formatMs(ocr.processing_time_ms)}
            />
          ) : null}
        </div>

        {displayFields.length === 0 ? (
          <p className="text-sm text-slate-500">
            No structured fields were extracted from this document.
          </p>
        ) : (
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Extracted fields
            </div>
            <div className="overflow-hidden rounded-xl border border-slate-100">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-3 py-2 font-semibold">Field</th>
                    <th className="px-3 py-2 font-semibold">Value</th>
                    <th className="px-3 py-2 text-right font-semibold">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {displayFields.map((f, i) => (
                    <tr key={`${f.field_name}-${i}`} className="border-b border-slate-50">
                      <td className="px-3 py-2 text-slate-500">
                        {f.field_name.replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-2 font-medium text-slate-800">
                        {f.value}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                Math.round(f.confidence * 100) >= 70
                                  ? "bg-emerald-500"
                                  : Math.round(f.confidence * 100) >= 40
                                    ? "bg-amber-500"
                                    : "bg-red-400",
                              )}
                              style={{ width: `${Math.round(f.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="w-10 text-right text-xs font-medium text-slate-600">
                            {Math.round(f.confidence * 100)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {ocr.raw_text ? (
          <details className="group">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-indigo-600 hover:text-indigo-500">
              View raw OCR text
            </summary>
            <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
              {ocr.raw_text}
            </pre>
          </details>
        ) : null}
      </div>
    </Card>
  );
}

function avgConfPct(ocr: OCRExtractionResult): number {
  if (ocr.fields.length === 0) return 0;
  const avg =
    ocr.fields.reduce((sum, f) => sum + f.confidence, 0) / ocr.fields.length;
  return Math.round(avg * 100);
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

function DocumentSection({ report }: { report: VerificationReport }) {
  const fields = (report.extracted_fields ?? {}) as Record<string, unknown>;
  const quality = (report.quality ?? {}) as Record<string, unknown>;
  const qualityScore = Number(quality.overall_score ?? quality.score ?? NaN);
  return (
    <SectionCard
      title="Document"
      icon={<FileSearch className="h-4 w-4 text-indigo-500" aria-hidden />}
      action={
        <Badge className="bg-slate-100 text-slate-700 ring-slate-500/20">
          {report.document_type || "unknown"}
        </Badge>
      }
    >
      <StatDisplay label="Type" value={report.document_type || "—"} />
      {report.extracted_fields && "document_number" in fields ? (
        <StatDisplay label="Document number" value={String(fields.document_number)} />
      ) : null}
      {!isNaN(qualityScore) ? (
        <StatDisplay
          label="Quality"
          value={`${Math.round(qualityScore * 100)}%`}
        />
      ) : null}
      {report.extracted_fields ? (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Extracted fields
          </div>
          {Object.keys(fields).length === 0 ? (
            <p className="text-sm text-slate-500">No fields extracted yet.</p>
          ) : (
            <dl className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
              {Object.entries(fields).map(([k, v]) => (
                <div key={k} className="py-1 text-sm">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-medium text-slate-800">
                    {String(v ?? "—")}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      ) : null}
    </SectionCard>
  );
}

function verdictTone(verdict: string | undefined): string {
  const v = (verdict ?? "").toUpperCase();
  if (v === "PASS") return "bg-emerald-50 text-emerald-700 ring-emerald-600/20";
  if (v === "FAIL" || v === "MISMATCH")
    return "bg-red-50 text-red-700 ring-red-600/20";
  if (v === "WARN") return "bg-amber-50 text-amber-700 ring-amber-600/20";
  return "bg-slate-100 text-slate-600 ring-slate-500/20";
}

function ValidationSection({ report }: { report: VerificationReport }) {
  const validation = (report.field_validation ?? {}) as Record<string, unknown>;
  const cross = (report.cross_validation ?? {}) as Record<string, unknown>;
  const mrz = (report.mrz ?? {}) as Record<string, unknown>;
  const mrzValid = mrz.valid === true || mrz.valid === "true";

  const crossOverall = String(cross.overall ?? cross.overall_verdict ?? "PASS");

  return (
    <SectionCard
      title="Validation"
      icon={<UserCheck className="h-4 w-4 text-indigo-500" aria-hidden />}
      action={
        <Badge className={verdictTone(crossOverall)}>{crossOverall}</Badge>
      }
    >
      <StatDisplay
        label="OCR confidence"
        value={
          report.ocr_confidence != null
            ? `${(report.ocr_confidence * 100).toFixed(0)}%`
            : "—"
        }
      />
      <StatDisplay
        label="MRZ status"
        value={
          Object.keys(mrz).length === 0
            ? "not present"
            : mrzValid
              ? "valid"
              : "invalid / unreadable"
        }
      />
      <StatDisplay
        label="Field consistency"
        value={`${String(cross.checked ?? "?")} checked / ${String(
          cross.passed ?? "?",
        )} passed`}
      />
      <StatDisplay
        label="Expiry status"
        value={expiryStatus(validation, mrz)}
      />
      {Object.keys(validation).length > 0 ? (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Field checks
          </div>
          <ul className="space-y-1.5">
            {Object.entries(validation).map(([field, detail]) => {
              const d = (detail ?? {}) as Record<string, unknown>;
              const verdict = String(d.verdict ?? "—");
              return (
                <li
                  key={field}
                  className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm"
                >
                  <span className="text-slate-600">{field.replace(/_/g, " ")}</span>
                  <Badge className={verdictTone(verdict)}>{verdict}</Badge>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </SectionCard>
  );
}

function expiryStatus(
  validation: Record<string, unknown>,
  mrz: Record<string, unknown>,
): string {
  const expiry = validation["expiry_date"] as Record<string, unknown> | undefined;
  if (expiry?.reason === "document_expired") return "EXPIRED";
  if (expiry?.verdict === "FAIL") return "FAIL";
  if (mrz.valid === true || mrz.valid === "true") return "valid";
  if (mrz.expiry_date) return String(mrz.expiry_date);
  return "unknown";
}

function BiometricsSection({ report }: { report: VerificationReport }) {
  const face = (report.face ?? {}) as Record<string, unknown>;
  const verification = (face.verification ?? {}) as Record<string, unknown>;
  const liveness = (face.liveness ?? {}) as Record<string, unknown>;
  const duplicate = (face.duplicate_identity ?? {}) as Record<string, unknown>;
  const hasFaceData =
    Object.keys(verification).length > 0 ||
    Object.keys(liveness).length > 0 ||
    Object.keys(duplicate).length > 0;

  return (
    <SectionCard
      title="Biometrics"
      icon={<Camera className="h-4 w-4 text-indigo-500" aria-hidden />}
      action={
        verification.verdict === "match" ? (
          <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">
            match
          </Badge>
        ) : hasFaceData ? (
          <Badge className="bg-amber-50 text-amber-700 ring-amber-600/20">
            {String(verification.verdict ?? "review")}
          </Badge>
        ) : null
      }
    >
      {!hasFaceData ? (
        <p className="text-sm text-slate-500">
          No face data provided for this verification.
        </p>
      ) : (
        <div className="space-y-3">
          <StatDisplay
            label="Face similarity"
            value={
              verification.similarity != null
                ? `${(Number(verification.similarity) * 100).toFixed(1)}%`
                : "—"
            }
          />
          <StatDisplay
            label="Verification status"
            value={String(verification.verdict ?? "—")}
          />
          <StatDisplay
            label="Liveness"
            value={String(liveness.verdict ?? "—")}
          />
          {duplicate.matches_found != null ? (
            <StatDisplay
              label="Duplicate identity"
              value={String(duplicate.matches_found ?? 0)}
            />
          ) : null}
        </div>
      )}
    </SectionCard>
  );
}

function ForensicsSection({ report }: { report: VerificationReport }) {
  const forensics = (report.forensics ?? {}) as Record<string, unknown>;
  const flags = Array.isArray(forensics.flags) ? (forensics.flags as unknown[]) : [];
  const evidenceStatus =
    forensics.forensic_status === "sufficient_evidence"
      ? "sufficient_evidence"
      : "insufficient_evidence";
  const tampering = forensics.tampering_score;
  const hasValidatedScore =
    typeof tampering === "number" && Number.isFinite(tampering);
  return (
    <SectionCard
      title="Forensics"
      icon={<Radar className="h-4 w-4 text-indigo-500" aria-hidden />}
      action={
        evidenceStatus === "sufficient_evidence" ? (
          <Badge className="bg-orange-50 text-orange-700 ring-orange-600/20">
            validated signal
          </Badge>
        ) : (
          <Badge className="bg-slate-100 text-slate-600 ring-slate-500/20">
            experimental
          </Badge>
        )
      }
    >
      {!report.forensics ? (
        <p className="text-sm text-slate-500">Forensic analysis not performed.</p>
      ) : (
        <div className="space-y-3">
          <StatDisplay
            label="Tamper score"
            value={
              hasValidatedScore
                ? `${Math.round(tampering * 100)}%`
                : "not assessed (experimental)"
            }
          />
          {hasValidatedScore ? null : (
            <p className="text-xs text-slate-500">
              Forensic detectors are experimental/unvalidated; experimental
              signals below are research indicators, not a tampering verdict.
            </p>
          )}
          {flags.length > 0 ? (
            <>
              <div>
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Suspicious regions
                </div>
                <ul className="space-y-1.5">
                  {flags.map((f, i) => {
                    const flag = (f ?? {}) as Record<string, unknown>;
                    return (
                      <li
                        key={i}
                        className="flex items-center justify-between rounded-lg bg-red-50/60 px-3 py-1.5 text-sm"
                      >
                        <span className="text-red-700">
                          {String(flag.signal ?? flag.description ?? "region")}
                        </span>
                        <Badge
                          className={cn(
                            "bg-red-50 text-red-700 ring-red-600/20",
                            String(flag.severity ?? "LOW").toUpperCase() === "HIGH" &&
                              "bg-red-100",
                          )}
                        >
                          {String((flag.score ?? 0) as number * 100).slice(0, 4)}%
                        </Badge>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </>
          ) : null}
          {forensics.summary ? (
            <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              {String(forensics.summary)}
            </div>
          ) : null}
        </div>
      )}
    </SectionCard>
  );
}

function RegistrySection({ report }: { report: VerificationReport }) {
  const registry = (report.registry ?? {}) as Record<string, unknown>;
  const found = Number((registry as { count?: number }).count ?? 0);
  if (!report.registry) {
    return (
      <SectionCard
        title="Registry"
        icon={<Landmark className="h-4 w-4 text-indigo-500" aria-hidden />}
        action={<Badge className="bg-slate-100 text-slate-600 ring-slate-500/20">skipped</Badge>}
      >
        <p className="text-sm text-slate-500">
          Registry check was not run for this verification.
        </p>
      </SectionCard>
    );
  }
  return (
    <SectionCard
      title="Registry"
      icon={<Landmark className="h-4 w-4 text-indigo-500" aria-hidden />}
      action={
        registry.alert ? (
          <Badge className="bg-red-50 text-red-700 ring-red-600/20">alert</Badge>
        ) : (
          <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">
            clear
          </Badge>
        )
      }
    >
      <StatDisplay label="Status" value={found > 0 ? "found" : "not found"} />
      <StatDisplay label="Match result" value={String(registry.match ?? "—")} />
      {Array.isArray(registry.entries) && registry.entries.length > 0 ? (
        <ul className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
          {(registry.entries as Array<Record<string, unknown>>).map((e, i) => (
            <li
              key={i}
              className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm"
            >
              <span className="text-slate-600">
                {String(e.registry_type ?? "registry")}
              </span>
              <Badge className="bg-slate-100 text-slate-700 ring-slate-500/20">
                {String(e.status ?? "?")}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}
    </SectionCard>
  );
}
