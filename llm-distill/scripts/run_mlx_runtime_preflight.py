#!/usr/bin/env python3
"""Check local MLX-LM runtime readiness for ClaimGuard distillation."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "mlx_runtime_preflight_report.json"
)
DEFAULT_BASE_URL = "http://localhost:8080/v1"
REQUIRED_COMMANDS = ("mlx_lm.server", "mlx_lm.lora", "mlx_lm.generate")


def package_status() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("mlx-lm")
    except importlib.metadata.PackageNotFoundError:
        return {
            "installed": False,
            "distribution": "mlx-lm",
            "version": None,
            "error": "mlx-lm package is not installed in the active Python environment",
        }
    return {
        "installed": True,
        "distribution": "mlx-lm",
        "version": version,
        "error": None,
    }


def command_status(command: str, timeout: float) -> dict[str, Any]:
    path = shutil.which(command)
    if not path:
        return {
            "command": command,
            "available": False,
            "path": None,
            "help_returncode": None,
            "help_stdout_tail": "",
            "help_stderr_tail": "",
            "error": f"{command} not found on PATH",
        }
    try:
        result = subprocess.run(
            [path, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "available": True,
            "path": path,
            "help_returncode": None,
            "help_stdout_tail": "",
            "help_stderr_tail": "",
            "error": f"{command} --help timed out after {timeout} seconds",
        }
    return {
        "command": command,
        "available": True,
        "path": path,
        "help_returncode": result.returncode,
        "help_stdout_tail": tail_text(result.stdout),
        "help_stderr_tail": tail_text(result.stderr),
        "error": None if result.returncode == 0 else f"{command} --help returned {result.returncode}",
    }


def tail_text(value: str, limit: int = 1200) -> str:
    return value[-limit:] if len(value) > limit else value


def server_status(base_url: str, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/models"
    request = urllib.request.Request(url, method="GET")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "base_url": base_url,
            "models_url": url,
            "available": False,
            "status_code": exc.code,
            "duration_seconds": round(time.perf_counter() - start, 4),
            "body_summary": safe_json_summary(body),
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:
        return {
            "base_url": base_url,
            "models_url": url,
            "available": False,
            "status_code": None,
            "duration_seconds": round(time.perf_counter() - start, 4),
            "body_summary": None,
            "error": str(exc),
        }
    return {
        "base_url": base_url,
        "models_url": url,
        "available": 200 <= status_code < 300,
        "status_code": status_code,
        "duration_seconds": round(time.perf_counter() - start, 4),
        "body_summary": safe_json_summary(body),
        "error": None,
    }


def safe_json_summary(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"json_valid": False, "raw_body_prefix": text[:500]}
    if isinstance(payload, dict):
        data = payload.get("data")
        return {
            "json_valid": True,
            "keys": sorted(payload.keys()),
            "model_count": len(data) if isinstance(data, list) else None,
            "model_ids": [
                item.get("id")
                for item in data[:5]
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
            if isinstance(data, list)
            else [],
        }
    return {"json_valid": True, "type": type(payload).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-MLX-4bit")
    parser.add_argument("--fallback-model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--command-timeout", type=float, default=10.0)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    package = package_status()
    commands = {command: command_status(command, args.command_timeout) for command in REQUIRED_COMMANDS}
    server = server_status(args.base_url, args.timeout)
    host = {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }

    blockers: list[str] = []
    warnings: list[str] = []
    if host["system"] != "Darwin":
        blockers.append("MLX runtime target should be macOS/Darwin for the primary Apple Silicon path")
    if host["machine"] != "arm64":
        blockers.append("MLX runtime target should be Apple Silicon arm64")
    if not package["installed"]:
        blockers.append(package["error"])
    for command, status in commands.items():
        if not status["available"]:
            blockers.append(status["error"])
        elif status["error"]:
            warnings.append(status["error"])
    if not server["available"]:
        blockers.append(f"mlx_lm.server is not reachable at {args.base_url}: {server['error']}")

    ready = not blockers
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": ready,
        "blocked_reasons": blockers,
        "warnings": warnings,
        "base_url": args.base_url,
        "model": args.model,
        "fallback_model": args.fallback_model,
        "host": host,
        "checks": {
            "python_package": package,
            "commands": commands,
            "server": server,
        },
        "next_actions": [
            "Install MLX-LM in a local virtual environment if the package or CLI commands are missing.",
            "Start mlx_lm.server with the primary model before running live base benchmarks.",
            "Install the MLX-LM training extras and verify mlx_lm.lora before reviewed-label LoRA training.",
            "Rerun the full 10-record base benchmark only after this runtime preflight is ready.",
        ],
        "notes": [
            "This preflight does not install packages, download models, start servers, call teacher endpoints, train, quantize, or write adapter weights.",
            "A reachable /v1/models endpoint is runtime availability evidence, not model-quality or training evidence.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote MLX runtime preflight report to {args.output}")
    if blockers and args.fail_on_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
