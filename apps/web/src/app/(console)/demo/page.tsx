"use client";

import { Suspense, useCallback, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  CalendarX2,
  FileWarning,
  FlaskConical,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  AADHAAR_DEMO,
  DEMO_CASES,
  getDemoCase,
} from "@/data/demo/verificationCases";
import type { DemoDecision } from "@/data/demo/demoResults";
import { Alert, Badge, Button, Card, CardHeader } from "@/components/ui";
import { cn } from "@/lib/utils";
import { DemoDashboard } from "@/components/verification/DemoDashboard";
import { VerificationPipeline } from "@/components/verification/VerificationPipeline";
import { DecisionPanel } from "@/components/verification/DecisionPanel";
import { RiskBreakdown } from "@/components/verification/RiskBreakdown";
import { DocumentDetails } from "@/components/verification/DocumentDetails";
import { ForensicAnalysis } from "@/components/verification/ForensicAnalysis";
import { FaceVerification } from "@/components/verification/FaceVerification";
import { CaseManagement } from "@/components/verification/CaseManagement";
import { AuditTimeline } from "@/components/verification/AuditTimeline";
import { ArchitectureMap } from "@/components/verification/ArchitectureMap";

const DECISION_CLASS: Record<DemoDecision, string> = {
  CLEAR: "bg-neutral-200/70 text-neutral-700 ring-neutral-400/40",
  ALERT: "bg-black text-white ring-neutral-800/60",
  MANUAL_REVIEW: "bg-neutral-400/40 text-neutral-900 ring-neutral-500/40",
};

const CASE_ICONS: Record<string, typeof ShieldCheck> = {
  suresh: ShieldCheck,
  rajesh: CalendarX2,
  amit: FileWarning,
};

type Phase = "idle" | "running" | "complete";

export default function DemoPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl p-6 text-sm text-[var(--muted)]">
          Loading demo…
        </div>
      }
    >
      <DemoInner />
    </Suspense>
  );
}

function DemoInner() {
  const params = useSearchParams();
  const preselected = params.get("case");

  const [selectedId, setSelectedId] = useState<string | null>(() =>
    preselected && getDemoCase(preselected) ? preselected : null,
  );
  const [phase, setPhase] = useState<Phase>("idle");
  const [runId, setRunId] = useState(0);
  const [createdAt, setCreatedAt] = useState<string | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const selected = selectedId ? getDemoCase(selectedId) : null;

  const selectCase = useCallback((id: string) => {
    setSelectedId(id);
    setPhase("idle");
    setCreatedAt(null);
  }, []);

  const startRun = useCallback(() => {
    if (!selectedId) return;
    setCreatedAt(null);
    setRunId((n) => n + 1);
    setPhase("running");
  }, [selectedId]);

  const onComplete = useCallback(() => {
    setCreatedAt(new Date().toISOString());
    setPhase("complete");
    window.setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">
            SIH Demonstration Workflow
          </h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Select a synthetic case, run the static pipeline, and inspect every
            stage, risk factor and audit entry. No backend calls are made.
          </p>
        </div>
        <Badge className="bg-black text-white ring-neutral-800/60">
          <FlaskConical className="h-3 w-3" aria-hidden />
          SYNTHETIC DEMO DATA
        </Badge>
      </div>

      <Alert tone="info" title="Demonstration notice">
        All results on this page are predetermined static data. No OCR, face,
        forensic or blockchain engine is actually executed, and no synthetic
        record represents a real person or government document.
      </Alert>

      <DemoDashboard />

      {/* Case selection */}
      <Card>
        <CardHeader
          title="Demo cases"
          subtitle="Three synthetic Indian passport cases plus the existing genuine Aadhaar demo"
        />
        <div className="p-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {DEMO_CASES.map((c) => {
              const Icon = CASE_ICONS[c.key] ?? ShieldCheck;
              const active = selectedId === c.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => selectCase(c.id)}
                  disabled={phase === "running"}
                  className={cn(
                    "flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-[transform,color,background-color,border-color,box-shadow] duration-150 hover:-translate-y-[2px] active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-60",
                    active
                      ? "border-neutral-800 bg-black text-white shadow-md shadow-neutral-900/20"
                      : "border-[var(--border)] bg-[var(--card)] text-[var(--text)] hover:border-neutral-500 hover:bg-neutral-100",
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
                  <span className="text-sm font-semibold">{c.name}</span>
                  <span
                    className={cn(
                      "font-mono text-[11px]",
                      active ? "text-neutral-300" : "text-[var(--muted)]",
                    )}
                  >
                    {c.document.passportNumber}
                  </span>
                  <span
                    className={cn(
                      "text-[11px] leading-snug",
                      active ? "text-neutral-300" : "text-[var(--muted)]",
                    )}
                  >
                    {c.signal}
                  </span>
                  <Badge
                    className={cn(
                      "mt-1",
                      active
                        ? "bg-white/15 text-white ring-white/30"
                        : DECISION_CLASS[c.result.decision.verdict],
                    )}
                  >
                    {c.result.decision.verdict.replace(/_/g, " ")}
                  </Badge>
                </button>
              );
            })}

            <Link
              href={AADHAAR_DEMO.href}
              className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-4 text-left text-[var(--text)] transition-colors hover:border-neutral-500 hover:bg-neutral-100"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-neutral-200/70 text-neutral-600">
                <ShieldCheck className="h-4 w-4" aria-hidden />
              </span>
              <span className="text-sm font-semibold">{AADHAAR_DEMO.label}</span>
              <span className="font-mono text-[11px] text-[var(--muted)]">
                {AADHAAR_DEMO.document}
              </span>
              <span className="text-[11px] leading-snug text-[var(--muted)]">
                {AADHAAR_DEMO.note}
              </span>
              <Badge className="mt-1 bg-neutral-200/70 text-neutral-700 ring-neutral-400/40">
                EXISTING · CLEAR
              </Badge>
            </Link>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-[var(--muted)]">
              {selected
                ? `Selected ${selected.caseInfo.caseId} · ${selected.name}`
                : "Select a synthetic passport case to enable the demo pipeline."}
            </p>
            <div className="flex items-center gap-2">
              {phase === "complete" ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPhase("idle");
                    setCreatedAt(null);
                  }}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden />
                  Reset
                </Button>
              ) : null}
              <Button onClick={startRun} disabled={!selected || phase === "running"}>
                {phase === "running" ? (
                  <RefreshCw className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <ShieldCheck className="h-4 w-4" aria-hidden />
                )}
                {phase === "running" ? "Running…" : "Run Verification"}
              </Button>
            </div>
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-[var(--muted)]">
            The genuine Aadhaar demonstration remains available through the live
            verification page and is preserved exactly as it currently works.
          </p>
        </div>
      </Card>

      {/* Pipeline */}
      {phase !== "idle" && selected ? (
        <Card>
          <VerificationPipeline
            key={runId}
            demoCase={selected}
            onComplete={onComplete}
          />
        </Card>
      ) : null}

      {/* Results */}
      {phase === "complete" && selected && createdAt ? (
        <div ref={resultsRef} className="space-y-6 scroll-mt-6">
          <DecisionPanel
            decision={selected.result.decision}
            riskScore={selected.result.risk.score}
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="lg:col-span-2">
              <RiskBreakdown
                score={selected.result.risk.score}
                level={selected.result.risk.level}
                decision={selected.result.decision.verdict}
                factors={selected.result.risk.factors}
              />
            </Card>

            <Card className="lg:col-span-2">
              <DocumentDetails
                document={selected.document}
                documentFile={selected.documentFile}
                mrz={selected.mrz}
              />
            </Card>

            <Card>
              <ForensicAnalysis forensics={selected.result.forensics} />
            </Card>

            <Card>
              <FaceVerification
                face={selected.result.face}
                subject={selected.document.name}
              />
            </Card>

            <Card className="lg:col-span-2">
              <CaseManagement demoCase={selected} createdAt={createdAt} />
            </Card>

            <Card className="lg:col-span-2">
              <AuditTimeline demoCase={selected} createdAt={createdAt} />
            </Card>

            <Card className="lg:col-span-2">
              <ArchitectureMap decision={selected.result.decision.verdict} />
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
