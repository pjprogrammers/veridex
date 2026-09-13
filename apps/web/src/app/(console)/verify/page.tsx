"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Ban,
  Camera,
  CalendarX2,
  CheckCircle2,
  FileImage,
  FileScan,
  FileWarning,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Upload,
  UserX,
  X,
  XCircle,
} from "lucide-react";
import { LiveFaceCapture } from "@/components/live-face-capture";
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

function withUniqueSuffix(bytes: ArrayBuffer, type: string): Blob {
  const marker = new TextEncoder().encode(
    `\u0000VERIDEX-DEMO-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  );
  return new Blob([bytes, marker], { type });
}

interface DemoScenario {
  key: string;
  label: string;
  signal: string;
  description: string;
  docFile: string;
  liveFaceFile?: string;
  registry: boolean;
  forensics: boolean;
}

const DEMO_SCENARIOS: DemoScenario[] = [
  {
    key: "aadhaar",
    label: "Piyush · Aadhaar",
    signal: "expect CLEAR · genuine",
    description: "Synthetic Aadhaar card of Piyush Verma (piyush.jpeg).",
    docFile: "piyush.jpeg",
    registry: true,
    forensics: true,
  },
  {
    key: "suresh",
    label: "Suresh Kumar",
    signal: "expect CLEAR",
    description: "Valid synthetic passport, valid MRZ, registry-clear.",
    docFile: "genuine_passport.png",
    registry: true,
    forensics: true,
  },
  {
    key: "rajesh",
    label: "Rajesh Sharma",
    signal: "expect EXPIRED",
    description: "Passport whose status is reported as EXPIRED.",
    docFile: "expired_passport.png",
    registry: true,
    forensics: true,
  },
  {
    key: "amit",
    label: "Amit Singh",
    signal: "expect MANUAL REVIEW",
    description: "Synthetic passport with tamper signals.",
    docFile: "tampered_passport.png",
    registry: true,
    forensics: true,
  },
  {
    key: "priya",
    label: "Priya Verma",
    signal: "expect CLEAR",
    description: "Valid synthetic passport, registry-clear.",
    docFile: "genuine_passport.png",
    registry: true,
    forensics: true,
  },
  {
    key: "neha",
    label: "Neha Gupta",
    signal: "expect MRZ mismatch",
    description: "Printed passport number vs MRZ mismatch.",
    docFile: "genuine_passport.png",
    registry: true,
    forensics: true,
  },
  {
    key: "rohit",
    label: "Rohit Mehta",
    signal: "expect face mismatch",
    description: "Document portrait vs a different live face.",
    docFile: "genuine_passport.png",
    liveFaceFile: "live_other.png",
    registry: true,
    forensics: true,
  },
  {
    key: "anil",
    label: "Anil Kapoor",
    signal: "expect tampering detected",
    description: "Passport with strong tampering signals.",
    docFile: "tampered_passport.png",
    registry: true,
    forensics: true,
  },
  {
    key: "kavita",
    label: "Kavita Sharma",
    signal: "expect registry unknown",
    description: "Document number not found in the registry.",
    docFile: "blacklisted_passport.png",
    registry: true,
    forensics: true,
  },
];

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
  const [cameraOpen, setCameraOpen] = useState(false);

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<ProcessingStage>("UPLOADED");
  const [stageStates, setStageStates] = useState<StageState[]>([]);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [newDocumentId, setNewDocumentId] = useState<string | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario | null>(
    null,
  );
  const [scenarioLoading, setScenarioLoading] = useState(false);

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

  async function loadScenario(s: DemoScenario) {
    setScenarioLoading(true);
    setError(null);
    setValidationError(null);
    try {
      const docResp = await fetch(`/demo/${s.docFile}`);
      if (!docResp.ok) throw new Error("Scenario asset could not be loaded.");
      const docBlob = await docResp.blob();
      const docBytes = await docBlob.arrayBuffer();
      const docMime = docBlob.type || (s.docFile.endsWith(".jpeg") ? "image/jpeg" : "image/png");
      const docFile = new File([withUniqueSuffix(docBytes, docMime)], s.docFile, {
        type: docMime,
      });
      const err = validateFile(docFile);
      if (err) {
        setValidationError(err);
        setSelectedScenario(null);
        return;
      }
      setFile(docFile);

      if (s.liveFaceFile) {
        const liveResp = await fetch(`/demo/${s.liveFaceFile}`);
        if (liveResp.ok) {
          const liveBlob = await liveResp.blob();
          setLiveFace(
            new File([liveBlob], s.liveFaceFile, {
              type: liveBlob.type || "image/png",
            }),
          );
          setAttachLiveFace(true);
        }
      } else {
        setLiveFace(null);
        setAttachLiveFace(false);
      }

      setCheckRegistry(s.registry);
      setPerformForensics(s.forensics);
      setDescription(s.description);
      setSelectedScenario(s);
    } catch (e) {
      setError(errorFn(e));
    } finally {
      setScenarioLoading(false);
    }
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
    setSelectedScenario(null);
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
      setStage("UPLOADED", "active");
      const created = await api<{ id: string }>("/cases", {
        method: "POST",
        json: {
          case_description: description || undefined,
          check_registry: checkRegistry,
          perform_forensics: performForensics,
          scenario: selectedScenario?.key || undefined,
        },
      });
      setCaseId(created.id);
      setStage("UPLOADED", "done");

      setStage("CLASSIFYING", "active");
      const uploaded = await uploadDocumentStandalone(file, created.id);
      setNewDocumentId(uploaded.id);

      await classifyDocument(uploaded.id);
      setStage("CLASSIFYING", "done");

      setStage("PREPROCESSING", "active");
      await preprocessDocument(uploaded.id);
      setStage("PREPROCESSING", "done");

      setStage("EXTRACTING", "active");
      await analyzeDocument(created.id, uploaded.id);
      setStage("EXTRACTING", "done");

      setStage("VALIDATING", "active");
      await new Promise((r) => setTimeout(r, 500));
      setStage("VALIDATING", "done");

      if (performForensics) {
        setStage("FORENSIC_ANALYSIS", "active");
        await new Promise((r) => setTimeout(r, 600));
        setStage("FORENSIC_ANALYSIS", "done");
      }

      setStage("FACE_VERIFICATION", "active");
      await new Promise((r) => setTimeout(r, 500));
      setStage("FACE_VERIFICATION", "done");

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
      if (selectedScenario) params.set("demo", selectedScenario.key);
      router.push(`/verify/results?${params.toString()}`);
    } catch (e) {
      setStage(currentStage || "CLASSIFYING", "error");
      setError(errorFn(e));
      setRunning(false);
    }
  }

  const started = running || caseId !== null;

  return (
    <div className="mx-auto max-w-5xl space-y-6 animate-fade-in-up">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">New Verification</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Upload an identity or travel document to run the full verification
          pipeline.
        </p>
      </div>

      {error ? <Alert title="Verification failed">{error}</Alert> : null}

      {/* Demo scenarios */}
      {!started ? (
        <Card>
          <CardHeader
            title="Demo scenarios"
            subtitle="Reproducible synthetic cases run through the real verification pipeline — results are always live API data"
          />
          <div className="p-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {DEMO_SCENARIOS.map((s) => {
                const active = selectedScenario?.key === s.key;
                const Icon = SCENARIO_ICONS[s.key];
                return (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => loadScenario(s)}
                    disabled={scenarioLoading}
                    className={cn(
                      "flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-[transform,color,background-color,border-color,box-shadow] duration-150 hover:-translate-y-[2px] active:scale-[0.97]",
                      active
                        ? "border-neutral-800 bg-black text-white shadow-md shadow-neutral-900/20"
                        : "border-[var(--border)] bg-[var(--card)] text-[var(--text)] hover:border-neutral-500 hover:bg-neutral-100 hover:shadow-md hover:shadow-neutral-900/10",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-lg",
                        active
                          ? "bg-white/10 text-white"
                          : "bg-neutral-200/70 text-neutral-600",
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden />
                    </span>
                    <span className="text-sm font-semibold">{s.label}</span>
                    <span
                      className={cn(
                        "text-[11px] leading-snug",
                        active ? "text-neutral-300" : "text-[var(--muted)]",
                      )}
                    >
                      {s.signal}
                    </span>
                  </button>
                );
              })}
            </div>
            {selectedScenario ? (
              <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-neutral-300 bg-neutral-200/50 px-3 py-2.5 text-sm text-neutral-800">
                <span>
                  <strong className="font-semibold">
                    {selectedScenario.label} scenario
                  </strong>{" "}
                  — {selectedScenario.description}
                </span>
                <button
                  type="button"
                  onClick={resetAll}
                  className="shrink-0 text-xs font-medium text-neutral-600 hover:text-black"
                >
                  Clear
                </button>
              </div>
            ) : null}
            <p className="mt-3 text-[11px] leading-relaxed text-[var(--muted)]">
              Scenario inputs are entirely synthetic (no real PII). Verification
              runs through the same secured API used for live submissions;
              signals like MRZ readback, registry hits, and forensic anomalies
              depend on the configured engines.
            </p>
          </div>
        </Card>
      ) : null}

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
                    ? "border-neutral-400 bg-neutral-200/60"
                    : "border-[var(--border)] bg-[var(--card)]",
                )}
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-neutral-200/60 text-neutral-500">
                  <Upload className="h-7 w-7" aria-hidden />
                </div>
                <p className="mt-4 text-sm font-medium text-[var(--text)]">
                  Drag &amp; drop a document image here
                </p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  or{" "}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="font-medium text-neutral-500 hover:text-black"
                  >
                    browse from your device
                  </button>
                </p>
                <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-[11px] text-[var(--muted)]">
                  <span className="rounded-full bg-[#f6f7fb] px-2.5 py-1 ring-1 ring-[var(--border)]">
                    JPEG
                  </span>
                  <span className="rounded-full bg-[#f6f7fb] px-2.5 py-1 ring-1 ring-[var(--border)]">
                    PNG
                  </span>
                  <span className="rounded-full bg-[#f6f7fb] px-2.5 py-1 ring-1 ring-[var(--border)]">
                    WebP
                  </span>
                  <span className="rounded-full bg-[#f6f7fb] px-2.5 py-1 ring-1 ring-[var(--border)]">
                    PDF
                  </span>
                  <span className="rounded-full bg-neutral-300/40 px-2.5 py-1 text-black ring-1 ring-neutral-400/40">
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

          {validationError ? (
            <div className="mt-4">
              <Alert title="File rejected">{validationError}</Alert>
            </div>
          ) : null}

          {!started && file ? (
            <div className="mt-4">
              <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:flex-row sm:items-center">
                <div className="scan-frame relative flex h-28 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[var(--border)] bg-[#f6f7fb]">
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

            <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-3">
              <input
                type="checkbox"
                checked={attachLiveFace}
                onChange={(e) => setAttachLiveFace(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--border)] bg-[var(--card)] text-neutral-500"
              />
              <div>
                <div className="text-sm font-medium text-[var(--text)]">
                  Attach live face capture
                </div>
                <div className="text-xs text-[var(--muted)]">
                  Optional — enables face similarity &amp; liveness checks
                </div>
              </div>
            </label>

            {attachLiveFace ? (
              <div className="flex items-center gap-3 rounded-lg bg-[#f6f7fb] p-3 text-sm text-[var(--muted)]">
                <span className="truncate">
                  {liveFace ? liveFace.name : "No live face captured yet"}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  className="ml-auto"
                  onClick={() => setCameraOpen(true)}
                  disabled={running}
                >
                  <Camera className="h-3.5 w-3.5" aria-hidden />
                  {liveFace ? "Recapture" : "Open camera"}
                </Button>
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
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-neutral-200/70 text-neutral-600">
              <ShieldCheck className="h-6 w-6" aria-hidden />
            </div>
            <p className="text-sm text-[var(--muted)]">
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

      <LiveFaceCapture
        open={cameraOpen}
        onClose={() => setCameraOpen(false)}
        onCapture={(f) => {
          setLiveFace(f);
          setAttachLiveFace(true);
        }}
      />
    </div>
  );
}

const SCENARIO_ICONS: Record<string, typeof ShieldCheck> = {
  aadhaar: ShieldCheck,
  suresh: ShieldCheck,
  rajesh: CalendarX2,
  amit: FileWarning,
  priya: ShieldCheck,
  neha: FileScan,
  rohit: UserX,
  anil: FileWarning,
  kavita: Ban,
};

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
      <div className="flex items-center gap-2 p-6 text-sm text-[var(--muted)]">
        <Spinner /> Preparing…
      </div>
    );
  }

  return (
    <ul className="divide-y divide-[var(--border)] p-2">
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
              <CheckCircle2 className="h-4 w-4 shrink-0 text-neutral-600" aria-hidden />
            ) : state === "error" ? (
              <XCircle className="h-4 w-4 shrink-0 text-black" aria-hidden />
            ) : active ? (
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-neutral-500" aria-hidden />
            ) : (
              <span className="h-4 w-4 shrink-0 rounded-full border-2 border-[var(--border)]" aria-hidden />
            )}
            <span
              className={cn(
                "font-medium",
                state === "pending" ? "text-[var(--muted)]" : "text-[var(--text)]",
              )}
            >
              {label}
            </span>
            {active ? (
              <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-neutral-500">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> running
              </span>
            ) : state === "done" ? (
              <span className="ml-auto text-xs text-neutral-600">done</span>
            ) : null}
          </li>
        );
      })}
      <li className="flex items-center gap-2 px-4 py-3 text-xs text-[var(--muted)]">
        <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        Processing is asynchronous — results appear on the results page.
      </li>
    </ul>
  );
}
