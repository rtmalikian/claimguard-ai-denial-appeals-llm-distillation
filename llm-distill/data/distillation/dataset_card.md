# ClaimGuard Synthetic Distillation Dataset Card

Architected by Raphael Malikian <rtmalikian@gmail.com>.

## Purpose

This seed dataset prepares ClaimGuard denial-processing and appeal-drafting records for a smaller local student model. It is not a production training corpus and is not a substitute for reviewed teacher labels.

## Data Status

- Data tier: synthetic.
- PHI status: no PHI intended; run `llm-distill/scripts/run_phi_scan.py` before use.
- Label source: deterministic ClaimGuard workflow seed pending large-teacher or human review.
- User-uploaded PHI: not allowed.
- Runtime target: MLX/MLX-LM student model path from `llm-distill/llm-distill-plan.md`.

## Counts

- Supervised seed records: 10.
- Teacher request records: 10.
- Splits: {'dev': 10}.
- Micro-skill coverage: {'MS01': 10, 'MS02': 10, 'MS03': 10, 'MS04': 1, 'MS05': 5, 'MS06': 10, 'MS07': 1, 'MS08': 10, 'MS09': 10, 'MS10': 10, 'MS11': 10, 'MS12': 1}.
- Required micro-skills: ['MS01', 'MS02', 'MS03', 'MS04', 'MS05', 'MS06', 'MS07', 'MS08', 'MS09', 'MS10', 'MS11', 'MS12'].
- Missing required micro-skills: [].

## Intended Use

Use these records to dry-run SFT formatting, teacher-label review, JSON validation, and regression scoring. Do not treat them as final teacher-labeled training data until a compliant teacher model or human reviewer has approved labels.

## Exclusions

Do not add real denial letters, user-uploaded documents, private claims, credentials, local model weights, or raw PHI to this dataset path.
