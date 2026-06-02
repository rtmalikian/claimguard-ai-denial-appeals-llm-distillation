#!/usr/bin/env python3
"""Preflight or run a guarded MLX-LM LoRA fine-tune for ClaimGuard."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from report_output_sanitizer import write_source_controlled_report_json
from run_phi_scan import scan_text


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "mlx_sft_seed" / "manifest.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "mlx_finetune_preflight_report.json"
)
DEFAULT_PRODUCTION_CORPUS_REPORT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "production_corpus_evidence_report.json"
)
REQUIRED_SPLITS = ("train", "valid", "test")
REQUIRED_MANIFEST_KEYS = {
    "adapter_path",
    "data_safety",
    "format",
    "model",
    "split_counts",
    "train_command",
    "training_allowed",
}
ALLOWED_DATA_TIERS = {"synthetic", "approved_deidentified_corpus", "safe_hybrid_corpus"}
CORPUS_DERIVED_DATA_TIERS = {"approved_deidentified_corpus", "safe_hybrid_corpus"}
ALLOWED_PHI_STATUSES = {"no_phi", "deidentified"}
REQUIRED_ASSISTANT_KEYS = {
    "case_summary",
    "known_from_documents",
    "inferred",
    "missing_needs_human_verification",
    "cited_rules",
    "plan_type",
    "denial_type",
    "recommended_route",
    "deadline_table",
    "evidence_gaps",
    "draft_sections",
    "follow_up_plan",
    "human_review_required",
    "warnings",
}


def load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"manifest not found: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"manifest is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        return None, ["manifest JSON must be an object"]
    missing = sorted(REQUIRED_MANIFEST_KEYS - set(payload))
    if missing:
        return payload, [f"manifest missing required keys: {missing}"]
    return payload, []


def load_json_report(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"production corpus evidence report not found: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"production corpus evidence report is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        return None, ["production corpus evidence report JSON must be an object"]
    return payload, []


def resolve_path(raw_path: str | Path, base_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def command_data_dir(command: list[Any], manifest_path: Path) -> Path:
    if "--data" in command:
        data_index = command.index("--data") + 1
        if data_index < len(command):
            return resolve_path(str(command[data_index]), REPO_ROOT)
    return manifest_path.parent.resolve()


def command_adapter_path(command: list[Any], manifest: dict[str, Any]) -> Path:
    if "--adapter-path" in command:
        adapter_index = command.index("--adapter-path") + 1
        if adapter_index < len(command):
            return resolve_path(str(command[adapter_index]), REPO_ROOT)
    return resolve_path(str(manifest.get("adapter_path", "")), REPO_ROOT)


def blocked_requirement_ids_from_report(report: dict[str, Any] | None) -> list[str]:
    if not isinstance(report, dict):
        return []
    requirements = report.get("requirements")
    if not isinstance(requirements, list):
        return []
    blocked_ids: list[str] = []
    for item in requirements:
        if not isinstance(item, dict) or item.get("status") != "blocked":
            continue
        requirement_id = item.get("requirement_id")
        if isinstance(requirement_id, str) and requirement_id:
            blocked_ids.append(requirement_id)
    return blocked_ids


def production_corpus_run_gate(
    manifest: dict[str, Any],
    *,
    report_path: Path = DEFAULT_PRODUCTION_CORPUS_REPORT,
    report_payload: dict[str, Any] | None = None,
    enforce: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    data_safety = manifest.get("data_safety") if isinstance(manifest, dict) else {}
    data_tier = (
        data_safety.get("data_tier") if isinstance(data_safety, dict) else None
    )
    corpus_derived_training = data_tier in CORPUS_DERIVED_DATA_TIERS
    blockers: list[str] = []
    report_errors: list[str] = []
    report_loaded = report_payload is not None
    if enforce and corpus_derived_training and report_payload is None:
        report_payload, report_errors = load_json_report(report_path)
        report_loaded = report_payload is not None

    report_ready = (
        report_payload.get("production_corpus_ready") is True
        if isinstance(report_payload, dict)
        else None
    )
    report_safe_to_review = (
        report_payload.get("safe_to_review") is True
        if isinstance(report_payload, dict)
        else None
    )
    blocked_requirement_ids = blocked_requirement_ids_from_report(report_payload)

    if enforce and corpus_derived_training:
        blockers.extend(report_errors)
        if report_loaded and report_ready is not True:
            blockers.append("production_corpus_evidence_report_not_ready_for_training_run")
        if report_loaded and report_safe_to_review is not True:
            blockers.append("production_corpus_evidence_report_not_safe_to_review")
        if blocked_requirement_ids:
            blockers.append("production_corpus_evidence_report_has_blocked_requirements")

    return {
        "required_for_run": corpus_derived_training,
        "enforced": enforce and corpus_derived_training,
        "data_tier": data_tier,
        "report_path": str(report_path),
        "report_loaded": report_loaded,
        "report_ready": report_ready,
        "report_safe_to_review": report_safe_to_review,
        "blocked_requirement_ids": blocked_requirement_ids,
        "blockers": blockers,
        "safe_context": {
            "raw_document_content_included": False,
            "raw_source_paths_included": False,
            "raw_checksums_included": False,
            "raw_phi_included": False,
            "raw_secret_included": False,
            "approval_reference_value_included": False,
        },
    }, blockers


def validate_manifest(
    manifest: dict[str, Any] | None,
    manifest_path: Path,
) -> tuple[dict[str, Any], list[str], list[str], list[str], Path | None, Path | None]:
    errors: list[str] = []
    warnings: list[str] = []
    blocked_reasons: list[str] = []
    data_dir: Path | None = None
    adapter_path: Path | None = None

    if manifest is None:
        return {}, errors, warnings, blocked_reasons, data_dir, adapter_path

    command = manifest.get("train_command")
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        errors.append("manifest train_command must be a list of strings")
        command = []

    if command:
        command_name = Path(command[0]).name
        if command_name != "mlx_lm.lora":
            errors.append("manifest train_command must execute mlx_lm.lora")
        if "--train" not in command:
            errors.append("manifest train_command must include --train")
        if "--data" not in command:
            errors.append("manifest train_command must include --data")
        if "--adapter-path" not in command:
            errors.append("manifest train_command must include --adapter-path")
        data_dir = command_data_dir(command, manifest_path)
        adapter_path = command_adapter_path(command, manifest)

    if manifest.get("format") != "mlx_lm_chat_jsonl":
        errors.append("manifest format must be mlx_lm_chat_jsonl")

    if manifest.get("training_allowed") is not True:
        blocked_reasons.append("manifest training_allowed is not true")
        for reason in manifest.get("blocked_reasons", []):
            if isinstance(reason, str) and reason not in blocked_reasons:
                blocked_reasons.append(reason)

    data_safety = manifest.get("data_safety")
    if not isinstance(data_safety, dict):
        errors.append("manifest data_safety must be an object")
    else:
        if data_safety.get("data_tier") not in ALLOWED_DATA_TIERS:
            blocked_reasons.append(
                "data_safety.data_tier must be synthetic, approved_deidentified_corpus, "
                "or safe_hybrid_corpus"
            )
        if data_safety.get("phi_status") not in ALLOWED_PHI_STATUSES:
            blocked_reasons.append("data_safety.phi_status must be no_phi or deidentified")
        if data_safety.get("user_phi_allowed") is not False:
            blocked_reasons.append("data_safety.user_phi_allowed must be false")

    split_counts = manifest.get("split_counts")
    if not isinstance(split_counts, dict):
        errors.append("manifest split_counts must be an object")
    else:
        for split_name in REQUIRED_SPLITS:
            if not isinstance(split_counts.get(split_name), int):
                errors.append(f"manifest split_counts.{split_name} must be an integer")

    return manifest, errors, warnings, blocked_reasons, data_dir, adapter_path


def validate_split_row(path: Path, line_number: int, row: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(row, dict):
        return [f"{path}:{line_number}: row must be a JSON object"]
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 3:
        return [f"{path}:{line_number}: messages must contain system, user, and assistant rows"]
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            errors.append(f"{path}:{line_number}: messages[{index}] must be an object")
            continue
        if message.get("role") not in {"system", "user", "assistant"}:
            errors.append(f"{path}:{line_number}: messages[{index}].role is invalid")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            errors.append(f"{path}:{line_number}: messages[{index}].content must be non-empty text")

    final_message = messages[-1]
    if isinstance(final_message, dict) and final_message.get("role") != "assistant":
        errors.append(f"{path}:{line_number}: final message must be assistant completion")

    final_content = final_message.get("content") if isinstance(final_message, dict) else None
    if isinstance(final_content, str):
        try:
            assistant_payload = json.loads(final_content)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: assistant completion is not valid JSON: {exc}")
        else:
            if not isinstance(assistant_payload, dict):
                errors.append(f"{path}:{line_number}: assistant completion JSON must be an object")
            else:
                missing_keys = sorted(REQUIRED_ASSISTANT_KEYS - set(assistant_payload))
                if missing_keys:
                    errors.append(
                        f"{path}:{line_number}: assistant completion missing keys {missing_keys}"
                    )
                if assistant_payload.get("human_review_required") is not True:
                    errors.append(
                        f"{path}:{line_number}: assistant completion must keep human_review_required=true"
                    )
                draft_sections = assistant_payload.get("draft_sections")
                if not isinstance(draft_sections, list) or not any(
                    isinstance(section, dict)
                    and section.get("draft_status") == "draft_for_human_review"
                    for section in draft_sections
                ):
                    errors.append(
                        f"{path}:{line_number}: assistant completion must include draft_for_human_review"
                    )
    return errors


def validate_split_file(path: Path, expected_count: int | None) -> dict[str, Any]:
    errors: list[str] = []
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "record_count": 0,
            "expected_count": expected_count,
            "phi_findings": [],
            "errors": [f"split file not found: {path}"],
        }

    text = path.read_text(encoding="utf-8")
    phi_findings = scan_text(path, text)
    records = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        records += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSONL row: {exc}")
            continue
        errors.extend(validate_split_row(path, line_number, row))

    if records == 0:
        errors.append(f"{path}: no records")
    if expected_count is not None and records != expected_count:
        errors.append(f"{path}: expected {expected_count} records but found {records}")
    if phi_findings:
        errors.append(f"{path}: PHI/PII scanner found {len(phi_findings)} finding(s)")

    return {
        "path": str(path),
        "exists": True,
        "record_count": records,
        "expected_count": expected_count,
        "phi_findings": phi_findings,
        "errors": errors,
    }


def validate_data_dir(data_dir: Path | None, manifest: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if data_dir is None:
        return {"ready": False, "errors": ["unable to resolve MLX data directory"]}, [
            "unable to resolve MLX data directory"
        ]

    split_counts = manifest.get("split_counts") if isinstance(manifest, dict) else {}
    split_reports = {}
    errors: list[str] = []
    for split_name in REQUIRED_SPLITS:
        expected_count = split_counts.get(split_name) if isinstance(split_counts, dict) else None
        split_report = validate_split_file(data_dir / f"{split_name}.jsonl", expected_count)
        split_reports[split_name] = split_report
        errors.extend(split_report["errors"])

    total_phi_findings = sum(
        len(split_report["phi_findings"]) for split_report in split_reports.values()
    )
    return {
        "ready": not errors,
        "data_dir": str(data_dir),
        "split_reports": split_reports,
        "total_phi_findings": total_phi_findings,
        "errors": errors,
    }, errors


def check_mlx_lora() -> tuple[dict[str, Any], list[str]]:
    executable = shutil.which("mlx_lm.lora")
    if not executable:
        return {
            "available": False,
            "path": None,
            "runtime_ready": False,
            "help_returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "error": "mlx_lm.lora not found on PATH",
        }, ["mlx_lm.lora is not installed or not on PATH"]

    try:
        result = subprocess.run(
            [executable, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        report = {
            "available": True,
            "path": executable,
            "runtime_ready": False,
            "help_returncode": None,
            "stdout_tail": tail_text(exc.stdout or ""),
            "stderr_tail": tail_text(exc.stderr or ""),
            "error": "mlx_lm.lora --help timed out during runtime check",
        }
        return report, [report["error"]]
    except OSError as exc:
        report = {
            "available": True,
            "path": executable,
            "runtime_ready": False,
            "help_returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "error": f"mlx_lm.lora runtime check failed: {exc}",
        }
        return report, [report["error"]]

    runtime_ready = result.returncode == 0
    stderr_tail = tail_text(result.stderr)
    stdout_tail = tail_text(result.stdout)
    error = None
    if not runtime_ready:
        error = (
            "mlx_lm.lora is installed but failed runtime import/help check"
        )
        if "No Metal device available" in result.stderr:
            error = "mlx_lm.lora cannot access a Metal device in this session"
    report = {
        "available": True,
        "path": executable,
        "runtime_ready": runtime_ready,
        "help_returncode": result.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "error": error,
    }
    if not runtime_ready:
        return report, [error or "mlx_lm.lora runtime check failed"]
    return {
        "available": True,
        "path": executable,
        "runtime_ready": True,
        "help_returncode": result.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "error": None,
    }, []


def sanitized_command(command: list[str], executable_path: str | None) -> list[str]:
    if executable_path:
        return [executable_path, *command[1:]]
    return command


def tail_text(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def write_report(path: Path, payload: dict[str, Any]) -> None:
    write_source_controlled_report_json(path, payload, REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually execute mlx_lm.lora after all preflight checks pass.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Optional timeout for --run. Omit for long local training jobs.",
    )
    parser.add_argument(
        "--production-corpus-report",
        type=Path,
        default=DEFAULT_PRODUCTION_CORPUS_REPORT,
        help=(
            "Boolean-only production corpus evidence report required before --run "
            "can train on corpus-derived SFT manifests."
        ),
    )
    args = parser.parse_args()

    manifest_payload, manifest_load_errors = load_manifest(args.manifest)
    (
        manifest,
        manifest_errors,
        manifest_warnings,
        manifest_blocked_reasons,
        data_dir,
        adapter_path,
    ) = validate_manifest(manifest_payload, args.manifest)
    data_report, data_errors = validate_data_dir(data_dir, manifest)
    mlx_report, mlx_errors = check_mlx_lora()
    production_corpus_report, production_corpus_blockers = production_corpus_run_gate(
        manifest,
        report_path=args.production_corpus_report,
        enforce=args.run,
    )

    raw_command = manifest.get("train_command", []) if isinstance(manifest, dict) else []
    command = (
        raw_command
        if isinstance(raw_command, list) and all(isinstance(item, str) for item in raw_command)
        else []
    )
    runnable_command = sanitized_command(command, mlx_report.get("path"))
    preflight_errors = manifest_load_errors + manifest_errors + data_errors
    blocked_reasons = manifest_blocked_reasons + mlx_errors + production_corpus_blockers
    ready = not preflight_errors and not blocked_reasons

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "run" if args.run else "preflight",
        "manifest": str(args.manifest),
        "ready": ready,
        "training_attempted": False,
        "training_succeeded": None,
        "blocked_reasons": blocked_reasons,
        "preflight_errors": preflight_errors,
        "command": runnable_command,
        "checks": {
            "manifest": {
                "ready": not manifest_load_errors
                and not manifest_errors
                and not manifest_blocked_reasons,
                "artifact": manifest.get("artifact") if manifest else None,
                "model": manifest.get("model") if manifest else None,
                "training_allowed": manifest.get("training_allowed") if manifest else None,
                "data_safety": manifest.get("data_safety") if manifest else None,
                "manifest_blocked_reasons": manifest_blocked_reasons,
                "warnings": manifest_warnings,
                "errors": manifest_load_errors + manifest_errors,
            },
            "data": data_report,
            "mlx_lm_lora": mlx_report,
            "adapter_output": {
                "path": str(adapter_path) if adapter_path else None,
                "exists_before_run": adapter_path.exists() if adapter_path else None,
                "exists_after_run": None,
            },
            "production_corpus_evidence": production_corpus_report,
            "host": {
                "system": platform.system(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python": platform.python_version(),
            },
        },
        "notes": [
            "Preflight mode does not download models, install dependencies, run training, or write adapter weights.",
            "Preflight mode does execute mlx_lm.lora --help to verify that the MLX runtime can import and access Metal in the current session.",
            "Run mode executes the manifest LoRA command with subprocess.run(..., shell=False) only after all checks pass.",
            "Run mode for corpus-derived data tiers also requires a ready and safe production corpus evidence report.",
            "The checked-in seed manifest is expected to remain blocked until labels are reviewed by a large teacher or human reviewer.",
        ],
    }

    if args.run:
        if not ready:
            write_report(args.output, payload)
            print(f"wrote MLX fine-tune preflight report to {args.output}")
            return 2
        payload["training_attempted"] = True
        result = subprocess.run(
            runnable_command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
            check=False,
        )
        payload["process"] = {
            "returncode": result.returncode,
            "stdout_tail": tail_text(result.stdout),
            "stderr_tail": tail_text(result.stderr),
        }
        payload["training_succeeded"] = result.returncode == 0
        payload["checks"]["adapter_output"]["exists_after_run"] = (
            adapter_path.exists() if adapter_path else None
        )
        write_report(args.output, payload)
        print(f"wrote MLX fine-tune run report to {args.output}")
        return result.returncode

    write_report(args.output, payload)
    print(f"wrote MLX fine-tune preflight report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
