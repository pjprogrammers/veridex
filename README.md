# VERIDEX

AI-Powered Fake Identity & Document Screening System for border/checkpoint officers.

**Prototype for Smart India Hackathon (SIH) — Problem Statement SIH26188**

> **IMPORTANT**: This is an officer **decision-support** system. AI results never
> prove a document is fraudulent. The system uses calibrated language
> ("potential manipulation detected", "verification mismatch", "high-risk
> indicators") and always recommends manual review. It does **not** autonomously
> make legal or enforcement decisions.

## Overview

VERIDEX is an end-to-end document and identity screening prototype that:
1. Accepts identity/travel document images
2. Identifies document type and assesses image quality
3. Preprocesses and runs OCR (PaddleOCR)
4. Parses and validates passport MRZ
5. Cross-validates OCR vs MRZ data
6. Performs cross-document consistency checks
7. Detects potential tampering (forensic signals)
8. Extracts and verifies the document portrait against a live face
9. Performs basic liveness/presentation-attack checks
10. Checks document status against a local/synthetic registry
11. Detects duplicate/multiple identities via face embeddings
12. Calculates an **explainable** risk score
13. Creates case records with a tamper-evident, SHA-256-chained audit trail

The officer dashboard (`apps/web`) provides the main console sections: **Overview**,
**Cases** (new verification + document analysis + face verification + forensics + risk),
**Registry**, and **System Health**.

## Architecture

```
Frontend (Next.js) → API Gateway (FastAPI) → Verification Orchestrator
                                              ├── OCR/MRZ Service
                                              ├── Forensics Service
                                              ├── Face Verification Service
                                              └── Registry Service
                                              ↓
                              Validation → Risk Engine → Case Mgmt → Audit/Hash
```

## Stack

- **Frontend**: Next.js, React, TypeScript, Tailwind CSS, custom component system, Recharts, Lucide icons
- **Backend**: Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic
- **AI/CV**: OpenCV, PaddleOCR, MRZ parsing, InsightFace, scikit-learn, NumPy
- **Data**: PostgreSQL, Redis, MinIO (S3-compatible)
- **Infrastructure**: Docker, Docker Compose
- **Security**: JWT, RBAC (`users → user_roles → roles`), Argon2 hashing, SHA-256 audit chaining, rate limiting, X-Request-ID correlation IDs
- **RBAC roles**: `OFFICER`, `SUPERVISOR`, `ADMIN`, `AUDITOR`

## Quick Start

```bash
make setup      # config + build images + start infra + migrate
make dev        # run all services (API on :8000, Web on :3000)
```

Or step by step:
```bash
cp .env.example .env
docker compose up --build
```

Default credentials (synthetic only):
- Admin: `admin` / `VeridexDev123!`
- Officer: `officer1` / `OfficerDev123!`
- Supervisor: `supervisor1` / `SupervisorDev123!`
- Auditor: `auditor1` / `AuditorDev123!`

## Standalone mode (no Docker)

The API can run entirely against a local SQLite file — useful for quick
demos of the auth, case, registry and audit/verification surfaces. Document
upload and full verification still require MinIO (run via `make dev`).

```bash
make seed-local   # create ./services/api/veridex.db with users, registry, demo cases
make api-local    # API on :8000 (uvicorn, reload)
make web-dev      # dashboard on :3000
```

Synthetic demo documents (passport with a valid ICAO TD3 machine-readable
zone) are generated into `data/synthetic/`:

```bash
make gen-docs
```

The generated passport document numbers match the seeded registry entries
(e.g. `P12345678` is a `valid` passport, `N87654321` is `reported_stolen`),
so registry lookups and full verification can be exercised end to end.

## Repository Layout

```
veridex/
├── .env.example            # environment template (tracked)
├── docker-compose.yml      # full stack orchestration
├── Makefile                # dev commands (dev, test, lint, seed-local, api-local, web-dev)
├── apps/web/               # Next.js 16 officer dashboard
├── services/api/           # FastAPI gateway + orchestrator
│   └── app/{core,models,schemas,routes,middleware,pipeline,forensics,face,risk,validation,services}
├── scripts/                # synthetic data generators
│   └── synthetic_documents.py   # ICAO TD3 passport + national ID with valid MRZ
├── data/synthetic/         # generated demo document images
├── packages/contracts/     # shared API contracts (future)
├── infrastructure/{docker,postgres}/
├── tests/{unit,integration}/
├── docs/
│   ├── migration.md        # environment setup & troubleshooting guide
│   └── sih-pitch.md        # SIH 2026 case study & pitch document
└── README.md
```

## Development

```bash
make test          # run all tests
make test-unit     # unit tests
make lint          # ruff
make typecheck     # mypy
make seed          # seed synthetic data
make gen-docs      # generate synthetic demo documents
make seed-local    # seed a local SQLite DB (standalone, no Docker)
make api-local     # run the API against local SQLite
```

## Data & Privacy

- **No real PII** in the repository. All identities and documents are synthetic.
- Raw images, faces, DOB and addresses are **never** written to a ledger.
- Only cryptographic hashes and minimal audit metadata would be anchored in a
  future Hyperledger implementation.

## Security Notes

- Config via environment variables only; no hardcoded secrets.
- Strict file validation (size, MIME type).
- Safe temp-file handling; no arbitrary file execution.
- Structured JSON logging; no PII in logs.
- Tamper-evident audit trail via chained SHA-256 hashes.

## Known Limitations (MVP)

- CPU-only inference (GPU optional/future).
- PaddleOCR/InsightFace require Python 3.11 (isolated in Docker images).
- Liveness is a heuristic baseline, not a certified spoof detector.
- Synthetic registry / identity database approximates real government systems.

## Contributing

This is a prototype built for Smart India Hackathon 2026. If you want to contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add your feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

Please run tests and lint before submitting:

```bash
make test
make lint
make typecheck
```

## License

This project is for educational and hackathon purposes. Internal use only.

## Team

Built by Team Cipher for Smart India Hackathon 2026 (Problem Statement SIH26188):

- Jashan Singla (Team Lead)
- Raashi
- Himanshu Sharma
- Anjli Rani
- Piyush Verma
- Lovepreet

## Documentation

- [Environment & Migration Guide](docs/migration.md) — setup, troubleshooting, standalone mode
- [SIH 2026 Case Study / Pitch](docs/sih-pitch.md) — architecture, demo walkthrough, technical highlights
