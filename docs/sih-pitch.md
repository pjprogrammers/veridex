# VERIDEX — Smart India Hackathon 2026

**Problem Statement 26188 · Identity & Document Fraud Detection at Border/Checkpoint Control**

---

## The Problem

Every year, border and checkpoint officers across India inspect millions of
identity and travel documents — passports, national IDs, visas, driving
licenses.  Officers face:

- **Volume pressure**: high-traffic crossings process thousands of travellers
  per shift; manual inspection is slow and fatiguing.
- **Sophistication**: modern forgeries exploit advanced printing, digital photo
  substitution, and MRZ manipulation; subtle signs are invisible to the naked
  eye.
- **No decision support**: officers rely solely on visual inspection; there is
  no system that systematically cross-checks documents against known databases,
  forensic signals, or risk indicators — leading to either missed detections or
  excessive secondary screening delays.

The result: long queues, missed fraud indicators, and unnecessary
false-positive delays that harm legitimate travellers.

---

## Our Solution: VERIDEX

**VERIDEX** is an end-to-end, AI-powered decision-support system that
amplifies an officer's expertise — it never makes an enforcement decision;
it gives the officer a clear, explainable, auditable risk picture in seconds.

```
┌───────────────────────────────────────────────────────────┐
│  Officer uploads document image  (+ optional live face)   │
└───────────────────────────┬───────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  Document Pipeline          │
              │  · Quality check            │
              │  · Document type ID         │
              │  · OCR (PaddleOCR)          │
              │  · MRZ parse + validation   │
              └─────────────┬──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌──────────┐      ┌──────────┐      ┌──────────────┐
  │Forensics │      │  Face    │      │  Registry    │
  │ELA, noise│      │ portrait │      │police/       │
  │copy-move │      │ match    │      │immigration/  │
  │edge sig  │      │ liveness │      │blacklist     │
  └────┬─────┘      └────┬─────┘      └──────┬───────┘
       │                 │                    │
       └─────────────────┼────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  Explainable Risk   │
              │  Engine             │
              │  Factor + score +   │
              │  recommendation     │
              └─────────┬──────────┘
                        ▼
              ┌─────────────────────┐
              │  Case + Audit Trail │
              │  SHA-256 chained,   │
              │  tamper-evident     │
              └─────────────────────┘
```

---

## What Makes VERIDEX Different

| Feature | Traditional systems | VERIDEX |
|---|---|---|
| **Decision** | Black-box / autonomous | Explainable risk factors shown to officer; no autonomy |
| **Forensics** | Manual, ad-hoc | Automated ELA + noise + copy-move + edge analysis |
| **Face** | No liveness check | Baseline liveness + duplicate identity detection |
| **Registry** | Manual DB lookup | Automated cross-check across police/immigration/blacklist registries |
| **Audit** | Basic logging | SHA-256 chained, tamper-evident log with chain-verification endpoint |
| **Deployment** | Heavy infra | Runs locally on any laptop or in a Docker container — zero cloud dependency |

---

## Architecture

| Layer | Technology | Purpose |
|---|---|---|
| **Dashboard** | Next.js 16, React 19, TypeScript, Tailwind | Officer UI — case list, analysis, risk gauge, audit trail |
| **API Gateway** | FastAPI, Pydantic v2, SQLAlchemy async | Authentication, routing, orchestration |
| **Document Pipeline** | PaddleOCR, MRZ parser (ICAO 9303), OpenCV | OCR, MRZ validation, document type classification |
| **Forensics** | OpenCV (error level analysis, Laplacian variance, frequency-domain noise) | Tampering signal detection |
| **Face Verification** | InsightFace (optional), baseline cosine matcher | Portrait vs live-face match, liveness heuristic, duplicate detection |
| **Risk Engine** | Custom weighted model | Combines all signals into a single explainable 0–1 score with LOW/MEDIUM/HIGH/CRITICAL levels |
| **Case Management** | SQLAlchemy async + PostgreSQL | Full CRUD, status workflow, linked documents |
| **Audit Trail** | SHA-256 chained hash with previous-hash pointer | Tamper-evident; `/audit/verify` detects any modification |
| **Data** | PostgreSQL, Redis (rate limit), MinIO (doc storage) | Production-grade; SQLite fallback for standalone demo |
| **Security** | JWT + Argon2 + RBAC | Role-based access; officer vs admin separation |

---

## Key Files

| Path | What it does |
|---|---|
| `services/api/app/forensics/analyze.py` | ELA, noise variance, copy-move detection, edge density |
| `services/api/app/face/analysis.py` | Portrait extraction, cosine similarity, liveness heuristic |
| `services/api/app/risk/engine.py` | Explainable risk scoring — `RiskEngine.compute()` |
| `services/api/app/services/audit.py` | Tamper-evident SHA-256 chained audit log |
| `services/api/app/services/verify.py` | Orchestrator — runs all checks and feeds the risk engine |
| `services/api/app/validation/fields.py` | Field format validation (DOB, document number, sex code) |
| `services/api/app/validation/cross_validate.py` | OCR vs MRZ cross-consistency check |
| `scripts/synthetic_documents.py` | Generates ICAO-compliant synthetic passport images |

---

## Demo Walkthrough (3 minutes)

1. **Login** → officer sees populated dashboard (case list, risk distribution chart)
2. **Registry lookup** → enter `P12345678` → system returns `valid` (matches seeded passport)
3. **Registry lookup** → enter `N87654321` → system returns `reported_stolen` — risk spikes
4. **Open a case** → select "High scrutiny traveller" → case created
5. **Upload synthetic passport** → `passport_P12345678.png`
6. **Full verification** → system runs pipeline + forensics + face + registry
7. **Result**: explainable risk gauge, contributing factors, MRZ validation, forensic signals
8. **Audit trail** → view chained log; click "Verify chain integrity" → ✅ confirmed
9. **Status update** → officer marks case as `under_examination` (audit logged)

---

## Our Approach: Decision-Support Only

VERIDEX is deliberately **not** an autonomous fraud detector.

- Language: "potential manipulation detected", "verification mismatch",
  "high-risk indicators" — never "fraud" or "fake"
- Every risk score includes its contributing factors
- The officer always makes the final call
- Every action is logged in a tamper-evident audit trail
- Clear disclaimer: "This is a decision-support analysis. It does not prove
  authenticity or fraud."

This is intentional: AI augments the officer's expertise; it does not replace
the officer's judgment.

---

## Technical Highlights

### Explainable Risk Engine

The risk engine combines weighted signals from all subsystems:

```
risk_score = 0.4 × mean(all signals) + 0.6 × max(signal)
```

Each signal is normalised to 0–1. Thresholds:
- `score < 0.4` → LOW (green)
- `0.4 ≤ score < 0.7` → MEDIUM (amber)
- `0.7 ≤ score < 1.0` → HIGH (orange/red)
- `score ≥ 1.0` → CRITICAL (auto-flagged)

Contributing factors are always surfaced to the officer.

### Tamper-Evident Audit Trail

Every case action produces an `AuditLog` entry.  Each entry's hash is computed
from its content + the previous entry's hash, forming an immutable chain.
The `/audit/verify/{case_id}` endpoint recomputes every hash and reports any
tampering — identical to how blockchain verification works, implemented
without any external chain infrastructure.

### ICAO 9303 MRZ Compliance

The synthetic passport generator and MRZ parser both implement the full
ICAO 9303 check-digit algorithm (weights 7,3,1 repeating) for TD1 and TD3
formats, ensuring the system accepts and validates real-world passport MRZ
lines correctly.

---

## Standalone Demo Mode

VERIDEX runs fully without Docker for quick demos:

```bash
make seed-local   # SQLite DB with users, 200 registry entries, demo cases
make api-local    # FastAPI on :8000
make web-dev      # Dashboard on :3000
```

No cloud, no external databases — runs on any laptop with Python 3.11+ and
Node.js 18+.

---

## Security by Design

- **No real PII**: all identities are synthetic; data never leaves the machine
- **JWT + Argon2**: industry-standard password hashing and token auth
- **RBAC**: officer vs admin separation; only admins can delete cases or
  write to the registry
- **SHA-256 audit chaining**: any modification to the audit log is detectable
- **Structured logging**: no PII in logs; all events carry context metadata
- **Rate limiting**: per-client in-memory (scales to Redis in production)

---

## Future Scope

| Phase | Description |
|---|---|
| GPU inference | Move PaddleOCR/InsightFace to GPU for sub-second verification |
| Real-time face liveness | Certified spoof detection (presentation attack detection) |
| Hyperledger anchoring | Anchor audit hashes to a permissioned blockchain |
| Multi-language OCR | Support for Hindi, Arabic, Mandarin MRZ and document text |
| Mobile-first | React Native app for officers at remote checkpoints |
| Integration API | REST/GraphQL API for immigration systems and Interpol lookups |

---

## Team

*Smart India Hackathon 2026 · Problem Statement 26188*

Built to make border control faster, fairer, and more secure — without
replacing the officer's judgment.

> "AI gives the officer superpowers, not a replacement badge."
