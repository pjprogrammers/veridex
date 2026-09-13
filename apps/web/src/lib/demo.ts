/**
 * Convenience re-exports for the VERIDEX SIH demonstration. All data is
 * synthetic, deterministic and frontend-only.
 */
export const DEMO_MODE_LABEL = "VERIDEX • SIH DEMONSTRATION MODE";
export const SYNTHETIC_LABEL =
  "SYNTHETIC DATA — NOT FOR REAL IDENTITY VERIFICATION";
export const SYNTHETIC_BADGE = "SYNTHETIC DEMO DATA";

export {
  AADHAAR_DEMO,
  DEMO_CASES,
  DEMO_STAGES,
  PHASE_LABELS,
  getDemoCase,
  getDemoCaseById,
  getDemoCaseByKey,
  getDemoStats,
} from "@/data/demo/verificationCases";
export type {
  DemoCase,
  DemoIdentityDocument,
  DemoStageDefinition,
} from "@/data/demo/verificationCases";
