"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  FileImage,
  FileScan,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import { api, errorFn } from "@/lib/api";
import {
  analyzeDocument,
  classifyDocument,
  preprocessDocument,
  runFullVerification,
  uploadDocumentStandalone,
  VERIFY_STAGES,
} from "@/lib/verify";
import type { ProcessingStage } from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Checkbox,
  Input,
  Label,
  Spinner,
} from "@/components/ui";
import { formatBytes, cn } from "@/lib/utils";
import { PROCESSING_LABELS } from "@/lib/types";

const ACCEPTED_MIME = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX_SIZE_MB = 15;

interface StageState {
  stage: ProcessingStage;
  state: "pending" | "active" | "done" | "error";
}

export default function VerifyPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [description, setDescription] = useState("");
  const [checkRegistry, setCheckRegistry] = useState(true);
  const [performForensics, setPerformForensics] = useState(true);
  const [attachLiveFace, setAttachLiveFace] = useState(false);
  const [liveFace, setLiveFace] = useState<File | null>(null);

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<ProcessingStage>("UPLOADED");
  const [stageStates, setStageStates] = useState<StageState[]>([]);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [newDocumentId, setNewDocumentId] = useState<string | null>(null);

  // Clear the in-memory preview when the file is replaced.
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

  function validateFile(f: File): string | null {
    if (!ACCEPTED_MIME.includes(f.type)) {
      return `Unsupported file type "${f.type}". Accepted: JPEG, PNG, WebP, PDF.`;
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

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    acceptFile(e.target.files?.[0]);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    acceptFile(e.dataTransfer.files?.[0]);
  }

  function resetAll() {
    setFile(null);
    setLiveFace(null);
    setPreviewUrl(null);
    setValidationError(null);
    setError(null);
    setRunning(false);
    setStageStates([]);
    setCaseId(null);
  }

  async function startVerification() {
    if (!file) return;
    setRunning(true);
    setError(null);
    setStageStates(
      VERIFY_STAGES.map((s) => ({ stage: s, state: "pending" as const })),
    );

    const setStage = (s: ProcessingStage, state: StageState["state"]) => {
      setCurrentStage(s);
      setStageStates((prev) =>
        prev.map((x) => (x.stage === s ? { ...x, state } : x)),
      );
    };

    try {
      // 1. Create the case
      setStage("UPLOADED", "active");
      const created = await api<{ id: string }>("/cases", {
        method: "POST",
        json: {
          case_description: description || undefined,
          check_registry: checkRegistry,
          perform_forensics: performForensics,
        },
      });
      setCaseId(created.id);
      setStage("UPLOADED", "done");

      // 2. Upload the document via Phase 3 ingestion endpoint
      setStage("CLASSIFYING", "active");
      const uploaded = await uploadDocumentStandalone(file, created.id);
      setNewDocumentId(uploaded.id);

      // 2b. Classify the document type
      await classifyDocument(uploaded.id);
      setStage("CLASSIFYING", "done");

      // 3. Preprocess the document image
      setStage("PREPROCESSING", "active");
      await preprocessDocument(uploaded.id);
      setStage("PREPROCESSING", "done");

      // 4. Run the document analysis pipeline
      setStage("EXTRACTING", "active");
      await analyzeDocument(created.id, uploaded.id);
      setStage("EXTRACTING", "done");

      // 4. Field validation
      setStage("VALIDATING", "active");
      await new Promise((r) => setTimeout(r, 500));
      setStage("VALIDATING", "done");

      // 5. Forensics
      if (performForensics) {
        setStage("FORENSIC_ANALYSIS", "active");
        await new Promise((r) => setTimeout(r, 600));
        setStage("FORENSIC_ANALYSIS", "done");
      }

      // 6. Face verification
      setStage("FACE_VERIFICATION", "active");
      await new Promise((r) => setTimeout(r, 500));
      setStage("FACE_VERIFICATION", "done");

      // 7. Risk assessment — full verification
      setStage("RISK_ASSESSMENT", "active");
      await runFullVerification(uploaded.id, {
        liveFace: attachLiveFace ? liveFace : null,
        checkRegistry,
      });
      await new Promise((r) => setTimeout(r, 300));
      setStage("RISK_ASSESSMENT", "done");

      setStage("COMPLETED", "active");
      setStage("COMPLETED", "done");

      const params = new URLSearchParams({
        case: created.id,
        doc: uploaded.id,
      });
      router.push(`/verify/results?${params.toString()}`);
    } catch (e) {
      setStage(currentStage || "CLASSIFYING", "error");
      setError(errorFn(e));
      setRunning(false);
    }
  }

  const started = running || caseId !== null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">New Verification</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload an identity or travel document to run the full verification
          pipeline.
        </p>
      </div>

      {error ? <Alert title="Verification failed">{error}</Alert> : null}

      {/* Upload area */}
      <Card>
        <CardHeader
          title="Document upload"
          subtitle="Drag & drop, or choose a file from your device"
        />
        <div className="p-5">
          {!started ? (
            <>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
                  dragging
                    ? "border-indigo-500 bg-indigo-50/50"
                    : "border-slate-300 bg-slate-50/50",
                )}
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
                  <Upload className="h-7 w-7" aria-hidden />
                </div>
                <p className="mt-4 text-sm font-medium text-slate-700">
                  Drag &amp; drop a document image here
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  or{" "}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="font-medium text-indigo-600 hover:text-indigo-500"
                  >
                    browse from your device
                  </button>
                </p>
                <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-[11px] text-slate-400">
                  <span className="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">
                    JPEG
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">
                    PNG
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">
                    WebP
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">
                    PDF
                  </span>
                  <span className="rounded-full bg-red-50 px-2.5 py-1 text-red-500 ring-1 ring-red-200">
                    max {MAX_SIZE_MB} MB
                  </span>
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_MIME.join(",")}
                className="sr-only"
                onChange={onPick}
              />
            </>
          ) : null}

          {/* Validation error */}
          {validationError ? (
            <div className="mt-4">
              <Alert title="File rejected">{validationError}</Alert>
            </div>
          ) : null}

          {/* Preview after upload */}
          {!started && file ? (
            <div className="mt-4">
              <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center">
                <div className="flex h-28 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white">
                  {previewUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={previewUrl}
                      alt={`Preview of ${file.name}`}
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <FileImage className="h-8 w-8 text-slate-300" aria-hidden />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                    <FileScan className="h-4 w-4 text-indigo-500" aria-hidden />
                    <span className="truncate">{file.name}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {file.type} · {formatBytes(file.size)} · ready
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={resetAll}
                    className="mt-2"
                  >
                    <X className="h-3.5 w-3.5" aria-hidden />
                    Remove
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      {/* Options */}
      {!started && file ? (
        <Card>
          <CardHeader
            title="Verification options"
            subtitle="Configure how this document is processed"
          />
          <div className="space-y-4 p-5">
            <div>
              <Label htmlFor="case-desc">Subject / description</Label>
              <Input
                id="case-desc"
                placeholder="e.g. Synthetic traveler at border checkpoint"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Checkbox
                checked={checkRegistry}
                onChange={(v) => setCheckRegistry(v)}
                label="Check against registry"
              />
              <Checkbox
                checked={performForensics}
                onChange={(v) => setPerformForensics(v)}
                label="Run forensic analysis"
              />
            </div>

            <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-3">
              <input
                type="checkbox"
                checked={attachLiveFace}
                onChange={(e) => setAttachLiveFace(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600"
              />
              <div>
                <div className="text-sm font-medium text-slate-800">
                  Attach live face capture
                </div>
                <div className="text-xs text-slate-500">
                  Optional — enables face similarity &amp; liveness checks
                </div>
              </div>
            </label>

            {attachLiveFace ? (
              <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                <span className="truncate">
                  {liveFace ? liveFace.name : "No live face attached"}
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  className="sr-only"
                  id="live-face-input"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setLiveFace(f);
                    e.target.value = "";
                  }}
                />
                <label
                  htmlFor="live-face-input"
                  className="ml-auto cursor-pointer text-xs font-medium text-indigo-600 hover:text-indigo-500"
                >
                  {liveFace ? "Replace" : "Choose file"}
                </label>
              </div>
            ) : null}

            <div className="flex justify-end">
              <Button onClick={startVerification} disabled={running}>
                <ScanIcon />
                Start verification
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Processing states */}
      {running ? (
        <Card>
          <CardHeader title="Processing" subtitle="Running the verification pipeline" />
          <ProcessingTracker stages={stageStates} />
        </Card>
      ) : null}

      {!running && caseId && newDocumentId ? (
        <Card>
          <div className="flex flex-col items-center gap-3 p-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <ShieldCheck className="h-6 w-6" aria-hidden />
            </div>
            <p className="text-sm text-slate-700">
              Verification pipeline finished.
            </p>
            <Button
              onClick={() =>
                router.push(`/verify/results?case=${caseId}&doc=${newDocumentId}`)
              }
            >
              View results
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function ScanIcon() {
  return (
    <span className="inline-flex items-center gap-2">
      <ShieldCheck className="h-4 w-4" aria-hidden />
      Start verification
    </span>
  );
}

function ProcessingTracker({ stages }: { stages: StageState[] }) {
  if (stages.length === 0) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
        <Spinner /> Preparing…
      </div>
    );
  }

  return (
    <ul className="divide-y divide-slate-50 p-2">
      {stages.map(({ stage, state }) => {
        const label = PROCESSING_LABELS[stage];
        const active = state === "active";
        return (
          <li
            key={stage}
            className="flex items-center gap-3 px-4 py-2.5 text-sm"
            aria-live="polite"
          >
            {state === "done" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" aria-hidden />
            ) : state === "error" ? (
              <XCircle className="h-4 w-4 shrink-0 text-red-500" aria-hidden />
            ) : active ? (
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-indigo-500" aria-hidden />
            ) : (
              <span className="h-4 w-4 shrink-0 rounded-full border-2 border-slate-200" aria-hidden />
            )}
            <span
              className={cn(
                "font-medium",
                state === "pending" ? "text-slate-400" : "text-slate-700",
              )}
            >
              {label}
            </span>
            {active ? (
              <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-indigo-500">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> running
              </span>
            ) : state === "done" ? (
              <span className="ml-auto text-xs text-emerald-600">done</span>
            ) : null}
          </li>
        );
      })}
      <li className="flex items-center gap-2 px-4 py-3 text-xs text-slate-400">
        <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        Processing is asynchronous — results appear on the results page.
      </li>
    </ul>
  );
}
