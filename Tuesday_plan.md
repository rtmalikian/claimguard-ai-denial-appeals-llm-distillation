# Tuesday Plan — Student LLM Training on M1 iMac

**Date:** 2026-06-03
**Goal:** Train the student model on the 900-pair synthetic corpus, benchmark it, and score performance.

## Todo List

- [ ] **1. Bootstrap MLX environment** (~5 min)
  - `python3 llm-distill/scripts/bootstrap_mlx_runtime.py`
  - Creates `.venv-mlx`, installs `mlx-lm[train]`, downloads Qwen3-4B-MLX-4bit (~2.5 GB)
  - Verify preflight passes with Metal access confirmed

- [ ] **2. Run synthetic-900 fine-tune** (~45 min)
  - `python3 llm-distill/scripts/run_mlx_finetune.py --manifest llm-distill/data/distillation/mlx_sft_synthetic_900/manifest.json --output llm-distill/evals/reports/mlx_finetune_synthetic_900_run_report.json --mlx-lora-executable .venv-mlx/bin/mlx_lm.lora --run`
  - 120 iterations, batch size 1, 8 LoRA layers, 720 train samples
  - Expected peak memory: ~10 GB (16 GB iMac has headroom)
  - Close Chrome/memory-heavy apps before starting

- [ ] **3. Run base + student benchmarks** (~10 min)
  - `python3 llm-distill/scripts/run_mlx_benchmark.py`
  - 10 records, measures score, latency, tokens/sec
  - Compares base model vs student adapter

- [ ] **4. Run student acceptance gate** (~1 min)
  - `python3 llm-distill/scripts/run_student_acceptance.py`
  - Checks: workflow baseline >=0.95, benchmark >=0.95, regression <=0.02, zero PHI findings
  - Writes `student_acceptance_report.json`

- [ ] **5. Run workflow evaluation** (~5 min)
  - `python3 llm-distill/scripts/run_workflow_eval.py`
  - 10 denial scenarios, validates denial type, route, human review flags

- [ ] **6. Review results and update CHANGELOG.md**
  - Record training loss, benchmark scores, acceptance result
  - Document in CHANGELOG.md per AGENTS.md directives
  - Back up any modified files

- [ ] **7. Commit and push to GitHub**
  - Stage new reports and any adapter metadata
  - Commit with results summary
  - Push to `main`

## Notes
- Must run natively in macOS Terminal (not Docker, not SSH, not Rosetta)
- If "No Metal device available" appears, check that Terminal has GPU access
- The 900-pair data is already generated, audited, and exported — no data prep needed
- Training data: 720 train / 90 valid / 90 test rows, zero PHI findings
- Model: `Qwen/Qwen3-4B-MLX-4bit` (4-bit quantized, ~2.5 GB)

## Current Baseline (for comparison)
- Base model benchmark: 96.67% (58/60)
- Reviewed-adapter benchmark: 96.67% (58/60), zero regression
- Workflow eval: 104/104 (1.0) on deterministic path
- Acceptance gate: release_ready=true
