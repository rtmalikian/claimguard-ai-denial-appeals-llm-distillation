#!/usr/bin/env python3
"""Render a private MLX launchd plist copy without installing it."""

from __future__ import annotations

import argparse
import json
import plistlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = (
    REPO_ROOT
    / "llm-distill"
    / "data"
    / "runtime_supervision"
    / "claimguard.mlx-student.launchd.template.plist"
)
DEFAULT_OUTPUT = Path("/private/tmp/claimguard.mlx-student.launchd.plist")
DEFAULT_ADAPTER_RELATIVE = (
    "llm-distill/models/adapters/claimguard-qwen3-4b-lora-reviewed"
)
RUNTIME_PROFILE_KEY = "CLAIMGUARD_RUNTIME_PROFILE"
RUNTIME_PROFILE_VALUE = "student_denial_workflow_local_only"
ALLOWED_ENVIRONMENT_KEYS = {RUNTIME_PROFILE_KEY}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "proxy",
    "secret",
    "token",
}


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    template_path: Path
    output_path: Path
    deployment_root: Path
    host: str
    port: int
    model: str
    max_tokens: int
    dry_run: bool = False


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _argument_value(arguments: list[str], flag: str) -> str | None:
    try:
        index = arguments.index(flag) + 1
    except ValueError:
        return None
    return arguments[index] if index < len(arguments) else None


def _set_argument_value(arguments: list[str], flag: str, value: str) -> None:
    try:
        index = arguments.index(flag) + 1
    except ValueError as exc:
        raise RenderError(f"template missing required argument: {flag}") from exc
    if index >= len(arguments):
        raise RenderError(f"template missing value for required argument: {flag}")
    arguments[index] = value


def _safe_environment() -> dict[str, str]:
    return {RUNTIME_PROFILE_KEY: RUNTIME_PROFILE_VALUE}


def _validate_environment(environment: dict[str, Any]) -> None:
    keys = {str(key) for key in environment}
    unexpected = keys - ALLOWED_ENVIRONMENT_KEYS
    forbidden = {
        key
        for key in keys
        if any(fragment in key.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS)
    }
    if unexpected:
        raise RenderError("unexpected environment keys would be written")
    if forbidden:
        raise RenderError("secret-like environment keys would be written")
    if environment.get(RUNTIME_PROFILE_KEY) != RUNTIME_PROFILE_VALUE:
        raise RenderError("runtime profile must remain student_denial_workflow_local_only")


def render_private_copy(config: RenderConfig) -> dict[str, Any]:
    template_path = config.template_path.resolve()
    output_path = config.output_path.resolve()
    deployment_root = config.deployment_root.resolve()
    if not template_path.exists():
        raise RenderError("launchd template is missing")
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")
    if config.host not in LOOPBACK_HOSTS:
        raise RenderError("launchd host must remain loopback-only")
    if config.port <= 0 or config.port > 65535:
        raise RenderError("launchd port must be between 1 and 65535")
    if config.max_tokens <= 0:
        raise RenderError("max tokens must be positive")

    try:
        plist = plistlib.loads(template_path.read_bytes())
    except Exception as exc:  # plistlib raises several parse errors.
        raise RenderError("launchd template is not a valid plist") from exc
    if not isinstance(plist, dict):
        raise RenderError("launchd template must be a plist dictionary")

    arguments = plist.get("ProgramArguments")
    if not isinstance(arguments, list):
        raise RenderError("launchd template ProgramArguments must be a list")
    arguments = [str(item) for item in arguments]
    if any(item.endswith(("/sh", "/bash", "zsh")) for item in arguments):
        raise RenderError("launchd template must not use a shell")

    server_path = deployment_root / ".venv-mlx" / "bin" / "mlx_lm.server"
    adapter_path = deployment_root / DEFAULT_ADAPTER_RELATIVE
    arguments[0] = str(server_path)
    _set_argument_value(arguments, "--model", config.model)
    _set_argument_value(arguments, "--adapter-path", str(adapter_path))
    _set_argument_value(arguments, "--host", config.host)
    _set_argument_value(arguments, "--port", str(config.port))
    _set_argument_value(arguments, "--max-tokens", str(config.max_tokens))

    environment = _safe_environment()
    _validate_environment(environment)
    plist["ProgramArguments"] = arguments
    plist["WorkingDirectory"] = str(deployment_root)
    plist["EnvironmentVariables"] = environment

    host = _argument_value(arguments, "--host")
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "template_exists": True,
        "output_path_in_source_control": False,
        "deployment_root_included": False,
        "program_argument_count": len(arguments),
        "runs_mlx_lm_server": arguments[0].endswith("mlx_lm.server"),
        "uses_shell": False,
        "uses_adapter_path": "--adapter-path" in arguments,
        "binds_loopback_only": host in LOOPBACK_HOSTS,
        "environment_variable_count": len(environment),
        "approved_environment_variable_count": len(ALLOWED_ENVIRONMENT_KEYS),
        "raw_environment_values_included": False,
        "raw_paths_in_summary": False,
        "values_redacted": True,
    }
    if not summary["runs_mlx_lm_server"]:
        raise RenderError("rendered plist must run mlx_lm.server")
    if not summary["uses_adapter_path"]:
        raise RenderError("rendered plist must include --adapter-path")
    if not summary["binds_loopback_only"]:
        raise RenderError("rendered plist must bind to loopback only")

    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(plistlib.dumps(plist))
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        template_path=args.template,
        output_path=args.output,
        deployment_root=args.deployment_root,
        host=args.host,
        port=args.port,
        model=args.model,
        max_tokens=args.max_tokens,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--deployment-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-MLX-4bit")
    parser.add_argument("--max-tokens", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_copy(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
