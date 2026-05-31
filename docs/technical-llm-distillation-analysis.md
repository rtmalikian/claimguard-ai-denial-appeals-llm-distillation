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
- `llm-distill/scripts/validate_phi_plan_manual_gate_packet.py` for manual
  production gate evidence.
- Targeted pytest tests for validators, reports, and manual gates.

## Reproduce The Core Checks

Run from the repository root unless noted otherwise.

```bash
python3 llm-distill/scripts/audit_synthetic_denial_appeal_corpus.py --fail-on-blocked
python3 llm-distill/scripts/run_distillation_readiness_audit.py
python3 llm-distill/scripts/run_phi_plan_production_readiness_audit.py
python3 llm-distill/scripts/validate_phi_plan_manual_gate_packet.py
```

Run focused unit tests from the application directory:

```bash
cd health-ai-medical-billing-medical-corporations-20260414_180528
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/claimguard-pycache \
  python3 -m pytest \
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

