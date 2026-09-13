// VERIDEX SIH demonstration — static audit trail + simulated ledger record.
//
// The audit timeline is SYNTHETIC DEMO DATA. The SHA-256 hash is computed
// locally in the browser from the static case JSON (clearly labelled "DEMO").
// The blockchain record is SIMULATED: no Hyperledger Fabric node is contacted.

export interface DemoAuditEvent {
  /** Seconds after the demo run started (used to build display timestamps). */
  offsetSeconds: number;
  action: string;
  detail?: string;
}

export interface DemoBlockchainRecord {
  network: string;
  channel: string;
  status: string;
  /** Base block height; the final height is blockNumber + caseOffset. */
  blockNumber: number;
}

export interface DemoAudit {
  events: DemoAuditEvent[];
  blockchain: DemoBlockchainRecord;
}

const SHARED_EVENTS: DemoAuditEvent[] = [
  { offsetSeconds: 0, action: "Document uploaded", detail: "Static demo document loaded from local data" },
  { offsetSeconds: 1, action: "Document classified", detail: "Classifier result applied from static demo data" },
  { offsetSeconds: 2, action: "OCR completed", detail: "Structured fields applied from static demo data" },
  { offsetSeconds: 3, action: "MRZ validated", detail: "ICAO 9303 check digits applied from static demo data" },
  { offsetSeconds: 4, action: "Face verification completed", detail: "Similarity signal applied from static demo data" },
  { offsetSeconds: 5, action: "Forensic analysis completed", detail: "Detector findings applied from static demo data" },
  { offsetSeconds: 6, action: "Registry check completed", detail: "Simulated registry status applied" },
  { offsetSeconds: 7, action: "Risk score calculated", detail: "Deterministic risk factors applied" },
  { offsetSeconds: 8, action: "Decision generated", detail: "Decision-support recommendation applied" },
  { offsetSeconds: 9, action: "Audit hash generated", detail: "SHA-256 computed locally in the browser (DEMO)" },
  { offsetSeconds: 10, action: "Blockchain record simulated", detail: "Hyperledger Fabric — DEMO (no network connection)" },
];

export const DEMO_AUDITS: Record<string, DemoAudit> = {
  "VX-DEMO-0001": {
    events: SHARED_EVENTS,
    blockchain: {
      network: "Hyperledger Fabric — DEMO",
      channel: "veridex-audit-demo",
      status: "RECORD SIMULATED",
      blockNumber: 1847201,
    },
  },
  "VX-DEMO-0002": {
    events: SHARED_EVENTS,
    blockchain: {
      network: "Hyperledger Fabric — DEMO",
      channel: "veridex-audit-demo",
      status: "RECORD SIMULATED",
      blockNumber: 1847202,
    },
  },
  "VX-DEMO-0003": {
    events: SHARED_EVENTS,
    blockchain: {
      network: "Hyperledger Fabric — DEMO",
      channel: "veridex-audit-demo",
      status: "RECORD SIMULATED",
      blockNumber: 1847203,
    },
  },
};

/** Fixed demo hash used when the browser crypto API is unavailable. */
export const FIXED_DEMO_HASH =
  "d3adb33fd3adb33fd3adb33fd3adb33fd3adb33fd3adb33fd3adb33fd3adb33f";

export function getDemoAudit(caseId: string): DemoAudit | null {
  return DEMO_AUDITS[caseId] ?? null;
}

/**
 * Compute a real SHA-256 over a string using the browser Web Crypto API.
 * Returns the fixed demo hash when crypto is unavailable (e.g. SSR).
 */
export async function sha256Hex(input: string): Promise<string> {
  try {
    const subtle = globalThis.crypto?.subtle;
    if (!subtle) return FIXED_DEMO_HASH;
    const bytes = new TextEncoder().encode(input);
    const digest = await subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return FIXED_DEMO_HASH;
  }
}

/** Deterministic-looking transaction id derived from the audit hash. */
export function demoTxId(auditHash: string): string {
  return `0x${auditHash.slice(0, 24)}`;
}

/** Deterministic block height derived from the static base height. */
export function demoBlockHeight(base: number): number {
  return base;
}
