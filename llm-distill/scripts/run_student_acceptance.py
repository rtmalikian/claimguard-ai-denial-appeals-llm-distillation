#!/usr/bin/env python3
"""Gate promotion of a trained ClaimGuard student model."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_phi_scan import scan_text


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "llm-distill" / "evals" / "reports"
DEFAULT_WORKFLOW_REPORT = REPORT_DIR / "workflow_baseline_report.json"
DEFAULT_BASE_BENCHMARK = REPORT_DIR / "local_mlx_benchmark_report.json"
DEFAULT_STUDENT_BENCHMARK = REPORT_DIR / "student_mlx_benchmark_report.json"
DEFAULT_FINE_TUNE_REPORT = REPORT_DIR / "mlx_finetune_preflight_report.json"
DEFAULT_OUTPUT = REPORT_DIR / "student_acceptance_report.json"
DEFAULT_ADAPTER_ROOT = REPO_ROOT / "llm-distill" / "models" / "adapters"
EXTERNAL_PATH_REDACTION = "external_path_redacted"


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_cli_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (REPO_ROOT / path).resolve()
    if repo_candidate.exists() or str(path).startswith("llm-distill/"):
        return repo_candidate
    return path.resolve()


def safe_report_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = path.expanduser().resolve()
    try:
        return resolved_path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return EXTERNAL_PATH_REDACTION


def load_report(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing report: {safe_report_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{safe_report_path(path)}: invalid JSON: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"{safe_report_path(path)}: report must be a JSON object"]
    return payload, []


def phi_scan_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": safe_report_path(path),
            "exists": False,
            "finding_count": None,
            "findings": [],
        }
    text = path.read_text(encoding="utf-8")
    findings = scan_text(path, text)
    safe_findings = [
        {
            **finding,
            "path": safe_report_path(Path(str(finding.get("path", path)))),
        }
        for finding in findings
    ]
    return {
        "path": safe_report_path(path),
        "exists": True,
        "finding_count": len(findings),
        "findings": safe_findings,
    }


def add_blockers(target: list[str], reasons: list[str]) -> None:
    for reason in reasons:
        if reason not in target:
            target.append(reason)


def input_report_path_check(label: str, path: Path) -> tuple[dict[str, Any], list[str]]:
    inside_report_dir = path_is_within(path, REPORT_DIR)
    blockers: list[str] = []
    if not inside_report_dir:
        blockers.append(f"{label} report path must stay inside llm-distill/evals/reports")
    return {
        "path": safe_report_path(path),
        "exists": path.exists(),
        "inside_report_dir": inside_report_dir,
        "expected_report_dir": safe_report_path(REPORT_DIR),
        "raw_report_values_included": False,
    }, blockers


def score_ratio(summary: dict[str, Any] | None) -> float | None:
    if not isinstance(summary, dict):
        return None
    value = summary.get("score_ratio")
    return value if isinstance(value, int | float) else None


def check_workflow_report(
    report: dict[str, Any] | None,
    load_errors: list[str],
    threshold: float,
) -> tuple[dict[str, Any], list[str]]:
    blockers = list(load_errors)
    summary = report.get("summary") if report else None
    ratio = score_ratio(summary)
    scenario_count = summary.get("scenario_count") if isinstance(summary, dict) else None
    passed_count = summary.get("passed_count") if isinstance(summary, dict) else None
    failed_scenarios: list[str] = []
    forbidden_scenarios: list[str] = []

    if not isinstance(summary, dict):
        blockers.append("workflow baseline report is missing summary")
    else:
        if ratio is None or ratio < threshold:
            blockers.append(
                f"workflow baseline score_ratio must be >= {threshold}"
            )
        if not isinstance(scenario_count, int) or scenario_count <= 0:
            blockers.append("workflow baseline scenario_count must be positive")
        if passed_count != scenario_count:
            blockers.append("workflow baseline must pass every scenario")

    for result in report.get("results", []) if report else []:
        if not isinstance(result, dict):
            continue
        if result.get("passed") is not True:
            failed_scenarios.append(str(result.get("scenario_id", "unknown")))
        if result.get("forbidden_terms_found"):
            forbidden_scenarios.append(str(result.get("scenario_id", "unknown")))

    if failed_scenarios:
        blockers.append(f"workflow baseline failed scenarios: {failed_scenarios}")
    if forbidden_scenarios:
        blockers.append(f"workflow baseline has forbidden terms: {forbidden_scenarios}")

    return {
        "ready": not blockers,
        "score_ratio": ratio,
        "scenario_count": scenario_count,
        "passed_count": passed_count,
        "failed_scenarios": failed_scenarios,
        "forbidden_scenarios": forbidden_scenarios,
        "errors": load_errors,
    }, blockers


def check_fine_tune_report(
    report: dict[str, Any] | None,
    load_errors: list[str],
) -> tuple[dict[str, Any], list[str]]:
    blockers = list(load_errors)
    mode = report.get("mode") if report else None
    training_attempted = report.get("training_attempted") if report else None
    training_succeeded = report.get("training_succeeded") if report else None
    blocked_reasons = report.get("blocked_reasons", []) if report else []
    preflight_errors = report.get("preflight_errors", []) if report else []
    process = report.get("process") if report else None
    checks = report.get("checks", {}) if report else {}
    manifest_check = checks.get("manifest", {}) if isinstance(checks, dict) else {}
    data_check = checks.get("data", {}) if isinstance(checks, dict) else {}
    adapter_check = checks.get("adapter_output", {}) if isinstance(checks, dict) else {}
    adapter_path = adapter_check.get("path") if isinstance(adapter_check, dict) else None
    resolved_adapter_path = (
        resolve_cli_path(Path(adapter_path)) if isinstance(adapter_path, str) else None
    )
    adapter_inside_expected_root = bool(
        resolved_adapter_path
        and path_is_within(resolved_adapter_path, DEFAULT_ADAPTER_ROOT)
    )
    adapter_exists = bool(resolved_adapter_path and resolved_adapter_path.exists())

    if mode != "run":
        blockers.append("fine-tune report must be from --run mode")
    if training_attempted is not True:
        blockers.append("fine-tune report must show training_attempted=true")
    if training_succeeded is not True:
        blockers.append("fine-tune report must show training_succeeded=true")
    if isinstance(process, dict) and process.get("returncode") != 0:
        blockers.append("fine-tune process returncode must be 0")
    if blocked_reasons:
        blockers.append("fine-tune report still has blocked_reasons")
    if preflight_errors:
        blockers.append("fine-tune report still has preflight_errors")
    if isinstance(manifest_check, dict) and manifest_check.get("training_allowed") is not True:
        blockers.append("fine-tune manifest must have training_allowed=true")
    if isinstance(data_check, dict) and data_check.get("total_phi_findings", 0) != 0:
        blockers.append("fine-tune data check must have zero PHI findings")
    if not adapter_inside_expected_root:
        blockers.append("trained adapter output path must stay inside llm-distill/models/adapters")
    if not adapter_exists:
        blockers.append("trained adapter output path must exist")

    return {
        "ready": not blockers,
        "mode": mode,
        "training_attempted": training_attempted,
        "training_succeeded": training_succeeded,
        "process_returncode": process.get("returncode") if isinstance(process, dict) else None,
        "manifest_training_allowed": manifest_check.get("training_allowed")
        if isinstance(manifest_check, dict)
        else None,
        "data_total_phi_findings": data_check.get("total_phi_findings")
        if isinstance(data_check, dict)
        else None,
        "adapter_path": safe_report_path(resolved_adapter_path)
        if resolved_adapter_path
        else adapter_path,
        "adapter_path_exists": adapter_exists,
        "adapter_path_inside_expected_root": adapter_inside_expected_root,
        "expected_adapter_root": safe_report_path(DEFAULT_ADAPTER_ROOT),
        "blocked_reasons": blocked_reasons,
        "preflight_errors": preflight_errors,
        "errors": load_errors,
    }, blockers


def benchmark_parse_error_count(report: dict[str, Any]) -> int:
    count = 0
    for result in report.get("results", []):
        if not isinstance(result, dict):
            continue
        runtime = result.get("runtime", {})
        if isinstance(runtime, dict) and runtime.get("parse_error"):
            count += 1
    return count


def benchmark_gate_failures(report: dict[str, Any]) -> dict[str, int]:
    failures = {
        "json_valid": 0,
        "required_keys_present": 0,
        "human_review_required": 0,
        "draft_for_human_review": 0,
    }
    for result in report.get("results", []):
        if not isinstance(result, dict):
            continue
        score = result.get("score", {})
        if not isinstance(score, dict):
            continue
        for key in failures:
            if score.get(key) is not True:
                failures[key] += 1
    return failures


def check_benchmark_report(
    label: str,
    report: dict[str, Any] | None,
    load_errors: list[str],
    *,
    min_records: int,
    min_score_ratio: float | None,
) -> tuple[dict[str, Any], list[str]]:
    blockers = list(load_errors)
    summary = report.get("summary") if report else None
    ratio = score_ratio(summary)
    endpoint_available = summary.get("endpoint_available") if isinstance(summary, dict) else None
    dry_run = summary.get("dry_run") if isinstance(summary, dict) else None
    endpoint_error_count = summary.get("endpoint_error_count") if isinstance(summary, dict) else None
    record_count = summary.get("record_count") if isinstance(summary, dict) else None
    parse_errors = benchmark_parse_error_count(report) if report else None
    gate_failures = benchmark_gate_failures(report) if report else {}

    if not isinstance(summary, dict):
        blockers.append(f"{label} benchmark report is missing summary")
    else:
        if endpoint_available is not True:
            blockers.append(f"{label} benchmark endpoint_available must be true")
        if dry_run is True:
            blockers.append(f"{label} benchmark must not be dry_run")
        if endpoint_error_count not in {0, None}:
            blockers.append(f"{label} benchmark endpoint_error_count must be 0")
        if not isinstance(record_count, int) or record_count < min_records:
            blockers.append(f"{label} benchmark must cover at least {min_records} records")
        if min_score_ratio is not None and (ratio is None or ratio < min_score_ratio):
            blockers.append(f"{label} benchmark score_ratio must be >= {min_score_ratio}")
    if parse_errors:
        blockers.append(f"{label} benchmark has parse errors")
    for key, count in gate_failures.items():
        if count:
            blockers.append(f"{label} benchmark failed {key} on {count} record(s)")

    return {
        "ready": not blockers,
        "model": report.get("model") if report else None,
        "endpoint_available": endpoint_available,
        "dry_run": dry_run,
        "endpoint_error_count": endpoint_error_count,
        "record_count": record_count,
        "score_ratio": ratio,
        "parse_error_count": parse_errors,
        "gate_failures": gate_failures,
        "errors": load_errors,
    }, blockers


def compare_student_to_base(
    base_check: dict[str, Any],
    student_check: dict[str, Any],
    max_regression: float,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    base_ratio = base_check.get("score_ratio")
    student_ratio = student_check.get("score_ratio")
    delta = None
    if isinstance(base_ratio, int | float) and isinstance(student_ratio, int | float):
        delta = round(student_ratio - base_ratio, 4)
        if delta < -max_regression:
            blockers.append(
                f"student benchmark score regressed by more than {max_regression}"
            )
    else:
        blockers.append("base and student benchmark score ratios are required for comparison")
    return {
        "ready": not blockers,
        "base_score_ratio": base_ratio,
        "student_score_ratio": student_ratio,
        "score_delta": delta,
        "max_allowed_regression": max_regression,
    }, blockers


def build_report(
    *,
    workflow_report_path: Path,
    fine_tune_report_path: Path,
    base_benchmark_path: Path,
    student_benchmark_path: Path,
    workflow_min_score: float = 0.95,
    student_min_score: float = 0.95,
    min_benchmark_records: int = 10,
    max_score_regression: float = 0.02,
) -> dict[str, Any]:
    workflow_report_path = resolve_cli_path(workflow_report_path)
    fine_tune_report_path = resolve_cli_path(fine_tune_report_path)
    base_benchmark_path = resolve_cli_path(base_benchmark_path)
    student_benchmark_path = resolve_cli_path(student_benchmark_path)

    input_path_checks: dict[str, dict[str, Any]] = {}
    input_path_blockers: list[str] = []
    for label, path in {
        "workflow": workflow_report_path,
        "fine_tune": fine_tune_report_path,
        "base_benchmark": base_benchmark_path,
        "student_benchmark": student_benchmark_path,
    }.items():
        check, blockers = input_report_path_check(label, path)
        input_path_checks[label] = check
        add_blockers(input_path_blockers, blockers)

    workflow_report, workflow_load_errors = load_report(workflow_report_path)
    fine_tune_report, fine_tune_load_errors = load_report(fine_tune_report_path)
    base_report, base_load_errors = load_report(base_benchmark_path)
    student_report, student_load_errors = load_report(student_benchmark_path)

    blocked_reasons: list[str] = []
    add_blockers(blocked_reasons, input_path_blockers)
    workflow_check, workflow_blockers = check_workflow_report(
        workflow_report,
        workflow_load_errors,
        workflow_min_score,
    )
    fine_tune_check, fine_tune_blockers = check_fine_tune_report(
        fine_tune_report,
        fine_tune_load_errors,
    )
    base_check, base_blockers = check_benchmark_report(
        "base",
        base_report,
        base_load_errors,
        min_records=min_benchmark_records,
        min_score_ratio=None,
    )
    student_check, student_blockers = check_benchmark_report(
        "student",
        student_report,
        student_load_errors,
        min_records=min_benchmark_records,
        min_score_ratio=student_min_score,
    )
    comparison_check, comparison_blockers = compare_student_to_base(
        base_check,
        student_check,
        max_score_regression,
    )

    add_blockers(blocked_reasons, workflow_blockers)
    add_blockers(blocked_reasons, fine_tune_blockers)
    add_blockers(blocked_reasons, base_blockers)
    add_blockers(blocked_reasons, student_blockers)
    add_blockers(blocked_reasons, comparison_blockers)

    phi_scans = {
        "workflow_report": phi_scan_report(workflow_report_path),
        "fine_tune_report": phi_scan_report(fine_tune_report_path),
        "base_benchmark": phi_scan_report(base_benchmark_path),
        "student_benchmark": phi_scan_report(student_benchmark_path),
    }
    for scan_name, scan in phi_scans.items():
        if scan["finding_count"]:
            blocked_reasons.append(f"{scan_name} contains PHI/PII scan findings")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_ready": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "thresholds": {
            "workflow_min_score": workflow_min_score,
            "student_min_score": student_min_score,
            "min_benchmark_records": min_benchmark_records,
            "max_score_regression": max_score_regression,
        },
        "inputs": {
            "workflow_report": safe_report_path(workflow_report_path),
            "fine_tune_report": safe_report_path(fine_tune_report_path),
            "base_benchmark": safe_report_path(base_benchmark_path),
            "student_benchmark": safe_report_path(student_benchmark_path),
        },
        "checks": {
            "input_paths": input_path_checks,
            "workflow_baseline": workflow_check,
            "fine_tune_run": fine_tune_check,
            "base_benchmark": base_check,
            "student_benchmark": student_check,
            "student_vs_base": comparison_check,
            "phi_scans": phi_scans,
        },
        "notes": [
            "This gate does not train, quantize, download models, call endpoints, or inspect adapter weights.",
            "A release-ready student requires reviewed-label training evidence and live base/student MLX benchmark reports.",
            "Report inputs must stay under llm-distill/evals/reports and the adapter path must stay under llm-distill/models/adapters before promotion.",
            "Use this gate before any adapter promotion, quantization, or application default-model change.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-report", type=Path, default=DEFAULT_WORKFLOW_REPORT)
    parser.add_argument("--fine-tune-report", type=Path, default=DEFAULT_FINE_TUNE_REPORT)
    parser.add_argument("--base-benchmark", type=Path, default=DEFAULT_BASE_BENCHMARK)
    parser.add_argument("--student-benchmark", type=Path, default=DEFAULT_STUDENT_BENCHMARK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workflow-min-score", type=float, default=0.95)
    parser.add_argument("--student-min-score", type=float, default=0.95)
    parser.add_argument("--min-benchmark-records", type=int, default=10)
    parser.add_argument("--max-score-regression", type=float, default=0.02)
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return exit code 2 when the student model is not promotable.",
    )
    args = parser.parse_args()

    payload = build_report(
        workflow_report_path=args.workflow_report,
        fine_tune_report_path=args.fine_tune_report,
        base_benchmark_path=args.base_benchmark,
        student_benchmark_path=args.student_benchmark,
        workflow_min_score=args.workflow_min_score,
        student_min_score=args.student_min_score,
        min_benchmark_records=args.min_benchmark_records,
        max_score_regression=args.max_score_regression,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote student acceptance report to {args.output}")
    if payload["blocked_reasons"] and args.fail_on_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
