"use client";

import { Fragment, useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import {
  DEMO_STAGES,
  PHASE_LABELS,
  type DemoCase,
  type DemoStageId,
} from "@/data/demo/verificationCases";
import { Progress } from "@/components/ui";
import {
  VerificationStage,
  stageResultToState,
  type PipelineState,
} from "./VerificationStage";

const STAGE_DELAY_MS: Record<DemoStageId, number> = {
  capture: 320,
  classification: 460,
  preprocessing: 380,
  ocr: 620,
  validation: 460,
  face_detect: 440,
  face_verify: 560,
  tamper: 680,
  registry: 480,
  risk: 520,
  decision: 420,
  case: 320,
  hash: 380,
  blockchain: 520,
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function initialState(): Record<DemoStageId, PipelineState> {
  return DEMO_STAGES.reduce(
    (acc, s) => ({ ...acc, [s.id]: "pending" as PipelineState }),
    {} as Record<DemoStageId, PipelineState>,
  );
}

export function VerificationPipeline({
  demoCase,
  onComplete,
}: {
  demoCase: DemoCase;
  onComplete: () => void;
}) {
  const [states, setStates] = useState<Record<DemoStageId, PipelineState>>(
    initialState,
  );

  useEffect(() => {
    let cancelled = false;

    (async () => {
      for (const stage of DEMO_STAGES) {
        if (cancelled) return;
        setStates((prev) => ({ ...prev, [stage.id]: "processing" }));
        await sleep(STAGE_DELAY_MS[stage.id]);
        if (cancelled) return;
        const final = stageResultToState(demoCase.result.stageResults[stage.id].status);
        setStates((prev) => ({ ...prev, [stage.id]: final }));
      }
      if (!cancelled) onComplete();
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const done = DEMO_STAGES.filter(
    (s) => states[s.id] !== "pending" && states[s.id] !== "processing",
  ).length;
  const pct = Math.round((done / DEMO_STAGES.length) * 100);

  return (
    <div>
      <div className="flex items-center justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-neutral-500" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-[var(--text)]">
              Verification pipeline
            </div>
            <div className="text-xs text-[var(--muted)]">
              {done} / {DEMO_STAGES.length} stages complete · synthetic demo
              results
            </div>
          </div>
        </div>
        <span className="text-sm font-semibold tabular-nums text-[var(--text)]">
          {pct}%
        </span>
      </div>

      <div className="px-5 pt-4">
        <Progress value={pct} />
      </div>

      <ul className="mt-3" aria-live="polite">
        {DEMO_STAGES.map((stage, index) => {
          const showPhase =
            index === 0 || DEMO_STAGES[index - 1].phase !== stage.phase;
          const phaseHeader = showPhase ? (
            <li
              key={`phase-${stage.phase}`}
              className="bg-[#f8f9fc] px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-[var(--muted)]"
            >
              {PHASE_LABELS[stage.phase]}
            </li>
          ) : null;
          return (
            <Fragment key={stage.id}>
              {phaseHeader}
              <VerificationStage
                definition={stage}
                state={states[stage.id]}
                result={demoCase.result.stageResults[stage.id]}
                index={index}
              />
            </Fragment>
          );
        })}
      </ul>
    </div>
  );
}
