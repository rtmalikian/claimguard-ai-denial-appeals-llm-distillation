#!/usr/bin/env python3
"""Render private MLX runtime supervisor evidence without printing values."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-mlx-runtime-supervisor.private.evidence.json")
DEFAULT_PLIST_PATH = (
    "llm-distill/data/runtime_supervision/claimguard.mlx-student.launchd.template.plist"
)
DEFAULT_PRIVATE_PLIST_PATH_ENV = "MLX_RUNTIME_SUPERVISOR_PRIVATE_PLIST_PATH"
DEFAULT_PRIVATE_SUMMARY_PATH_ENV = "MLX_RUNTIME_SUPERVISOR_PRIVATE_SUMMARY_PATH"
DEFAULT_OWNER_REFERENCE_ENV = "MLX_RUNTIME_SUPERVISOR_OWNER_REFERENCE"
DEFAULT_PREFLIGHT_REFERENCE_ENV = "MLX_RUNTIME_SUPERVISOR_PREFLIGHT_REFERENCE"
DEFAULT_HEALTH_REFERENCE_ENV = "MLX_RUNTIME_SUPERVISOR_HEALTH_REFERENCE"
DEFAULT_RESTART_REFERENCE_ENV = "MLX_RUNTIME_SUPERVISOR_RESTART_REFERENCE"
DEFAULT_ROLLBACK_REFERENCE_ENV = "MLX_RUNTIME_SUPERVISOR_ROLLBACK_REFERENCE"
DEFAULT_PRIVATE_EVIDENCE_RENDERER_PATH = (
    "llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py"
)
RUNTIME_PROFILE_KEY = "CLAIMGUARD_RUNTIME_PROFILE"
RUNTIME_PROFILE_VALUE = "student_denial_workflow_local_only"
REQUIRED_PLIST_ENVIRONMENT = {
    RUNTIME_PROFILE_KEY: RUNTIME_PROFILE_VALUE,
}
ALLOWED_PLIST_ENVIRONMENT_KEYS = set(REQUIRED_PLIST_ENVIRONMENT)
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
REQUIRED_ATTESTATIONS = {
    "runtime_owner_attested": "runtime owner attestation is required",
    "private_launchd_copy_attested": "private launchd copy attestation is required",
    "restart_policy_reviewed": "restart policy review attestation is required",
    "health_check_reviewed": "health check review attestation is required",
    "manual_start_command_reviewed": "manual start command review is required",
    "rollback_to_nvidia_reviewed": "rollback-to-NVIDIA review is required",
    "environment_file_excluded_attested": (
        "environment file exclusion attestation is required"
    ),
    "mlx_runtime_preflight_ready": "MLX runtime preflight attestation is required",
    "student_status_endpoint_checked": (
        "student status endpoint attestation is required"
    ),
    "student_runtime_health_ok": "student runtime health attestation is required",
    "supervisor_loaded_in_user_session": (
        "supervisor loaded-in-session attestation is required"
    ),
    "supervisor_restart_test_passed": (
        "supervisor restart-test attestation is required"
    ),
    "no_raw_values_attested": "no raw values attestation is required",
}
ALLOWED_ENV_KEYS = {
    DEFAULT_PRIVATE_PLIST_PATH_ENV,
    DEFAULT_PRIVATE_SUMMARY_PATH_ENV,
    DEFAULT_OWNER_REFERENCE_ENV,
    DEFAULT_PREFLIGHT_REFERENCE_ENV,
    DEFAULT_HEALTH_REFERENCE_ENV,
    DEFAULT_RESTART_REFERENCE_ENV,
    DEFAULT_ROLLBACK_REFERENCE_ENV,
}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "proxy",
    "raw",
    "secret",
    "token",
}
SAFE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS = {
    "runtime_owner_attested",
    "private_launchd_copy_attested",
    "restart_policy_reviewed",
    "health_check_reviewed",
    "manual_start_command_reviewed",
    "rollback_to_nvidia_reviewed",
    "environment_file_excluded_attested",
    "mlx_runtime_preflight_ready",
    "student_status_endpoint_checked",
    "student_runtime_health_ok",
    "supervisor_loaded_in_user_session",
    "supervisor_restart_test_passed",
    "private_plist_reviewed",
    "private_plist_loopback_reviewed",
    "private_plist_runtime_profile_reviewed",
    "private_plist_environment_reviewed",
    "private_references_configured",
    "runtime_scope_reviewed",
    "rollback_path_reviewed",
    "no_raw_values_attested",
    "values_redacted",
}
REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS = {
    "private_summary_path_value_included",
    "private_plist_path_value_included",
    "owner_reference_value_included",
    "preflight_reference_value_included",
    "health_reference_value_included",
    "restart_reference_value_included",
    "rollback_reference_value_included",
    "raw_private_values_included",
    "raw_runtime_output_included",
    "endpoint_output_included",
    "model_output_included",
    "approval_reference_value_included",
    "runtime_owner_value_included",
    "credential_values_included",
    "phi_or_secret_values_included",
    "production_document_content_included",
}
REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS = {
    "private_reference_count",
    "private_plist_count",
    "launchd_program_argument_count",
    "launchd_environment_variable_count",
    "required_environment_variable_count",
    "operator_control_count",
    "runtime_validation_count",
}
ALLOWED_PRIVATE_SUMMARY_KEYS = (
    REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS
    | REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS
    | REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS
)
EXPECTED_OPERATOR_CONTROL_COUNT = 7
EXPECTED_RUNTIME_VALIDATION_COUNT = 5


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    approved_supervisor: bool = False
    private_plist_path_env: str = DEFAULT_PRIVATE_PLIST_PATH_ENV
    private_summary_path_env: str = DEFAULT_PRIVATE_SUMMARY_PATH_ENV
    owner_reference_env: str = DEFAULT_OWNER_REFERENCE_ENV
    preflight_reference_env: str = DEFAULT_PREFLIGHT_REFERENCE_ENV
    health_reference_env: str = DEFAULT_HEALTH_REFERENCE_ENV
    restart_reference_env: str = DEFAULT_RESTART_REFERENCE_ENV
    rollback_reference_env: str = DEFAULT_ROLLBACK_REFERENCE_ENV
    runtime_owner_attested: bool = False
    private_launchd_copy_attested: bool = False
    restart_policy_reviewed: bool = False
    health_check_reviewed: bool = False
    manual_start_command_reviewed: bool = False
    rollback_to_nvidia_reviewed: bool = False
    environment_file_excluded_attested: bool = False
    mlx_runtime_preflight_ready: bool = False
    student_status_endpoint_checked: bool = False
    student_runtime_health_ok: bool = False
    supervisor_loaded_in_user_session: bool = False
    supervisor_restart_test_passed: bool = False
    no_raw_values_attested: bool = False
    dry_run: bool = False


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _validate_env_key(name: str) -> None:
    if name not in ALLOWED_ENV_KEYS and not ENV_KEY_RE.match(name):
        raise RenderError("unexpected environment key requested")
    if any(fragment in name.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS):
        raise RenderError("secret-like environment key requested")


def _validate_private_reference(value: str, label: str) -> None:
    if not value:
        raise RenderError(f"{label} env var is required for approved supervisor")
    if "\n" in value or "\r" in value or "\t" in value or " " in value:
        raise RenderError(f"{label} must not contain whitespace or control characters")
    if "#" in value:
        raise RenderError(f"{label} must not contain comment delimiters")
    if not SAFE_REFERENCE_RE.match(value):
        raise RenderError(f"{label} contains unsupported characters")


def _load_private_reference(env_name: str, label: str) -> str:
    _validate_env_key(env_name)
    value = os.environ.get(env_name, "").strip()
    _validate_private_reference(value, label)
    return value


def _load_private_plist_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private plist path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private plist path contains unsupported characters")
    plist_path = Path(raw_path).expanduser().resolve()
    if path_is_within(plist_path, REPO_ROOT):
        raise RenderError("private plist path must be outside source control")
    if not plist_path.exists():
        raise RenderError("private plist path does not exist")
    if not plist_path.is_file():
        raise RenderError("private plist path must be a file")
    return plist_path


def _load_private_summary_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private supervisor summary path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private supervisor summary path contains unsupported characters")
    summary_path = Path(raw_path).expanduser().resolve()
    if path_is_within(summary_path, REPO_ROOT):
        raise RenderError("private supervisor summary path must be outside source control")
    if not summary_path.exists():
        raise RenderError("private supervisor summary path does not exist")
    if not summary_path.is_file():
        raise RenderError("private supervisor summary path must be a file")
    return summary_path


def _load_private_summary_payload(summary_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise RenderError("private supervisor summary must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise RenderError("private supervisor summary must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RenderError("private supervisor summary must be a JSON object")
    return payload


def _argument_value(arguments: list[str], flag: str) -> str | None:
    prefix = f"{flag}="
    for index, item in enumerate(arguments):
        if item == flag:
            value_index = index + 1
            return arguments[value_index] if value_index < len(arguments) else None
        if item.startswith(prefix):
            return item[len(prefix) :]
    return None


def _contains_argument(arguments: list[str], flag: str) -> bool:
    prefix = f"{flag}="
    return flag in arguments or any(item.startswith(prefix) for item in arguments)


def _validate_private_plist(plist_path: Path) -> dict[str, Any]:
    try:
        plist = plistlib.loads(plist_path.read_bytes())
    except Exception as exc:  # plistlib raises several parse errors.
        raise RenderError("private plist is not a valid plist") from exc
    if not isinstance(plist, dict):
        raise RenderError("private plist must be a plist dictionary")

    program_arguments = plist.get("ProgramArguments")
    if not isinstance(program_arguments, list):
        raise RenderError("private plist ProgramArguments must be a list")
    arguments = [str(item) for item in program_arguments]
    uses_shell = any(item.endswith(("/sh", "/bash", "zsh")) for item in arguments)
    runs_mlx_lm_server = any(item.endswith("mlx_lm.server") for item in arguments)
    uses_adapter_path = _contains_argument(arguments, "--adapter-path")
    host = _argument_value(arguments, "--host")
    port = _argument_value(arguments, "--port")
    if uses_shell:
        raise RenderError("private plist must not launch through a shell")
    if not runs_mlx_lm_server:
        raise RenderError("private plist must run mlx_lm.server")
    if not uses_adapter_path:
        raise RenderError("private plist must include --adapter-path")
    if host not in LOOPBACK_HOSTS:
        raise RenderError("private plist must bind to loopback host")
    if not port:
        raise RenderError("private plist must include --port")
    if not plist.get("WorkingDirectory"):
        raise RenderError("private plist must configure WorkingDirectory")
    if not plist.get("KeepAlive"):
        raise RenderError("private plist must configure KeepAlive")
    if not plist.get("StandardOutPath") or not plist.get("StandardErrorPath"):
        raise RenderError("private plist must configure log paths")

    environment = plist.get("EnvironmentVariables")
    if not isinstance(environment, dict):
        raise RenderError("private plist EnvironmentVariables must be a dictionary")
    environment_keys = {str(key) for key in environment}
    missing_environment_keys = sorted(
        set(REQUIRED_PLIST_ENVIRONMENT) - environment_keys
    )
    wrong_environment_keys = sorted(
        key
        for key, expected_value in REQUIRED_PLIST_ENVIRONMENT.items()
        if key in environment and environment.get(key) != expected_value
    )
    unexpected_environment_keys = sorted(
        environment_keys - ALLOWED_PLIST_ENVIRONMENT_KEYS
    )
    forbidden_environment_keys = sorted(
        key
        for key in environment_keys
        if any(fragment in key.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS)
    )
    if missing_environment_keys:
        raise RenderError("private plist missing required environment keys")
    if wrong_environment_keys:
        raise RenderError("private plist has unsafe runtime profile")
    if forbidden_environment_keys:
        raise RenderError("private plist has secret-like environment keys")
    if unexpected_environment_keys:
        raise RenderError("private plist has unapproved environment keys")

    return {
        "program_argument_count": len(arguments),
        "environment_variable_count": len(environment_keys),
        "required_environment_variable_count": len(REQUIRED_PLIST_ENVIRONMENT),
        "runs_mlx_lm_server": runs_mlx_lm_server,
        "uses_adapter_path": uses_adapter_path,
        "uses_loopback_host": True,
        "port_configured": True,
        "working_directory_configured": True,
        "keepalive_configured": True,
        "log_paths_configured": True,
        "runtime_profile_ok": True,
        "unexpected_environment_key_count": len(unexpected_environment_keys),
        "forbidden_environment_key_count": len(forbidden_environment_keys),
        "raw_private_plist_values_included": False,
        "values_redacted": True,
    }


def _validate_private_supervisor_summary(
    summary_path: Path,
    private_reference_count: int,
    private_plist_checks: dict[str, Any],
) -> dict[str, int]:
    payload = _load_private_summary_payload(summary_path)
    unsupported_keys = sorted(set(payload) - ALLOWED_PRIVATE_SUMMARY_KEYS)
    if unsupported_keys:
        raise RenderError("private supervisor summary contains unsupported fields")

    for key in sorted(REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS):
        if payload.get(key) is not True:
            raise RenderError(f"private supervisor summary requires {key}=true")
    for key in sorted(REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS):
        if payload.get(key) is not False:
            raise RenderError(f"private supervisor summary requires {key}=false")

    counts: dict[str, int] = {}
    for key in sorted(REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderError(f"private supervisor summary requires positive {key}")
        counts[key] = int(value)

    if counts["private_reference_count"] != private_reference_count:
        raise RenderError("private supervisor summary private reference count mismatch")
    if counts["private_plist_count"] != 1:
        raise RenderError("private supervisor summary private plist count mismatch")
    if counts["launchd_program_argument_count"] != private_plist_checks[
        "program_argument_count"
    ]:
        raise RenderError("private supervisor summary launchd argument count mismatch")
    if counts["launchd_environment_variable_count"] != private_plist_checks[
        "environment_variable_count"
    ]:
        raise RenderError("private supervisor summary environment variable count mismatch")
    if counts["required_environment_variable_count"] != len(
        REQUIRED_PLIST_ENVIRONMENT
    ):
        raise RenderError("private supervisor summary required environment count mismatch")
    if counts["operator_control_count"] != EXPECTED_OPERATOR_CONTROL_COUNT:
        raise RenderError("private supervisor summary operator control count mismatch")
    if counts["runtime_validation_count"] != EXPECTED_RUNTIME_VALIDATION_COUNT:
        raise RenderError("private supervisor summary runtime validation count mismatch")
    return counts


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved supervisor requires explicit attestations")


def _load_private_references(config: RenderConfig) -> list[str]:
    reference_specs = [
        (config.owner_reference_env, "runtime owner reference"),
        (config.preflight_reference_env, "MLX runtime preflight reference"),
        (config.health_reference_env, "student runtime health reference"),
        (config.restart_reference_env, "supervisor restart-test reference"),
        (config.rollback_reference_env, "rollback review reference"),
    ]
    return [
        _load_private_reference(env_name, label)
        for env_name, label in reference_specs
    ]


def _evidence_payload(config: RenderConfig) -> tuple[dict[str, Any], int]:
    private_reference_count = 0
    private_summary_validation = {
        "private_supervisor_summary_checked": False,
        "private_supervisor_summary_path_env_configured": False,
        "private_supervisor_summary_path_value_included": False,
        "private_supervisor_summary_private_reference_count": 0,
        "private_supervisor_summary_private_plist_count": 0,
        "private_supervisor_summary_launchd_program_argument_count": 0,
        "private_supervisor_summary_launchd_environment_variable_count": 0,
        "private_supervisor_summary_required_environment_variable_count": 0,
        "private_supervisor_summary_operator_control_count": 0,
        "private_supervisor_summary_runtime_validation_count": 0,
        "private_supervisor_summary_raw_values_included": False,
    }
    private_plist_validation = {
        "private_plist_metadata_checked": False,
        "private_plist_program_arguments_checked": False,
        "private_plist_environment_checked": False,
        "private_plist_program_argument_count": 0,
        "private_plist_environment_key_count": 0,
        "private_plist_required_environment_key_count": 0,
        "private_plist_runs_mlx_lm_server": False,
        "private_plist_uses_adapter_path": False,
        "private_plist_uses_loopback": False,
        "private_plist_port_configured": False,
        "private_plist_working_directory_configured": False,
        "private_plist_keepalive_configured": False,
        "private_plist_log_paths_configured": False,
        "private_plist_runtime_profile_ok": False,
        "private_plist_secret_like_env_keys_present": False,
        "private_plist_unapproved_env_keys_present": False,
        "private_plist_path_value_included": False,
        "private_plist_raw_values_included": False,
        "values_redacted": True,
    }
    if config.approved_supervisor:
        _validate_approved_attestations(config)
        private_plist_path = _load_private_plist_path(config.private_plist_path_env)
        private_plist_checks = _validate_private_plist(private_plist_path)
        plist_path = str(private_plist_path)
        private_reference_count = len(_load_private_references(config))
        private_summary_counts = _validate_private_supervisor_summary(
            _load_private_summary_path(config.private_summary_path_env),
            private_reference_count,
            private_plist_checks,
        )
        status = "supervisor_ready_private_runtime_validation_complete"
        runtime_ready = True
        private_summary_validation = {
            "private_supervisor_summary_checked": True,
            "private_supervisor_summary_path_env_configured": True,
            "private_supervisor_summary_path_value_included": False,
            "private_supervisor_summary_private_reference_count": (
                private_summary_counts["private_reference_count"]
            ),
            "private_supervisor_summary_private_plist_count": (
                private_summary_counts["private_plist_count"]
            ),
            "private_supervisor_summary_launchd_program_argument_count": (
                private_summary_counts["launchd_program_argument_count"]
            ),
            "private_supervisor_summary_launchd_environment_variable_count": (
                private_summary_counts["launchd_environment_variable_count"]
            ),
            "private_supervisor_summary_required_environment_variable_count": (
                private_summary_counts["required_environment_variable_count"]
            ),
            "private_supervisor_summary_operator_control_count": (
                private_summary_counts["operator_control_count"]
            ),
            "private_supervisor_summary_runtime_validation_count": (
                private_summary_counts["runtime_validation_count"]
            ),
            "private_supervisor_summary_raw_values_included": False,
        }
        private_plist_validation = {
            "private_plist_metadata_checked": True,
            "private_plist_program_arguments_checked": True,
            "private_plist_environment_checked": True,
            "private_plist_program_argument_count": private_plist_checks[
                "program_argument_count"
            ],
            "private_plist_environment_key_count": private_plist_checks[
                "environment_variable_count"
            ],
            "private_plist_required_environment_key_count": private_plist_checks[
                "required_environment_variable_count"
            ],
            "private_plist_runs_mlx_lm_server": private_plist_checks[
                "runs_mlx_lm_server"
            ],
            "private_plist_uses_adapter_path": private_plist_checks[
                "uses_adapter_path"
            ],
            "private_plist_uses_loopback": private_plist_checks[
                "uses_loopback_host"
            ],
            "private_plist_port_configured": private_plist_checks["port_configured"],
            "private_plist_working_directory_configured": private_plist_checks[
                "working_directory_configured"
            ],
            "private_plist_keepalive_configured": private_plist_checks[
                "keepalive_configured"
            ],
            "private_plist_log_paths_configured": private_plist_checks[
                "log_paths_configured"
            ],
            "private_plist_runtime_profile_ok": private_plist_checks[
                "runtime_profile_ok"
            ],
            "private_plist_secret_like_env_keys_present": False,
            "private_plist_unapproved_env_keys_present": False,
            "private_plist_path_value_included": False,
            "private_plist_raw_values_included": False,
            "values_redacted": True,
        }
    else:
        plist_path = DEFAULT_PLIST_PATH
        status = "private_renderer_default_supervisor_ready_false"
        runtime_ready = False

    evidence = {
        "artifact": "claimguard_mlx_runtime_supervisor_evidence",
        "version": "1.0",
        "evidence_status": status,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "no_phi_or_secret_values_attested": True,
        "launchd_template": {
            "plist_path": plist_path,
            "uses_shell": False,
            "runs_mlx_lm_server": True,
            "uses_adapter_path": True,
            "binds_loopback_only": True,
            "base_url_matches_mlx_base_url": True,
            "keepalive_enabled": True,
            "working_directory_configured": True,
            "log_paths_configured": True,
            "contains_secrets": False,
        },
        "operator_controls": {
            "runtime_owner_configured": runtime_ready,
            "launchd_private_copy_renderer_available": True,
            "launchd_private_copy_renderer_path": (
                "llm-distill/scripts/render_mlx_launchd_private_copy.py"
            ),
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": DEFAULT_PRIVATE_EVIDENCE_RENDERER_PATH,
            "source_control_runbook_documented": True,
            "source_control_runbook_path": (
                "llm-distill/docs/mlx-runtime-supervisor-runbook.md"
            ),
            "source_control_owner_handoff_checklist_documented": True,
            "source_control_owner_handoff_checklist_path": (
                "llm-distill/docs/mlx-runtime-owner-handoff-checklist.md"
            ),
            "restart_policy_reviewed": runtime_ready,
            "health_check_reviewed": runtime_ready,
            "manual_start_command_reviewed": runtime_ready,
            "rollback_to_nvidia_reviewed": runtime_ready,
            "environment_file_excluded_from_source_control": True,
        },
        "runtime_validation": {
            "source_control_validation_checklist_documented": True,
            "source_control_validation_checklist_path": (
                "llm-distill/docs/mlx-runtime-validation-checklist.md"
            ),
            "mlx_runtime_preflight_ready": runtime_ready,
            "student_status_endpoint_checked": runtime_ready,
            "student_runtime_health_ok": runtime_ready,
            "supervisor_loaded_in_user_session": runtime_ready,
            "supervisor_restart_test_passed": runtime_ready,
        },
        "private_plist_validation": private_plist_validation,
        "private_summary_validation": private_summary_validation,
        "operator_notes": [
            "supervisor_ready=false until private owner, preflight, health, "
            "load, restart, and rollback evidence is complete.",
            "Checked-in evidence must not include private plist paths, runtime "
            "owner names, approval references, logs, endpoint output, PHI, or secrets.",
        ],
    }
    return evidence, private_reference_count


def _json_file_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_private_evidence(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    evidence, private_reference_count = _evidence_payload(config)
    operator_controls = evidence["operator_controls"]
    runtime_validation = evidence["runtime_validation"]
    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_supervisor_requested": config.approved_supervisor,
        "runtime_owner_configured": operator_controls["runtime_owner_configured"],
        "private_launchd_copy_attested": config.private_launchd_copy_attested,
        "restart_policy_reviewed": operator_controls["restart_policy_reviewed"],
        "health_check_reviewed": operator_controls["health_check_reviewed"],
        "manual_start_command_reviewed": operator_controls[
            "manual_start_command_reviewed"
        ],
        "rollback_to_nvidia_reviewed": operator_controls["rollback_to_nvidia_reviewed"],
        "environment_file_excluded_from_source_control": operator_controls[
            "environment_file_excluded_from_source_control"
        ],
        "mlx_runtime_preflight_ready": runtime_validation[
            "mlx_runtime_preflight_ready"
        ],
        "student_status_endpoint_checked": runtime_validation[
            "student_status_endpoint_checked"
        ],
        "student_runtime_health_ok": runtime_validation["student_runtime_health_ok"],
        "supervisor_loaded_in_user_session": runtime_validation[
            "supervisor_loaded_in_user_session"
        ],
        "supervisor_restart_test_passed": runtime_validation[
            "supervisor_restart_test_passed"
        ],
        "private_reference_count": private_reference_count,
        "private_supervisor_summary_checked": evidence["private_summary_validation"][
            "private_supervisor_summary_checked"
        ],
        "private_supervisor_summary_path_env_configured": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_path_env_configured"],
        "private_supervisor_summary_path_value_included": False,
        "private_supervisor_summary_private_reference_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_private_reference_count"],
        "private_supervisor_summary_private_plist_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_private_plist_count"],
        "private_supervisor_summary_launchd_program_argument_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_launchd_program_argument_count"],
        "private_supervisor_summary_launchd_environment_variable_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_launchd_environment_variable_count"],
        "private_supervisor_summary_required_environment_variable_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_required_environment_variable_count"],
        "private_supervisor_summary_operator_control_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_operator_control_count"],
        "private_supervisor_summary_runtime_validation_count": evidence[
            "private_summary_validation"
        ]["private_supervisor_summary_runtime_validation_count"],
        "private_supervisor_summary_raw_values_included": False,
        "plist_path_configured": bool(evidence["launchd_template"]["plist_path"]),
        "private_plist_metadata_checked": evidence["private_plist_validation"][
            "private_plist_metadata_checked"
        ],
        "private_plist_program_arguments_checked": evidence[
            "private_plist_validation"
        ]["private_plist_program_arguments_checked"],
        "private_plist_environment_checked": evidence["private_plist_validation"][
            "private_plist_environment_checked"
        ],
        "private_plist_uses_loopback": evidence["private_plist_validation"][
            "private_plist_uses_loopback"
        ],
        "private_plist_runtime_profile_ok": evidence["private_plist_validation"][
            "private_plist_runtime_profile_ok"
        ],
        "private_plist_secret_like_env_keys_present": evidence[
            "private_plist_validation"
        ]["private_plist_secret_like_env_keys_present"],
        "private_plist_unapproved_env_keys_present": evidence[
            "private_plist_validation"
        ]["private_plist_unapproved_env_keys_present"],
        "private_plist_path_value_included": False,
        "private_plist_raw_values_included": False,
        "raw_private_values_included": False,
        "raw_runtime_output_included": False,
        "approval_reference_value_included": False,
        "runtime_owner_value_included": False,
        "values_redacted": True,
        "output_path_in_source_control": False,
        "file_mode": "0600" if not config.dry_run else None,
    }

    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_json_file_text(evidence))
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        output_path=args.output,
        approved_supervisor=args.approved_supervisor,
        private_plist_path_env=args.private_plist_path_env,
        private_summary_path_env=args.private_summary_path_env,
        owner_reference_env=args.owner_reference_env,
        preflight_reference_env=args.preflight_reference_env,
        health_reference_env=args.health_reference_env,
        restart_reference_env=args.restart_reference_env,
        rollback_reference_env=args.rollback_reference_env,
        runtime_owner_attested=args.runtime_owner_attested,
        private_launchd_copy_attested=args.private_launchd_copy_attested,
        restart_policy_reviewed=args.restart_policy_reviewed,
        health_check_reviewed=args.health_check_reviewed,
        manual_start_command_reviewed=args.manual_start_command_reviewed,
        rollback_to_nvidia_reviewed=args.rollback_to_nvidia_reviewed,
        environment_file_excluded_attested=args.environment_file_excluded_attested,
        mlx_runtime_preflight_ready=args.mlx_runtime_preflight_ready,
        student_status_endpoint_checked=args.student_status_endpoint_checked,
        student_runtime_health_ok=args.student_runtime_health_ok,
        supervisor_loaded_in_user_session=args.supervisor_loaded_in_user_session,
        supervisor_restart_test_passed=args.supervisor_restart_test_passed,
        no_raw_values_attested=args.no_raw_values_attested,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-supervisor", action="store_true")
    parser.add_argument("--private-plist-path-env", default=DEFAULT_PRIVATE_PLIST_PATH_ENV)
    parser.add_argument(
        "--private-summary-path-env",
        default=DEFAULT_PRIVATE_SUMMARY_PATH_ENV,
    )
    parser.add_argument("--owner-reference-env", default=DEFAULT_OWNER_REFERENCE_ENV)
    parser.add_argument("--preflight-reference-env", default=DEFAULT_PREFLIGHT_REFERENCE_ENV)
    parser.add_argument("--health-reference-env", default=DEFAULT_HEALTH_REFERENCE_ENV)
    parser.add_argument("--restart-reference-env", default=DEFAULT_RESTART_REFERENCE_ENV)
    parser.add_argument("--rollback-reference-env", default=DEFAULT_ROLLBACK_REFERENCE_ENV)
    parser.add_argument("--runtime-owner-attested", action="store_true")
    parser.add_argument("--private-launchd-copy-attested", action="store_true")
    parser.add_argument("--restart-policy-reviewed", action="store_true")
    parser.add_argument("--health-check-reviewed", action="store_true")
    parser.add_argument("--manual-start-command-reviewed", action="store_true")
    parser.add_argument("--rollback-to-nvidia-reviewed", action="store_true")
    parser.add_argument("--environment-file-excluded-attested", action="store_true")
    parser.add_argument("--mlx-runtime-preflight-ready", action="store_true")
    parser.add_argument("--student-status-endpoint-checked", action="store_true")
    parser.add_argument("--student-runtime-health-ok", action="store_true")
    parser.add_argument("--supervisor-loaded-in-user-session", action="store_true")
    parser.add_argument("--supervisor-restart-test-passed", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_evidence(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
