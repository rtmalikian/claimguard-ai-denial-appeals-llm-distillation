# ClaimGuard AI - Medical Billing Claim Denial Prediction & Prevention System

Architected by Raphael Malikian | Palmdale, California  
📧 rtmalikian@gmail.com | 🔗 https://github.com/rtmalikian  

Questions, comments, support, donations, or healthcare problem solutions? Reach out!

---

## 🎯 Problem Statement

Medical claim denials cost healthcare providers **$20B+ annually**. 65% of denials are preventable with proper coding and documentation before submission. ClaimGuard AI predicts denials **BEFORE** submission and provides actionable recommendations to fix issues.

## 🚀 Features

- **Claim Denial Prediction** - ML model predicts likelihood of denial before submission
- **Root Cause Analysis** - AI identifies specific issues (coding errors, missing data, policy violations)
- **Recommendation Engine** - Suggests specific fixes to prevent denial
- **Denial Analytics Dashboard** - Track denial patterns, identify trends
- **Appeal Assistance** - Generate appeal letters with supporting documentation
- **Source-grounded denial workflow** - Classify denial facts, route appeal/correction
  paths, identify evidence gaps, produce human-review drafts, and export packets
- **Encrypted retrieval source store** - Store trusted source chunks for RAG with
  encrypted title, URL, text, free-text metadata, and hashed retrieval vectors

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| AI/ML | NVIDIA NIM API (Llama Nemotron + Nemotron Parse) |
| Local LLM | Optional MLX-LM OpenAI-compatible endpoint for Apple Silicon |
| Frontend | React 18 + TypeScript + Tailwind + Vite |
| Container | Docker + Docker Compose |

## 📋 Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL (or use Docker)

## 🏁 Quick Start

```bash
# 1. Clone and navigate to project
cd health-ai-medical-billing-medical-corporations-20260414_180528

# 2. Copy environment configuration
cp .env.example .env

# 3. Start all services
docker-compose up -d

# 4. Access the application
# API: http://localhost:8001/docs
# Frontend: http://localhost:5173
```

## 📦 Moving The Project Folder

`docker-compose.yml` pins the Compose project name to
`health-ai-medical-billing-medical-corporations-20260414_180528`, so moving or
copying this folder on the same Docker host keeps using the existing local
PostgreSQL volume:
`health-ai-medical-billing-medical-corporations-20260414_180528_postgres_data`.

After copying the folder, run `docker compose up -d` from the new directory. If
the copy is on a different machine or CPU architecture, regenerate frontend
dependencies with `npm --prefix frontend install` before local frontend work.
Keep `.env` private; it may contain local credentials or API keys and should not
be shared, committed, or copied to untrusted locations.

## ⚙️ Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/claimguard

# Security
SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEYS=
BOOTSTRAP_ADMIN_EMAIL=admin@example.test
BOOTSTRAP_ADMIN_PASSWORD=change-this-bootstrap-password
BOOTSTRAP_ADMIN_NAME=ClaimGuard Admin
BOOTSTRAP_ADMIN_SYNC_FROM_ENV=false

# NVIDIA AI
LLM_PROVIDER=nvidia_nim
NVIDIA_API_KEY=replace-with-your-nvidia-api-key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/llama-3.3-nemotron-super-49b-v1.5
NVIDIA_OCR_MODEL=nvidia/nemotron-parse
OCR_ENGINE=nvidia_nemotron_parse

# Local MLX-LM AI
MLX_BASE_URL=http://localhost:8080/v1
MLX_MODEL=Qwen/Qwen3-4B-MLX-4bit
MLX_FALLBACK_MODEL=Qwen/Qwen3-1.7B
MLX_TIMEOUT=120

# Application
APP_NAME=ClaimGuard AI
DEBUG=False
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

`CORS_ALLOWED_ORIGINS` accepts a comma-separated list of full origins such as
`http://localhost:5173,https://billing.example.com`. Do not include `*`, paths,
queries, or fragments.

Set `BOOTSTRAP_ADMIN_SYNC_FROM_ENV=true` only when a local or controlled
environment should reconcile the bootstrap admin from `.env` on API startup.
Leave it `false` in production unless a deliberate credential reset is planned.

Generate encryption keys with `python3 scripts/generate_fernet_key.py`; do not
commit generated keys. Set `ENCRYPTION_KEYS` to a comma-separated list of Fernet
keys, with the newest primary key first. To rotate keys, prepend the new key,
deploy, run ciphertext rotation with the application `EncryptionService.rotate`
or `rotate_dict` helpers, then remove the retired key after old ciphertext has
been re-encrypted.

## 📁 Project Structure

```
├── app/                    # FastAPI backend
│   ├── api/v1/            # API endpoints
│   ├── core/              # Security, config
│   ├── db/                # Database connection
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   └── services/          # Business logic
├── frontend/              # React frontend
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # React components
│   │   └── pages/        # Page components
│   └── ...
├── alembic/               # Database migrations
├── docs/                  # Auth, EDI, and deployment runbooks
├── docker/                # Dockerfiles
├── tests/                 # Tests (unit + integration)
└── docker-compose.yml    # Container orchestration
```

## Operational Documentation

- [API authentication and authorization](docs/api-authentication.md)
- [EDI format notes](docs/edi-formats.md)
- [Deployment guide](docs/deployment-guide.md)
- [Backup and disaster recovery runbook](docs/backup-disaster-recovery.md)

## 🔌 API Endpoints

All `/api/v1/*` endpoints require `Authorization: Bearer <token>` except `POST /api/v1/auth/login`.
Health, root, docs, and OpenAPI remain public for local operations.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Authenticate and receive JWT |
| GET | `/api/v1/auth/me` | Get current authenticated user |
| POST | `/api/v1/auth/logout` | Log out current session |
| POST | `/api/v1/claims/predict` | Get denial prediction |
| POST | `/api/v1/claims/submit` | Submit claim for processing |
| POST | `/api/v1/claims/analyze-document` | Analyze denial letter (PDF/TXT) |
| POST | `/api/v1/denial-workflow/analyze` | Generate source-grounded denial workflow artifacts |
| POST | `/api/v1/denial-workflow/sources` | Store and chunk an encrypted retrieval source |
| GET | `/api/v1/denial-workflow/sources` | List encrypted retrieval source metadata |
| POST | `/api/v1/denial-workflow/sources/search` | Search authorized persisted retrieval chunks |
| POST | `/api/v1/denial-workflow/export` | Export workflow packet as Markdown, DOCX, or PDF |
| GET | `/api/v1/denial-workflow/source-registry` | List built-in public rule source metadata |
| GET | `/api/v1/claims/{id}` | Get claim with prediction |
| GET | `/api/v1/analytics/denial-trends` | Get denial trends |
| GET | `/api/v1/analytics/summary` | Get analytics summary |
| POST | `/api/v1/appeals/generate` | Generate appeal letter |
| GET | `/api/v1/health` | Health check |
| GET | `/ready` | Readiness check |

```bash
# Synthetic local login example. Load BOOTSTRAP_ADMIN_* from .env first.
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"${BOOTSTRAP_ADMIN_EMAIL}\", \"password\": \"${BOOTSTRAP_ADMIN_PASSWORD}\"}"
```

## 📊 Document Analysis

Upload and analyze denial letters to extract key information and get AI-powered recommendations.
Text PDFs are read directly with `pypdf`; images and scanned PDFs are OCR'd through
NVIDIA Nemotron Parse using the configured NVIDIA API key.

```bash
# Test document analysis
curl -X POST http://localhost:8001/api/v1/claims/analyze-document \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CLAIMGUARD_TOKEN" \
  -d '{"document_text": "Denial Notice from Aetna. Denial Code: CO29. Amount: $500."}'
```

Supported formats: PDF, TXT, JPG, PNG, GIF, WebP, BMP, TIFF
Extracted fields: payer, patient, policy number, claim amount, denial code, service date

### NVIDIA API Setup

Add your NVIDIA API key to `.env` as `NVIDIA_API_KEY`. Do not commit real keys. NVIDIA free-tier
calls should only use synthetic or de-identified healthcare documents, not PHI/PII.

### Local MLX-LM Setup

The denial workflow service can use deterministic extraction/routing without a
network LLM. For local model review on Apple Silicon, install and start MLX-LM
outside Docker:

```bash
python3 -m pip install --upgrade mlx-lm
mlx_lm.server --model "Qwen/Qwen3-4B-MLX-4bit"
```

Then set `LLM_PROVIDER=mlx_lm`. When the API runs in Docker, use
`MLX_BASE_URL=http://host.docker.internal:8080/v1`; when running the API
directly on macOS, use `http://localhost:8080/v1`. The fallback model target is
`Qwen/Qwen3-1.7B` for lower-resource routing and extraction.

### Denial Workflow Output

`POST /api/v1/denial-workflow/analyze` returns the provider-staff work product
defined by `denial_skill`: known facts, inferred facts, missing verification
tasks, cited rules, route decision, deadline table, evidence gaps,
provider-letter checklist, draft appeal/correction packet, attachment index,
submission plan, follow-up plan, quality gates, and human-review warnings. The
service does not train on uploaded documents and does not treat generated drafts
as filing-ready.

### Encrypted Retrieval Sources

`POST /api/v1/denial-workflow/sources` stores a trusted source for workflow
retrieval. The service chunks the supplied text and encrypts source title, source
URL, chunk text, section label, and free-text metadata before database storage.
Metadata fields used for filtering, such as `source_type`, `jurisdiction`,
`payer_type`, `phi_status`, and `license_status`, remain structured so authorized
staff can search and audit the index.

`POST /api/v1/denial-workflow/sources/search` decrypts chunks only inside the
authorized backend request path and returns cited snippets for review. Search
supports `hybrid`, `keyword`, and `embedding` modes. The embedding mode uses a
dependency-free deterministic hash vector (`claimguard-hash-embedding-v1`) so
local indexing works without sending source text to an external embedding API.
The hash vectors are stored inside encrypted chunk metadata. Denial workflow
analysis also includes persisted chunks in hybrid retrieval ranking. Audit
events record source IDs, query length, result count, search mode, source type,
PHI status, and chunk counts, but not raw source text or search query text.

Use public, synthetic, de-identified, or minimum-necessary source text only.
Production deployments must configure persistent `ENCRYPTION_KEYS`; development
may use an ephemeral key when no valid key is configured, which means encrypted
local retrieval records may not decrypt after an app restart.
Semantic embedding providers, vector database tuning, and reviewed corpus
ingestion are still separate production hardening steps.

## 🔒 Compliance

### HIPAA
- PHI encryption at rest (AES-256) and in transit (TLS 1.3)
- RBAC with audit logging
- Environment-restricted CORS and response security headers
- Minimum necessary data principle
- BAA readiness checklist

### SOC 2
- Security controls documentation
- Availability monitoring
- Processing integrity controls
- Annual audit readiness

## 🧪 Testing

```bash
# Backend tests
pytest tests/unit/ tests/integration/ -v

# Frontend tests
cd frontend && npm test

# Linting
ruff check app/

# Type checking
mypy app/
```

## 📝 License

MIT License - See LICENSE file for details.

---

Built with ❤️ for healthcare innovation
