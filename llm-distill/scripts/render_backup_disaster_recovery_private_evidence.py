#!/usr/bin/env python3
"""Render private backup/disaster-recovery evidence without exposing values."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_SUMMARY_ENV = "CLAIMGUARD_BACKUP_DR_PRIVATE_SUMMARY_PATH"
PRIVATE_REFERENCE_ENVS = (
    "CLAIMGUARD_BACKUP_DR_STORAGE_REFERENCE",
    "CLAIMGUARD_BACKUP_DR_RESTORE_VERIFICATION_REFERENCE",
    "CLAIMGUARD_BACKUP_DR_KEY_RECOVERY_REFERENCE",
    "CLAIMGUARD_BACKUP_DR_RETENTION_APPROVAL_REFERENCE",
)
ALLOWED_SUMMARY_FIELDS = {
    "backup_storage_outside_repository_verified",
    "backup_artifact_encryption_verified",
    "scheduler_least_privilege_verified",
    "restore_verification_completed",
    "restore_verification_metadata_only",
    "encryption_key_recovery_tested",
    "key_custody_reviewed",
    "disaster_recovery_smoke_completed",
    "retention_period_approved",
    "recovery_objectives_approved",
    "rollback_restore_procedure_reviewed",
    "metadata_only_audit_reviewed",
    "incident_recording_without_phi_reviewed",
    "no_phi_or_secret_values_included",
    "no_backup_paths_included",
    "no_database_rows_included",
    "no_encryption_key_values_included",
    "private_reference_count",
    "backup_artifact_count",
    "restore_verification_count",
    "key_recovery_artifact_count",
    "retention_policy_count",
}
REQUIRED_READY_SUMMARY_FLAGS = (
    "backup_storage_outside_repository_verified",
    "backup_artifact_encryption_verified",
    "scheduler_least_privilege_verified",
    "restore_verification_completed",
    "restore_verification_metadata_only",
    "encryption_key_recovery_tested",
    "key_custody_reviewed",
    "disaster_recovery_smoke_completed",
    "retention_period_approved",
    "recovery_objectives_approved",
    "rollback_restore_procedure_reviewed",
    "metadata_only_audit_reviewed",
    "incident_recording_without_phi_reviewed",
    "no_phi_or_secret_values_included",
    "no_backup_paths_included",
    "no_database_rows_included",
    "no_encryption_key_values_included",
)
REQUIRED_POSITIVE_SUMMARY_COUNTS = (
    "private_reference_count",
    "backup_artifact_count",
    "restore_verification_count",
    "key_recovery_artifact_count",
    "retention_policy_count",
)


@dataclass(frozen=True)
class RenderConfig:
    output: Path
    approved_mode: bool
    backup_storage_configured: bool
    encrypted_at_rest: bool
    scheduler_least_privilege: bool
    restore_verification_completed: bool
    restore_verification_metadata_only: bool
    key_recovery_tested: bool
    key_custody_reviewed: bool
    disaster_recovery_smoke_completed: bool
    retention_approved: bool
    recovery_objectives_approved: bool
    rollback_restore_reviewed: bool
    metadata_only_audit_reviewed: bool
    incident_recording_without_phi_reviewed: bool
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
        return {}, ["private backup/DR summary path is not configured"]
    summary_path = Path(path_value).expanduser()
    if path_is_inside_source_control(summary_path):
        return {}, ["private backup/DR summary path must not be inside source control"]
    if not summary_path.exists():
        return {}, ["private backup/DR summary file is missing"]
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, ["private backup/DR summary JSON is invalid"]
    if not isinstance(payload, dict):
        return {}, ["private backup/DR summary must be a JSON object"]
    return payload, []


def _positive_int(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _validate_private_backup_summary(
    payload: dict[str, Any],
    *,
    approved_mode: bool,
    expected_reference_count: int,
) -> list[str]:
    blockers: list[str] = []
    unsupported = sorted(set(payload) - ALLOWED_SUMMARY_FIELDS)
    if unsupported:
        blockers.append("unsupported fields in private backup/DR summary")
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
        blockers.append("private backup/DR summary private reference count mismatch")
    if payload.get("no_backup_paths_included") is not True:
        blockers.append("backup path values are included or unverified")
    if payload.get("no_database_rows_included") is not True:
        blockers.append("database row values are included or unverified")
    if payload.get("no_encryption_key_values_included") is not True:
        blockers.append("encryption key values are included or unverified")
    return blockers


def _require_approved_mode_flags(config: RenderConfig) -> list[str]:
    if not config.approved_mode:
        return []
    required = {
        "backup_storage_configured": config.backup_storage_configured,
        "encrypted_at_rest": config.encrypted_at_rest,
        "scheduler_least_privilege": config.scheduler_least_privilege,
        "restore_verification_completed": config.restore_verification_completed,
        "restore_verification_metadata_only": config.restore_verification_metadata_only,
        "key_recovery_tested": config.key_recovery_tested,
        "key_custody_reviewed": config.key_custody_reviewed,
        "disaster_recovery_smoke_completed": config.disaster_recovery_smoke_completed,
        "retention_approved": config.retention_approved,
        "recovery_objectives_approved": config.recovery_objectives_approved,
        "rollback_restore_reviewed": config.rollback_restore_reviewed,
        "metadata_only_audit_reviewed": config.metadata_only_audit_reviewed,
        "incident_recording_without_phi_reviewed": (
            config.incident_recording_without_phi_reviewed
        ),
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
        _validate_private_backup_summary(
            summary_payload,
            approved_mode=config.approved_mode,
            expected_reference_count=len(configured_reference_envs),
        )
    )
    if config.approved_mode and len(configured_reference_envs) != len(PRIVATE_REFERENCE_ENVS):
        blockers.append("all private backup/DR reference environment variables are required")

    ready = config.approved_mode and not blockers
    return {
        "artifact": "claimguard_backup_disaster_recovery_evidence",
        "version": "1.0",
        "evidence_status": "backup_disaster_recovery_ready" if ready else "draft_not_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backup_disaster_recovery_ready": ready,
        "approved_mode_requested": config.approved_mode,
        "blockers": blockers,
        "no_phi_or_secret_values_attested": config.no_raw_values_attested,
        "no_backup_storage_values_attested": config.no_raw_values_attested,
        "no_database_row_values_attested": config.no_raw_values_attested,
        "no_encryption_key_values_attested": config.no_raw_values_attested,
        "private_reference_env_vars": list(PRIVATE_REFERENCE_ENVS),
        "private_reference_value_count": len(configured_reference_envs),
        "private_reference_values_included": False,
        "private_backup_summary_path_env": PRIVATE_SUMMARY_ENV,
        "private_backup_summary_path_configured": bool(summary_path_value.strip()),
        "private_backup_summary_path_value_included": False,
        "private_backup_summary_checked": not summary_errors,
        "private_backup_summary_private_reference_count": summary_payload.get(
            "private_reference_count",
            0,
        ),
        "private_backup_summary_backup_artifact_count": summary_payload.get(
            "backup_artifact_count",
            0,
        ),
        "private_backup_summary_restore_verification_count": summary_payload.get(
            "restore_verification_count",
            0,
        ),
        "private_backup_summary_key_recovery_artifact_count": summary_payload.get(
            "key_recovery_artifact_count",
            0,
        ),
        "private_backup_summary_retention_policy_count": summary_payload.get(
            "retention_policy_count",
            0,
        ),
        "private_backup_summary_raw_values_included": False,
        "backup_storage_controls": {
            "off_repository_backup_storage_configured": config.backup_storage_configured,
            "backup_artifacts_encrypted_at_rest": config.encrypted_at_rest,
            "scheduler_least_privilege_verified": config.scheduler_least_privilege,
            "backup_restore_access_reviewed": config.no_raw_values_attested,
            "retention_period_approved": config.retention_approved,
        },
        "restore_validation_controls": {
            "restore_verification_completed": config.restore_verification_completed,
            "restore_verification_metadata_only": config.restore_verification_metadata_only,
            "disaster_recovery_smoke_completed": config.disaster_recovery_smoke_completed,
            "recovery_objectives_approved": config.recovery_objectives_approved,
            "rollback_restore_procedure_reviewed": config.rollback_restore_reviewed,
        },
        "key_recovery_controls": {
            "encryption_key_recovery_tested": config.key_recovery_tested,
            "key_custody_reviewed": config.key_custody_reviewed,
            "no_key_values_in_evidence": config.no_raw_values_attested,
        },
        "governance_controls": {
            "source_control_runbook_documented": True,
            "runbook_path": (
                "health-ai-medical-billing-medical-corporations-20260414_180528/"
                "docs/backup-disaster-recovery.md"
            ),
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_backup_disaster_recovery_private_evidence.py"
            ),
            "metadata_only_audit_reviewed": config.metadata_only_audit_reviewed,
            "incident_recording_without_phi_reviewed": (
                config.incident_recording_without_phi_reviewed
            ),
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
    parser.add_argument("--backup-storage-configured", action="store_true")
    parser.add_argument("--encrypted-at-rest", action="store_true")
    parser.add_argument("--scheduler-least-privilege", action="store_true")
    parser.add_argument("--restore-verification-completed", action="store_true")
    parser.add_argument("--restore-verification-metadata-only", action="store_true")
    parser.add_argument("--key-recovery-tested", action="store_true")
    parser.add_argument("--key-custody-reviewed", action="store_true")
    parser.add_argument("--disaster-recovery-smoke-completed", action="store_true")
    parser.add_argument("--retention-approved", action="store_true")
    parser.add_argument("--recovery-objectives-approved", action="store_true")
    parser.add_argument("--rollback-restore-reviewed", action="store_true")
    parser.add_argument("--metadata-only-audit-reviewed", action="store_true")
    parser.add_argument("--incident-recording-without-phi-reviewed", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    config = RenderConfig(
        output=args.output,
        approved_mode=args.approved_mode,
        backup_storage_configured=args.backup_storage_configured,
        encrypted_at_rest=args.encrypted_at_rest,
        scheduler_least_privilege=args.scheduler_least_privilege,
        restore_verification_completed=args.restore_verification_completed,
        restore_verification_metadata_only=args.restore_verification_metadata_only,
        key_recovery_tested=args.key_recovery_tested,
        key_custody_reviewed=args.key_custody_reviewed,
        disaster_recovery_smoke_completed=args.disaster_recovery_smoke_completed,
        retention_approved=args.retention_approved,
        recovery_objectives_approved=args.recovery_objectives_approved,
        rollback_restore_reviewed=args.rollback_restore_reviewed,
        metadata_only_audit_reviewed=args.metadata_only_audit_reviewed,
        incident_recording_without_phi_reviewed=args.incident_recording_without_phi_reviewed,
        no_raw_values_attested=args.no_raw_values_attested,
    )
    payload = render_private_evidence(config)
    if payload["blockers"]:
        print(
            "backup_disaster_recovery_private_evidence "
            f"ready={payload['backup_disaster_recovery_ready']} "
            f"blocked={len(payload['blockers'])} values_redacted=True"
        )
        if config.approved_mode:
            return 2
    write_private_evidence(config.output, payload)
    print(
        "backup_disaster_recovery_private_evidence "
        f"ready={payload['backup_disaster_recovery_ready']} "
        f"blocked={len(payload['blockers'])} values_redacted=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
