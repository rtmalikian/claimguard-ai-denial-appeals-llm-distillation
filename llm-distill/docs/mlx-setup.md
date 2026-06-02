# MLX-LM Local Setup

Recommended primary local model:

- `Qwen/Qwen3-4B-MLX-4bit`

Recommended fallback:

- `Qwen/Qwen3-1.7B`

Install and start the local OpenAI-compatible endpoint:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade mlx-lm
mlx_lm.server --model "Qwen/Qwen3-4B-MLX-4bit"
```

Application configuration:

```env
LLM_PROVIDER=mlx_lm
MLX_BASE_URL=http://localhost:8080/v1
MLX_MODEL=Qwen/Qwen3-4B-MLX-4bit
MLX_FALLBACK_MODEL=Qwen/Qwen3-1.7B
```

When the API runs inside Docker, point `MLX_BASE_URL` at
`http://host.docker.internal:8080/v1`.

## Project-Local Bootstrap

For repeatable local setup from the repository root, use:

```bash
python3 llm-distill/scripts/bootstrap_mlx_runtime.py
```

The bootstrap creates or refreshes `.venv-mlx`, installs `mlx-lm`, and then
regenerates:

- `llm-distill/evals/reports/mlx_runtime_preflight_report.json`
- `llm-distill/evals/reports/mlx_finetune_preflight_report.json`
- `llm-distill/evals/reports/distillation_readiness_audit_report.json`
- `llm-distill/evals/reports/mlx_runtime_bootstrap_report.json`

It does not download model weights, start `mlx_lm.server`, call teacher
endpoints, train, benchmark, quantize, or write adapter weights. To use the
local CLI tools directly:

```bash
source .venv-mlx/bin/activate
mlx_lm.server --model "Qwen/Qwen3-4B-MLX-4bit"
```

Delete `.venv-mlx` to roll back the local tooling environment.

## Runtime Preflight

Before running live benchmarks or reviewed-label LoRA training, check the local
MLX-LM runtime state:

```bash
python3 llm-distill/scripts/run_mlx_runtime_preflight.py \
  --output llm-distill/evals/reports/mlx_runtime_preflight_report.json
```

The preflight writes a report only. It does not install packages, download
models, start servers, train, benchmark, quantize, or write adapter weights. It
checks:

- Apple Silicon/macOS host shape for the primary MLX path;
- the active Python environment for the `mlx-lm` package;
- `mlx_lm.server`, `mlx_lm.lora`, and `mlx_lm.generate` availability on
  `PATH`;
- the OpenAI-compatible `/v1/models` endpoint at the configured base URL.

Use `--fail-on-blocked` in automation when missing package/CLI/server evidence
should return exit code 2. A ready runtime preflight is still not model-quality
evidence; it only proves the local server and tools are available for the live
benchmark and fine-tune gates.

## Supervised Student Runtime

Production default student use also requires a supervised `mlx_lm.server`
process. The repository includes a non-secret launchd template and a
boolean-only evidence packet:

- `llm-distill/data/runtime_supervision/claimguard.mlx-student.launchd.template.plist`
- `llm-distill/data/runtime_supervision/supervisor_evidence.template.json`

Validate them with:

```bash
python3 llm-distill/scripts/validate_mlx_runtime_supervisor.py \
  --report llm-distill/evals/reports/mlx_runtime_supervisor_report.json
```

Use `--fail-on-blocked` when automation should fail until owner assignment,
restart policy review, runtime health checks, launchd load evidence, and restart
test evidence are complete. The validator only reads local JSON/plist
templates. It does not install launchd services, start `mlx_lm.server`, call
model endpoints, enable `CLAIMGUARD_STUDENT_USE_BY_DEFAULT`, or store approval
reference values.

Operator rules:

- Replace `/ABSOLUTE/PATH/TO` only in a private operator copy of the plist.
- Keep approval references, credentials, tokens, environment secrets, PHI, and
  production document details outside source control.
- Bind the supervised server to loopback only (`127.0.0.1`, `localhost`, or
  `::1`) and route application access through the configured `MLX_BASE_URL`.
- Keep `CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA` available as the rollback path.
- Do not set `CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=true` until the supervisor
  evidence report is ready, the runtime health endpoint passes, and Raphael has
  approved default student cutover.

## SFT Dry-Run Data Preparation

Prepare MLX-LM chat-format files from the synthetic seed records:

```bash
python3 llm-distill/scripts/prepare_mlx_sft_data.py
```

The script writes `train.jsonl`, `valid.jsonl`, and `test.jsonl` under
`llm-distill/data/distillation/mlx_sft_seed/`. Each row uses the MLX-LM chat
dataset shape:

```json
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

The generated `manifest.json` records the model, split counts, safety status,
and LoRA command. It intentionally marks training blocked until labels are
reviewed by a larger teacher model or human reviewer.

After labels are reviewed and `mlx-lm[train]` is installed outside the repo, the
command shape is:

```bash
mlx_lm.lora \
  --model Qwen/Qwen3-4B-MLX-4bit \
  --train \
  --data llm-distill/data/distillation/mlx_sft_seed \
  --iters 600 \
  --batch-size 1 \
  --num-layers 8 \
  --fine-tune-type lora \
  --mask-prompt \
  --adapter-path llm-distill/models/adapters/claimguard-qwen3-4b-lora-seed
```

Do not commit generated adapter contents. `llm-distill/models/adapters/` is
reserved for local outputs and ignored except for its README.

## Fine-Tune Preflight And Guarded Run

Use the fine-tune runner in preflight mode before any local LoRA job:

```bash
python3 llm-distill/scripts/run_mlx_finetune.py \
  --manifest llm-distill/data/distillation/mlx_sft_seed/manifest.json \
  --output llm-distill/evals/reports/mlx_finetune_preflight_report.json
```

Preflight mode writes a report only. It does not download model files, install
MLX-LM, start a server, run training, or write adapter weights. It blocks unless
all of these are true:

- the manifest has `training_allowed=true`;
- train/valid/test split files exist and match manifest counts;
- all split rows use valid MLX-LM chat `messages`;
- assistant completions are valid ClaimGuard JSON with
  `human_review_required=true` and `draft_for_human_review`;
- PHI/PII scanning has zero findings;
- `mlx_lm.lora` is installed and discoverable on `PATH`, through an explicit
  `--mlx-lora-executable` value, or through
  `CLAIMGUARD_MLX_LORA_EXECUTABLE`.

When using the project-local bootstrap environment without activating it in
the shell, run:

```bash
python3 llm-distill/scripts/run_mlx_finetune.py \
  --manifest llm-distill/data/distillation/mlx_sft_seed/manifest.json \
  --output llm-distill/evals/reports/mlx_finetune_preflight_report.json \
  --mlx-lora-executable .venv-mlx/bin/mlx_lm.lora
```

The current checked-in seed manifest should remain blocked because labels are
still `pending_large_teacher_review`. After real reviewed labels are exported to
a separate MLX SFT directory and preflight reports `ready=true`, use:

```bash
python3 llm-distill/scripts/run_mlx_finetune.py \
  --manifest /path/to/reviewed_mlx_sft/manifest.json \
  --output /path/to/reviewed_mlx_sft/finetune_run_report.json \
  --run
```

The runner executes the manifest LoRA command with `shell=False` and records
the process return code plus stdout/stderr tails. Use a local, ignored adapter
path for the output; do not commit adapter files or fused model weights.

## Reviewed Pipeline Orchestration

Use the reviewed distillation pipeline runner to connect the reviewed-label
handoff stages before any adapter promotion:

```bash
python3 llm-distill/scripts/run_reviewed_distillation_pipeline.py \
  --report-output llm-distill/evals/reports/reviewed_distillation_pipeline_report.json
```

The default preflight checks teacher response readiness, ingestion evidence,
reviewed MLX SFT export readiness, fine-tune evidence, and acceptance evidence.
It does not call teacher endpoints, run LoRA, call benchmark endpoints, or write
adapter weights.

When real reviewed teacher responses are available, run the data stages first:

```bash
python3 llm-distill/scripts/run_reviewed_distillation_pipeline.py \
  --teacher-responses llm-distill/data/distillation/teacher_responses_pending.jsonl \
  --reviewed-output llm-distill/data/distillation/reviewed_supervised.jsonl \
  --ingestion-report llm-distill/data/distillation/teacher_label_ingestion_report.json \
  --reviewed-sft-dir llm-distill/data/distillation/mlx_sft_reviewed \
  --run-ingest \
  --run-sft-export
```

Use `--run-finetune` only after the reviewed SFT manifest reports
`training_allowed=true` and MLX-LM training tools are installed. Use
`--run-acceptance` only after a successful fine-tune report plus full live base
and student benchmark reports exist. Keep reviewed responses, reviewed SFT
outputs, adapter files, and benchmark artifacts out of version control unless a
separate data-governance review explicitly approves them.

## Local Benchmark Harness

Run the local model benchmark after `mlx_lm.server` is listening:

```bash
python3 llm-distill/scripts/run_mlx_benchmark.py \
  --records llm-distill/data/distillation/seed_synthetic_supervised.jsonl \
  --base-url http://localhost:8080/v1 \
  --model Qwen/Qwen3-4B-MLX-4bit \
  --output llm-distill/evals/reports/local_mlx_benchmark_report.json
```

The harness sends synthetic prompts to the OpenAI-compatible chat endpoint,
then measures:

- request duration;
- approximate output tokens per second when usage metrics are absent;
- JSON parse validity;
- required ClaimGuard output keys;
- route and denial-type agreement with seed labels;
- `human_review_required` and `draft_for_human_review` preservation.

If the server is not running, use:

```bash
python3 llm-distill/scripts/run_mlx_benchmark.py --allow-unavailable
```

This writes an availability report instead of pretending a benchmark completed.
Use `--dry-run` only to validate scoring/report shape without making endpoint
calls.

## Student Promotion Gate

After a successful reviewed-label LoRA run, benchmark both the base model and
the trained student adapter against the synthetic ClaimGuard records. Then run:

```bash
python3 llm-distill/scripts/run_student_acceptance.py \
  --workflow-report llm-distill/evals/reports/workflow_baseline_report.json \
  --fine-tune-report /path/to/finetune_run_report.json \
  --base-benchmark /path/to/base_mlx_benchmark_report.json \
  --student-benchmark /path/to/student_mlx_benchmark_report.json \
  --output llm-distill/evals/reports/student_acceptance_report.json \
  --fail-on-blocked
```

The acceptance gate must pass before adapter promotion, quantization, or making
the student the application default. It requires:

- deterministic workflow baseline score at or above the configured threshold;
- a `--run` fine-tune report with `training_succeeded=true`;
- full live base and student benchmark reports, not dry-runs or unavailable
  endpoint reports;
- student score at or above threshold and not materially regressed from base;
- zero JSON/output-contract, human-review, draft-marker, parse, endpoint, or
  PHI scan failures.

The checked-in report may remain blocked until reviewed labels, MLX training,
and live student benchmarks exist.
