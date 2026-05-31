# ClaimGuard Deployment Guide

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

Current Objective Scratchpad: Document local and production deployment steps
while keeping production readiness blocked until PHIplan manual gates,
student-default approval, model-improvement approval, production vector
evidence, and non-synthetic corpus evidence are complete.

## Read This First

The checked-in deployment scaffolding is safe to review, but it is not a final
production approval. The current PHIplan production-readiness audit is expected
to report `production_ready=false` and `safe_current_state=true` until external
manual gates are completed outside source control.

Do not deploy with real healthcare data until:

- `llm-distill/evals/reports/phi_plan_production_readiness_report.json` clears
  all blockers.
- Production secrets are stored outside the repository.
- Legal, BAA, consent, student-cutover, production corpus, runtime owner, and
  production vector-backend evidence is approved through the boolean-only
  evidence packets.
- Any EHR, RCM, payer, clearinghouse, or document-ingestion path has audit,
  retention, access-control, encryption, and minimum-necessary review.

## Local Development

1. Create a private `.env` from `.env.example`.
2. Generate persistent development encryption keys:

```bash
python3 scripts/generate_fernet_key.py
```

3. Set `ENCRYPTION_KEYS` in `.env`. Do not commit generated keys.
4. Set local bootstrap admin values only in `.env`.
5. Start the local stack:

```bash
docker compose up -d
```

6. Validate basic availability:

```bash
curl -sS http://localhost:8001/health
curl -sS http://localhost:5173
```

The development compose path exposes the API on host port `8001` and the Vite
frontend on host port `5173`.

## Production Compose Path

The production compose file is `docker-compose.production.yml`. Use a private
environment file stored outside this repository:

```bash
docker compose --env-file /path/to/private-production.env \
  -f docker-compose.production.yml config
```

Review the rendered config for missing required variables before starting the
stack. Then deploy in an approved environment:

```bash
docker compose --env-file /path/to/private-production.env \
  -f docker-compose.production.yml up -d --build
```

Production services:

| Service | Notes |
|---|---|
| `db` | PostgreSQL 15 with health check and named volume |
| `api` | Multi-stage backend image, non-root runtime user, `/health` health check |
| `frontend` | Production Vite build served through nginx with `/healthz` health check |

## Required Production Configuration

Set these in a private runtime environment, not in source control:

| Category | Variables or evidence |
|---|---|
| Database | `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `DATABASE_URL` rendered by compose |
| API security | `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ALLOWED_ORIGINS` |
| Encryption | `ENCRYPTION_KEYS` with newest Fernet key first |
| Bootstrap admin | `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_NAME`, `BOOTSTRAP_ADMIN_SYNC_FROM_ENV` only when intentional |
| NVIDIA runtime | `LLM_PROVIDER=nvidia_nim`, `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`, `NVIDIA_OCR_MODEL`, `NVIDIA_TIMEOUT` |
| Optional MLX runtime | `MLX_BASE_URL`, `MLX_MODEL`, `MLX_FALLBACK_MODEL`, `MLX_TIMEOUT` |
| Student runtime gates | `CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false`, `CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=false`, `CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=false`, `CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=false`, and `CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=true` unless Raphael-approved cutover evidence and supervised runtime ownership are complete |
| Model improvement | `USER_DATA_MODEL_IMPROVEMENT_ENABLED=false`, legal/BAA flags false, and approval reference/consent version blank unless legal, BAA, consent, approval reference, request, and revocation evidence are complete |
| Prediction fairness | `PREDICTION_FAIRNESS_EVIDENCE_REPORT` must point to the boolean-only report or a private rendered evidence file; production startup fails fast while threshold/fairness evidence remains blocked |
| Retrieval vector backend | `RETRIEVAL_EMBEDDING_BACKEND=hash`, `RETRIEVAL_VECTOR_BACKEND=encrypted_local_metadata`, and production semantic/backend flags false until production vector evidence passes |

Do not use placeholder values for `SECRET_KEY`, `ENCRYPTION_KEYS`, production
database credentials, NVIDIA keys, or approval references.
Use the exact environment variable names consumed by `app/core/config.py`.
`CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT` is not a production gate for the current
application settings.

For retrieval vector backend promotion, keep the conservative deployment path
as:

```env
RETRIEVAL_EMBEDDING_BACKEND=hash
RETRIEVAL_EMBEDDING_MODEL=claimguard-hash-embedding-v1
RETRIEVAL_EMBEDDING_MODEL_APPROVED=false
RETRIEVAL_VECTOR_BACKEND=encrypted_local_metadata
RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=false
RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=false
```

Only after semantic backend selection, approved embedding model review,
production vector backend configuration, active chunk reindexing, vector
health checks, retrieval quality smoke checks, rollback review, and
`llm-distill/evals/reports/retrieval_vector_backend_report.json` are ready,
render the final retrieval vector environment file to a private path:

```bash
# Set RETRIEVAL_PRODUCTION_EMBEDDING_BACKEND,
# RETRIEVAL_PRODUCTION_EMBEDDING_MODEL, and
# RETRIEVAL_PRODUCTION_VECTOR_BACKEND in a private shell first.
python3 ../llm-distill/scripts/render_retrieval_vector_private_env.py \
  --approved-vector-backend \
  --semantic-backend-attested \
  --embedding-model-approved-attested \
  --production-vector-backend-attested \
  --hash-fallback-disabled-attested \
  --reindex-completed-attested \
  --vector-health-attested \
  --retrieval-quality-smoke-attested \
  --rollback-reviewed \
  --no-raw-values-attested \
  --output /path/to/private-retrieval-vector.env
```

The helper refuses source-control output, writes the private env file with
`0600` permissions, and prints only redacted booleans/counts. Keep backend
labels, model names, vector-store labels, service URLs, credentials, source
text, and vector values out of docs, screenshots, logs, and committed files.

For user-data model improvement, keep the conservative deployment path as:

```env
USER_DATA_MODEL_IMPROVEMENT_ENABLED=false
USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=false
USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=false
USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION=
USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE=
```

Only after legal approval, BAA confirmation, consent notice version,
approval-reference configuration, explicit request, retention/revocation
review, per-request attestations, and
`llm-distill/evals/reports/model_improvement_evidence_report.json` are ready,
render the final model-improvement environment file to a private path:

```bash
# Set USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE and
# USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION in a private shell first.
python3 ../llm-distill/scripts/render_model_improvement_private_env.py \
  --approved-model-improvement \
  --model-improvement-request-attested \
  --legal-approval-attested \
  --baa-confirmed-attested \
  --consent-notice-attested \
  --retention-reviewed \
  --revocation-reviewed \
  --per-request-attestations-reviewed \
  --evidence-ready-attested \
  --output /path/to/private-model-improvement.env
```

The helper refuses source-control output, writes `0600`, and prints only
redacted booleans/counts. Keep approval-reference values, consent values,
legal/BAA documents, user data, PHI, credentials, and tokens out of source
control, logs, screenshots, and changelogs.

## Student Runtime Deployment Boundary

The reviewed local student adapter is integrated into status and workflow
metadata, but production default use remains blocked until the PHIplan gates
clear. Keep the conservative deployment path as:

```env
LLM_PROVIDER=nvidia_nim
CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false
CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=false
CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=true
```

Only enable effective student default use or student runtime auto-launch after:

- Raphael-approved cutover reference is configured outside source control.
- Supervised runtime ownership and launch evidence are complete.
- Runtime health and rollback-to-NVIDIA evidence pass.
- PHIplan production-readiness audit reports no blockers.

When those private gates are complete, render the final student cutover
environment file with the source-controlled helper, writing only to a private
path:

```bash
# Set CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE in a private shell first.
python3 ../llm-distill/scripts/render_student_cutover_private_env.py \
  --approved-cutover \
  --raphael-approval-attested \
  --runtime-supervised-attested \
  --distillation-release-attested \
  --rollback-reviewed \
  --output /path/to/private-student-cutover.env
```

The helper refuses source-control output, writes the private env file with
`0600` permissions, and prints only redacted booleans/counts. Keep the real
approval reference in a private shell or approved secret path, not in docs,
screenshots, logs, or committed files.

Only point production corpus gates at private approved corpus evidence after at
least one approved non-synthetic denial/appeal pair exists in a private
metadata-only manifest and privacy, license, residual-risk, training-scope,
no-PHI, source/license, pair-id, source-document, and metadata-only manifest
reviews are complete outside source control. When those gates are complete,
render the final private evidence file with the source-controlled helper:

```bash
# Set PRODUCTION_CORPUS_* reference variables and
# PRODUCTION_CORPUS_PRIVATE_MANIFEST_PATH in a private shell first.
python3 ../llm-distill/scripts/render_production_corpus_private_evidence.py \
  --approved-production-corpus \
  --approved-non-synthetic-pair-attested \
  --privacy-review-attested \
  --license-review-attested \
  --residual-risk-review-attested \
  --training-scope-reviewed \
  --no-phi-review-attested \
  --source-license-scope-documented \
  --pair-ids-reviewed-outside-source-control \
  --source-documents-reviewed-outside-source-control \
  --metadata-only-manifest-attested \
  --no-raw-document-content-attested \
  --no-raw-values-attested \
  --output /path/to/private-production-corpus-evidence.json
```

The helper refuses source-control output, writes the private evidence file with
`0600` permissions, and prints only redacted booleans/counts. Keep private
manifest paths, review references, raw denial letters, raw appeal letters,
source paths, checksums, approval references, and production document content
out of docs, screenshots, logs, tests, reports, and committed files.

Only point `PREDICTION_FAIRNESS_EVIDENCE_REPORT` at a private approved
fairness evidence file after approved outcome-data, sample-size,
threshold-review, demographic-grouping, monitoring-config, alert-owner,
latest-run, legal/privacy, rollback, and metadata-only audit evidence are
complete outside source control. When those gates are complete, render the
final private evidence file with the source-controlled helper:

```bash
# Set the PREDICTION_FAIRNESS_*_REFERENCE variables in a private shell first.
python3 ../llm-distill/scripts/render_prediction_fairness_private_evidence.py \
  --approved-monitoring \
  --approved-outcome-dataset-attested \
  --minimum-sample-size-attested \
  --calibration-run-attested \
  --threshold-review-attested \
  --human-review-policy-attested \
  --demographic-grouping-reviewed \
  --continuous-monitoring-configured \
  --disparity-thresholds-documented \
  --alert-owner-configured \
  --latest-monitoring-run-passed \
  --legal-privacy-review-completed \
  --rollback-reviewed \
  --metadata-only-audit-verified \
  --no-raw-values-attested \
  --output /path/to/private-prediction-fairness-evidence.json
```

The helper refuses source-control output, writes the private evidence file with
`0600` permissions, and prints only redacted booleans/counts. Keep real
dataset, threshold-review, monitoring, alert-owner, latest-run, and
legal/privacy references in a private shell or approved secret path, not in
docs, screenshots, logs, or committed files.

## Pre-Deployment Validation

Run these checks in a sandbox or approved staging environment:

```bash
python3 -m pytest tests/unit/test_auth.py tests/unit/test_cors_security.py tests/unit/test_api_endpoints.py -q
python3 -m pytest tests/unit/test_production_compose_env.py -q
python3 ../llm-distill/scripts/audit_file_ingestion_surfaces.py --fail-on-blocked
python3 ../llm-distill/scripts/run_phi_plan_production_readiness_audit.py --report /private/tmp/claimguard-phi-plan-production-readiness.json
python3 -m json.tool /private/tmp/claimguard-phi-plan-production-readiness.json
```

For a release candidate, also run the focused tests for any route, parser,
model, corpus, or frontend surface changed in that release.

## Rollback

Use the changelog entry for the specific slice being rolled back. For this
documentation slice, restore:

- `../PHIplan.md`
- `../CHANGELOG.md`
- `README.md`
- `implementation.md`
- `CHANGELOG.md`

from `../backups/20260531-000545-api-edi-deployment-docs/`, then remove:

- `docs/api-authentication.md`
- `docs/edi-formats.md`
- `docs/deployment-guide.md`

Rerun the validation commands recorded in the changelog after rollback.
