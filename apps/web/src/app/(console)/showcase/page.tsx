"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BrainCircuit,
  CheckCircle2,
  FileImage,
  FileScan,
  Loader2,
  ScanText,
  Type,
  Upload,
  X,
} from "lucide-react";
import { errorFn } from "@/lib/api";
import {
  formatMs,
  getAiStatus,
  OCR_DOCUMENT_TYPES,
  pct,
  runAiFaceVerify,
  runAiOcr,
} from "@/lib/ai";
import type {
  AIStackStatus,
  FaceVerificationResult,
  OCREngineResult,
} from "@/lib/ai";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Select,
  Spinner,
  StatDisplay,
  Label,
} from "@/components/ui";
import { cn, formatBytes } from "@/lib/utils";

const ACCEPTED_MIME = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE_MB = 15;

type ViewMode = "general" | "raw";

export default function ShowcasePage() {
  const [status, setStatus] = useState<AIStackStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  // Uploads
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState<string>("generic");
  const [liveFace, setLiveFace] = useState<File | null>(null);
  const [livePreviewUrl, setLivePreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // Results
  const [mode, setMode] = useState<ViewMode>("general");
  const [ocr, setOcr] = useState<OCREngineResult | null>(null);
  const [face, setFace] = useState<FaceVerificationResult | null>(null);
  const [ocrRunning, setOcrRunning] = useState(false);
  const [faceRunning, setFaceRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAiStatus()
      .then(setStatus)
      .catch((e) => setStatusError(errorFn(e)))
      .finally(() => setStatusLoading(false));
  }, []);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    if (file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    setPreviewUrl(null);
  }, [file]);

  useEffect(() => {
    if (!liveFace) {
      setLivePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(liveFace);
    setLivePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [liveFace]);

  function validateFile(f: File): string | null {
    if (!ACCEPTED_MIME.includes(f.type)) {
      return `Unsupported file type "${f.type}". Accepted: JPEG, PNG, WebP.`;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File is ${formatBytes(f.size)} — exceeds the ${MAX_SIZE_MB} MB limit.`;
    }
    if (f.size === 0) return "File is empty.";
    return null;
  }

  const acceptFile = useCallback((f: File | undefined | null) => {
    if (!f) return;
    const err = validateFile(f);
    setValidationError(err);
    if (!err) {
      setFile(f);
    } else {
      setFile(null);
    }
  }, []);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    acceptFile(e.dataTransfer.files?.[0]);
  }

  function resetAll() {
    setFile(null);
    setLiveFace(null);
    setOcr(null);
    setFace(null);
    setPreviewUrl(null);
    setLivePreviewUrl(null);
    setValidationError(null);
    setError(null);
  }

  async function runOcr() {
    if (!file) return;
    setOcrRunning(true);
    setError(null);
    try {
      setOcr(await runAiOcr(file, documentType));
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setOcrRunning(false);
    }
  }

  async function runFace() {
    if (!file || !liveFace) return;
    setFaceRunning(true);
    setError(null);
    try {
      setFace(await runAiFaceVerify(file, liveFace));
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setFaceRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">
            AI Showcase
          </h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Direct one-shot calls into the reusable AI/CV layer — PaddleOCR
            extraction and InsightFace face-to-face verification. Outputs are
            evidence, not verdicts.
          </p>
        </div>
        <GetStatusChip loading={statusLoading} status={status} error={statusError} />
      </div>

      {error ? <Alert title="Request failed">{error}</Alert> : null}

      {status && !status.available ? (
        <Alert title="AI layer unavailable in this environment">
          {status.reason ?? "The ai package could not be imported. Install services/api/requirements-ai.txt."}
        </Alert>
      ) : null}

      {/* Upload */}
      <Card>
        <CardHeader
          title="Document image"
          subtitle="Drag & drop, or browse. This is the photo used for OCR and/or face verification."
        />
        <div className="p-5">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
              dragging
                ? "border-neutral-400 bg-neutral-200/60"
                : "border-[var(--border)] bg-[var(--card)]",
            )}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-neutral-200/60 text-neutral-500">
              <Upload className="h-6 w-6" aria-hidden />
            </div>
            <p className="mt-3 text-sm font-medium text-[var(--text)]">
              Drag &amp; drop a document image here
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">
              JPEG · PNG · WebP · max {MAX_SIZE_MB} MB
            </p>
            {previewUrl ? null : (
              <label className="mt-3 cursor-pointer rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-neutral-500 hover:bg-neutral-100">
                Browse files
                <input
                  type="file"
                  accept={ACCEPTED_MIME.join(",")}
                  className="sr-only"
                  onChange={(e) => {
                    acceptFile(e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
              </label>
            )}
          </div>

          {validationError ? (
            <div className="mt-4">
              <Alert title="File rejected">{validationError}</Alert>
            </div>
          ) : null}

          {file ? (
            <div className="mt-4">
              <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:flex-row sm:items-center">
                <div className="flex h-28 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[var(--border)] bg-[#f6f7fb]">
                  {previewUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={previewUrl}
                      alt={`Preview of ${file.name}`}
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <FileImage className="h-8 w-8 text-[var(--muted)]" aria-hidden />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
                    <FileScan className="h-4 w-4 text-neutral-500" aria-hidden />
                    <span className="truncate">{file.name}</span>
                  </div>
                  <div className="mt-1 text-xs text-[var(--muted)]">
                    {file.type} · {formatBytes(file.size)} · ready
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={runOcr}
                      disabled={ocrRunning}
                    >
                      {ocrRunning ? <Spinner /> : <ScanText className="h-3.5 w-3.5" aria-hidden />}
                      Run OCR
                    </Button>
                    {liveFace ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={runFace}
                        disabled={faceRunning}
                      >
                        {faceRunning ? <Spinner /> : null}
                        Verify faces
                      </Button>
                    ) : null}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={resetAll}
                      className="ml-auto"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden />
                      Reset
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Document type */}
        <Card>
          <CardHeader
            title="OCR targeting"
            subtitle="Selected document schema used for field extraction"
          />
          <div className="p-5">
            <Label htmlFor="doc-type">Document type</Label>
            <Select
              id="doc-type"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
            >
              {OCR_DOCUMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </Select>
            {file ? (
              <div className="mt-3 flex justify-end">
                <Button onClick={runOcr} disabled={ocrRunning}>
                  {ocrRunning ? <Spinner /> : <ScanText className="h-4 w-4" aria-hidden />}
                  Extract text &amp; fields
                </Button>
              </div>
            ) : null}
          </div>
        </Card>

        {/* Live face */}
        <Card>
          <CardHeader
            title="Live face capture"
            subtitle="Optional — enables document-vs-live face similarity"
          />
          <div className="p-5">
            {!liveFace ? (
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-[var(--border)] px-4 py-8 text-sm text-[var(--muted)] transition-colors hover:border-neutral-400 hover:bg-neutral-100">
                <Upload className="h-4 w-4" aria-hidden />
                Attach a live / reference face photo…
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setLiveFace(f);
                    e.target.value = "";
                  }}
                />
              </label>
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="flex h-24 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[var(--border)] bg-[#f6f7fb]">
                  {livePreviewUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={livePreviewUrl}
                      alt={`Live face ${liveFace.name}`}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <FileImage className="h-7 w-7 text-[var(--muted)]" aria-hidden />
                  )}
                </div>
                <div className="min-w-0 flex-1 text-sm">
                  <div className="truncate font-medium text-[var(--text)]">
                    {liveFace.name}
                  </div>
                  <div className="mt-0.5 text-xs text-[var(--muted)]">
                    {file ? `${formatBytes(liveFace.size)} · ready` : "Attached"}
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={runFace}
                      disabled={faceRunning || !file}
                    >
                      {faceRunning ? <Spinner /> : null}
                      Verify faces
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setLiveFace(null)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Results */}
      <div className="space-y-4">
        <ResultHeader
          mode={mode}
          onMode={setMode}
          hasResults={Boolean(ocr || face)}
        />

        {mode === "general" ? (
          <div className="space-y-4">
            {ocr ? <OCRGeneral result={ocr} /> : null}
            {face ? <FaceGeneral result={face} /> : null}
            {!ocr && !face && !ocrRunning && !faceRunning ? (
              <Card>
                <div className="flex flex-col items-center gap-2 p-10 text-center">
                  <BrainCircuit className="h-7 w-7 text-neutral-500" aria-hidden />
                  <p className="text-sm font-medium text-[var(--muted)]">
                    Upload a document and run OCR to see structured output here.
                  </p>
                  <p className="text-xs text-[var(--muted)]">
                    Switch to Raw to inspect the exact JSON contract.
                  </p>
                </div>
              </Card>
            ) : null}
          </div>
        ) : (
          <RawView ocr={ocr} face={face} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status chip
// ---------------------------------------------------------------------------

function GetStatusChip({
  loading,
  status,
  error,
}: {
  loading: boolean;
  status: AIStackStatus | null;
  error: string | null;
}) {
  if (loading)
    return (
      <div className="flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs text-[var(--muted)]">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> checking…
      </div>
    );
  return (
    <div className="flex flex-col items-end gap-1">
      <Badge
        className={
          status?.available
            ? "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40"
            : "bg-neutral-200/80 text-black ring-neutral-400/40"
        }
      >
        {status?.available ? "AI layer online" : "AI layer unavailable"}
      </Badge>
      <span className="text-[11px] text-[var(--muted)]">
        {error ?? (status?.version ? `veridex-ai v${status.version}` : "")}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode toggle
// ---------------------------------------------------------------------------

function ResultHeader({
  mode,
  onMode,
  hasResults,
}: {
  mode: ViewMode;
  onMode: (m: ViewMode) => void;
  hasResults: boolean;
}) {
  if (!hasResults) return null;
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Results
        </h2>
      </div>
      <div className="flex overflow-hidden rounded-lg border border-[var(--border)]">
        <button
          type="button"
          onClick={() => onMode("general")}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors",
            mode === "general"
              ? "bg-neutral-700 text-white"
              : "bg-[var(--card)] text-[var(--muted)] hover:text-[var(--text)]",
          )}
        >
          <Type className="h-3.5 w-3.5" aria-hidden />
          General
        </button>
        <button
          type="button"
          onClick={() => onMode("raw")}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors",
            mode === "raw"
              ? "bg-neutral-700 text-white"
              : "bg-[var(--card)] text-[var(--muted)] hover:text-[var(--text)]",
          )}
        >
          <Code2 className="h-3.5 w-3.5" aria-hidden />
          Raw JSON
        </button>
      </div>
    </div>
  );
}

function Code2({ className }: { className?: string }) {
  return (
    <span
      className={cn("inline-flex items-center", className)}
      aria-hidden
    >
      {"{ }"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Raw JSON view
// ---------------------------------------------------------------------------

function RawView({
  ocr,
  face,
}: {
  ocr: OCREngineResult | null;
  face: FaceVerificationResult | null;
}) {
  const payloads: Array<{ label: string; data: unknown }> = [];
  if (ocr) payloads.push({ label: "OCR — /ai/v1/ocr/upload", data: ocr });
  if (face) payloads.push({ label: "FACE — /ai/v1/face/verify", data: face });
  return (
    <div className="space-y-4">
      {payloads.map((p) => (
        <Card key={p.label} className="overflow-hidden">
          <div className="border-b border-[var(--border)] px-5 py-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {p.label}
          </div>
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words bg-[#f8f9fc] p-5 text-xs leading-relaxed text-[var(--text)]">
            {JSON.stringify(p.data, null, 2)}
          </pre>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// General (rendered) view — OCR
// ---------------------------------------------------------------------------

function OCRGeneral({ result }: { result: OCREngineResult }) {
  if (result.error) {
    return (
      <Alert title={`OCR error (${result.error})`}>
        {result.error_detail ?? "The OCR engine could not extract text."}
      </Alert>
    );
  }

  const fields = Object.entries(result.fields ?? {});
  const blocks = result.text_blocks ?? [];
  const mrz = result.mrz;

  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <ScanText className="h-4 w-4 text-neutral-500" aria-hidden />
          OCR Extraction
        </h2>
        <Badge className="bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]">
          {result.engine} {result.engine_version}
        </Badge>
      </div>

      <div className="space-y-5 p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <StatDisplay
            label="Overall confidence"
            value={pct(result.overall_confidence)}
          />
          <StatDisplay
            label="Image"
            value={`${result.image_width} × ${result.image_height}`}
          />
          <StatDisplay
            label="Total latency"
            value={formatMs(result.latency_ms?.total_latency_ms)}
          />
        </div>

        <div>
          <SectionLabel icon={<Type className="h-3.5 w-3.5" aria-hidden />}>
            Extracted fields
          </SectionLabel>
          {fields.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">
              No structured fields matched the selected document schema.
            </p>
          ) : (
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
                  {fields.map(([name, f]) => (
                    <tr key={name} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-3 py-2 text-[var(--muted)]">
                        {name.replace(/_/g, " ")}
                        {f.low_confidence ? (
                          <Badge className="ml-2 bg-neutral-300/40 text-neutral-800 ring-neutral-400/40">
                            low
                          </Badge>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 font-medium text-[var(--text)]">
                        {f.value || "—"}
                      </td>
                      <td className="px-3 py-2 text-right text-xs font-medium text-[var(--text)]">
                        {pct(f.confidence)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div>
          <SectionLabel icon={<ScanText className="h-3.5 w-3.5" aria-hidden />}>
            Detected text blocks
          </SectionLabel>
          {blocks.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No text detected.</p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-[var(--border)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[#f8f9fc] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                    <th className="px-3 py-2 font-semibold">#</th>
                    <th className="px-3 py-2 font-semibold">Text</th>
                    <th className="px-3 py-2 text-right font-semibold">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {blocks.slice(0, 300).map((b, i) => (
                    <tr key={i} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-3 py-1.5 text-xs text-[var(--muted)]">{i + 1}</td>
                      <td className="px-3 py-1.5 font-medium text-[var(--text)]">
                        {b.text}
                        {b.low_confidence ? (
                          <Badge className="ml-2 bg-neutral-300/40 text-neutral-800 ring-neutral-400/40">
                            low
                          </Badge>
                        ) : null}
                      </td>
                      <td className="px-3 py-1.5 text-right text-xs font-medium text-[var(--text)]">
                        {pct(b.confidence)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {blocks.length > 300 ? (
                <div className="border-t border-[var(--border)] px-3 py-2 text-xs text-[var(--muted)]">
                  Showing first 300 of {blocks.length} blocks.
                </div>
              ) : null}
            </div>
          )}
        </div>

        {mrz && mrz.detected ? <MRZGeneral mrz={mrz} /> : null}

        {Object.keys(result.consistency ?? {}).length > 0 ? (
          <div>
            <SectionLabel icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>
              Visual vs MRZ consistency
            </SectionLabel>
            <div className="overflow-hidden rounded-xl border border-[var(--border)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[#f8f9fc] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                    <th className="px-3 py-2 font-semibold">Field</th>
                    <th className="px-3 py-2 font-semibold">Visual</th>
                    <th className="px-3 py-2 font-semibold">MRZ</th>
                    <th className="px-3 py-2 text-right font-semibold">Match</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.consistency).map(([name, c]) => (
                    <tr key={name} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-3 py-2 text-[var(--muted)]">{name.replace(/_/g, " ")}</td>
                      <td className="px-3 py-2 text-[var(--text)]">{c.visual || "—"}</td>
                      <td className="px-3 py-2 text-[var(--text)]">{c.mrz || "—"}</td>
                      <td className="px-3 py-2 text-right">
                        {c.match === true ? (
                          <Badge className="bg-neutral-200/70 text-neutral-600 ring-neutral-400/40">Match</Badge>
                        ) : c.match === false ? (
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
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function MRZGeneral({ mrz }: { mrz: NonNullable<OCREngineResult["mrz"]> }) {
  const checkDigits = Object.entries(mrz.check_digits ?? {}).filter(
    ([, v]) => v !== null,
  );
  return (
    <div>
      <SectionLabel icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>
        Machine-readable zone
      </SectionLabel>
      <div className="rounded-xl border border-[var(--border)] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            className={
              mrz.valid
                ? "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40"
                : "bg-neutral-200/80 text-black ring-neutral-400/40"
            }
          >
            {mrz.valid ? "VALID" : mrz.format ? "CHECK FAILED" : "UNREADABLE"}
          </Badge>
          {mrz.format ? (
            <span className="text-xs text-[var(--muted)]">{mrz.format}</span>
          ) : null}
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Parsed fields
            </div>
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(mrz.parsed_fields ?? {}).map(([k, v]) => (
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
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              ICAO check digits
            </div>
            {checkDigits.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">Not validated.</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {checkDigits.map(([k, v]) => (
                    <tr key={k} className="border-b border-[var(--border)] last:border-0">
                      <td className="py-1.5 pr-3 text-[var(--muted)]">
                        {k.replace(/_/g, " ")}
                      </td>
                      <td className="py-1.5 text-right">
                        {v === true ? (
                          <Badge className="bg-neutral-200/70 text-neutral-600 ring-neutral-400/40">Valid</Badge>
                        ) : (
                          <Badge className="bg-neutral-200/80 text-black ring-neutral-400/40">Invalid</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {mrz.lines.length > 0 ? (
          <details className="group mt-3">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-neutral-500 hover:text-black">
              View raw MRZ lines
            </summary>
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-[#f6f7fb] p-3 font-mono text-xs text-[var(--text)]">
              {mrz.lines.join("\n")}
            </pre>
          </details>
        ) : null}

        {mrz.warnings && mrz.warnings.length > 0 ? (
          <p className="mt-2 text-xs text-[var(--muted)]">
            Warnings: {mrz.warnings.join(", ")}
          </p>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// General (rendered) view — Face
// ---------------------------------------------------------------------------

const FACE_STYLES: Record<string, { label: string; cls: string }> = {
  MATCH: {
    label: "MATCH",
    cls: "bg-neutral-200/70 text-neutral-600 ring-neutral-400/40",
  },
  NO_MATCH: {
    label: "NO MATCH",
    cls: "bg-neutral-200/80 text-black ring-neutral-400/40",
  },
  LOW_QUALITY: {
    label: "LOW QUALITY",
    cls: "bg-neutral-300/40 text-neutral-800 ring-neutral-400/40",
  },
};

function FaceGeneral({ result }: { result: FaceVerificationResult }) {
  const style = FACE_STYLES[result.result] ?? {
    label: result.result.replace(/_/g, " "),
    cls: "bg-[#f6f7fb] text-[var(--muted)] ring-[var(--border)]",
  };
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <ScanText className="h-4 w-4 text-neutral-500" aria-hidden />
          Face Verification
        </h2>
        {result.error ? (
          <Badge className="bg-neutral-200/80 text-black ring-neutral-400/40">
            {result.error}
          </Badge>
        ) : (
          <Badge className={style.cls}>{style.label}</Badge>
        )}
      </div>
      <div className="p-5">
        {result.error ? (
          <Alert title="Face engine error">
            {result.error_detail ?? "The face pipeline could not run."}
          </Alert>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatDisplay
            label="Similarity"
            value={result.similarity != null ? pct(result.similarity) : "—"}
          />
          <StatDisplay
            label="Similarity threshold"
            value={result.threshold.toFixed(2)}
          />
          <StatDisplay
            label="Total latency"
            value={formatMs(result.latency_ms?.total_latency_ms)}
          />
          <StatDisplay
            label="Document faces"
            value={String(result.document_face_count)}
          />
          <StatDisplay
            label="Live faces"
            value={String(result.live_face_count)}
          />
          <StatDisplay
            label="Document face quality"
            value={result.document_face_quality != null ? pct(result.document_face_quality) : "—"}
          />
        </div>
        <StatDisplay
          label="Live face quality"
          value={result.live_face_quality != null ? pct(result.live_face_quality) : "—"}
        />
        <p className="mt-3 text-[11px] leading-4 text-[var(--muted)]">
          Evidence only — a MATCH is a similarity signal, not proof of identity.
          Business decisions belong to the risk/evidence engine.
        </p>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SectionLabel({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
      {icon}
      {children}
    </div>
  );
}