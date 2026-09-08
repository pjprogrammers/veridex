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
import { RiskReasons, RiskRecommendations } from "@/components/risk-reasons";
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
  const demoKey = params.get("demo") ?? "";

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
        <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
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
          className="inline-flex items-center gap-2 text-sm text-neutral-500 hover:text-black"
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
            className="text-xs font-medium text-neutral-500 hover:text-black"
          >
            ← Back to case {caseDetail?.case_number ?? ""}
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)]">
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
          className="inline-flex items-center gap-2 text-sm text-neutral-500 hover:text-black"
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
            className="text-xs font-medium text-neutral-500 hover:text-black"
          >
            ← Back to case {caseDetail?.case_number ?? ""}
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)]">
            Verification Results
          </h1>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            {caseDetail?.case_number} · {formatDate(caseDetail?.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {running ? (
            <span className="inline-flex items-center gap-2 text-sm text-[var(--muted)]">
              <Spinner /> Re-running…
            </span>
          ) : null}
          <Button variant="secondary" size="sm" onClick={runNow} disabled={running}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            Re-run verification
          </Button>
          {demoKey ? <DemoBadge demoKey={demoKey} /> : null}
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
        This is a decision-support analysis. It does
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
    cls: "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40",
  },
  MANUAL_REVIEW: {
    label: "MANUAL REVIEW",
    cls: "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40",
  },
  HIGH_RISK_ALERT: {
    label: "HIGH-RISK ALERT",
    cls: "bg-neutral-200/80 text-black ring-neutral-400/40",
  },
  INCONCLUSIVE: {
    label: "INCONCLUSIVE",
    cls: "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]",
  },
};

function DecisionBadge({ decision }: { decision: Verdict }) {
  const s = DECISION_STYLES[decision];
  return (
    <Badge className={cn("micro-badge-in px-3 py-1 text-xs font-semibold", s.cls)}>
      {s.label}
    </Badge>
  );
}

const DEMO_LABELS: Record<string, string> = {
  genuine: "Genuine",
  tampered: "Tampered",
  expired: "Expired",
  blacklisted: "Blacklisted",
  impersonation: "Impersonation",
};

function DemoBadge({ demoKey }: { demoKey: string }) {
  const label = DEMO_LABELS[demoKey] ?? demoKey;
  return (
    <Badge className="bg-neutral-100 text-neutral-600 ring-neutral-300">
      Demo · {label}
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
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
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
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <Radar className="h-4 w-4 text-neutral-500" aria-hidden />
          Risk Assessment
        </h2>
        <RiskBadge level={risk?.level ?? "UNKNOWN"} />
      </div>
      <div className="p-5">
        <RiskGauge
          score={risk?.score ?? 0}
          level={risk?.level ?? "UNKNOWN"}
        />
        <RiskReasons factors={factors} className="mt-5" />
        <RiskRecommendations
          recommendations={risk?.recommendations ?? []}
          explanation={risk?.explanation}
        />
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
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <FileSearch className="h-4 w-4 text-neutral-500" aria-hidden />
          Detected Document
        </h2>
        <Badge className="bg-neutral-200/60 text-neutral-500 ring-neutral-400/40">
          {typeLabel}
        </Badge>
      </div>
      <div className="p-5 space-y-4">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Confidence
          </div>
          <div className="flex items-center gap-3">
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[#f6f7fb]">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  pct >= 70 ? "bg-neutral-500" : pct >= 40 ? "bg-neutral-500" : "bg-black",
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-sm font-medium text-[var(--text)]">{pct}%</span>
          </div>
        </div>
        <StatDisplay label="Method" value={classification.method} />
        {classification.template_id ? (
          <StatDisplay label="Template" value={classification.template_id} />
        ) : null}
        {classification.warnings.length > 0 ? (
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Warnings
            </div>
            <ul className="space-y-1.5">
              {classification.warnings.map((w, i) => (
                <li
                  key={i}
                  className="flex items-center gap-2 rounded-lg bg-neutral-300/40 px-3 py-1.5 text-sm text-neutral-800"
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
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <ScanLine className="h-4 w-4 text-neutral-500" aria-hidden />
          MRZ Analysis
        </h2>
        <div className="flex items-center gap-2">
          {result && validChip ? (
            <Badge
              className={
                result.mrz.mrz_valid
                  ? "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40"
                  : result.mrz.mrz_detected
                    ? "bg-neutral-200/80 text-black ring-neutral-400/40"
                    : "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]"
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
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <Spinner /> Detecting and validating the machine-readable zone…
            </div>
          ) : (
            <p className="text-sm text-[var(--muted)]">
              The machine-readable zone (MRZ) has not been extracted yet. Run
              MRZ analysis to detect, parse, and validate the ICAO 9303 zone.
            </p>
          )
        ) : (
          <>
            {!result.mrz.mrz_detected ? (
              <p className="text-sm text-[var(--muted)]">
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
                    <div className="border-b border-[var(--border)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                      Parsed fields
                    </div>
                    <div className="p-4">
                      <table className="w-full text-sm">
                        <tbody>
                          {Object.entries(result.mrz.parsed_fields).map(([k, v]) => (
                            <tr key={k} className="border-b border-[var(--border)] last:border-0">
                              <td className="py-1.5 pr-3 text-[var(--muted)]">
                                {k.replace(/_/g, " ")}
                              </td>
                              <td className="py-1.5 font-medium text-[var(--text)]">{v || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>

                  <Card className="!p-0 shadow-none">
                    <div className="border-b border-[var(--border)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                      ICAO check digits
                    </div>
                    <div className="p-4">
                      <table className="w-full text-sm">
                        <tbody>
                          {Object.entries(result.mrz.check_digits).map(([k, v]) => (
                            <tr key={k} className="border-b border-[var(--border)] last:border-0">
                              <td className="py-1.5 pr-3 text-[var(--muted)]">
                                {k.replace(/_/g, " ")}
                              </td>
                              <td className="py-1.5 text-right">
                                {v === true ? (
                                  <Badge className="bg-neutral-200/70 text-neutral-600 ring-neutral-400/40">
                                    Valid
                                  </Badge>
                                ) : v === false ? (
                                  <Badge className="bg-neutral-200/80 text-black ring-neutral-400/40">
                                    Invalid
                                  </Badge>
                                ) : (
                                  <span className="text-[var(--muted)]">—</span>
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
                    <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-neutral-500 hover:text-black">
                      View raw MRZ lines
                    </summary>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-[#f6f7fb] p-3 text-xs text-[var(--text)]">
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
    NONE: "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40",
    LOW: "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40",
    MEDIUM: "bg-neutral-400/30 text-neutral-800 ring-neutral-400/40",
    HIGH: "bg-neutral-200/80 text-black ring-neutral-400/40",
  };
  return (
    <div className="rounded-xl border border-[var(--border)] p-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          Visual vs MRZ comparison
        </div>
        <Badge className={severityStyles[comparison.severity] ?? severityStyles.NONE!}>
          {comparison.severity}
        </Badge>
      </div>
      <div className="mt-3 overflow-hidden rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[#f8f9fc] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
              <th className="px-3 py-2 font-semibold">Field</th>
              <th className="px-3 py-2 font-semibold">Visual</th>
              <th className="px-3 py-2 font-semibold">MRZ</th>
              <th className="px-3 py-2 text-right font-semibold">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {comparison.comparisons.map((c) => (
              <tr key={c.field_name} className="border-b border-[var(--border)] last:border-0">
                <td className="px-3 py-2 text-[var(--muted)]">{c.field_name.replace(/_/g, " ")}</td>
                <td className="px-3 py-2 text-[var(--text)]">{c.visual_value || "—"}</td>
                <td className="px-3 py-2 text-[var(--text)]">{c.mrz_value || "—"}</td>
                <td className="px-3 py-2 text-right">
                  {c.verdict === "MATCH" ? (
                    <Badge className="bg-neutral-200/70 text-neutral-600 ring-neutral-400/40">Match</Badge>
                  ) : c.verdict === "MISMATCH" ? (
                    <Badge className="bg-neutral-200/80 text-black ring-neutral-400/40">Mismatch</Badge>
                  ) : (
                    <span className="text-[var(--muted)]">N/A</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {comparison.severity_reasons.length > 0 ? (
        <p className="mt-2 text-xs text-[var(--muted)]">
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
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <Type className="h-4 w-4 text-neutral-500" aria-hidden />
          OCR Extraction
        </h2>
        {ocr.engine ? (
          <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
            {ocr.engine}
          </Badge>
        ) : null}
      </div>
      <div className="p-5 space-y-5">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
          <div className="min-w-[240px] flex-1">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Average field confidence
            </div>
            <div className="flex items-center gap-3">
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[#f6f7fb]">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    avgConfPct(ocr) >= 70
                      ? "bg-neutral-500"
                      : avgConfPct(ocr) >= 40
                        ? "bg-neutral-500"
                        : "bg-black",
                  )}
                  style={{ width: `${avgConfPct(ocr)}%` }}
                />
              </div>
              <span className="text-sm font-medium text-[var(--text)]">
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
          <p className="text-sm text-[var(--muted)]">
            No structured fields were extracted from this document.
          </p>
        ) : (
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Extracted fields
            </div>
            <div className="overflow-hidden rounded-xl border border-[var(--border)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[#f8f9fc] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                    <th className="px-3 py-2 font-semibold">Field</th>
                    <th className="px-3 py-2 font-semibold">Value</th>
                    <th className="px-3 py-2 text-right font-semibold">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {displayFields.map((f, i) => (
                    <tr key={`${f.field_name}-${i}`} className="border-b border-[var(--border)]">
                      <td className="px-3 py-2 text-[var(--muted)]">
                        {f.field_name.replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-2 font-medium text-[var(--text)]">
                        {f.value}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[#f6f7fb]">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                Math.round(f.confidence * 100) >= 70
                                  ? "bg-neutral-500"
                                  : Math.round(f.confidence * 100) >= 40
                                    ? "bg-neutral-500"
                                    : "bg-black",
                              )}
                              style={{ width: `${Math.round(f.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="w-10 text-right text-xs font-medium text-[var(--text)]">
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
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-neutral-500 hover:text-black">
              View raw OCR text
            </summary>
            <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-[#f6f7fb] p-3 text-xs text-[var(--text)]">
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
      icon={<FileSearch className="h-4 w-4 text-neutral-500" aria-hidden />}
      action={
        <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
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
        <div className="mt-3 border-t border-[var(--border)] pt-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Extracted fields
          </div>
          {Object.keys(fields).length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No fields extracted yet.</p>
          ) : (
            <dl className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
              {Object.entries(fields).map(([k, v]) => (
                <div key={k} className="py-1 text-sm">
                  <dt className="text-[var(--muted)]">{k}</dt>
                  <dd className="font-medium text-[var(--text)]">
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
  if (v === "PASS") return "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40";
  if (v === "FAIL" || v === "MISMATCH")
    return "bg-neutral-200/80 text-black ring-neutral-400/40";
  if (v === "WARN") return "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40";
  return "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]";
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
      icon={<UserCheck className="h-4 w-4 text-neutral-500" aria-hidden />}
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
        <div className="mt-3 border-t border-[var(--border)] pt-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Field checks
          </div>
          <ul className="space-y-1.5">
            {Object.entries(validation).map(([field, detail]) => {
              const d = (detail ?? {}) as Record<string, unknown>;
              const verdict = String(d.verdict ?? "—");
              return (
                <li
                  key={field}
                  className="flex items-center justify-between rounded-lg bg-[#f6f7fb] px-3 py-1.5 text-sm"
                >
                  <span className="text-[var(--text)]">{field.replace(/_/g, " ")}</span>
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
      icon={<Camera className="h-4 w-4 text-neutral-500" aria-hidden />}
      action={
        verification.verdict === "match" ? (
          <Badge className="bg-neutral-200/70 text-neutral-600 ring-neutral-400/40">
            match
          </Badge>
        ) : hasFaceData ? (
          <Badge className="bg-neutral-300/40 text-neutral-800 ring-neutral-400/40">
            {String(verification.verdict ?? "review")}
          </Badge>
        ) : null
      }
    >
      {!hasFaceData ? (
        <p className="text-sm text-[var(--muted)]">
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
      icon={<Radar className="h-4 w-4 text-neutral-500" aria-hidden />}
      action={
        evidenceStatus === "sufficient_evidence" ? (
          <Badge className="bg-neutral-400/30 text-neutral-800 ring-neutral-400/40">
            validated signal
          </Badge>
        ) : (
          <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
            experimental
          </Badge>
        )
      }
    >
      {!report.forensics ? (
        <p className="text-sm text-[var(--muted)]">Forensic analysis not performed.</p>
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
            <p className="text-[11px] text-[var(--muted)]">
              Forensic detectors are experimental/unvalidated; experimental
              signals below are research indicators, not a tampering verdict.
            </p>
          )}
          {flags.length > 0 ? (
            <>
              <div>
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  Suspicious regions
                </div>
                <ul className="space-y-1.5">
                  {flags.map((f, i) => {
                    const flag = (f ?? {}) as Record<string, unknown>;
                    return (
                      <li
                        key={i}
                        className="flex items-center justify-between rounded-lg bg-neutral-200/80 px-3 py-1.5 text-sm"
                      >
                        <span className="text-black">
                          {String(flag.signal ?? flag.description ?? "region")}
                        </span>
                        <Badge
                          className={cn(
                            "bg-neutral-200/80 text-black ring-neutral-400/40",
                            String(flag.severity ?? "LOW").toUpperCase() === "HIGH" &&
                              "bg-neutral-400/60",
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
            <div className="rounded-lg bg-[#f6f7fb] p-3 text-sm text-[var(--text)]">
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
        icon={<Landmark className="h-4 w-4 text-neutral-500" aria-hidden />}
        action={<Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">skipped</Badge>}
      >
        <p className="text-sm text-[var(--muted)]">
          Registry check was not run for this verification.
        </p>
      </SectionCard>
    );
  }
  return (
    <SectionCard
      title="Registry"
      icon={<Landmark className="h-4 w-4 text-neutral-500" aria-hidden />}
      action={
        registry.alert ? (
          <Badge className="bg-neutral-200/80 text-black ring-neutral-400/40">alert</Badge>
        ) : (
          <Badge className="bg-neutral-200/70 text-neutral-600 ring-neutral-400/40">
            clear
          </Badge>
        )
      }
    >
      <StatDisplay label="Status" value={found > 0 ? "found" : "not found"} />
      <StatDisplay label="Match result" value={String(registry.match ?? "—")} />
      {Array.isArray(registry.entries) && registry.entries.length > 0 ? (
        <ul className="mt-3 space-y-1.5 border-t border-[var(--border)] pt-3">
          {(registry.entries as Array<Record<string, unknown>>).map((e, i) => (
            <li
              key={i}
              className="flex items-center justify-between rounded-lg bg-[#f6f7fb] px-3 py-1.5 text-sm"
            >
              <span className="text-[var(--text)]">
                {String(e.registry_type ?? "registry")}
              </span>
              <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
                {String(e.status ?? "?")}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}
    </SectionCard>
  );
}
