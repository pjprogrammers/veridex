"use client";

import { FileText, ShieldAlert } from "lucide-react";
import type { DemoIdentityDocument } from "@/data/demo/verificationCases";
import { Badge } from "@/components/ui";

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="py-1.5">
      <dt className="text-xs text-[var(--muted)]">{label}</dt>
      <dd className="text-sm font-medium text-[var(--text)]">{value || "—"}</dd>
    </div>
  );
}

export function DocumentDetails({
  document,
  documentFile,
  mrz,
}: {
  document: DemoIdentityDocument;
  documentFile: string;
  mrz: string[];
}) {
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-neutral-500" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-[var(--text)]">
              Document Details
            </div>
            <div className="text-xs text-[var(--muted)]">
              {document.documentType} · {document.passportNumber}
            </div>
          </div>
        </div>
        <Badge className="bg-black text-white ring-neutral-800/60">
          SYNTHETIC DEMO DATA
        </Badge>
      </div>

      <div className="grid gap-5 p-5 md:grid-cols-[200px_1fr]">
        <div className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[#f6f7fb]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/demo/${documentFile}`}
            alt="Synthetic demonstration document"
            className="h-full w-full object-contain"
          />
          <span className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 rotate-[-18deg] text-center text-[11px] font-bold uppercase tracking-widest text-black/25">
            Synthetic demo
          </span>
          <span className="absolute left-2 top-2 rounded bg-black/80 px-2 py-0.5 text-[10px] font-semibold text-white">
            NOT A REAL DOCUMENT
          </span>
        </div>

        <div>
          <dl className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
            <Field label="Document type" value={document.documentType} />
            <Field label="Passport number" value={document.passportNumber} />
            <Field label="Name" value={document.name} />
            <Field label="Nationality" value={document.nationality} />
            <Field label="Date of birth" value={document.dateOfBirth} />
            <Field label="Age" value={document.age} />
            <Field label="Sex" value={document.sex} />
            <Field label="Place of birth" value={document.placeOfBirth} />
            <Field label="Issue date" value={document.issueDate} />
            <Field label="Expiry date" value={document.expiryDate} />
            <Field label="Registry status" value={document.registryStatus} />
            <Field label="Watchlist status" value={document.watchlistStatus} />
          </dl>

          <div className="mt-4 border-t border-[var(--border)] pt-3">
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Synthetic MRZ
            </div>
            <pre className="overflow-x-auto whitespace-pre rounded-lg bg-[#f6f7fb] p-3 font-mono text-[11px] leading-5 text-[var(--text)]">
              {mrz.join("\n")}
            </pre>
          </div>

          <div className="mt-3 flex items-start gap-2 rounded-lg bg-[#f6f7fb] px-3 py-2">
            <ShieldAlert
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neutral-500"
              aria-hidden
            />
            <p className="text-[11px] leading-4 text-[var(--muted)]">
              This fictional passport is synthetic demonstration data. It is not
              issued by any government and does not represent a real person.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
