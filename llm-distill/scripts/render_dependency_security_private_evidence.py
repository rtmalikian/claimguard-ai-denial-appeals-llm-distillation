#!/usr/bin/env python3
"""Render private dependency security evidence without exposing values."""

from __future__ import annotations

import argparse
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_SUMMARY_ENV = "CLAIMGUARD_DEPENDENCY_SECURITY_PRIVATE_SUMMARY_PATH"
PRIVATE_REFERENCE_ENVS = (
    "CLAIMGUARD_DEPENDENCY_SECURITY_PYTHON_SCAN_REFERENCE",
    "CLAIMGUARD_DEPENDENCY_SECURITY_FRONTEND_SCAN_REFERENCE",
    "CLAIMGUARD_DEPENDENCY_SECURITY_CONTAINER_SCAN_REFERENCE",
    "CLAIMGUARD_DEPENDENCY_SECURITY_REMEDIATION_REFERENCE",
)
ALLOWED_SUMMARY_FIELDS = {
    "python_dependency_scan_completed",
    "frontend_dependency_scan_completed",
    "container_image_scan_completed",
    "lockfiles_reviewed",
    "scan_tools_documented",
    "critical_high_findings_remediated_or_approved",
    "known_vulnerable_packages_reviewed",
    "compensating_controls_documented",
    "rebuild_and_retest_completed",
    "upgrade_plan_documented",
    "approval_or_risk_acceptance_private",
    "metadata_only_audit_reviewed",
    "no_phi_or_secret_values_included",
    "no_raw_scan_output_included",
    "no_vulnerability_detail_values_included",
    "no_approval_reference_values_included",
    "private_reference_count",
    "python_package_count",
    "frontend_package_count",
    "container_image_count",
    "remediated_or_approved_finding_count",
}
REQUIRED_READY_SUMMARY_FLAGS = (
    "python_dependency_scan_completed",
    "frontend_dependency_scan_completed",
    "container_image_scan_completed",
    "lockfiles_reviewed",
    "scan_tools_documented",
    "critical_high_findings_remediated_or_approved",
    "known_vulnerable_packages_reviewed",
    "compensating_controls_documented",
    "rebuild_and_retest_completed",
    "upgrade_plan_documented",
    "approval_or_risk_acceptance_private",
    "metadata_only_audit_reviewed",
    "no_phi_or_secret_values_included",
    "no_raw_scan_output_included",
    "no_vulnerability_detail_values_included",
    "no_approval_reference_values_included",
)
REQUIRED_POSITIVE_SUMMARY_COUNTS = (
    "private_reference_count",
    "python_package_count",
    "frontend_package_count",
    "container_image_count",
)


@dataclass(frozen=True)
class RenderConfig:
    output: Path
    approved_mode: bool
    python_scan_completed: bool
    frontend_scan_completed: bool
    container_scan_completed: bool
    lockfiles_reviewed: bool
    scan_tools_documented: bool
    critical_high_findings_remediated_or_approved: bool
    known_vulnerable_packages_reviewed: bool
    compensating_controls_documented: bool
    rebuild_and_retest_completed: bool
    upgrade_plan_documented: bool
    approval_or_risk_acceptance_private: bool
    metadata_only_audit_reviewed: bool
    no_raw_values_attested: bool


def path_is_inside_source_control(path: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False
    return True


def refusing_to_write_inside_source_control(output: Path) -> str | None:
    if path_is_inside_source_control(output):
        return "refusing_to_write_inside_source_control"
    return None


def _load_private_summary(path_value: str) -> tuple[dict[str, Any], list[str]]:
    if not path_value.strip():
        return {}, ["private dependency security summary path is not configured"]
    summary_path = Path(path_value).expanduser()
    if path_is_inside_source_control(summary_path):
        return {}, ["private dependency security summary path must not be inside source control"]
    if not summary_path.exists():
        return {}, ["private dependency security summary file is missing"]
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, ["private dependency security summary JSON is invalid"]
    if not isinstance(payload, dict):
        return {}, ["private dependency security summary must be a JSON object"]
    return payload, []


def _positive_int(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _validate_private_dependency_security_summary(
    payload: dict[str, Any],
    *,
    approved_mode: bool,
    expected_reference_count: int,
) -> list[str]:
    blockers: list[str] = []
    unsupported = sorted(set(payload) - ALLOWED_SUMMARY_FIELDS)
    if unsupported:
        blockers.append("unsupported fields in private dependency security summary")
    if not approved_mode:
        return blockers
    for key in REQUIRED_READY_SUMMARY_FLAGS:
        if payload.get(key) is not True:
            blockers.append(f"{key} is not true")
    for key in REQUIRED_POSITIVE_SUMMARY_COUNTS:
        if not _positive_int(payload, key):
            blockers.append(f"{key} must be a positive integer")
    private_reference_count = payload.get("private_reference_count")
    if (
        isinstance(private_reference_count, int)
        and not isinstance(private_reference_count, bool)
        and private_reference_count != expected_reference_count
    ):
        blockers.append("private dependency security summary private reference count mismatch")
    if payload.get("no_raw_scan_output_included") is not True:
        blockers.append("raw scan output is included or unverified")
    if payload.get("no_vulnerability_detail_values_included") is not True:
        blockers.append("vulnerability detail values are included or unverified")
    if payload.get("no_approval_reference_values_included") is not True:
        blockers.append("approval reference values are included or unverified")
    return blockers


def _require_approved_mode_flags(config: RenderConfig) -> list[str]:
    if not config.approved_mode:
        return []
    required = {
        "python_scan_completed": config.python_scan_completed,
        "frontend_scan_completed": config.frontend_scan_completed,
        "container_scan_completed": config.container_scan_completed,
        "lockfiles_reviewed": config.lockfiles_reviewed,
        "scan_tools_documented": config.scan_tools_documented,
        "critical_high_findings_remediated_or_approved": (
            config.critical_high_findings_remediated_or_approved
        ),
        "known_vulnerable_packages_reviewed": config.known_vulnerable_packages_reviewed,
        "compensating_controls_documented": config.compensating_controls_documented,
        "rebuild_and_retest_completed": config.rebuild_and_retest_completed,
        "upgrade_plan_documented": config.upgrade_plan_documented,
        "approval_or_risk_acceptance_private": config.approval_or_risk_acceptance_private,
        "metadata_only_audit_reviewed": config.metadata_only_audit_reviewed,
        "no_raw_values_attested": config.no_raw_values_attested,
    }
    return [f"{key} is required for approved mode" for key, value in required.items() if not value]


def render_private_evidence(config: RenderConfig, env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or os.environ
    blockers = _require_approved_mode_flags(config)
    output_blocker = refusing_to_write_inside_source_control(config.output)
    if output_blocker:
        blockers.append(output_blocker)

    configured_reference_envs = [name for name in PRIVATE_REFERENCE_ENVS if env.get(name, "").strip()]
    summary_path_value = env.get(PRIVATE_SUMMARY_ENV, "")
    summary_payload, summary_errors = _load_private_summary(summary_path_value)
    blockers.extend(summary_errors)
    blockers.extend(
        _validate_private_dependency_security_summary(
            summary_payload,
            approved_mode=config.approved_mode,
            expected_reference_count=len(configured_reference_envs),
        )
    )
    if config.approved_mode and len(configured_reference_envs) != len(PRIVATE_REFERENCE_ENVS):
        blockers.append("all private dependency security reference environment variables are required")

    ready = config.approved_mode and not blockers
    return {
        "artifact": "claimguard_dependency_security_evidence",
        "version": "1.0",
        "evidence_status": "dependency_security_ready" if ready else "draft_not_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dependency_security_ready": ready,
        "approved_mode_requested": config.approved_mode,
        "blockers": blockers,
        "no_phi_or_secret_values_attested": config.no_raw_values_attested,
        "no_raw_scan_output_attested": config.no_raw_values_attested,
        "no_vulnerability_detail_values_attested": config.no_raw_values_attested,
        "no_approval_reference_values_attested": config.no_raw_values_attested,
        "private_reference_env_vars": list(PRIVATE_REFERENCE_ENVS),
        "private_reference_value_count": len(configured_reference_envs),
        "private_reference_values_included": False,
        "private_dependency_security_summary_path_env": PRIVATE_SUMMARY_ENV,
        "private_dependency_security_summary_path_configured": bool(summary_path_value.strip()),
        "private_dependency_security_summary_path_value_included": False,
        "private_dependency_security_summary_checked": not summary_errors,
        "private_dependency_security_summary_private_reference_count": summary_payload.get(
            "private_reference_count",
            0,
        ),
        "private_dependency_security_summary_python_package_count": summary_payload.get(
            "python_package_count",
            0,
        ),
        "private_dependency_security_summary_frontend_package_count": summary_payload.get(
            "frontend_package_count",
            0,
        ),
        "private_dependency_security_summary_container_image_count": summary_payload.get(
            "container_image_count",
            0,
        ),
        "private_dependency_security_summary_remediated_or_approved_finding_count": (
            summary_payload.get("remediated_or_approved_finding_count", 0)
        ),
        "private_dependency_security_summary_raw_values_included": False,
        "scan_controls": {
            "python_dependency_scan_completed": config.python_scan_completed,
            "frontend_dependency_scan_completed": config.frontend_scan_completed,
            "container_image_scan_completed": config.container_scan_completed,
            "lockfiles_reviewed": config.lockfiles_reviewed,
            "scan_tools_documented": config.scan_tools_documented,
        },
        "remediation_controls": {
            "critical_high_findings_remediated_or_approved": (
                config.critical_high_findings_remediated_or_approved
            ),
            "known_vulnerable_packages_reviewed": config.known_vulnerable_packages_reviewed,
            "compensating_controls_documented": config.compensating_controls_documented,
            "rebuild_and_retest_completed": config.rebuild_and_retest_completed,
            "upgrade_plan_documented": config.upgrade_plan_documented,
        },
        "governance_controls": {
            "source_control_runbook_documented": True,
            "runbook_path": "llm-distill/docs/dependency-security-runbook.md",
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_dependency_security_private_evidence.py"
            ),
            "approval_or_risk_acceptance_private": (
                config.approval_or_risk_acceptance_private
            ),
            "metadata_only_audit_reviewed": config.metadata_only_audit_reviewed,
        },
        "values_redacted": True,
    }


def write_private_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Private evidence files are written with 0600 permissions.
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-mode", action="store_true")
    parser.add_argument("--python-scan-completed", action="store_true")
    parser.add_argument("--frontend-scan-completed", action="store_true")
    parser.add_argument("--container-scan-completed", action="store_true")
    parser.add_argument("--lockfiles-reviewed", action="store_true")
    parser.add_argument("--scan-tools-documented", action="store_true")
    parser.add_argument("--critical-high-findings-remediated-or-approved", action="store_true")
    parser.add_argument("--known-vulnerable-packages-reviewed", action="store_true")
    parser.add_argument("--compensating-controls-documented", action="store_true")
    parser.add_argument("--rebuild-and-retest-completed", action="store_true")
    parser.add_argument("--upgrade-plan-documented", action="store_true")
    parser.add_argument("--approval-or-risk-acceptance-private", action="store_true")
    parser.add_argument("--metadata-only-audit-reviewed", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    config = RenderConfig(
        output=args.output,
        approved_mode=args.approved_mode,
        python_scan_completed=args.python_scan_completed,
        frontend_scan_completed=args.frontend_scan_completed,
        container_scan_completed=args.container_scan_completed,
        lockfiles_reviewed=args.lockfiles_reviewed,
        scan_tools_documented=args.scan_tools_documented,
        critical_high_findings_remediated_or_approved=(
            args.critical_high_findings_remediated_or_approved
        ),
        known_vulnerable_packages_reviewed=args.known_vulnerable_packages_reviewed,
        compensating_controls_documented=args.compensating_controls_documented,
        rebuild_and_retest_completed=args.rebuild_and_retest_completed,
        upgrade_plan_documented=args.upgrade_plan_documented,
        approval_or_risk_acceptance_private=args.approval_or_risk_acceptance_private,
        metadata_only_audit_reviewed=args.metadata_only_audit_reviewed,
        no_raw_values_attested=args.no_raw_values_attested,
    )
    payload = render_private_evidence(config)
    if payload["blockers"]:
        print(
            "dependency_security_private_evidence "
            f"ready={payload['dependency_security_ready']} "
            f"blocked={len(payload['blockers'])} values_redacted=True"
        )
        if config.approved_mode:
            return 2
    write_private_evidence(config.output, payload)
    print(
        "dependency_security_private_evidence "
        f"ready={payload['dependency_security_ready']} "
        f"blocked={len(payload['blockers'])} values_redacted=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
