"use client";

import { Camera, UserCheck } from "lucide-react";
import type { DemoFace } from "@/data/demo/demoResults";
import { Badge, StatDisplay } from "@/components/ui";

export function FaceVerification({
  face,
  subject,
}: {
  face: DemoFace;
  subject: string;
}) {
  return (
    <div>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-neutral-500" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-[var(--text)]">
              Face Verification
            </div>
            <div className="text-xs text-[var(--muted)]">
              Document portrait vs live capture · {subject}
            </div>
          </div>
        </div>
        <Badge className="bg-neutral-200/70 text-neutral-700 ring-neutral-400/40">
          {face.match}
        </Badge>
      </div>

      <div className="space-y-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <StatDisplay label="Face detection" value={face.detection} />
          <StatDisplay label="Liveness" value={face.liveness} />
          <StatDisplay label="Face embedding" value={face.embedding} />
          <StatDisplay label="Threshold" value={`${face.threshold}%`} />
          <StatDisplay label="Final match" value={face.match} />
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
              <UserCheck className="h-4 w-4 text-neutral-500" aria-hidden />
              Similarity score
            </span>
            <span className="text-sm font-bold tabular-nums text-[var(--text)]">
              {face.similarity.toFixed(1)}%
            </span>
          </div>
          <div className="relative mt-3">
            <div className="progress-track h-2.5">
              <div
                className="progress-fill micro-grow-x h-full rounded-full bg-black"
                style={{ width: `${Math.min(100, face.similarity)}%` }}
              />
            </div>
            <div
              className="absolute -top-1 h-4 border-l-2 border-dashed border-neutral-500"
              style={{ left: `${face.threshold}%` }}
              aria-hidden
            />
          </div>
          <div
            className="mt-1 text-[11px] text-[var(--muted)]"
            style={{ paddingLeft: `${Math.max(0, face.threshold - 6)}%` }}
          >
            Demo threshold {face.threshold}%
          </div>
        </div>

        <p className="rounded-lg bg-[#f6f7fb] px-3 py-2 text-[11px] leading-4 text-[var(--muted)]">
          Face matching is a similarity signal, not proof of identity and not the
          reason any passport in this demonstration is flagged. All examples are
          synthetic.
        </p>
      </div>
    </div>
  );
}
