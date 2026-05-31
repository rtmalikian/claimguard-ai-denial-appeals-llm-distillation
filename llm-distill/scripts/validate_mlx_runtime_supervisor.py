#!/usr/bin/env python3
"""Validate MLX student runtime supervisor evidence without storing values."""

from __future__ import annotations

import argparse
import json
import plistlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_EVIDENCE = DISTILL_DIR / "data" / "runtime_supervision" / "supervisor_evidence.template.json"
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "mlx_runtime_supervisor_report.json"
EXPECTED_ARTIFACT = "claimguard_mlx_runtime_supervisor_evidence"
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "api_key",
    "approval_reference",
    "authorization_header",
    "credential",
    "password",
    "raw_document",
    "secret",
    "token",
}
ALLOWED_CONFIGURED_FLAG_KEYS = {
    "approval_reference_configured",
    "contains_secrets",
    "no_phi_or_secret_values_attested",
}
REQUIRED_LAUNCHD_ENVIRONMENT_VARIABLES = {
    "CLAIMGUARD_RUNTIME_PROFILE": "student_denial_workflow_local_only",
}
ALLOWED_LAUNCHD_ENVIRONMENT_VARIABLES = set(REQUIRED_LAUNCHD_ENVIRONMENT_VARIABLES)
RUNBOOK_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "private operator copy",
    "CLAIMGUARD_RUNTIME_PROFILE=student_denial_workflow_local_only",
    "loopback",
    "Do not store approval reference values",
    "CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false",
    "Rollback To NVIDIA",
    "supervisor_ready=false",
)
VALIDATION_CHECKLIST_REQUIRED_MARKERS = (
    "Current status: not runtime-validated.",
    "CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false",
    "CLAIMGUARD_RUNTIME_PROFILE=student_denial_workflow_local_only",
    "loopback",
    "MLX runtime preflight required",
    "Student status endpoint check required",
    "Student runtime health check required",
    "Supervisor restart test required",
    "Rollback to NVIDIA required",
    "boolean-only evidence",
    "no raw runtime output",
    "supervisor_ready=false",
)
OWNER_HANDOFF_CHECKLIST_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: runtime owner not assigned for production.",
    "private runtime owner assignment required",
    "Raphael approval required",
    "approval reference configured outside source control required",
    "private launchd copy required",
    "loopback runtime required",
    "MLX runtime preflight required",
    "student status endpoint check required",
    "student runtime health check required",
    "supervisor restart test required",
    "rollback to NVIDIA required",
    "CLAIMGUARD_STUDENT_USE_BY_DEFAULT=false",
    "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=false",
    "boolean-only evidence",
    "no approval reference values",
    "no raw runtime output",
    "supervisor_ready=false",
)
FORBIDDEN_LAUNCHD_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "proxy",
    "secret",
    "token",
}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing evidence file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def bool_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is True


def str_value(section: dict[str, Any], key: str) -> str:
    value = section.get(key)
    return value if isinstance(value, str) else ""


def requirement(
    *,
    requirement_id: str,
    name: str,
    status: str,
    evidence: dict[str, Any],
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "evidence": evidence,
    }


def find_forbidden_value_keys(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            child_path = f"{path}.{key_text}"
            if (
                key_lower not in ALLOWED_CONFIGURED_FLAG_KEYS
                and any(fragment in key_lower for fragment in FORBIDDEN_VALUE_KEY_FRAGMENTS)
                and not isinstance(child, bool)
                and child not in (None, "", [])
            ):
                findings.append(f"{child_path}: raw approval, secret, or document value key is not allowed")
            findings.extend(find_forbidden_value_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_forbidden_value_keys(child, f"{path}[{index}]"))
    return findings


def evidence_format_requirement(evidence: Any) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(evidence, dict):
        blockers.append("evidence must be a JSON object")
        evidence = {}
    if evidence.get("artifact") != EXPECTED_ARTIFACT:
        blockers.append(f"artifact must be {EXPECTED_ARTIFACT}")
    for section_name in ["launchd_template", "operator_controls", "runtime_validation"]:
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="mlx_runtime_supervisor_evidence_format",
        name="MLX runtime supervisor evidence has the required structure",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "artifact": evidence.get("artifact") if isinstance(evidence, dict) else None,
            "version_configured": bool(evidence.get("version")) if isinstance(evidence, dict) else False,
            "evidence_status": evidence.get("evidence_status") if isinstance(evidence, dict) else None,
        },
    )


def no_phi_or_secret_values_requirement(evidence_path: Path, evidence: Any, plist_path: Path | None) -> dict[str, Any]:
    evidence_text = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else ""
    plist_text = plist_path.read_text(encoding="utf-8") if plist_path and plist_path.exists() else ""
    phi_findings = []
    if evidence_text:
        phi_findings.extend(scan_text(evidence_path, evidence_text))
    if plist_text and plist_path:
        phi_findings.extend(scan_text(plist_path, plist_text))
    forbidden_key_findings = find_forbidden_value_keys(evidence)
    attested = bool_value(evidence, "no_phi_or_secret_values_attested") if isinstance(evidence, dict) else False
    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(f"supervisor evidence contains PHI/PII-like metadata findings: {finding_types}")
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    if not attested:
        blockers.append("no_phi_or_secret_values_attested is not true")

    return requirement(
        requirement_id="mlx_runtime_supervisor_no_phi_or_secret_values",
        name="Supervisor evidence contains no PHI, secrets, or raw approval values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "evidence_path": str(evidence_path),
            "plist_path": str(plist_path) if plist_path else None,
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            "no_phi_or_secret_values_attested": attested,
            "values_redacted": True,
        },
    )


def resolve_plist_path(evidence_path: Path, evidence: dict[str, Any]) -> Path | None:
    launchd_section = evidence.get("launchd_template", {})
    configured_path = str_value(launchd_section, "plist_path")
    if not configured_path:
        return None
    path = Path(configured_path)
    if path.is_absolute():
        return path
    candidate = REPO_ROOT / path
    if candidate.exists():
        return candidate
    return evidence_path.parent / path


def resolve_repo_path(raw_path: str, base_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    candidate = (REPO_ROOT / path).resolve()
    if candidate.exists():
        return candidate
    return (base_path.parent / path).resolve()


def load_plist(path: Path | None) -> tuple[dict[str, Any], list[str]]:
    if path is None:
        return {}, ["launchd_template.plist_path is required"]
    if not path.exists():
        return {}, [f"missing launchd plist template: {path}"]
    try:
        payload = plistlib.loads(path.read_bytes())
    except Exception as exc:  # plistlib raises several parse errors.
        return {}, [f"invalid launchd plist template: {path}: {type(exc).__name__}"]
    return payload if isinstance(payload, dict) else {}, []


def launchd_template_requirement(evidence: dict[str, Any], plist_path: Path | None) -> dict[str, Any]:
    plist, load_errors = load_plist(plist_path)
    section = evidence.get("launchd_template", {})
    program_arguments = plist.get("ProgramArguments", [])
    if not isinstance(program_arguments, list):
        program_arguments = []
    argument_text = "\n".join(str(item) for item in program_arguments)
    environment_variables = plist.get("EnvironmentVariables", {})
    if not isinstance(environment_variables, dict):
        environment_variables = {}
        environment_variable_section_is_object = False
    else:
        environment_variable_section_is_object = True
    configured_env_keys = {str(key) for key in environment_variables}
    missing_required_env_keys = sorted(
        set(REQUIRED_LAUNCHD_ENVIRONMENT_VARIABLES) - configured_env_keys
    )
    wrong_required_env_keys = sorted(
        key
        for key, expected_value in REQUIRED_LAUNCHD_ENVIRONMENT_VARIABLES.items()
        if key in environment_variables and environment_variables.get(key) != expected_value
    )
    unexpected_env_keys = sorted(
        configured_env_keys - ALLOWED_LAUNCHD_ENVIRONMENT_VARIABLES
    )
    forbidden_env_keys = sorted(
        key
        for key in configured_env_keys
        if any(
            fragment in key.lower()
            for fragment in FORBIDDEN_LAUNCHD_ENV_KEY_FRAGMENTS
        )
    )
    blockers = list(load_errors)
    if not bool_value(section, "runs_mlx_lm_server") or not any(
        str(item).endswith("mlx_lm.server") for item in program_arguments
    ):
        blockers.append("launchd_template_must_run_mlx_lm_server")
    if bool_value(section, "uses_shell") or any(str(item).endswith(("/sh", "/bash", "zsh")) for item in program_arguments):
        blockers.append("launchd_template_must_not_use_shell")
    if not bool_value(section, "uses_adapter_path") or "--adapter-path" not in program_arguments:
        blockers.append("launchd_template_missing_adapter_path")
    if not bool_value(section, "binds_loopback_only"):
        blockers.append("launchd_template_loopback_binding_not_attested")
    if "--host" in program_arguments:
        host_index = program_arguments.index("--host") + 1
        host = str(program_arguments[host_index]) if host_index < len(program_arguments) else ""
        if host not in {"127.0.0.1", "localhost", "::1"}:
            blockers.append("launchd_template_host_must_be_loopback")
    else:
        blockers.append("launchd_template_missing_host_argument")
    if "--port" not in program_arguments:
        blockers.append("launchd_template_missing_port_argument")
    if not bool_value(section, "base_url_matches_mlx_base_url"):
        blockers.append("launchd_template_base_url_match_not_attested")
    if not bool_value(section, "keepalive_enabled") or not bool(plist.get("KeepAlive")):
        blockers.append("launchd_template_keepalive_not_enabled")
    if not bool_value(section, "working_directory_configured") or not plist.get("WorkingDirectory"):
        blockers.append("launchd_template_working_directory_missing")
    if not bool_value(section, "log_paths_configured") or not (
        plist.get("StandardOutPath") and plist.get("StandardErrorPath")
    ):
        blockers.append("launchd_template_log_paths_missing")
    if not environment_variable_section_is_object:
        blockers.append("launchd_template_environment_variables_not_object")
    if missing_required_env_keys:
        blockers.append("launchd_template_missing_required_environment_variables")
    if wrong_required_env_keys:
        blockers.append("launchd_template_required_environment_values_not_conservative")
    if unexpected_env_keys:
        blockers.append("launchd_template_has_unapproved_environment_variables")
    if forbidden_env_keys:
        blockers.append("launchd_template_has_secret_or_proxy_environment_names")
    if bool_value(section, "contains_secrets"):
        blockers.append("launchd_template_contains_secrets_attested_true")
    return requirement(
        requirement_id="mlx_runtime_supervisor_launchd_template",
        name="Launchd supervisor template starts mlx_lm.server safely",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "plist_path": str(plist_path) if plist_path else None,
            "program_argument_count": len(program_arguments),
            "runs_mlx_lm_server": "mlx_lm.server" in argument_text,
            "uses_shell": bool_value(section, "uses_shell"),
            "uses_adapter_path": "--adapter-path" in program_arguments,
            "binds_loopback_only": bool_value(section, "binds_loopback_only"),
            "keepalive_configured": bool(plist.get("KeepAlive")),
            "working_directory_configured": bool(plist.get("WorkingDirectory")),
            "log_paths_configured": bool(plist.get("StandardOutPath") and plist.get("StandardErrorPath")),
            "environment_variable_count": len(configured_env_keys),
            "required_environment_variable_count": len(REQUIRED_LAUNCHD_ENVIRONMENT_VARIABLES),
            "missing_required_environment_variables": missing_required_env_keys,
            "wrong_required_environment_variables": wrong_required_env_keys,
            "unexpected_environment_variables": unexpected_env_keys,
            "forbidden_environment_variables": forbidden_env_keys,
            "raw_environment_values_included": False,
            "values_redacted": True,
        },
    )


def operator_runbook_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("operator_controls", {})
    runbook_configured = bool_value(section, "source_control_runbook_documented")
    configured_path = str_value(section, "source_control_runbook_path")
    runbook_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS)
    if not runbook_configured:
        blockers.append("source_control_runbook_not_documented")
    if runbook_path is None:
        blockers.append("source_control_runbook_path_missing")
    elif not runbook_path.exists():
        blockers.append("source_control_runbook_missing")
    else:
        try:
            runbook_text = runbook_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            runbook_text = ""
            blockers.append("source_control_runbook_must_be_utf8")
        present_marker_count = sum(
            1 for marker in RUNBOOK_REQUIRED_MARKERS if marker in runbook_text
        )
        missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS) - present_marker_count
        if missing_marker_count:
            blockers.append("source_control_runbook_required_markers_missing")

    return requirement(
        requirement_id="mlx_runtime_supervisor_operator_runbook",
        name="Source-controlled MLX runtime supervisor runbook is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_runbook_documented": runbook_configured,
            "runbook_path": str(runbook_path) if runbook_path else None,
            "runbook_exists": bool(runbook_path and runbook_path.exists()),
            "required_marker_count": len(RUNBOOK_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_runbook_text_included": False,
            "values_redacted": True,
        },
    )


def owner_handoff_checklist_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("operator_controls", {})
    checklist_configured = bool_value(
        section,
        "source_control_owner_handoff_checklist_documented",
    )
    configured_path = str_value(section, "source_control_owner_handoff_checklist_path")
    checklist_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(OWNER_HANDOFF_CHECKLIST_REQUIRED_MARKERS)
    if not checklist_configured:
        blockers.append("source_control_owner_handoff_checklist_not_documented")
    if checklist_path is None:
        blockers.append("source_control_owner_handoff_checklist_path_missing")
    elif not checklist_path.exists():
        blockers.append("source_control_owner_handoff_checklist_missing")
    else:
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checklist_text = ""
            blockers.append("source_control_owner_handoff_checklist_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in OWNER_HANDOFF_CHECKLIST_REQUIRED_MARKERS
            if marker in checklist_text
        )
        missing_marker_count = (
            len(OWNER_HANDOFF_CHECKLIST_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_owner_handoff_checklist_required_markers_missing")

    return requirement(
        requirement_id="mlx_runtime_supervisor_owner_handoff_checklist",
        name="Source-controlled MLX runtime owner handoff checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_owner_handoff_checklist_documented": checklist_configured,
            "owner_handoff_checklist_path": str(checklist_path) if checklist_path else None,
            "owner_handoff_checklist_exists": bool(checklist_path and checklist_path.exists()),
            "required_marker_count": len(OWNER_HANDOFF_CHECKLIST_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_checklist_text_included": False,
            "values_redacted": True,
        },
    )


def operator_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("operator_controls", {})
    required_flags = {
        "runtime_owner_configured": "runtime_owner_not_configured",
        "source_control_runbook_documented": "source_control_runbook_not_documented",
        "source_control_owner_handoff_checklist_documented": (
            "source_control_owner_handoff_checklist_not_documented"
        ),
        "restart_policy_reviewed": "restart_policy_not_reviewed",
        "health_check_reviewed": "health_check_not_reviewed",
        "manual_start_command_reviewed": "manual_start_command_not_reviewed",
        "rollback_to_nvidia_reviewed": "rollback_to_nvidia_not_reviewed",
        "environment_file_excluded_from_source_control": "environment_file_exclusion_not_attested",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="mlx_runtime_supervisor_operator_controls",
        name="Supervisor operator controls and rollback review are attested",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def runtime_validation_checklist_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("runtime_validation", {})
    checklist_configured = bool_value(section, "source_control_validation_checklist_documented")
    configured_path = str_value(section, "source_control_validation_checklist_path")
    checklist_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(VALIDATION_CHECKLIST_REQUIRED_MARKERS)
    if not checklist_configured:
        blockers.append("source_control_validation_checklist_not_documented")
    if checklist_path is None:
        blockers.append("source_control_validation_checklist_path_missing")
    elif not checklist_path.exists():
        blockers.append("source_control_validation_checklist_missing")
    else:
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checklist_text = ""
            blockers.append("source_control_validation_checklist_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in VALIDATION_CHECKLIST_REQUIRED_MARKERS
            if marker in checklist_text
        )
        missing_marker_count = (
            len(VALIDATION_CHECKLIST_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_validation_checklist_required_markers_missing")

    return requirement(
        requirement_id="mlx_runtime_supervisor_runtime_validation_checklist",
        name="Source-controlled MLX runtime validation checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_validation_checklist_documented": checklist_configured,
            "validation_checklist_path": str(checklist_path) if checklist_path else None,
            "validation_checklist_exists": bool(checklist_path and checklist_path.exists()),
            "required_marker_count": len(VALIDATION_CHECKLIST_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_checklist_text_included": False,
            "values_redacted": True,
        },
    )


def runtime_validation_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("runtime_validation", {})
    required_flags = {
        "mlx_runtime_preflight_ready": "mlx_runtime_preflight_not_ready",
        "student_status_endpoint_checked": "student_status_endpoint_not_checked",
        "student_runtime_health_ok": "student_runtime_health_not_ok",
        "supervisor_loaded_in_user_session": "supervisor_not_loaded_in_user_session",
        "supervisor_restart_test_passed": "supervisor_restart_test_not_passed",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="mlx_runtime_supervisor_runtime_validation",
        name="Supervisor runtime health and restart validation are attested",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def build_report(evidence_path: Path) -> dict[str, Any]:
    evidence, load_errors = load_json(evidence_path)
    if evidence is None:
        evidence = {}
    plist_path = resolve_plist_path(evidence_path, evidence) if isinstance(evidence, dict) else None
    requirements = [
        evidence_format_requirement(evidence),
        no_phi_or_secret_values_requirement(evidence_path, evidence, plist_path),
        launchd_template_requirement(evidence if isinstance(evidence, dict) else {}, plist_path),
        operator_runbook_requirement(evidence_path, evidence if isinstance(evidence, dict) else {}),
        owner_handoff_checklist_requirement(evidence_path, evidence if isinstance(evidence, dict) else {}),
        operator_controls_requirement(evidence if isinstance(evidence, dict) else {}),
        runtime_validation_checklist_requirement(evidence_path, evidence if isinstance(evidence, dict) else {}),
        runtime_validation_requirement(evidence if isinstance(evidence, dict) else {}),
    ]
    if load_errors:
        requirements.insert(
            0,
            requirement(
                requirement_id="mlx_runtime_supervisor_evidence_load",
                name="MLX runtime supervisor evidence can be loaded",
                status="blocked",
                blockers=load_errors,
                evidence={"evidence_path": str(evidence_path)},
            ),
        )

    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    ready_items = [item for item in requirements if item["status"] == "ready"]
    safe_to_review = not any(
        item["requirement_id"] in {
            "mlx_runtime_supervisor_evidence_load",
            "mlx_runtime_supervisor_evidence_format",
            "mlx_runtime_supervisor_no_phi_or_secret_values",
            "mlx_runtime_supervisor_launchd_template",
        }
        and item["status"] == "blocked"
        for item in requirements
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Validate MLX student runtime supervisor evidence without storing "
            "approval references, PHI, secrets, or production document content."
        ),
        "evidence_path": str(evidence_path),
        "safe_to_review": safe_to_review,
        "supervisor_ready": not blocked_items,
        "blocked_item_count": len(blocked_items),
        "ready_item_count": len(ready_items),
        "blocked_items": blocked_items,
        "requirements": requirements,
        "notes": [
            "This validator reads local JSON and plist templates only; it does not install launchd services, start mlx_lm.server, call model endpoints, or enable student default routing.",
            "Approval references, environment secrets, and production document details must remain outside source control.",
            "A template evidence file is expected to be safe_to_review=true but supervisor_ready=false until owner, runtime, health, and restart evidence are complete.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.evidence)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.report} supervisor_ready={report['supervisor_ready']} "
        f"safe_to_review={report['safe_to_review']} blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and report["blocked_item_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
