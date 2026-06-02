#!/usr/bin/env python3
"""Orchestrate reviewed-label distillation stages for ClaimGuard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from report_output_sanitizer import write_source_controlled_report_json
from run_phi_scan import scan_text


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DATA_DIR = DISTILL_DIR / "data" / "distillation"
REPORT_DIR = DISTILL_DIR / "evals" / "reports"
DEFAULT_PENDING_TEACHER_RESPONSES = DATA_DIR / "teacher_responses_pending.jsonl"
DEFAULT_REVIEW_TEACHER_RESPONSES = DATA_DIR / "teacher_responses_from_review.jsonl"
DEFAULT_REVIEWED_OUTPUT = DATA_DIR / "reviewed_supervised.jsonl"
DEFAULT_INGESTION_REPORT = DATA_DIR / "teacher_label_ingestion_report.json"
DEFAULT_REVIEWED_SFT_DIR = DATA_DIR / "mlx_sft_reviewed"
DEFAULT_REVIEWED_ADAPTER_PATH = (
    DISTILL_DIR / "models" / "adapters" / "claimguard-qwen3-4b-lora-reviewed"
)
DEFAULT_FINE_TUNE_REPORT = REPORT_DIR / "mlx_finetune_reviewed_report.json"
DEFAULT_BASE_BENCHMARK = REPORT_DIR / "local_mlx_benchmark_report.json"
DEFAULT_STUDENT_BENCHMARK = REPORT_DIR / "student_mlx_benchmark_report.json"
DEFAULT_ACCEPTANCE_REPORT = REPORT_DIR / "student_acceptance_report.json"
DEFAULT_PIPELINE_REPORT = REPORT_DIR / "reviewed_distillation_pipeline_report.json"


def default_teacher_responses() -> Path:
    if DEFAULT_REVIEW_TEACHER_RESPONSES.exists():
        return DEFAULT_REVIEW_TEACHER_RESPONSES
    return DEFAULT_PENDING_TEACHER_RESPONSES


def count_jsonl(path: Path) -> int | None:
    if not path.exists():
        return None
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def phi_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "finding_count": None, "findings": []}
    findings = scan_text(path, path.read_text(encoding="utf-8"))
    return {"exists": True, "finding_count": len(findings), "findings": findings}


def tail_text(value: str, limit: int = 3000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def run_command(command: list[str], *, cwd: Path = REPO_ROOT) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout_tail": tail_text(result.stdout),
        "stderr_tail": tail_text(result.stderr),
    }


def stage_status(
    *,
    name: str,
    ready: bool,
    blockers: list[str],
    evidence: dict[str, Any],
    command_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "stage": name,
        "ready": ready,
        "blockers": blockers,
        "evidence": evidence,
    }
    if command_result is not None:
        payload["command_result"] = command_result
    return payload


def teacher_response_stage(path: Path) -> dict[str, Any]:
    blockers = []
    record_count = count_jsonl(path)
    phi = phi_summary(path)
    if record_count is None:
        blockers.append("teacher response JSONL is missing")
    elif record_count <= 0:
        blockers.append("teacher response JSONL has no records")
    if phi["finding_count"]:
        blockers.append("teacher response JSONL has PHI/PII scan findings")
    return stage_status(
        name="teacher_responses",
        ready=not blockers,
        blockers=blockers,
        evidence={
            "path": str(path),
            "record_count": record_count,
            "phi_scan": phi,
        },
    )


def ingestion_stage(
    *,
    teacher_responses: Path,
    reviewed_output: Path,
    ingestion_report: Path,
    teacher_model: str,
    run_stage: bool,
) -> dict[str, Any]:
    blockers = []
    command_result = None
    if not teacher_responses.exists():
        blockers.append("teacher response JSONL is required before ingestion")
    if run_stage and not blockers:
        command = [
            sys.executable,
            str(SCRIPT_DIR / "ingest_teacher_labels.py"),
            "--teacher-responses",
            str(teacher_responses),
            "--reviewed-output",
            str(reviewed_output),
            "--report-output",
            str(ingestion_report),
            "--teacher-model",
            teacher_model,
        ]
        command_result = run_command(command)
        if command_result["returncode"] != 0:
            blockers.append("teacher label ingestion command failed")

    report = load_json(ingestion_report)
    if report is None:
        blockers.append("teacher label ingestion report is missing")
    else:
        if report.get("error_count") != 0:
            blockers.append("teacher label ingestion report has errors")
        training_gate = report.get("training_gate", {})
        if not isinstance(training_gate, dict) or training_gate.get("training_allowed") is not True:
            blockers.append("teacher label ingestion did not allow training")
    reviewed_count = count_jsonl(reviewed_output)
    if reviewed_count is None:
        blockers.append("reviewed supervised JSONL is missing")
    elif reviewed_count <= 0:
        blockers.append("reviewed supervised JSONL has no records")
    phi = phi_summary(reviewed_output)
    if phi["finding_count"]:
        blockers.append("reviewed supervised JSONL has PHI/PII scan findings")

    return stage_status(
        name="ingest_reviewed_labels",
        ready=not blockers,
        blockers=blockers,
        evidence={
            "reviewed_output": str(reviewed_output),
            "reviewed_record_count": reviewed_count,
            "ingestion_report": str(ingestion_report),
            "ingestion_report_summary": report,
            "phi_scan": phi,
            "run_requested": run_stage,
        },
        command_result=command_result,
    )


def sft_stage(
    *,
    reviewed_output: Path,
    reviewed_sft_dir: Path,
    adapter_path: Path,
    model: str,
    run_stage: bool,
) -> dict[str, Any]:
    blockers = []
    command_result = None
    if not reviewed_output.exists():
        blockers.append("reviewed supervised JSONL is required before reviewed SFT export")
    if run_stage and not blockers:
        command = [
            sys.executable,
            str(SCRIPT_DIR / "prepare_mlx_sft_data.py"),
            "--input",
            str(reviewed_output),
            "--output-dir",
            str(reviewed_sft_dir),
            "--adapter-path",
            str(adapter_path),
            "--model",
            model,
        ]
        command_result = run_command(command)
        if command_result["returncode"] != 0:
            blockers.append("reviewed MLX SFT export command failed")

    manifest = load_json(reviewed_sft_dir / "manifest.json")
    if manifest is None:
        blockers.append("reviewed MLX SFT manifest is missing")
    else:
        if manifest.get("training_allowed") is not True:
            blockers.append("reviewed MLX SFT manifest does not allow training")
    split_counts: dict[str, int | None] = {
        split: count_jsonl(reviewed_sft_dir / f"{split}.jsonl")
        for split in ["train", "valid", "test"]
    }
    for split, count in split_counts.items():
        if count is None:
            blockers.append(f"reviewed MLX SFT {split}.jsonl is missing")
        elif count <= 0:
            blockers.append(f"reviewed MLX SFT {split}.jsonl has no records")
    phi_scans = {
        split: phi_summary(reviewed_sft_dir / f"{split}.jsonl")
        for split in ["train", "valid", "test"]
    }
    for split, scan in phi_scans.items():
        if scan["finding_count"]:
            blockers.append(f"reviewed MLX SFT {split}.jsonl has PHI/PII scan findings")

    return stage_status(
        name="export_reviewed_mlx_sft",
        ready=not blockers,
        blockers=blockers,
        evidence={
            "reviewed_sft_dir": str(reviewed_sft_dir),
            "adapter_path": str(adapter_path),
            "manifest": str(reviewed_sft_dir / "manifest.json"),
            "manifest_summary": manifest,
            "split_counts": split_counts,
            "phi_scans": phi_scans,
            "run_requested": run_stage,
        },
        command_result=command_result,
    )


def fine_tune_stage(
    *,
    manifest: Path,
    fine_tune_report: Path,
    run_stage: bool,
) -> dict[str, Any]:
    blockers = []
    command_result = None
    if not manifest.exists():
        blockers.append("reviewed MLX SFT manifest is required before fine-tune")
    command = [
        sys.executable,
        str(SCRIPT_DIR / "run_mlx_finetune.py"),
        "--manifest",
        str(manifest),
        "--output",
        str(fine_tune_report),
    ]
    if run_stage:
        command.append("--run")
    if run_stage and not blockers:
        command_result = run_command(command)
        if command_result["returncode"] != 0:
            blockers.append("MLX fine-tune command failed or was blocked")

    report = load_json(fine_tune_report)
    if report is None:
        blockers.append("fine-tune report is missing")
    else:
        if run_stage:
            if report.get("training_attempted") is not True:
                blockers.append("fine-tune report did not attempt training")
            if report.get("training_succeeded") is not True:
                blockers.append("fine-tune report did not succeed")
        else:
            if report.get("ready") is not True:
                blockers.append("fine-tune preflight is not ready")
    return stage_status(
        name="fine_tune_student",
        ready=not blockers,
        blockers=blockers,
        evidence={
            "manifest": str(manifest),
            "fine_tune_report": str(fine_tune_report),
            "fine_tune_report_summary": report,
            "run_requested": run_stage,
        },
        command_result=command_result,
    )


def acceptance_stage(
    *,
    workflow_report: Path,
    fine_tune_report: Path,
    base_benchmark: Path,
    student_benchmark: Path,
    acceptance_report: Path,
    run_stage: bool,
) -> dict[str, Any]:
    blockers = []
    command_result = None
    if run_stage:
        command = [
            sys.executable,
            str(SCRIPT_DIR / "run_student_acceptance.py"),
            "--workflow-report",
            str(workflow_report),
            "--fine-tune-report",
            str(fine_tune_report),
            "--base-benchmark",
            str(base_benchmark),
            "--student-benchmark",
            str(student_benchmark),
            "--output",
            str(acceptance_report),
            "--fail-on-blocked",
        ]
        command_result = run_command(command)
        if command_result["returncode"] != 0:
            blockers.append("student acceptance command failed or was blocked")

    report = load_json(acceptance_report)
    if report is None:
        blockers.append("student acceptance report is missing")
    elif report.get("release_ready") is not True:
        blockers.append("student acceptance report is not release-ready")
    return stage_status(
        name="student_acceptance",
        ready=not blockers,
        blockers=blockers,
        evidence={
            "workflow_report": str(workflow_report),
            "fine_tune_report": str(fine_tune_report),
            "base_benchmark": str(base_benchmark),
            "student_benchmark": str(student_benchmark),
            "acceptance_report": str(acceptance_report),
            "acceptance_report_summary": report,
            "run_requested": run_stage,
        },
        command_result=command_result,
    )


def write_report(path: Path, payload: dict[str, Any]) -> None:
    write_source_controlled_report_json(path, payload, REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-responses", type=Path, default=default_teacher_responses())
    parser.add_argument("--reviewed-output", type=Path, default=DEFAULT_REVIEWED_OUTPUT)
    parser.add_argument("--ingestion-report", type=Path, default=DEFAULT_INGESTION_REPORT)
    parser.add_argument("--reviewed-sft-dir", type=Path, default=DEFAULT_REVIEWED_SFT_DIR)
    parser.add_argument("--adapter-path", type=Path, default=DEFAULT_REVIEWED_ADAPTER_PATH)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-MLX-4bit")
    parser.add_argument("--teacher-model", default="teacher_model_reviewed")
    parser.add_argument("--fine-tune-report", type=Path, default=DEFAULT_FINE_TUNE_REPORT)
    parser.add_argument(
        "--workflow-report",
        type=Path,
        default=REPORT_DIR / "workflow_baseline_report.json",
    )
    parser.add_argument("--base-benchmark", type=Path, default=DEFAULT_BASE_BENCHMARK)
    parser.add_argument("--student-benchmark", type=Path, default=DEFAULT_STUDENT_BENCHMARK)
    parser.add_argument("--acceptance-report", type=Path, default=DEFAULT_ACCEPTANCE_REPORT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_PIPELINE_REPORT)
    parser.add_argument("--run-ingest", action="store_true")
    parser.add_argument("--run-sft-export", action="store_true")
    parser.add_argument("--run-finetune", action="store_true")
    parser.add_argument("--run-acceptance", action="store_true")
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return exit code 2 when any pipeline stage is blocked.",
    )
    args = parser.parse_args()

    stages = [
        teacher_response_stage(args.teacher_responses),
        ingestion_stage(
            teacher_responses=args.teacher_responses,
            reviewed_output=args.reviewed_output,
            ingestion_report=args.ingestion_report,
            teacher_model=args.teacher_model,
            run_stage=args.run_ingest,
        ),
        sft_stage(
            reviewed_output=args.reviewed_output,
            reviewed_sft_dir=args.reviewed_sft_dir,
            adapter_path=args.adapter_path,
            model=args.model,
            run_stage=args.run_sft_export,
        ),
        fine_tune_stage(
            manifest=args.reviewed_sft_dir / "manifest.json",
            fine_tune_report=args.fine_tune_report,
            run_stage=args.run_finetune,
        ),
        acceptance_stage(
            workflow_report=args.workflow_report,
            fine_tune_report=args.fine_tune_report,
            base_benchmark=args.base_benchmark,
            student_benchmark=args.student_benchmark,
            acceptance_report=args.acceptance_report,
            run_stage=args.run_acceptance,
        ),
    ]
    blocked_stages = [stage for stage in stages if not stage["ready"]]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "run" if any([args.run_ingest, args.run_sft_export, args.run_finetune, args.run_acceptance]) else "preflight",
        "pipeline_ready": not blocked_stages,
        "blocked_stage_count": len(blocked_stages),
        "blocked_stages": [
            {"stage": stage["stage"], "blockers": stage["blockers"]}
            for stage in blocked_stages
        ],
        "stage_run_requests": {
            "run_ingest": args.run_ingest,
            "run_sft_export": args.run_sft_export,
            "run_finetune": args.run_finetune,
            "run_acceptance": args.run_acceptance,
        },
        "stages": stages,
        "notes": [
            "Default preflight mode does not call teacher endpoints, train models, benchmark endpoints, or write adapter weights.",
            "Each stage runs only when its explicit --run-* flag is supplied.",
            "Raw teacher responses and reviewed training outputs are ignored by repository .gitignore rules.",
        ],
    }
    write_report(args.report_output, payload)
    print(f"wrote reviewed distillation pipeline report to {args.report_output}")
    if blocked_stages and args.fail_on_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
