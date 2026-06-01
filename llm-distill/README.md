# ClaimGuard LLM Distillation MVP

Architected by Raphael Malikian <rtmalikian@gmail.com>.

This directory implements the planning artifacts for distilling a larger
teacher LLM into a smaller, lightweight, source-grounded student model focused
only on ClaimGuard denial-claim processing and appeal-letter generation. The
runtime application lives in
`health-ai-medical-billing-medical-corporations-20260414_180528/`.

## Implemented Slice

- Source registry for public rules, public notices, adjudication sources, and
  insurer-policy candidates.
- Safety and HIPAA controls for corpus building and distillation.
- MLX-LM setup notes for `Qwen/Qwen3-4B-MLX-4bit` and fallback
  `Qwen/Qwen3-1.7B`.
- Prompt and output contract aligned to `denial_skill`.
- Synthetic evaluation scenarios and scripts for source collection validation,
  PHI scanning, normalization, eval-set generation, and offline workflow
  baseline scoring.
- Synthetic supervised seed records and teacher-label request generation for
  the future larger-teacher to lightweight-student distillation pass.
- Synthetic micro-skill coverage across `denial_skill` MS01-MS12, including
  authority validation and upheld-response outcome analysis cases.
- Guarded teacher-label batch runner for submitting reviewed synthetic/public
  requests to an operator-configured large teacher endpoint without storing
  secrets or checked-in raw response files.
- Offline teacher/human review packet generator that preserves pending labels,
  requires explicit safety checks before response export, and emits
  ingestion-compatible teacher response JSONL only after approval.
- Synthetic large-teacher review helper that can approve the checked-in
  synthetic/no-PHI packet after schema, source-status, citation, draft-label,
  and PHI checks pass, without calling external teacher endpoints or claiming
  human approval.
- Teacher-label ingestion and validation for replacing deterministic seed labels
  with reviewed large-teacher or human-approved outputs.
- MLX-LM chat-format SFT seed export with train/valid/test JSONL, a LoRA
  command manifest, and training blocks while labels remain pending review.
- Guarded MLX-LM LoRA fine-tune preflight/run harness that validates the SFT
  manifest, split files, PHI scan results, and local `mlx_lm.lora`
  availability before allowing adapter training.
- MLX runtime preflight for package, CLI, Apple Silicon host, and local
  OpenAI-compatible server readiness before live benchmarks or LoRA training.
- Project-local MLX-LM bootstrap runner that creates or refreshes `.venv-mlx`,
  installs `mlx-lm`, and regenerates runtime/fine-tune/readiness evidence
  without starting the model server or downloading model weights.
- Local MLX-LM benchmark harness for synthetic prompts, strict ClaimGuard JSON
  schema-contract prompting, JSON/output-contract scoring, latency,
  approximate throughput, and endpoint availability reports.
- Student-model acceptance gate that refuses adapter promotion unless workflow
  regression, fine-tune, base benchmark, student benchmark, and PHI-safety
  evidence all pass; live benchmark evidence must cover the current 10-record
  synthetic scenario set.
- Reviewed-label distillation pipeline runner that sequences teacher-response
  validation, reviewed-label ingestion, reviewed MLX SFT export, guarded
  fine-tuning, and student acceptance without treating missing downstream
  evidence as complete.
- Reviewed synthetic-label export, reviewed MLX SFT splits with
  `training_allowed=true`, a 60-iteration local MLX-LM LoRA run that produced a
  reviewed adapter, and live adapter-backed student benchmark evidence.
- Manifest-gated approved corpus SFT exporter that writes MLX-LM chat splits
  only from `training_eligible=true` de-identified/reviewed denial plus appeal
  pairs, verifies checksums and zero PHI/PII scan findings, preserves `pair_id`
  metadata, and reports MS01-MS12 plus payer/denial/route/outcome coverage
  before `training_allowed=true`.
- Strict benchmark/runtime schema contract `strict_claim_guard_json_v1`, with
  required JSON keys, array-typed source-status groups, object-based
  `draft_sections`, human-review draft markers, and the reviewed-label
  denial-type taxonomy.
- Passing live base and reviewed student-adapter MLX benchmarks over the full
  10-record synthetic scenario set, passing student acceptance, and passing
  top-level distillation readiness for the reviewed adapter path.
- Distillation readiness audit that aggregates source, synthetic data,
  micro-skill coverage, teacher labeling, reviewed SFT, MLX training,
  approved corpus manifest, corpus SFT export, benchmark, acceptance,
  quantization, and PHI-safety evidence before the smaller ClaimGuard student
  model is considered ready for production/default use.

## Runtime Integration

The FastAPI app now exposes:

- `POST /api/v1/denial-workflow/analyze`
- `POST /api/v1/denial-workflow/export`
- `GET /api/v1/denial-workflow/source-registry`

Existing document analysis stores the generated denial workflow packet in
`claim_data.denial_workflow`.

## Evaluation Harness

Run the deterministic denial workflow baseline against the synthetic held-out
scenario families before any teacher labeling or fine-tuning:

```bash
python3 llm-distill/scripts/run_workflow_eval.py \
  --cases llm-distill/evals/cases/gold_scenarios.jsonl \
  --output /private/tmp/claimguard-workflow-eval.json
```

The script uses the local application service with `use_llm=false`, writes JSON
summary/results, and exits non-zero only when `--fail-under <score_ratio>` is
provided and not met. Gold scenarios are synthetic/de-identified and should stay
free of real member, patient, claim, contact, or credential values.

## Distillation Dataset Preparation

Build synthetic seed records and teacher-label request batches for the student
model format:

```bash
python3 llm-distill/scripts/build_distillation_records.py
```

The script writes:

- `llm-distill/data/distillation/seed_synthetic_supervised.jsonl`
- `llm-distill/data/distillation/teacher_label_requests.jsonl`
- `llm-distill/data/distillation/dataset_card.md`

The seed labels come from the deterministic ClaimGuard workflow and are marked
`pending_large_teacher_review`. They are useful for format checks and dry runs,
not as final teacher-labeled production training data.

The checked-in seed set is synthetic and covers all required `denial_skill`
micro-skills MS01-MS12. The MLX SFT manifest records
`micro_skill_coverage_complete`, `required_micro_skill_ids`, and
`missing_required_micro_skill_ids`; training remains blocked if any required
micro-skill is missing or if labels are still pending review.

When reviewed large-teacher batch responses are available, merge them into a
reviewed supervised dataset:

```bash
python3 llm-distill/scripts/run_teacher_label_batch.py \
  --report-output llm-distill/evals/reports/teacher_label_batch_preflight_report.json
```

The preflight validates request JSONL shape, required output-key instructions,
JSON-object response settings, deterministic temperature, and PHI scan results
without sending data. To run against a compliant teacher endpoint, configure
runtime-only environment variables and use `--run`:

```bash
TEACHER_BASE_URL=https://teacher.example/v1 \
TEACHER_MODEL=large-teacher-model-name \
TEACHER_API_KEY=runtime-only-secret \
python3 llm-distill/scripts/run_teacher_label_batch.py \
  --response-output llm-distill/data/distillation/teacher_responses_pending.jsonl \
  --report-output llm-distill/evals/reports/teacher_label_batch_preflight_report.json \
  --run
```

The response output path is ignored by `.gitignore`. Do not check in raw teacher
responses until they pass ingestion validation, PHI scanning, and human review
where required.

If no compliant teacher endpoint is configured yet, create an offline review
packet for a human reviewer or separately operated teacher workflow:

```bash
python3 llm-distill/scripts/run_teacher_review_packet.py \
  --packet-output llm-distill/data/distillation/teacher_review_packet.jsonl \
  --report-output llm-distill/evals/reports/teacher_review_packet_report.json
```

The packet includes the synthetic input, the deterministic seed candidate
output, required output keys, micro-skill IDs, and per-record approval checks.
It does not approve labels by itself. A reviewer must update a completed packet
with `review_status=human_reviewed` or `large_teacher_reviewed`,
`approved_for_sft=true`, a pseudonymous `reviewer_id`, `reviewed_at`, and all
required checks set to `true`. Use an ignored completed-packet path such as
`llm-distill/data/distillation/teacher_review_packet_completed.local.jsonl`.

For this repository's synthetic/no-PHI seed set, a local large-teacher review
helper can approve candidate labels only after repeatable safety and schema
checks pass:

```bash
python3 llm-distill/scripts/run_synthetic_teacher_review.py \
  --packet-input llm-distill/data/distillation/teacher_review_packet.jsonl \
  --packet-output llm-distill/data/distillation/teacher_review_packet.jsonl \
  --report-output llm-distill/evals/reports/synthetic_teacher_review_report.json \
  --fail-on-blocked
```

This is not human review and does not call external teacher endpoints. It only
marks the synthetic packet as `large_teacher_reviewed` for local SFT
experiments when every record remains synthetic/no-PHI, source-status-tagged,
citation-backed, schema-valid, and clearly gated for human review.

After approval, export ingestion-compatible response JSONL:

```bash
python3 llm-distill/scripts/run_teacher_review_packet.py \
  --packet-input llm-distill/data/distillation/teacher_review_packet.jsonl \
  --response-output llm-distill/data/distillation/teacher_responses_from_review.jsonl \
  --report-output llm-distill/evals/reports/teacher_review_packet_report.json \
  --export-responses \
  --fail-on-unapproved
```

The response output path is ignored by `.gitignore` and still must pass
`ingest_teacher_labels.py` before SFT export. The checked-in packet report is
expected to show `review_packet_ready=true` but `training_ready=false` until all
10 labels are approved.

```bash
python3 llm-distill/scripts/ingest_teacher_labels.py \
  --teacher-responses llm-distill/data/distillation/teacher_responses_from_review.jsonl \
  --reviewed-output llm-distill/data/distillation/reviewed_supervised.jsonl
```

The ingestion script validates required output keys, JSON parseability,
human-review gates, `draft_for_human_review`, source-status groups, unsafe
phrases, and PHI scan results before writing reviewed records. It writes
`llm-distill/data/distillation/teacher_label_ingestion_report.json` whether the
merge passes or fails.

Prepare MLX-LM chat-format SFT files from the seed records:

```bash
python3 llm-distill/scripts/prepare_mlx_sft_data.py
```

The script writes:

- `llm-distill/data/distillation/mlx_sft_seed/train.jsonl`
- `llm-distill/data/distillation/mlx_sft_seed/valid.jsonl`
- `llm-distill/data/distillation/mlx_sft_seed/test.jsonl`
- `llm-distill/data/distillation/mlx_sft_seed/manifest.json`
- `llm-distill/data/distillation/mlx_sft_seed/train_lora_command.txt`

The manifest marks `training_allowed=false` while records are still
`pending_large_teacher_review`. Replace seed labels with reviewed large-teacher
or human-approved labels before running the LoRA command.

The generated local LoRA command defaults to 60 iterations for a first M1 iMac
student-adapter run. Increase `--iters` only after the short reviewed-label run
and live student benchmark justify more training time.

## Approved Corpus SFT Export

Use the corpus exporter only after the safe corpus manifest has approved
de-identified denial/appeal pairs:

```bash
python3 llm-distill/scripts/export_corpus_sft_data.py \
  --manifest llm-distill/data/corpus/manifest.json \
  --output-dir llm-distill/data/distillation/mlx_sft_corpus \
  --fail-on-blocked
```

The exporter reads only local UTF-8 text files referenced by manifest
`source_url_or_path`, ignores records that are not `training_eligible=true`,
requires complete denial-letter plus appeal-letter pairs, verifies
`sha256:` checksums, and blocks generated rows when the metadata-only PHI/PII
scanner reports findings. The generated manifest preserves `pair_id`,
document IDs, source IDs, MS01-MS12 counts, payer type, denial type, appeal
route, appeal level, outcome, source type, and document-role coverage. It keeps
`training_allowed=false` unless train/valid/test splits are populated and all
required micro-skills are covered.

The default output directory is ignored by `.gitignore`. Do not check in
approved corpus split files, de-identified real examples, private review
artifacts, or adapter weights.

## Reviewed Distillation Pipeline

Run the full reviewed-label pipeline in preflight mode to see which gates are
ready before writing reviewed outputs, training, or promoting a student:

```bash
python3 llm-distill/scripts/run_reviewed_distillation_pipeline.py \
  --report-output llm-distill/evals/reports/reviewed_distillation_pipeline_report.json
```

Preflight mode does not call teacher endpoints, train models, benchmark
endpoints, or write adapter weights. It reports the status of:

- teacher response JSONL availability and PHI scan;
- teacher-label ingestion and reviewed supervised JSONL readiness;
- reviewed MLX SFT split export and `training_allowed` status;
- guarded LoRA fine-tune evidence;
- student acceptance evidence.

After real reviewed teacher responses exist, run only the data stages first:

```bash
python3 llm-distill/scripts/run_reviewed_distillation_pipeline.py \
  --teacher-responses llm-distill/data/distillation/teacher_responses_pending.jsonl \
  --reviewed-output llm-distill/data/distillation/reviewed_supervised.jsonl \
  --ingestion-report llm-distill/data/distillation/teacher_label_ingestion_report.json \
  --reviewed-sft-dir llm-distill/data/distillation/mlx_sft_reviewed \
  --run-ingest \
  --run-sft-export
```

Then run `--run-finetune` only after the reviewed MLX SFT manifest is ready and
`mlx_lm.lora` is installed. Run `--run-acceptance` only after live base and
student benchmark reports exist. The default reviewed response, reviewed SFT,
and reviewed-label report paths are ignored by `.gitignore`; do not check in raw
teacher responses, reviewed supervised labels, adapter weights, or private
benchmark artifacts.

## Distillation Readiness Audit

Run the top-level readiness audit before treating the distillation goal as
complete:

```bash
python3 llm-distill/scripts/run_distillation_readiness_audit.py \
  --output llm-distill/evals/reports/distillation_readiness_audit_report.json
```

The audit reads the current source registry, safe corpus manifest, corpus SFT
manifest, synthetic seed set, MLX SFT manifest, workflow baseline,
teacher-label preflight, reviewed-pipeline report, fine-tune report, live
benchmark reports, student acceptance report, and PHI scan evidence. It does
not call endpoints, train, benchmark, download weights, quantize, or write
adapter files.

The checked-in report is expected to show `distillation_ready=false` and
`release_ready=false` until the approved safe corpus has at least three
training-eligible denial/appeal pairs, corpus SFT export is trainable, reviewed
labels exist, reviewed MLX SFT export is ready, MLX-LM training has completed,
live base/student benchmarks cover the full 10-record scenario set, and student
acceptance passes. Use
`--fail-on-blocked` in automation when any missing evidence should return exit
code 2.

## Local MLX Fine-Tune Preflight

Before running live benchmarks or LoRA jobs, verify the local runtime:

```bash
python3 llm-distill/scripts/run_mlx_runtime_preflight.py \
  --output llm-distill/evals/reports/mlx_runtime_preflight_report.json
```

This check does not install dependencies, download models, start servers, call
teacher endpoints, train, benchmark, quantize, or write adapter weights. It
records whether `mlx-lm` is installed, MLX-LM CLI commands are available, and
`mlx_lm.server` is reachable at the configured OpenAI-compatible base URL.

To create the project-local MLX environment and refresh the checked-in evidence
from that environment, run:

```bash
python3 llm-distill/scripts/bootstrap_mlx_runtime.py
```

The bootstrap creates or reuses `.venv-mlx`, installs `mlx-lm`, then runs the
runtime preflight, fine-tune preflight, and readiness audit with the virtualenv
on `PATH`. It does not download model weights, start `mlx_lm.server`, call a
teacher endpoint, train, benchmark, quantize, or write adapter weights. Delete
`.venv-mlx` to roll back the local environment.

Before running LoRA, validate the manifest and local training environment:

```bash
python3 llm-distill/scripts/run_mlx_finetune.py \
  --manifest llm-distill/data/distillation/mlx_sft_seed/manifest.json \
  --output llm-distill/evals/reports/mlx_finetune_preflight_report.json
```

Preflight mode does not install dependencies, download models, run training, or
write adapter weights. It checks:

- `manifest.json` has `training_allowed=true`;
- train/valid/test JSONL files exist and match split counts;
- chat rows keep the ClaimGuard assistant JSON contract;
- `human_review_required=true` and `draft_for_human_review` are preserved;
- PHI/PII scan findings are absent;
- `mlx_lm.lora` is available on `PATH`.

The checked-in seed manifest is expected to report `ready=false` until real
large-teacher or human-reviewed labels replace pending seed labels and MLX-LM
training tools are installed locally.

Only after reviewed labels are exported and preflight is ready, run:

```bash
python3 llm-distill/scripts/run_mlx_finetune.py \
  --manifest /path/to/reviewed_mlx_sft/manifest.json \
  --output /path/to/reviewed_mlx_sft/finetune_run_report.json \
  --run
```

The run path executes the manifest command with `subprocess.run(...,
shell=False)` and records exit status plus stdout/stderr tails in the report.

## Local MLX Benchmarking

After starting `mlx_lm.server`, run a benchmark against the synthetic records:

```bash
python3 llm-distill/scripts/run_mlx_benchmark.py \
  --records llm-distill/data/distillation/seed_synthetic_supervised.jsonl \
  --base-url http://localhost:8080/v1 \
  --model Qwen/Qwen3-4B-MLX-4bit \
  --output llm-distill/evals/reports/local_mlx_benchmark_report.json
```

For format-only validation without a local model server:

```bash
python3 llm-distill/scripts/run_mlx_benchmark.py --dry-run
```

The report captures endpoint availability, latency, approximate output tokens
per second, JSON validity, required output keys, route/denial-type agreement,
and human-review/draft gates. By default, benchmark prompts append the
`strict_claim_guard_json_v1` contract so both base and student runs are scored
against the same explicit JSON-array and `draft_sections` object requirements.
The contract also restricts `denial_type` to the reviewed-label taxonomy and
prevents appeal route/status labels from being used as denial reasons. Use
`--no-strict-schema-contract` only for historical comparison runs.

## Student Acceptance Gate

After a reviewed-label LoRA run and live model benchmarks, run the promotion
gate before treating an adapter as the ClaimGuard student model:

```bash
python3 llm-distill/scripts/run_student_acceptance.py \
  --workflow-report llm-distill/evals/reports/workflow_baseline_report.json \
  --fine-tune-report llm-distill/evals/reports/mlx_finetune_preflight_report.json \
  --base-benchmark llm-distill/evals/reports/local_mlx_benchmark_report.json \
  --student-benchmark llm-distill/evals/reports/student_mlx_benchmark_report.json \
  --output llm-distill/evals/reports/student_acceptance_report.json \
  --fail-on-blocked
```

The gate checks deterministic workflow regression, successful LoRA run evidence,
full live base/student benchmark reports, JSON/output-contract gates,
human-review and draft markers, score regression, and PHI scan results. The
input reports must stay under `llm-distill/evals/reports/`, and the adapter
path must stay under `llm-distill/models/adapters/` before the acceptance report
can be release-ready. The current checked-in report should be treated as the
source of truth for whether the reviewed adapter is promotable; do not promote
an adapter while `release_ready=false`.

## Data Rule

Do not store raw PHI, real denial letters, production claim files, local model
weights, private eval cases, or unreviewed production training corpora in this
directory. Checked-in synthetic seed records are limited to no-PHI format and
safety-gate validation; they are not final production training data. Use the
`.gitignore` rules at the repository root before any corpus or model-output
work.
