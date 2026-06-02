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

### Report Provenance And Drift Guard

The GitHub-facing `README.md` links to this document, and
`llm-distill/scripts/validate_public_repo_docs.py` checks that the link,
required section headings, report links, tool references, architect
attribution, and aggregate statistics remain present. The validator re-reads
the checked-in JSON reports and blocks if the public docs omit the current
values.

Public-doc validation checks these aggregate evidence counts without exposing
raw documents, prompts, source text, private approval references, PHI, or
secrets:

| Evidence area | Checked-in value |
|---|---:|
| Distillation ready requirements | 23 |
| Distillation total requirements | 25 |
| Public-doc expected statistic count | 30 |
| Public-doc required tool markers | 12 |
| Public-doc validation raw value exposure | 0 |

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
   - Student acceptance now requires every input report to resolve under
     `llm-distill/evals/reports/` and the adapter path to resolve under
     `llm-distill/models/adapters/` before `release_ready=true`.
   - The checked-in student acceptance report emits repository-relative paths
     for source-controlled evidence and redacts outside paths, so local
     workstation paths are not part of release-readiness evidence.

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
| Blocked production items | 9 |
| Warning production items | 1 |
| Manual production gate ready | false |
| User-data model improvement enabled | false |
| Student model used by default | false |
| Production vector backend configured | false |
| Complete approved production pair count | 0 |
| Prediction fairness report ready | false |

#### PHIplan Completion Audit Matrix

The checked-in PHIplan report includes a derived `completion_audit` matrix. It
is an audit surface, not an approval record, and it intentionally keeps raw
approval references, raw evidence values, report paths, PHI, and secrets out of
the public repository.

| Matrix field | Checked-in value |
|---|---:|
| PHIplan completion proven | false |
| Completion status | not_complete_private_or_external_evidence_required |
| Total requirement count | 18 |
| Ready requirement count | 8 |
| Blocked requirement count | 9 |
| Warning requirement count | 1 |
| Private/external blocker count | 9 |
| Source-control ready requirement count | 8 |
| Raw approval values included | false |
| Raw evidence values included | false |
| Raw report paths included | false |
| Raw PHI or secret values included | false |

Source-control-ready requirement IDs:

- `current_runtime_default_safe`
- `external_phi_service_guard`
- `file_ingestion_surface_audit_ready`
- `monitoring_gate_metrics_ready`
- `monitoring_readiness_endpoint_ready`
- `private_evidence_handoff_ready`
- `production_compose_startup_guard_env`
- `security_control_surface_ready`

Private/external blocker IDs:

- `backup_disaster_recovery_evidence`
- `clearinghouse_submission_evidence`
- `dependency_security_evidence`
- `manual_production_gate_packet_evidence`
- `production_corpus_expansion_beyond_synthetic`
- `production_prediction_fairness_monitoring`
- `production_semantic_vector_backend`
- `student_default_cutover_external_approval`
- `user_data_model_improvement_external_approval`

The top-level PHIplan production-readiness report uses repository-relative
paths for source-controlled evidence and redacts outside paths from load-error
evidence. This keeps public readiness metadata useful without publishing local
workstation paths, approval values, PHI, secrets, raw source text, vectors, or
production outcome rows.

The report now also verifies
`llm-distill/docs/phi-plan-private-evidence-handoff.md` as the source-controlled
private evidence handoff. That handoff maps every remaining private/external
blocker to its validator, private renderer, and no-raw-value boundary without
including approval references, private summary paths, raw report paths, PHI,
secrets, or production document content.
`llm-distill/scripts/validate_phi_plan_private_evidence_handoff.py` now
generates
`llm-distill/evals/reports/phi_plan_private_evidence_handoff_report.json`, a
redacted status report with `handoff_ready=true`,
`private_evidence_complete=false`, nine private blocker domains, and explicit
raw-value exclusion flags.

The direct PHIplan evidence reports for MLX runtime supervision, model
improvement, retrieval-vector backend readiness, production-corpus evidence,
prediction-fairness monitoring, backup/disaster recovery, dependency security,
clearinghouse submission, and the manual production-gate packet now use the
same output sanitizer before JSON is written. The validators still inspect the
actual source-controlled paths internally, but checked-in report payloads emit
repository-relative paths and redact outside local paths.

The repository also includes `llm-distill/scripts/sanitize_public_eval_reports.py`
for batch-sanitizing checked-in eval report JSON artifacts. Running it across
`llm-distill/evals/reports/*.json` removes local workstation paths from older
generated evidence files without changing readiness booleans, blockers,
warnings, counts, or benchmark results; `--check` verifies no report would be
rewritten.

The report generators for teacher labeling, teacher-review packets, MLX
fine-tune evidence, MLX bootstrap evidence, reviewed distillation pipeline
evidence, file-ingestion surface coverage, public-source-note coverage,
generated-corpus format coverage, and generated-denial extraction coverage now
write through the same sanitizer. That keeps future regenerated eval reports
from reintroducing local workstation paths before the batch `--check` gate
runs.

The generated synthetic corpus reports and seed MLX SFT artifacts use the same
public-path posture. `generation_report.json`, `visual_render_report.json`,
`llm-distill/data/distillation/mlx_sft_seed/manifest.json`, and
`train_lora_command.txt` publish repository-relative paths for checked-in
manifest, data, source, and adapter references, while the audit resolvers still
validate the corresponding files in the repository. The GitHub docs validator
checks these four public artifacts, the README screenshot references, and the
README link to this technical breakdown.

Reviewed-label and corpus-SFT generated data artifacts follow the same local
path-hygiene rule:
`teacher_label_ingestion_report.json`, the reviewed MLX SFT manifest/command,
and the corpus MLX SFT manifest/command publish repository-relative paths for
local generated inputs, outputs, data directories, and adapter references. The
teacher-label ingestion writer and corpus-SFT export writer sanitize only
source-controlled outputs, so temporary local scratch runs remain fully
auditable and checked-in reports avoid workstation paths.

The remaining eval report writers now share
`write_source_controlled_report_json(...)`: workflow baseline evaluation, MLX
runtime preflight, MLX benchmark, student acceptance, and synthetic
teacher-review outputs sanitize repository-owned report files while preserving
raw scratch paths for out-of-repo diagnostics.

The top-level distillation readiness audit also sanitizes its checked-in JSON
output recursively: source-controlled paths are written relative to the
repository, and outside local paths are redacted before publication. The audit
still reads and validates the real filesystem paths internally.

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
reads the approval reference and private aggregate cutover-summary path from
private environment variables, verifies the configured MLX runtime supervisor
evidence report is safe, ready, and unblocked, validates required private
cutover summary booleans, positive aggregate counts, and explicit no-raw-value
flags before writing enabled settings, writes the private env file with `0600`
permissions, and prints only redacted booleans/counts. It does not enable
student default routing by itself, validate the live runtime, install launchd
services, or store approval values in checked-in reports.

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
no-raw-value attestations before approved mode, reads private launchd plist,
validation references, and a private aggregate runtime-summary path from
environment variables, parses the private plist, validates required private
summary booleans, positive aggregate counts, and no-raw-value flags, and rejects
non-loopback hosts, missing MLX server/adapter/port arguments, unsafe runtime
profiles, missing launchd operational settings, unapproved or secret-like
environment keys, unsupported summary fields, and count mismatches before it can
write approved evidence. The private evidence file is written with `0600`
permissions and the command summary prints only redacted booleans/counts. It
does not install launchd, start MLX, validate endpoint output, or store private
runtime values or private summary paths in checked-in reports.

The MLX runtime supervisor validator also requires that renderer-shaped private
plist and runtime-summary metadata before `supervisor_ready=true`. Missing
private plist checks, unchecked private summaries, zero private
reference/plist/argument/environment/operator/validation counts, count
mismatches, or marked private plist path/raw-value inclusion keep the checked-in
evidence blocked. It also verifies that source-controlled supervisor artifacts
resolve inside this repository before reading marker text, covering the private
launchd-copy renderer, private supervisor evidence renderer, supervisor runbook,
owner-handoff checklist, and runtime validation checklist. Outside files with
matching marker text block readiness and are not read into the report.

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
and consent notice version plus a private aggregate approval-summary path from
private environment variables, verifies the configured model-improvement
evidence report is safe, ready, and unblocked, validates required private
approval-summary booleans, positive aggregate counts, and explicit
no-raw-value flags before writing an enabled private env, writes the private
env file with `0600` permissions, and prints only redacted booleans/counts. It
does not approve
user-data use, validate legal/BAA records, train a model, or store
approval/consent values in checked-in reports.

The model-improvement evidence validator also verifies that the documented
approval runbook and private env renderer paths resolve inside this repository.
This prevents a ready evidence packet from pointing at arbitrary private or
temporary files with matching marker text while still keeping approval
references, consent versions, user data, and legal records outside source
control.

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
references from environment variables, validates that the private manifest
metadata contains at least one approved non-synthetic denial/appeal pair before
writing ready private evidence, and validates a private aggregate production
corpus summary for required readiness booleans, positive manifest/review
counts, no-raw-value flags, unsupported-field rejection, and count mismatch
refusal. It stores only environment-variable names in private evidence, writes
the private evidence file with `0600` permissions, and prints only redacted
booleans/counts. The validator resolves the private manifest env var at
operator runtime without emitting the raw private manifest path in reports. It
does not add approved production pairs, open raw source documents, or store
review reference values, private summary paths, pair ids, source paths,
checksums, PHI, secrets, or production document content in checked-in reports.

The production corpus validator also requires that renderer-shaped private
manifest and production-corpus summary metadata before
`production_corpus_ready=true`. Checked-in manifest paths, missing private
summary checks, zero private manifest/reference/review counts, count
mismatches, or marked private path/reference/raw-document/source/checksum/
credential/PHI/production-content inclusion keep the checked-in evidence
blocked. The source-controlled corpus review runbook, collection/license
checklist, pair/source checklist, and private evidence renderer must resolve
inside this repository; outside temporary or private paths block before marker
text is read into the validator.

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
mode, reads private governance references and a private aggregate monitoring
summary path from environment variables, validates required readiness booleans,
positive aggregate counts, private reference-count parity, and explicit
no-raw-value flags, and rejects unsupported fields, raw-value inclusion flags,
or count mismatches. The private evidence file is written with `0600`
permissions and the command summary prints only redacted booleans/counts. It
does not store the private references, private summary path, raw demographic
values, production outcome rows, claim content, or approval documents in
either the checked-in report or its command output. The renderer does not
require its own prediction-fairness evidence report before writing evidence
because that report is produced by validating the rendered evidence packet;
startup and manual-gate controls continue to block production while that report
is missing, unsafe, blocked, or not ready.

The prediction fairness validator also requires that renderer-shaped private
monitoring-summary metadata before `prediction_fairness_monitoring_ready=true`.
Missing summary checks, zero private reference/outcome/group/metric/alert
counts, or marked private summary path/raw-value inclusion keep the checked-in
evidence blocked. It also verifies that the source-controlled model card,
monitoring runbook, calibration checklist, monitoring validation checklist,
legal/privacy checklist, and private evidence renderer resolve inside this
repository before reading marker text. Outside files with matching marker text
block readiness and are not read into the report.

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
backend/model/vector labels plus a private aggregate configuration-summary path
from environment variables, verifies the configured retrieval/vector backend
evidence report is safe, ready, and unblocked, validates required private
configuration-summary booleans, positive counts, no-raw-value flags,
unsupported-field rejection, and count mismatch refusal before writing enabled
settings, writes the private env file with `0600` permissions, and prints only
redacted booleans/counts. It does not store private provider labels, model
names, vector-store labels, private summary paths, service URLs, credentials,
source text, vector values, PHI, or production document content in checked-in
reports or command output.

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

The retrieval runtime private evidence renderer now also requires a private
aggregate runtime summary before it can write ready evidence. Approved mode
validates required semantic/reindex/health/quality/backup/rollback booleans,
positive aggregate counts, and explicit no-raw-source/vector/endpoint/
credential flags, then writes only redacted booleans/counts with `0600`
permissions.

The retrieval vector backend validator also treats those redacted private
reference booleans and aggregate runtime-summary counts as readiness inputs.
It blocks `vector_backend_ready=true` if health, quality-smoke, or reindex
references are absent, if the private summary was not checked, if aggregate
counts are zero, or if a private summary path or raw runtime values are marked
as included. It also verifies that source-controlled retrieval artifacts
resolve inside this repository before reading marker text, covering the private
env renderer, private semantic provider loader, operator runbook, reindex
checklist, runtime smoke checklist, and runtime private evidence renderer.
Outside files with matching marker text block readiness and are not read into
the report.

This means the technical implementation path exists, but production readiness
still requires private semantic backend configuration, a production vector
backend, a completed write reindex, a metadata-only reindex audit, backend
health checks, and retrieval quality smoke checks.

### Manual Gate Private Summary Controls

The final PHIplan manual production gate is also split between checked-in
source-control evidence and private governance evidence. The private manual
gate packet renderer validates dependent report readiness, private manifest
record counts, private reference counts, and a private aggregate manual-gate
summary before writing a ready packet outside source control.

The manual gate validator now requires the renderer-shaped private summary
metadata before `production_gate_ready=true`. Missing private summary checks,
zero private pair/source/manifest/dependent-report/reference counts, count
mismatches, or marked private summary path/reference/raw-value inclusion keep
the checked-in manual gate packet blocked. It also requires the source-controlled
manual checklist, manual private packet renderer, and student cutover
private-env renderer to resolve inside this repository before marker text is
read.

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
  student-cutover env rendering after external approvals and supervisor-report
  readiness are complete, with approved mode validating a private aggregate
  cutover summary before enabled settings are written.
- `llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py` for
  private boolean-only MLX runtime supervisor evidence rendering after runtime
  owner, private launchd, preflight, health, load, restart, rollback, and
  no-raw-output gates are complete; approved mode parses the private launchd
  plist, validates a private aggregate runtime summary, and rejects
  non-loopback, unsafe runtime-profile, missing-argument, unsupported-summary,
  count-mismatch, or secret-like environment-key configurations.
- `llm-distill/scripts/render_model_improvement_private_env.py` for private
  model-improvement env rendering after external legal, BAA, consent, and
  approval gates are complete and the configured evidence report is safe,
  ready, and unblocked, with approved mode validating a private aggregate
  approval summary before enabled settings are written.
- `llm-distill/scripts/render_production_corpus_private_evidence.py` for
  private boolean-only production corpus evidence rendering after approved
  non-synthetic pair, privacy, license, residual-risk, training-scope,
  pair/source, and metadata-only manifest gates are complete, with approved
  mode validating private manifest metadata and a private aggregate production
  corpus summary before ready evidence can be written.
- `llm-distill/scripts/render_prediction_fairness_private_evidence.py` for
  private boolean-only prediction-fairness evidence rendering after approved
  outcome, monitoring, latest-run, and legal/privacy gates are complete, with
  approved mode validating a private aggregate monitoring summary before ready
  evidence can be written.
- `llm-distill/scripts/render_retrieval_vector_private_env.py` for private
  retrieval/vector env rendering after semantic backend, reindex, health,
  quality-smoke, rollback, and evidence-report readiness gates are complete,
  with approved mode validating a private aggregate configuration summary before
  enabled settings are written.
- `llm-distill/scripts/render_retrieval_vector_runtime_private_evidence.py`
  for private boolean-only retrieval runtime evidence rendering after reindex,
  vector health, retrieval quality smoke, backup, rollback, and no-raw-value
  gates are complete, with approved mode validating a private aggregate runtime
  summary before ready evidence can be written.
- `health-ai-medical-billing-medical-corporations-20260414_180528/app/services/retrieval_semantic_provider.py`
  for source-controlled private semantic provider loading with redacted
  configuration status, HTTPS or loopback endpoint safety, dimension checks,
  and default hash fallback preservation.
- `llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py` for
  private manual production-gate packet rendering after every dependent
  evidence report and external/manual attestation is complete, with dependent
  report readiness and a private aggregate manual-gate summary checked before
  any ready private packet is written.
- `llm-distill/scripts/render_backup_disaster_recovery_private_evidence.py`
  for private boolean-only backup/DR evidence rendering after off-repository
  encrypted storage, metadata-only restore verification, key recovery, retention
  approval, and disaster-recovery smoke gates are complete, with approved mode
  validating a private aggregate backup/DR summary before ready evidence can be
  written.
- `llm-distill/scripts/render_dependency_security_private_evidence.py` for
  private boolean-only dependency security evidence rendering after Python,
  frontend, and container dependency scans, lockfile review, remediation or
  private approval, compensating controls, rebuild/retest, upgrade planning,
  governance review, and no-raw-value gates are complete, with approved mode
  validating a private aggregate dependency-security summary before ready
  evidence can be written.
- `llm-distill/scripts/render_clearinghouse_submission_private_evidence.py`
  for private boolean-only clearinghouse submission evidence rendering after
  payer or clearinghouse enrollment, private credentials, encrypted-transit
  validation, EDI 837 submission-contract testing, control-number review,
  999/277CA acknowledgement handling, retry/duplicate controls, rollback,
  audit, access, retention, governance, and no-raw-value gates are complete,
  with approved mode validating a private aggregate clearinghouse submission
  summary before ready evidence can be written.
- `llm-distill/scripts/validate_retrieval_vector_backend.py` for boolean-only
  retrieval vector configuration, reindex, runbook, and runtime evidence.
- `llm-distill/scripts/validate_phi_plan_manual_gate_packet.py` for manual
  production gate evidence.
- `llm-distill/scripts/validate_backup_disaster_recovery_evidence.py` for
  boolean-only backup/DR storage, restore, key-recovery, runbook, and private
  summary evidence.
- `llm-distill/scripts/validate_dependency_security_evidence.py` for
  boolean-only dependency scan, remediation, governance, runbook, and private
  summary evidence without publishing raw scan output, vulnerability detail
  values, approval references, registry URLs, credentials, PHI, secrets, or
  production documents.
- `llm-distill/scripts/validate_clearinghouse_submission_evidence.py` for
  boolean-only clearinghouse and payer submission connectivity, EDI 837
  submission-contract, 999/277CA acknowledgement, retry/duplicate, rollback,
  audit, access, retention, governance, runbook, and private summary evidence
  without publishing raw EDI payloads, endpoint URLs, credentials, approval
  references, PHI, secrets, or production claim content.
- `llm-distill/scripts/validate_phi_plan_private_evidence_handoff.py` for the
  source-controlled private evidence handoff status report that maps each
  private/external blocker to its validator, renderer, current ready flag,
  blocked requirement IDs, and no-raw-value boundary.
- Targeted pytest tests for validators, reports, and manual gates.

## Reproduce The Core Checks

Run from the repository root unless noted otherwise.

```bash
python3 llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py --fail-on-blocked
python3 llm-distill/scripts/validate_retrieval_vector_backend.py
python3 llm-distill/scripts/validate_prediction_fairness_evidence.py
python3 llm-distill/scripts/run_distillation_readiness_audit.py
python3 llm-distill/scripts/validate_phi_plan_private_evidence_handoff.py --fail-on-source-control-blocked
python3 llm-distill/scripts/run_phi_plan_production_readiness_audit.py
python3 llm-distill/scripts/validate_phi_plan_manual_gate_packet.py
python3 llm-distill/scripts/validate_backup_disaster_recovery_evidence.py
python3 llm-distill/scripts/validate_dependency_security_evidence.py
python3 llm-distill/scripts/validate_clearinghouse_submission_evidence.py
```

Run focused unit tests from the application directory:

```bash
cd health-ai-medical-billing-medical-corporations-20260414_180528
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="${TMPDIR:-.}/claimguard-pycache" \
  python3 -m pytest \
  tests/unit/test_retrieval_store.py \
  tests/unit/test_retrieval_semantic_provider.py \
  tests/unit/test_retrieval_vector_startup_config.py \
  tests/unit/test_retrieval_vector_private_env_renderer.py \
  tests/unit/test_retrieval_vector_runtime_private_evidence_renderer.py \
  tests/unit/test_retrieval_vector_backend_evidence.py \
  tests/unit/test_prediction_fairness_private_evidence_renderer.py \
  tests/unit/test_phi_plan_manual_gate_private_packet_renderer.py \
  tests/unit/test_backup_disaster_recovery_evidence.py \
  tests/unit/test_prediction_fairness_evidence.py \
  tests/unit/test_phi_plan_manual_gate_packet.py \
  tests/unit/test_dependency_security_evidence.py \
  tests/unit/test_clearinghouse_submission_evidence.py \
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
