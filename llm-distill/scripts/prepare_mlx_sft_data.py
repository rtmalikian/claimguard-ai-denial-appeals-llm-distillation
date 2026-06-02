#!/usr/bin/env python3
"""Prepare MLX-LM chat-format SFT files from ClaimGuard distillation records."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "seed_synthetic_supervised.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "mlx_sft_seed"
)
DEFAULT_ADAPTER_PATH = (
    REPO_ROOT / "llm-distill" / "models" / "adapters" / "claimguard-qwen3-4b-lora-seed"
)
REQUIRED_RECORD_KEYS = {
    "example_id",
    "dataset_split",
    "task",
    "micro_skill_ids",
    "source_policy",
    "expected_output",
    "teacher_label",
    "sft_messages",
    "quality_gates",
}
TRAINING_APPROVED_STATUSES = {"large_teacher_reviewed", "human_reviewed"}
REQUIRED_MICRO_SKILLS = {f"MS{index:02d}" for index in range(1, 13)}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import (  # noqa: E402
    sanitize_report_string,
    write_sanitized_report_json,
)


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            missing = REQUIRED_RECORD_KEYS - set(record)
            if missing:
                raise ValueError(f"{path}:{line_number}: missing keys {sorted(missing)}")
            records.append(record)
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def validate_record(record: dict[str, Any]) -> list[str]:
    errors = []
    micro_skill_ids = record["micro_skill_ids"]
    if not isinstance(micro_skill_ids, list) or not micro_skill_ids:
        errors.append("micro_skill_ids must be a non-empty list")
    else:
        invalid_skills = sorted(
            skill for skill in micro_skill_ids if skill not in REQUIRED_MICRO_SKILLS
        )
        if invalid_skills:
            errors.append(f"micro_skill_ids contains unknown values: {invalid_skills}")
    source_policy = record["source_policy"]
    if source_policy.get("data_tier") != "synthetic":
        errors.append("data_tier must be synthetic for this seed export")
    if source_policy.get("phi_status") != "no_phi":
        errors.append("phi_status must be no_phi")
    if source_policy.get("user_phi_allowed") is not False:
        errors.append("user_phi_allowed must be false")
    if record["teacher_label"].get("human_review_required") is not True:
        errors.append("teacher_label.human_review_required must be true")
    if record["quality_gates"].get("draft_for_human_review_present") is not True:
        errors.append("draft_for_human_review gate must be true")
    if record["quality_gates"].get("human_review_required") is not True:
        errors.append("human_review_required gate must be true")

    messages = record["sft_messages"]
    if not isinstance(messages, list) or len(messages) < 3:
        errors.append("sft_messages must contain at least system, user, and assistant messages")
        return errors
    if messages[-1].get("role") != "assistant":
        errors.append("final SFT message must be assistant completion")
    for index, message in enumerate(messages):
        if message.get("role") not in {"system", "user", "assistant"}:
            errors.append(f"sft_messages[{index}].role is invalid")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            errors.append(f"sft_messages[{index}].content must be a non-empty string")

    try:
        assistant_payload = json.loads(messages[-1]["content"])
    except json.JSONDecodeError as exc:
        errors.append(f"assistant completion is not valid JSON: {exc}")
    else:
        if assistant_payload.get("human_review_required") is not True:
            errors.append("assistant completion must preserve human_review_required=true")
        draft_sections = assistant_payload.get("draft_sections", [])
        if draft_sections and not any(
            section.get("draft_status") == "draft_for_human_review"
            for section in draft_sections
        ):
            errors.append("assistant completion draft_sections must include draft_for_human_review")
    return errors


def split_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(records, key=lambda record: record["example_id"])
    if len(ordered) < 3:
        raise ValueError("at least 3 records are required for train/valid/test split")
    test_records = [ordered[-1]]
    valid_records = [ordered[-2]]
    train_records = ordered[:-2]
    return {
        "train": train_records,
        "valid": valid_records,
        "test": test_records,
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps({"messages": record["sft_messages"]}, sort_keys=True) + "\n")


def label_status_counts(records: list[dict[str, Any]]) -> Counter[str]:
    return Counter(record["teacher_label"].get("teacher_review_status", "unknown") for record in records)


def micro_skill_counts(records: list[dict[str, Any]]) -> Counter[str]:
    return Counter(skill for record in records for skill in record["micro_skill_ids"])


def build_train_command(
    model: str,
    data_dir: Path,
    adapter_path: Path,
    *,
    iters: int,
    steps_per_report: int,
    steps_per_eval: int,
) -> list[str]:
    return [
        "mlx_lm.lora",
        "--model",
        model,
        "--train",
        "--data",
        str(data_dir),
        "--iters",
        str(iters),
        "--batch-size",
        "1",
        "--num-layers",
        "8",
        "--fine-tune-type",
        "lora",
        "--mask-prompt",
        "--steps-per-report",
        str(steps_per_report),
        "--steps-per-eval",
        str(steps_per_eval),
        "--adapter-path",
        str(adapter_path),
    ]


def public_command(command: list[str]) -> list[str]:
    return [sanitize_report_string(item, REPO_ROOT) for item in command]


def write_command_file(path: Path, train_command: list[str], training_allowed: bool) -> None:
    status = "training_allowed" if training_allowed else "review_required_do_not_run"
    public_output = path_is_within(path, REPO_ROOT)
    command = public_command(train_command) if public_output else train_command
    wrapped = " \\\n  ".join(command)
    run_context_lines = ["Run from the repository root:", ""] if public_output else []
    path.write_text(
        "\n".join(
            [
                "# ClaimGuard MLX-LM LoRA Command",
                "",
                f"status={status}",
                "",
                "Install training dependencies outside this repository:",
                "",
                "python3 -m pip install \"mlx-lm[train]\"",
                "",
                "Training command:",
                "",
                *run_context_lines,
                wrapped,
                "",
                "Do not run this command on pending seed labels. Replace labels with reviewed large-teacher or human-approved outputs first.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_manifest(
    path: Path,
    records: list[dict[str, Any]],
    splits: dict[str, list[dict[str, Any]]],
    model: str,
    adapter_path: Path,
    train_command: list[str],
    allow_pending_labels: bool,
    source_data: Path,
) -> None:
    status_counts = label_status_counts(records)
    skill_counts = micro_skill_counts(records)
    missing_required_skills = sorted(REQUIRED_MICRO_SKILLS - set(skill_counts))
    all_labels_approved = set(status_counts).issubset(TRAINING_APPROVED_STATUSES)
    micro_skill_coverage_complete = not missing_required_skills
    training_allowed = (
        all_labels_approved and micro_skill_coverage_complete
    ) or allow_pending_labels
    blocked_reasons = []
    if not all_labels_approved:
        blocked_reasons.append(
            "One or more records are pending large-teacher or human review."
        )
    if not micro_skill_coverage_complete:
        blocked_reasons.append(
            "Missing required ClaimGuard micro-skill coverage: "
            + ", ".join(missing_required_skills)
        )
    if allow_pending_labels:
        blocked_reasons.append(
            "Operator override enabled; use only for format dry-runs, not production training."
        )

    payload = {
        "artifact": "claimguard_mlx_sft_seed",
        "model": model,
        "adapter_path": str(adapter_path),
        "format": "mlx_lm_chat_jsonl",
        "training_allowed": training_allowed,
        "blocked_reasons": blocked_reasons,
        "source_data": str(source_data),
        "record_count": len(records),
        "split_counts": {name: len(items) for name, items in splits.items()},
        "teacher_review_status_counts": dict(sorted(status_counts.items())),
        "micro_skill_counts": dict(sorted(skill_counts.items())),
        "required_micro_skill_ids": sorted(REQUIRED_MICRO_SKILLS),
        "missing_required_micro_skill_ids": missing_required_skills,
        "micro_skill_coverage_complete": micro_skill_coverage_complete,
        "data_safety": {
            "data_tier": "synthetic",
            "phi_status": "no_phi",
            "user_phi_allowed": False,
            "local_model_weights_written": False,
            "external_model_calls_made": False,
        },
        "train_command": train_command,
        "notes": [
            "MLX-LM expects train.jsonl for training, optional valid.jsonl for validation, and test.jsonl for adapter evaluation.",
            "Each generated JSONL row uses the chat dataset shape: {'messages': [...]}",
            "The final assistant message is the completion and contains compact ClaimGuard JSON.",
            "Use --mask-prompt so loss is applied to the assistant completion for chat SFT.",
        ],
    }
    if path_is_within(path, REPO_ROOT):
        write_sanitized_report_json(path, payload, REPO_ROOT)
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-MLX-4bit")
    parser.add_argument("--adapter-path", type=Path, default=DEFAULT_ADAPTER_PATH)
    parser.add_argument(
        "--iters",
        type=int,
        default=60,
        help="LoRA iterations for the generated local training command.",
    )
    parser.add_argument("--steps-per-report", type=int, default=10)
    parser.add_argument("--steps-per-eval", type=int, default=30)
    parser.add_argument(
        "--allow-pending-labels",
        action="store_true",
        help="Mark manifest as allowed despite pending labels. Use only for local format dry-runs.",
    )
    args = parser.parse_args()

    records = load_jsonl(args.input)
    validation_errors = {
        record["example_id"]: validate_record(record)
        for record in records
    }
    validation_errors = {key: value for key, value in validation_errors.items() if value}
    if validation_errors:
        raise ValueError(json.dumps(validation_errors, indent=2, sort_keys=True))

    splits = split_records(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split_name, split_records_for_name in splits.items():
        write_jsonl(args.output_dir / f"{split_name}.jsonl", split_records_for_name)

    train_command = build_train_command(
        args.model,
        args.output_dir,
        args.adapter_path,
        iters=args.iters,
        steps_per_report=args.steps_per_report,
        steps_per_eval=args.steps_per_eval,
    )
    write_manifest(
        args.output_dir / "manifest.json",
        records,
        splits,
        args.model,
        args.adapter_path,
        train_command,
        args.allow_pending_labels,
        args.input,
    )
    write_command_file(
        args.output_dir / "train_lora_command.txt",
        train_command,
        training_allowed=args.allow_pending_labels
        or set(label_status_counts(records)).issubset(TRAINING_APPROVED_STATUSES),
    )

    print(
        "wrote MLX SFT seed data to "
        f"{args.output_dir} "
        f"(train={len(splits['train'])}, valid={len(splits['valid'])}, test={len(splits['test'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
