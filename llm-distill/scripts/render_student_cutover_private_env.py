#!/usr/bin/env python3
"""Render a private student cutover env file without printing values."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-student-cutover.private.env")
DEFAULT_APPROVAL_REFERENCE_ENV = "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE"
RUNTIME_PROFILE_KEY = "CLAIMGUARD_RUNTIME_PROFILE"
RUNTIME_PROFILE_VALUE = "student_denial_workflow_local_only"
REQUIRED_ATTESTATIONS = {
    "raphael_approval_attested": "Raphael approval attestation is required",
    "runtime_supervised_attested": "supervised runtime attestation is required",
    "distillation_release_attested": "distillation release attestation is required",
    "rollback_reviewed": "rollback review attestation is required",
}
ALLOWED_ENV_KEYS = {
    "CLAIMGUARD_STUDENT_USE_BY_DEFAULT",
    "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH",
    "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
    "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE",
    "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED",
    "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA",
    RUNTIME_PROFILE_KEY,
}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}
APPROVAL_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    approved_cutover: bool = False
    enable_auto_launch: bool = False
    approval_reference_env: str = DEFAULT_APPROVAL_REFERENCE_ENV
    raphael_approval_attested: bool = False
    runtime_supervised_attested: bool = False
    distillation_release_attested: bool = False
    rollback_reviewed: bool = False
    dry_run: bool = False


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _validate_env_key(name: str) -> None:
    if name not in ALLOWED_ENV_KEYS and not ENV_KEY_RE.match(name):
        raise RenderError("unexpected environment key requested")
    if any(fragment in name.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS):
        raise RenderError("secret-like environment key requested")


def _validate_approval_reference(value: str) -> None:
    if not value:
        raise RenderError("approval reference env var is required for approved cutover")
    if "\n" in value or "\r" in value or "\t" in value or " " in value:
        raise RenderError("approval reference must not contain whitespace or control characters")
    if "#" in value:
        raise RenderError("approval reference must not contain comment delimiters")
    if not APPROVAL_REFERENCE_RE.match(value):
        raise RenderError("approval reference contains unsupported characters")


def _load_approval_reference(config: RenderConfig) -> str:
    _validate_env_key(config.approval_reference_env)
    value = os.environ.get(config.approval_reference_env, "").strip()
    _validate_approval_reference(value)
    return value


def _validate_approved_cutover_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved cutover requires explicit attestations")


def _build_environment(config: RenderConfig) -> dict[str, str]:
    if config.enable_auto_launch and not config.approved_cutover:
        raise RenderError("student auto-launch can only be rendered for approved cutover")

    if config.approved_cutover:
        _validate_approved_cutover_attestations(config)
        approval_reference = _load_approval_reference(config)
        env = {
            "CLAIMGUARD_STUDENT_USE_BY_DEFAULT": "true",
            "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH": _bool_text(config.enable_auto_launch),
            "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED": "true",
            "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE": approval_reference,
            "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED": "true",
            "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA": "false",
            RUNTIME_PROFILE_KEY: RUNTIME_PROFILE_VALUE,
        }
    else:
        env = {
            "CLAIMGUARD_STUDENT_USE_BY_DEFAULT": "false",
            "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH": "false",
            "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED": "false",
            "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE": "",
            "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED": "false",
            "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA": "true",
            RUNTIME_PROFILE_KEY: RUNTIME_PROFILE_VALUE,
        }
    unexpected = set(env) - ALLOWED_ENV_KEYS
    if unexpected:
        raise RenderError("unexpected environment keys would be written")
    for key in env:
        _validate_env_key(key)
    if env[RUNTIME_PROFILE_KEY] != RUNTIME_PROFILE_VALUE:
        raise RenderError("runtime profile must remain student_denial_workflow_local_only")
    return env


def _env_file_text(env: dict[str, str]) -> str:
    lines = [
        "# ClaimGuard AI private student cutover environment.",
        "# Do not commit this file. Store it outside source control.",
    ]
    lines.extend(f"{key}={value}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def render_private_env(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    env = _build_environment(config)
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_cutover_requested": config.approved_cutover,
        "student_use_by_default": env["CLAIMGUARD_STUDENT_USE_BY_DEFAULT"] == "true",
        "student_auto_launch_requested": (
            env["CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH"] == "true"
        ),
        "cutover_approved": (
            env["CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED"] == "true"
        ),
        "approval_reference_configured": bool(
            env["CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE"]
        ),
        "runtime_supervised": env["CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED"] == "true",
        "rollback_to_nvidia": (
            env["CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA"] == "true"
        ),
        "runtime_profile_configured": env[RUNTIME_PROFILE_KEY] == RUNTIME_PROFILE_VALUE,
        "environment_variable_count": len(env),
        "output_path_in_source_control": False,
        "raw_env_values_included": False,
        "approval_reference_value_included": False,
        "raw_paths_in_summary": False,
        "values_redacted": True,
        "file_mode": "0600" if not config.dry_run else None,
    }

    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_env_file_text(env))
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        output_path=args.output,
        approved_cutover=args.approved_cutover,
        enable_auto_launch=args.enable_auto_launch,
        approval_reference_env=args.approval_reference_env,
        raphael_approval_attested=args.raphael_approval_attested,
        runtime_supervised_attested=args.runtime_supervised_attested,
        distillation_release_attested=args.distillation_release_attested,
        rollback_reviewed=args.rollback_reviewed,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-cutover", action="store_true")
    parser.add_argument("--enable-auto-launch", action="store_true")
    parser.add_argument(
        "--approval-reference-env",
        default=DEFAULT_APPROVAL_REFERENCE_ENV,
        help="Environment variable containing the private approval reference value.",
    )
    parser.add_argument("--raphael-approval-attested", action="store_true")
    parser.add_argument("--runtime-supervised-attested", action="store_true")
    parser.add_argument("--distillation-release-attested", action="store_true")
    parser.add_argument("--rollback-reviewed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_env(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
