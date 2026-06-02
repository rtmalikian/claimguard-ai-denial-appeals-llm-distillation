#!/usr/bin/env python3
"""Bootstrap local MLX-LM tooling and refresh ClaimGuard runtime evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from report_output_sanitizer import write_source_controlled_report_json


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
REPORT_DIR = DISTILL_DIR / "evals" / "reports"
DEFAULT_VENV = REPO_ROOT / ".venv-mlx"
DEFAULT_RUNTIME_REPORT = REPORT_DIR / "mlx_runtime_preflight_report.json"
DEFAULT_FINE_TUNE_REPORT = REPORT_DIR / "mlx_finetune_preflight_report.json"
DEFAULT_AUDIT_REPORT = REPORT_DIR / "distillation_readiness_audit_report.json"
DEFAULT_BOOTSTRAP_REPORT = REPORT_DIR / "mlx_runtime_bootstrap_report.json"


def tail_text(value: str, limit: int = 4000) -> str:
    return value if len(value) <= limit else value[-limit:]


def run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": tail_text(exc.stdout or ""),
            "stderr_tail": tail_text(exc.stderr or ""),
        }
    return {
        "command": command,
        "returncode": result.returncode,
        "timed_out": False,
        "timeout_seconds": timeout_seconds,
        "stdout_tail": tail_text(result.stdout),
        "stderr_tail": tail_text(result.stderr),
    }


def venv_python(venv_path: Path) -> Path:
    return venv_path / "bin" / "python"


def venv_bin(venv_path: Path) -> Path:
    return venv_path / "bin"


def venv_lora(venv_path: Path) -> Path:
    return venv_bin(venv_path) / "mlx_lm.lora"


def env_with_venv(venv_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    current_path = env.get("PATH", "")
    env["PATH"] = f"{venv_bin(venv_path)}{os.pathsep}{current_path}"
    return env


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def summarize_runtime(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    checks = report.get("checks", {})
    commands = checks.get("commands", {}) if isinstance(checks, dict) else {}
    package = checks.get("python_package", {}) if isinstance(checks, dict) else {}
    server = checks.get("server", {}) if isinstance(checks, dict) else {}
    return {
        "ready": report.get("ready"),
        "blocked_reasons": report.get("blocked_reasons"),
        "package_installed": package.get("installed") if isinstance(package, dict) else None,
        "package_version": package.get("version") if isinstance(package, dict) else None,
        "server_available": server.get("available") if isinstance(server, dict) else None,
        "commands_available": {
            command: status.get("available")
            for command, status in commands.items()
            if isinstance(status, dict)
        }
        if isinstance(commands, dict)
        else {},
    }


def summarize_fine_tune(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    checks = report.get("checks", {})
    lora = checks.get("mlx_lm_lora", {}) if isinstance(checks, dict) else {}
    manifest = checks.get("manifest", {}) if isinstance(checks, dict) else {}
    data = checks.get("data", {}) if isinstance(checks, dict) else {}
    return {
        "ready": report.get("ready"),
        "mode": report.get("mode"),
        "blocked_reasons": report.get("blocked_reasons"),
        "mlx_lm_lora_available": lora.get("available") if isinstance(lora, dict) else None,
        "manifest_training_allowed": manifest.get("training_allowed") if isinstance(manifest, dict) else None,
        "data_ready": data.get("ready") if isinstance(data, dict) else None,
    }


def summarize_audit(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    summary = report.get("summary", {})
    return {
        "distillation_ready": report.get("distillation_ready"),
        "release_ready": report.get("release_ready"),
        "requirement_count": summary.get("requirement_count") if isinstance(summary, dict) else None,
        "ready_count": summary.get("ready_count") if isinstance(summary, dict) else None,
        "warning_count": summary.get("warning_count") if isinstance(summary, dict) else None,
        "blocked_count": summary.get("blocked_count") if isinstance(summary, dict) else None,
        "blocked_requirement_ids": summary.get("blocked_requirement_ids")
        if isinstance(summary, dict)
        else None,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_source_controlled_report_json(path, payload, REPO_ROOT)


def install_commands(args: argparse.Namespace, python_path: Path) -> list[dict[str, Any]]:
    if args.skip_install:
        return []

    uv = shutil.which("uv")
    if uv:
        return [
            run_command([uv, "venv", "--python", args.python, str(args.venv_path)]),
            run_command([uv, "pip", "install", "--python", str(python_path), args.package]),
        ]

    return [
        run_command([args.python, "-m", "venv", str(args.venv_path)]),
        run_command([str(python_path), "-m", "ensurepip", "--upgrade"]),
        run_command([str(python_path), "-m", "pip", "install", "--upgrade", "pip", args.package]),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venv-path", type=Path, default=DEFAULT_VENV)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--package", default="mlx-lm")
    parser.add_argument("--runtime-report", type=Path, default=DEFAULT_RUNTIME_REPORT)
    parser.add_argument("--fine-tune-report", type=Path, default=DEFAULT_FINE_TUNE_REPORT)
    parser.add_argument("--audit-report", type=Path, default=DEFAULT_AUDIT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_BOOTSTRAP_REPORT)
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-fine-tune-preflight", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    args.venv_path = args.venv_path.resolve()
    python_path = venv_python(args.venv_path)
    command_results: list[dict[str, Any]] = []
    blockers: list[str] = []

    command_results.extend(install_commands(args, python_path))
    failed_install = [result for result in command_results if result.get("returncode") not in (0, None)]
    timed_out_install = [result for result in command_results if result.get("timed_out")]
    if failed_install:
        blockers.append("one or more MLX-LM install commands returned non-zero")
    if timed_out_install:
        blockers.append("one or more MLX-LM install commands timed out")
    if not python_path.exists():
        blockers.append(f"virtualenv python was not created: {python_path}")

    env = env_with_venv(args.venv_path)
    if python_path.exists():
        command_results.append(
            run_command(
                [
                    str(python_path),
                    str(SCRIPT_DIR / "run_mlx_runtime_preflight.py"),
                    "--output",
                    str(args.runtime_report),
                ],
                env=env,
                timeout_seconds=args.timeout_seconds,
            )
        )
        if not args.skip_fine_tune_preflight:
            command_results.append(
                run_command(
                    [
                        str(python_path),
                        str(SCRIPT_DIR / "run_mlx_finetune.py"),
                        "--output",
                        str(args.fine_tune_report),
                        "--mlx-lora-executable",
                        str(venv_lora(args.venv_path)),
                    ],
                    env=env,
                    timeout_seconds=args.timeout_seconds,
                )
            )

    command_results.append(
        run_command(
            [
                sys.executable,
                str(SCRIPT_DIR / "run_distillation_readiness_audit.py"),
                "--output",
                str(args.audit_report),
            ],
            timeout_seconds=args.timeout_seconds,
        )
    )
    for result in command_results:
        if result.get("returncode") not in (0, None):
            blockers.append(f"command returned non-zero: {' '.join(result['command'])}")
        if result.get("timed_out"):
            blockers.append(f"command timed out: {' '.join(result['command'])}")

    runtime_report = load_json(args.runtime_report)
    fine_tune_report = load_json(args.fine_tune_report)
    audit_report = load_json(args.audit_report)
    runtime_summary = summarize_runtime(runtime_report)
    fine_tune_summary = summarize_fine_tune(fine_tune_report)
    audit_summary = summarize_audit(audit_report)

    if runtime_summary.get("package_installed") is not True:
        blockers.append("runtime preflight still does not see the mlx-lm package")
    commands_available = runtime_summary.get("commands_available")
    if not isinstance(commands_available, dict) or not all(commands_available.values()):
        blockers.append("runtime preflight still does not see all required MLX-LM CLI commands")
    if fine_tune_summary and fine_tune_summary.get("mlx_lm_lora_available") is not True:
        blockers.append("fine-tune preflight still does not see mlx_lm.lora")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_ready": not blockers,
        "blocked_reasons": sorted(set(blockers)),
        "venv_path": str(args.venv_path),
        "venv_python": str(python_path),
        "package": args.package,
        "runtime_report": str(args.runtime_report),
        "fine_tune_report": str(args.fine_tune_report),
        "audit_report": str(args.audit_report),
        "command_results": command_results,
        "runtime_summary": runtime_summary,
        "fine_tune_summary": fine_tune_summary,
        "audit_summary": audit_summary,
        "notes": [
            "This bootstrap installs MLX-LM tooling into a local virtual environment only.",
            "It does not download model weights, start mlx_lm.server, call teacher endpoints, run LoRA training, benchmark, quantize, or write adapter weights.",
            "A bootstrap_ready=true report proves local package and CLI tooling only; the model server and reviewed-label training gates must still pass separately.",
        ],
        "next_actions": [
            "Start mlx_lm.server from the local virtual environment before live benchmarks.",
            "Complete large-teacher or human review approvals before reviewed SFT export and LoRA training.",
            "Rerun this bootstrap or the individual preflight reports after changing the local MLX environment.",
        ],
    }
    write_json(args.output, payload)
    print(f"wrote MLX runtime bootstrap report to {args.output}")
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
