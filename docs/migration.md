# VERIDEX — Environment & Migration Guide

This guide walks you through setting up a working `.env` and migrating from
a fresh clone to a fully running local instance.

---

## 1. Create your `.env`

```bash
cp .env.example .env
```

`.env` is git-ignored. Edit it with real values for your machine.

---

## 2. Decide: Docker (full) vs Standalone (SQLite)

| Mode           | Infra required          | Supports upload/verify | Best for         |
|----------------|------------------------|------------------------|-------------------|
| **Docker**     | Docker + Compose       | ✅ Full                 | Full dev/demo     |
| **Standalone** | None (SQLite on disk)  | ❌ Documents only       | Quick demo/API    |

### Standalone (no Docker)

```bash
# Uncomment/set this in .env
DATABASE_URL=sqlite+aiosqlite:///./veridex.db
```

Then:
```bash
make seed-local   # create DB + seed users, registry, demo cases
make api-local    # API on http://localhost:8000
make web-dev      # Dashboard on http://localhost:3000
```

**Supported flows**: login, case CRUD, status updates, registry lookup,
audit trail + chain verification, front-end dashboard.

**Not available**: document upload, full verification, forensics/face analysis
(these require MinIO + Redis for document storage).

### Docker (full stack)

```bash
make setup        # config + build + infra + migrate
make dev          # everything up (API :8000, Web :3000, DB, MinIO, Redis)
```

---

## 3. Key settings to review

| Variable                  | Default                              | Notes                                                |
|---------------------------|--------------------------------------|------------------------------------------------------|
| `SECRET_KEY`              | `change-me`                          | Used for internal signing; change for any non-local use |
| `JWT_SECRET_KEY`          | `change-me`                          | JWT signing; change for production                   |
| `DATABASE_URL`            | unset (→ PostgreSQL)                 | Set to `sqlite+aiosqlite:///./veridex.db` for standalone |
| `FACE_ENGINE`             | `baseline`                           | Deterministic, no GPU; set to `insightface` in AI image |
| `OCR_ENGINE`              | `paddleocr` (`.env`) / `baseline` (code) | `baseline` = offline deterministic OCR placeholders |
| `RISK_HIGH_THRESHOLD`     | `0.7`                                | Scores ≥ this → HIGH; ≥ 1.0 → CRITICAL               |
| `RISK_MEDIUM_THRESHOLD`   | `0.4`                                | Scores ≥ this → MEDIUM                                |
| `RATE_LIMIT_PER_MINUTE`   | `60`                                 | In-memory per-client IP                               |
| `MAX_UPLOAD_SIZE_MB`      | `20`                                 | Document upload cap                                   |

---

## 4. Default synthetic credentials

| Role    | Username  | Password    | Access                                        |
|---------|-----------|-------------|-----------------------------------------------|
| Admin   | `admin`   | `Admin123!` | Full access, registry write, case delete       |
| Officer | `officer1`| `Officer123!`| Case CRUD, analysis, audit read               |

These are seeded by `make seed` / `make seed-local`.  **Never use in production.**

---

## 5. Generating synthetic demo documents

```bash
make gen-docs
# → data/synthetic/passport_P12345678.png
# → data/synthetic/national_id_N87654321.png
```

The passport includes a valid ICAO TD3 machine-readable zone (MRZ) with
correct check digits, so the backend MRZ parser accepts it.  The passport
number `P12345678` is also seeded in the registry as `valid`.

---

## 6. Migrating between commits

After pulling a new commit:

```bash
# Always safe to run again — seed is idempotent
make seed-local   # or: make seed (Docker)

# If models changed, run Alembic (Docker only)
make migrate
```

---

## 7. Troubleshooting

| Symptom                                     | Cause / Fix                                           |
|---------------------------------------------|-------------------------------------------------------|
| `Invalid argument 'pool_size' sent to ... SQLite` | Old commit — update `database.py` (now handles SQLite) |
| `401 Invalid credentials` on fresh DB        | Run `make seed` / `make seed-local` first              |
| Dashboard shows "Could not reach API"        | API not running, or `NEXT_PUBLIC_API_URL` misconfigured |
| MRZ says `INVALID`                           | Script font issue; re-run `make gen-docs`              |

---

## 8. Repo layout (cheat sheet)

```
veridex/
├── .env.example            # template (tracked)
├── docker-compose.yml      # full stack orchestration
├── Makefile                # dev commands
├── apps/web/               # Next.js officer dashboard
├── services/api/           # FastAPI gateway + orchestrator
├── scripts/                # synthetic data generators
│   └── synthetic_documents.py
├── data/synthetic/         # generated demo document images
├── docs/                   # this file, SIH pitch, migration guide
├── tests/{unit,integration}/
└── infrastructure/{docker,postgres}/
```
