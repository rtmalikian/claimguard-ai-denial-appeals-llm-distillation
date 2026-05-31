# Technical LLM Distillation Breakdown And Analysis Statistics

ClaimGuard AI is architected by Raphael Malikian <rtmalikian@gmail.com>.

This document is the technical companion to the clinician-friendly project
walkthrough. It summarizes the checked-in LLM distillation process, analysis
statistics, validation reports, and tools used to build a smaller ClaimGuard
student model for healthcare claim denial review and draft appeal support.

## Scope

The distillation work is designed for denial-claim processing, appeal workflow
support, and synthetic document stress testing. It is not a production approval
record and does not make generated appeal text filing-ready. The production
readiness report currently separates a safe local state from open production
gates such as approved real-world corpus expansion, supervised student-model
cutover, production retrieval backend configuration, legal/BAA/consent
controls, and fairness monitoring.

Primary evidence files:

- [`llm-distill/evals/reports/distillation_readiness_audit_report.json`](../llm-distill/evals/reports/distillation_readiness_audit_report.json)
- [`llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json`](../llm-distill/evals/reports/synthetic_denial_appeal_corpus_format_audit_report.json)
- [`llm-distill/evals/reports/student_acceptance_report.json`](../llm-distill/evals/reports/student_acceptance_report.json)
- [`llm-distill/evals/reports/phi_plan_production_readiness_report.json`](../llm-distill/evals/reports/phi_plan_production_readiness_report.json)

## Distillation Pipeline

1. Source and safety specification
   - Public source registry is validated as PHI-clean.
   - Denial workflow contracts define required output keys, source status
     groups, human review gating, and draft appeal restrictions.
   - PHI/PII scans run against source registry, manifests, distillation splits,
     benchmark reports, and generated corpus artifacts.

2. Synthetic and reviewed data preparation
   - Synthetic seed examples cover ClaimGuard denial and appeal workflow
     scenarios.
   - Teacher-review packets require explicit approval checks before labels are
     allowed into supervised fine-tuning data.
   - Reviewed synthetic labels are exported to MLX chat-format SFT JSONL
     splits only when `training_allowed=true`.

3. Local student training
   - The reviewed-label LoRA run targets `Qwen/Qwen3-4B-MLX-4bit`.
   - The checked-in reviewed run used 60 iterations, batch size 1, 8 LoRA
     layers, prompt masking, validation every 30 steps, and an adapter path
     under `llm-distill/models/adapters/`.
   - Adapter weight files are ignored by repository rules and are not part of
     the source-available GitHub package.

4. Benchmarking and acceptance
   - The workflow baseline, base lightweight model, and fine-tuned student
     model are checked against synthetic ClaimGuard scenario records.
   - The strict output contract requires JSON validity, required keys,
     source-grounded draft sections, human review requirement, and
     draft-for-review markers.
   - Student acceptance is gated before quantization, promotion, or application
     default-model changes.

5. Production-readiness separation
   - Distillation evidence can be ready while production deployment remains
     blocked.
   - `safe_current_state=true` means conservative defaults are preserved.
   - `production_ready=false` means external approvals and live operating
     controls remain incomplete.

## Analysis Statistics

### Synthetic Denial And Appeal Stress Corpus

The synthetic stress corpus is intended to stress document parsing and model
format robustness with realistic but fictitious denial and appeal documents.

| Metric | Checked-in value |
|---|---:|
| Complete denial/appeal pairs | 900 |
| Total letters | 1,800 |
| Denial letters | 900 |
| Appeal letters | 900 |
| Training split letters | 1,440 |
| Validation split letters | 180 |
| Test split letters | 180 |
| Unique text count | 1,800 |
| Duplicate text groups | 0 |
| Duplicate pair groups | 0 |
| PHI scan findings | 0 |
| Rendered HTML layouts | 1,800 |
| Layout profiles | 12 |
| Typography profiles | 8 |
| Length profiles | 6 |
| Minimum word count | 124 |
| Average word count | 205.86 |
| Maximum word count | 300 |

Document format coverage:

- Denial formats: formal letter, EOB summary, portal message, fax cover
  summary, utilization review notice, Medicare reconsideration notice, Medicaid
  managed care notice, and employer plan adverse benefit notice.
- Appeal formats: provider formal letter, portal appeal message, coding review
  appeal, corrected claim cover letter, clinical reconsideration packet,
  medical records index, timely filing rebuttal, and network exception appeal.
- Denial types: coding modifier mismatch, coordination of benefits,
  documentation support, duplicate service, eligibility, experimental or
  investigational, medical necessity, out of network, prior authorization
  missing, and timely filing.

### Reviewed-Label Student Distillation

| Metric | Checked-in value |
|---|---:|
| Reviewed synthetic records | 10 |
| Reviewed train records | 8 |
| Reviewed validation records | 1 |
| Reviewed test records | 1 |
| Required micro-skill IDs | 12 |
| Missing required micro-skill IDs | 0 |
| Reviewed split PHI findings | 0 |
| LoRA iterations | 60 |
| LoRA batch size | 1 |
| LoRA layers | 8 |
| Final train loss in report | 0.055 |
| Final validation loss in report | 0.290 |
| Peak memory in report | 10.042 GB |
| Training succeeded | true |

### Benchmark And Acceptance Results

| Gate | Checked-in value |
|---|---:|
| Workflow baseline scenarios | 10 |
| Workflow baseline score ratio | 1.0 |
| Base model benchmark records | 10 |
| Base model score ratio | 0.9667 |
| Student model benchmark records | 10 |
| Student model score ratio | 0.9667 |
| Student vs base score delta | 0.0 |
| Student acceptance release-ready | true |
| Student minimum score threshold | 0.95 |
| Maximum allowed score regression | 0.02 |
| Benchmark PHI findings | 0 |

Performance details from the checked-in live benchmark reports:

- Base model average latency: 33.7823 seconds.
- Base model average throughput: 12.7288 tokens per second.
- Student model average latency: 32.9436 seconds.
- Student model average throughput: 13.4021 tokens per second.

### Production-Readiness State

| Gate | Checked-in value |
|---|---:|
| PHIplan safe current state | true |
| PHIplan production ready | false |
| Blocked production items | 6 |
| Warning production items | 1 |
| Manual production gate ready | false |
| User-data model improvement enabled | false |
| Student model used by default | false |
| Production vector backend configured | false |
| Complete approved production pair count | 0 |
| Prediction fairness report ready | false |

The synthetic-900 SFT export is ready as a data artifact, but its full LoRA run
is blocked in the current headless session because MLX cannot access a Metal
device. That block is recorded separately from the reviewed-label adapter run.

### Student Cutover Private Env Controls

The final student-default switch still requires private Raphael approval,
supervised MLX runtime ownership, runtime health evidence, rollback review, and
clean PHIplan readiness. The repository now includes
`llm-distill/scripts/render_student_cutover_private_env.py` so an operator can
render the cutover env file to a private path after those gates are complete.

The renderer refuses output inside source control, requires explicit approval,
runtime, distillation, and rollback attestations before approved-cutover mode,
reads the approval reference from a private environment variable, writes the
private env file with `0600` permissions, and prints only redacted
booleans/counts. It does not enable student default routing by itself, validate
the live runtime, install launchd services, or store approval values in
checked-in reports.

### MLX Runtime Supervisor Private Evidence Controls

Supervised MLX runtime readiness remains blocked until a private runtime owner,
private launchd copy, runtime preflight, student status endpoint check, runtime
health, launchd load, supervisor restart test, rollback review, and no-raw
evidence review are complete outside source control. The repository now
includes `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py`
so an operator can render the final boolean-only supervisor evidence file to a
private path after those gates are complete.

The renderer refuses output inside source control, requires explicit runtime
owner, launchd copy, restart-policy, health, manual-start, rollback, preflight,
status, runtime health, load, restart-test, environment-exclusion, and
no-raw-value attestations before approved mode, reads private launchd plist and
validation references from environment variables, writes the private evidence
file with `0600` permissions, and prints only redacted booleans/counts. It does
not install launchd, start MLX, validate endpoint output, or store private
runtime values in checked-in reports.

### Model-Improvement Private Env Controls

User-data model improvement remains disabled until legal approval, BAA
confirmation, consent notice version, approval reference, explicit request,
retention/revocation review, per-request attestations, and model-improvement
evidence are complete outside source control. The repository now includes
`llm-distill/scripts/render_model_improvement_private_env.py` so an operator
can render the final model-improvement env file to a private path after those
gates are complete.

The renderer refuses output inside source control, requires explicit legal,
BAA, consent, request, retention, revocation, per-request attestation, and
evidence-readiness attestations before approved mode, reads approval reference
and consent notice version from private environment variables, verifies the
configured model-improvement evidence report is safe, ready, and unblocked
before writing an enabled private env, writes the private env file with `0600`
permissions, and prints only redacted booleans/counts. It does not approve
user-data use, validate legal/BAA records, train a model, or store
approval/consent values in checked-in reports.

### Production Corpus Private Evidence Controls

Production corpus readiness remains blocked until at least one approved
non-synthetic denial/appeal pair exists in a private metadata-only manifest
after privacy review, license review, residual-risk review, training-scope
review, no-PHI review, source/license scope documentation, pair-id review, and
source-document review outside source control. The repository now includes
`llm-distill/scripts/render_production_corpus_private_evidence.py` so an
operator can render the final production corpus evidence file to a private path
after those gates are complete.

The renderer refuses output inside source control, requires explicit corpus,
review, pair/source, metadata-only manifest, no-raw-document, and no-raw-value
attestations before approved mode, reads the private manifest path and review
references from environment variables, stores only the manifest-path env var
name in private evidence, writes the private evidence file with `0600`
permissions, and prints only redacted booleans/counts. The validator resolves
that env var at operator runtime without emitting the raw private manifest path
in reports. It does not add approved production pairs, validate raw source
documents, or store review reference values in checked-in reports.

### Prediction-Fairness Private Evidence Controls

Production threshold calibration and fairness monitoring remain blocked until
approved outcome data, minimum sample size, threshold review, demographic
grouping review, monitoring configuration, alert ownership, latest monitoring
run evidence, legal/privacy review, rollback review, and metadata-only audit
evidence are complete outside source control. The repository now includes
`llm-distill/scripts/render_prediction_fairness_private_evidence.py` so an
operator can render the final boolean-only fairness evidence file to a private
path after those gates are complete.

The renderer refuses output inside source control, requires explicit
outcome-data, sample-size, calibration, threshold-review, human-review-policy,
demographic-grouping, monitoring, alert-owner, latest-run, legal/privacy,
rollback, metadata-only audit, and no-raw-value attestations before approved
mode, reads private governance references from environment variables, writes
the private evidence file with `0600` permissions, and prints only redacted
booleans/counts. It does not store the private references, raw demographic
values, production outcome rows, claim content, or approval documents in either
the checked-in report or its command output.

### Retrieval Vector Private Env Controls

Production semantic retrieval remains blocked until the semantic embedding
backend, approved embedding model, production vector backend, active chunk
reindex, vector backend health, retrieval quality smoke checks, and rollback
path are complete outside source control. The repository now includes
`llm-distill/scripts/render_retrieval_vector_private_env.py` so an operator can
render the final retrieval/vector environment file to a private path after
those gates are complete.

The renderer refuses output inside source control, requires explicit semantic
backend, embedding model approval, production vector backend, hash-fallback
disablement, reindex completion, vector health, retrieval quality smoke,
rollback, and no-raw-value attestations before approved mode, reads private
backend/model/vector labels from environment variables, writes the private env
file with `0600` permissions, and prints only redacted booleans/counts. It does
not store private provider labels, model names, vector-store labels, service
URLs, credentials, source text, vector values, PHI, or production document
content in checked-in reports or command output.

### Retrieval Reindex Controls

The production retrieval path is intentionally split between checked-in safety
controls and private infrastructure evidence. The repository now includes an
admin-only reindex operation,
`POST /api/v1/denial-workflow/sources/reindex-embeddings`, for approved private
semantic providers. It defaults to dry-run mode, refuses non-dry-run writes
with the development hash provider, and returns only aggregate counts, provider
labels, warning tokens, and safe-context flags. It does not return source text,
raw vectors, provider endpoints, credentials, PHI, secrets, or production
document content.

This means the technical implementation path exists, but production readiness
still requires private semantic backend configuration, a production vector
backend, a completed write reindex, a metadata-only reindex audit, backend
health checks, and retrieval quality smoke checks.

## Tools Used

Core application and workflow:

- FastAPI for backend APIs.
- React and Vite for the local frontend.
- Docker Compose for local service orchestration.
- SQLAlchemy and Alembic for persistence and migrations.
- Playwright for screenshot capture and browser-flow validation.

LLM and distillation:

- NVIDIA NIM-compatible provider path for the conservative default runtime.
- MLX-LM for Apple Silicon local model serving, benchmarking, and LoRA runs.
- `Qwen/Qwen3-4B-MLX-4bit` as the lightweight student model target.
- Python JSONL scripts for teacher-review packets, supervised fine-tuning
  exports, benchmark reports, acceptance gates, and readiness audits.

Safety and validation:

- `llm-distill/scripts/run_phi_scan.py` for PHI/PII scanning.
- `llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py` for corpus
  format, pair, uniqueness, layout, and PHI-cleanliness checks.
- `llm-distill/scripts/run_distillation_readiness_audit.py` for distillation
  release evidence aggregation.
- `llm-distill/scripts/run_phi_plan_production_readiness_audit.py` for
  production-gate separation.
- `llm-distill/scripts/render_student_cutover_private_env.py` for private
  student-cutover env rendering after external approvals are complete.
- `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py` for
  private boolean-only MLX runtime supervisor evidence rendering after runtime
  owner, private launchd, preflight, health, load, restart, rollback, and
  no-raw-output gates are complete.
- `llm-distill/scripts/render_model_improvement_private_env.py` for private
  model-improvement env rendering after external legal, BAA, consent, and
  approval gates are complete and the configured evidence report is safe,
  ready, and unblocked.
- `llm-distill/scripts/render_production_corpus_private_evidence.py` for
  private boolean-only production corpus evidence rendering after approved
  non-synthetic pair, privacy, license, residual-risk, training-scope,
  pair/source, and metadata-only manifest gates are complete, with private
  manifest paths resolved from env vars and redacted from output evidence.
- `llm-distill/scripts/render_prediction_fairness_private_evidence.py` for
  private boolean-only prediction-fairness evidence rendering after approved
  outcome, monitoring, latest-run, and legal/privacy gates are complete.
- `llm-distill/scripts/render_retrieval_vector_private_env.py` for private
  retrieval/vector env rendering after semantic backend, reindex, health,
  quality-smoke, and rollback gates are complete.
- `llm-distill/scripts/render_retrieval_vector_runtime_private_evidence.py`
  for private boolean-only retrieval runtime evidence rendering after reindex,
  vector health, retrieval quality smoke, backup, rollback, and no-raw-value
  gates are complete.
- `health-ai-medical-billing-medical-corporations-20260414_180528/app/services/retrieval_semantic_provider.py`
  for source-controlled private semantic provider loading with redacted
  configuration status, HTTPS or loopback endpoint safety, dimension checks,
  and default hash fallback preservation.
- `llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py` for
  private manual production-gate packet rendering after every dependent
  evidence report and external/manual attestation is complete.
- `llm-distill/scripts/validate_retrieval_vector_backend.py` for boolean-only
  retrieval vector configuration, reindex, runbook, and runtime evidence.
- `llm-distill/scripts/validate_phi_plan_manual_gate_packet.py` for manual
  production gate evidence.
- Targeted pytest tests for validators, reports, and manual gates.

## Reproduce The Core Checks

Run from the repository root unless noted otherwise.

```bash
python3 llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py --fail-on-blocked
python3 llm-distill/scripts/validate_retrieval_vector_backend.py
python3 llm-distill/scripts/validate_prediction_fairness_evidence.py
python3 llm-distill/scripts/run_distillation_readiness_audit.py
python3 llm-distill/scripts/run_phi_plan_production_readiness_audit.py
python3 llm-distill/scripts/validate_phi_plan_manual_gate_packet.py
```

Run focused unit tests from the application directory:

```bash
cd health-ai-medical-billing-medical-corporations-20260414_180528
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/claimguard-pycache \
  python3 -m pytest \
  tests/unit/test_retrieval_store.py \
  tests/unit/test_retrieval_semantic_provider.py \
  tests/unit/test_retrieval_vector_startup_config.py \
  tests/unit/test_retrieval_vector_private_env_renderer.py \
  tests/unit/test_retrieval_vector_runtime_private_evidence_renderer.py \
  tests/unit/test_retrieval_vector_backend_evidence.py \
  tests/unit/test_prediction_fairness_private_evidence_renderer.py \
  tests/unit/test_phi_plan_manual_gate_private_packet_renderer.py \
  tests/unit/test_prediction_fairness_evidence.py \
  tests/unit/test_phi_plan_manual_gate_packet.py \
  tests/unit/test_phi_plan_production_readiness_audit.py \
  -q -p no:cacheprovider
```

## Interpretation For Engineers

The repository has enough local evidence to show a working, PHI-clean
distillation workflow and a release-ready reviewed-label student adapter path
for synthetic ClaimGuard scenarios. It does not have enough evidence to justify
commercial production deployment, automatic student-model default routing,
training on real user data, or automated filing of appeal letters. Those steps
require external approvals, live supervised runtime evidence, approved
non-synthetic corpus records, production retrieval infrastructure, and fairness
monitoring evidence that are deliberately kept outside source control.
