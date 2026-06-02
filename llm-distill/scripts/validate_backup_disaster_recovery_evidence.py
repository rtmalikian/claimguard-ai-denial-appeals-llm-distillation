#!/usr/bin/env python3
"""Validate backup/disaster-recovery evidence without storing values."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_source_controlled_report_json  # noqa: E402

DEFAULT_EVIDENCE = (
    DISTILL_DIR
    / "data"
    / "backup_disaster_recovery_evidence"
    / "backup_disaster_recovery_evidence.template.json"
)
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "backup_disaster_recovery_evidence_report.json"
DEFAULT_RUNBOOK = APP_ROOT / "docs" / "backup-disaster-recovery.md"
DEFAULT_PRIVATE_EVIDENCE_RENDERER = (
    DISTILL_DIR / "scripts" / "render_backup_disaster_recovery_private_evidence.py"
)
EXPECTED_ARTIFACT = "claimguard_backup_disaster_recovery_evidence"
RUNBOOK_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "backup_disaster_recovery_ready=false",
    "Store backup output outside this repository",
    "Encrypt backup artifacts at rest",
    "Restore verification must not print table rows",
    "Verification logs contain only metadata",
    "Encryption-key recovery is tested",
    "PHIplan production-readiness audit is rerun after backup evidence is",
)
PRIVATE_RENDERER_REQUIRED_MARKERS = (
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "CLAIMGUARD_BACKUP_DR_PRIVATE_SUMMARY_PATH",
    "CLAIMGUARD_BACKUP_DR_STORAGE_REFERENCE",
    "CLAIMGUARD_BACKUP_DR_RESTORE_VERIFICATION_REFERENCE",
    "CLAIMGUARD_BACKUP_DR_KEY_RECOVERY_REFERENCE",
    "CLAIMGUARD_BACKUP_DR_RETENTION_APPROVAL_REFERENCE",
    "_validate_private_backup_summary",
    "private_backup_summary_checked",
    "private_backup_summary_path_value_included",
    "private_backup_summary_private_reference_count",
    "private_backup_summary_backup_artifact_count",
    "private_backup_summary_restore_verification_count",
    "private_backup_summary_key_recovery_artifact_count",
    "private_backup_summary_retention_policy_count",
    "private_backup_summary_raw_values_included",
    "private backup/DR summary private reference count mismatch",
    "unsupported fields",
    "backup_disaster_recovery_ready",
    "0600",
    "values_redacted",
)
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "api_key",
    "approval_reference",
    "backup_path_value",
    "backup_storage_reference",
    "credential",
    "database_row",
    "document_content",
    "encryption_key_value",
    "password",
    "raw_backup",
    "raw_database",
    "raw_document",
    "raw_restore",
    "secret",
    "source_text",
    "token",
    "user_data",
}
ALLOWED_BOOLEAN_FLAG_KEYS = {
    "no_phi_or_secret_values_attested",
    "no_backup_storage_values_attested",
    "no_database_row_values_attested",
    "no_encryption_key_values_attested",
    "private_backup_summary_path_value_included",
    "private_backup_summary_raw_values_included",
    "private_reference_values_included",
}

from report_output_sanitizer import sanitize_report_value  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


def scan_text_allowing_architect_attribution(path: Path, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    allowed_line = "Raphael Malikian <rtmalikian@gmail.com>"
    findings = []
    for finding in scan_text(path, text):
        line_index = int(finding.get("line", 0)) - 1
        line_text = lines[line_index] if 0 <= line_index < len(lines) else ""
        if finding.get("finding_type") == "email_like" and allowed_line in line_text:
            continue
        findings.append(finding)
    return findings


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing evidence file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def bool_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is True


def false_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is False


def positive_int_value(section: dict[str, Any], key: str) -> bool:
    value = section.get(key)
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def resolve_repo_path(raw_path: Any, default_path: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return default_path
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


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
                key_lower not in ALLOWED_BOOLEAN_FLAG_KEYS
                and any(fragment in key_lower for fragment in FORBIDDEN_VALUE_KEY_FRAGMENTS)
                and not isinstance(child, bool)
                and child not in (None, "", [])
            ):
                findings.append(
                    f"{child_path}: raw backup, restore, key, approval, secret, or data value key is not allowed"
                )
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
    for section_name in (
        "backup_storage_controls",
        "restore_validation_controls",
        "key_recovery_controls",
        "governance_controls",
    ):
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="backup_disaster_recovery_evidence_format",
        name="Backup/DR evidence has the required structure",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "artifact": evidence.get("artifact") if isinstance(evidence, dict) else None,
            "version_configured": bool(evidence.get("version")) if isinstance(evidence, dict) else False,
            "evidence_status": evidence.get("evidence_status") if isinstance(evidence, dict) else None,
            "values_redacted": True,
        },
    )


def no_values_requirement(evidence_path: Path, evidence: Any) -> dict[str, Any]:
    evidence_text = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else ""
    phi_findings = (
        scan_text_allowing_architect_attribution(evidence_path, evidence_text)
        if evidence_text
        else []
    )
    forbidden_key_findings = find_forbidden_value_keys(evidence)
    if not isinstance(evidence, dict):
        evidence = {}
    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(f"backup/DR evidence contains PHI/PII-like metadata findings: {finding_types}")
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    required_attestations = {
        "no_phi_or_secret_values_attested": bool_value(evidence, "no_phi_or_secret_values_attested"),
        "no_backup_storage_values_attested": bool_value(evidence, "no_backup_storage_values_attested"),
        "no_database_row_values_attested": bool_value(evidence, "no_database_row_values_attested"),
        "no_encryption_key_values_attested": bool_value(evidence, "no_encryption_key_values_attested"),
        "private_backup_summary_path_value_included_false": false_value(
            evidence,
            "private_backup_summary_path_value_included",
        ),
        "private_backup_summary_raw_values_included_false": false_value(
            evidence,
            "private_backup_summary_raw_values_included",
        ),
    }
    for key, passed in required_attestations.items():
        if not passed:
            blockers.append(f"{key} is not satisfied")
    return requirement(
        requirement_id="backup_disaster_recovery_no_phi_secret_or_values",
        name="Backup/DR evidence contains no PHI, secrets, backup paths, database rows, or key values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "evidence_path": str(evidence_path),
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            **required_attestations,
            "values_redacted": True,
        },
    )


def backup_storage_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("backup_storage_controls", {})
    required = {
        "off_repository_backup_storage_configured": "off_repository_backup_storage_not_configured",
        "backup_artifacts_encrypted_at_rest": "backup_artifacts_not_encrypted_at_rest",
        "scheduler_least_privilege_verified": "scheduler_least_privilege_not_verified",
        "backup_restore_access_reviewed": "backup_restore_access_not_reviewed",
        "retention_period_approved": "retention_period_not_approved",
    }
    blockers = [blocker for key, blocker in required.items() if not bool_value(section, key)]
    return requirement(
        requirement_id="backup_disaster_recovery_storage_controls",
        name="Backup storage, encryption, scheduler, access, and retention controls are ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required} | {"values_redacted": True},
    )


def restore_validation_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("restore_validation_controls", {})
    required = {
        "restore_verification_completed": "restore_verification_not_completed",
        "restore_verification_metadata_only": "restore_verification_not_metadata_only",
        "disaster_recovery_smoke_completed": "disaster_recovery_smoke_not_completed",
        "recovery_objectives_approved": "recovery_objectives_not_approved",
        "rollback_restore_procedure_reviewed": "rollback_restore_procedure_not_reviewed",
    }
    blockers = [blocker for key, blocker in required.items() if not bool_value(section, key)]
    return requirement(
        requirement_id="backup_disaster_recovery_restore_validation",
        name="Restore verification and disaster-recovery smoke evidence are ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required} | {"values_redacted": True},
    )


def key_recovery_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("key_recovery_controls", {})
    required = {
        "encryption_key_recovery_tested": "encryption_key_recovery_not_tested",
        "key_custody_reviewed": "key_custody_not_reviewed",
        "no_key_values_in_evidence": "key_values_in_evidence_not_attested_absent",
    }
    blockers = [blocker for key, blocker in required.items() if not bool_value(section, key)]
    return requirement(
        requirement_id="backup_disaster_recovery_key_recovery",
        name="Encryption-key recovery and custody controls are ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required} | {"values_redacted": True},
    )


def private_summary_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    required_positive_counts = {
        "private_backup_summary_private_reference_count": "private_backup_summary_private_reference_count_missing",
        "private_backup_summary_backup_artifact_count": "private_backup_summary_backup_artifact_count_missing",
        "private_backup_summary_restore_verification_count": (
            "private_backup_summary_restore_verification_count_missing"
        ),
        "private_backup_summary_key_recovery_artifact_count": (
            "private_backup_summary_key_recovery_artifact_count_missing"
        ),
        "private_backup_summary_retention_policy_count": (
            "private_backup_summary_retention_policy_count_missing"
        ),
    }
    blockers: list[str] = []
    if not bool_value(evidence, "private_backup_summary_path_configured"):
        blockers.append("private_backup_summary_path_not_configured")
    if not bool_value(evidence, "private_backup_summary_checked"):
        blockers.append("private_backup_summary_not_checked")
    if not false_value(evidence, "private_backup_summary_path_value_included"):
        blockers.append("private_backup_summary_path_value_included")
    if not false_value(evidence, "private_backup_summary_raw_values_included"):
        blockers.append("private_backup_summary_raw_values_included")
    for key, blocker in required_positive_counts.items():
        if not positive_int_value(evidence, key):
            blockers.append(blocker)
    return requirement(
        requirement_id="backup_disaster_recovery_private_summary_metadata",
        name="Private backup/DR summary metadata is present without raw values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "private_backup_summary_path_env": evidence.get("private_backup_summary_path_env"),
            "private_backup_summary_path_configured": bool_value(
                evidence,
                "private_backup_summary_path_configured",
            ),
            "private_backup_summary_path_value_included": bool_value(
                evidence,
                "private_backup_summary_path_value_included",
            ),
            "private_backup_summary_checked": bool_value(
                evidence,
                "private_backup_summary_checked",
            ),
            **{
                key: evidence.get(key)
                for key in required_positive_counts
            },
            "values_redacted": True,
        },
    )


def source_control_runbook_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    documented = bool_value(section, "source_control_runbook_documented")
    runbook_path = resolve_repo_path(section.get("runbook_path"), DEFAULT_RUNBOOK)
    blockers: list[str] = []
    missing_markers: list[str] = []
    phi_findings: list[dict[str, Any]] = []
    if not documented:
        blockers.append("source_control_runbook_not_documented")
    if not path_is_within(runbook_path, REPO_ROOT):
        blockers.append("source_control_runbook_path_outside_repository")
    elif not runbook_path.exists():
        blockers.append("source_control_runbook_missing")
    else:
        text = runbook_path.read_text(encoding="utf-8")
        missing_markers = [marker for marker in RUNBOOK_REQUIRED_MARKERS if marker not in text]
        phi_findings = scan_text_allowing_architect_attribution(runbook_path, text)
        if missing_markers:
            blockers.append("source_control_runbook_required_markers_missing")
        if phi_findings:
            blockers.append("source_control_runbook_phi_or_secret_findings")
    return requirement(
        requirement_id="backup_disaster_recovery_runbook",
        name="Source-controlled backup/DR runbook has required safety markers",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_runbook_documented": documented,
            "runbook_path": sanitize_report_value(str(runbook_path), REPO_ROOT),
            "runbook_exists": runbook_path.exists(),
            "runbook_inside_source_control": path_is_within(runbook_path, REPO_ROOT),
            "runbook_missing_marker_count": len(missing_markers),
            "phi_finding_count": len(phi_findings),
            "runbook_values_included": False,
            "values_redacted": True,
        },
    )


def private_renderer_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    documented = bool_value(section, "source_control_private_evidence_renderer_documented")
    renderer_path = resolve_repo_path(
        section.get("private_evidence_renderer_path"),
        DEFAULT_PRIVATE_EVIDENCE_RENDERER,
    )
    blockers: list[str] = []
    missing_markers: list[str] = []
    phi_findings: list[dict[str, Any]] = []
    if not documented:
        blockers.append("source_control_private_evidence_renderer_not_documented")
    if not path_is_within(renderer_path, REPO_ROOT):
        blockers.append("source_control_private_evidence_renderer_path_outside_repository")
    elif not renderer_path.exists():
        blockers.append("source_control_private_evidence_renderer_missing")
    else:
        text = renderer_path.read_text(encoding="utf-8")
        missing_markers = [
            marker for marker in PRIVATE_RENDERER_REQUIRED_MARKERS if marker not in text
        ]
        phi_findings = scan_text_allowing_architect_attribution(renderer_path, text)
        if missing_markers:
            blockers.append("source_control_private_evidence_renderer_markers_missing")
        if phi_findings:
            blockers.append("source_control_private_evidence_renderer_phi_or_secret_findings")
    return requirement(
        requirement_id="backup_disaster_recovery_private_evidence_renderer",
        name="Private backup/DR evidence renderer exists with no-source-control and redaction markers",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_private_evidence_renderer_documented": documented,
            "private_evidence_renderer_path": sanitize_report_value(str(renderer_path), REPO_ROOT),
            "private_evidence_renderer_exists": renderer_path.exists(),
            "private_evidence_renderer_inside_source_control": path_is_within(
                renderer_path,
                REPO_ROOT,
            ),
            "private_evidence_renderer_missing_marker_count": len(missing_markers),
            "phi_finding_count": len(phi_findings),
            "private_evidence_renderer_values_included": False,
            "values_redacted": True,
        },
    )


def governance_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    required = {
        "metadata_only_audit_reviewed": "metadata_only_audit_not_reviewed",
        "incident_recording_without_phi_reviewed": "incident_recording_without_phi_not_reviewed",
    }
    blockers = [blocker for key, blocker in required.items() if not bool_value(section, key)]
    return requirement(
        requirement_id="backup_disaster_recovery_governance_controls",
        name="Backup/DR audit and incident-recording governance controls are ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required} | {"values_redacted": True},
    )


def build_report(evidence_path: Path = DEFAULT_EVIDENCE) -> dict[str, Any]:
    evidence, load_errors = load_json(evidence_path)
    if not isinstance(evidence, dict):
        evidence = {}
    requirements = [
        evidence_format_requirement(evidence),
        no_values_requirement(evidence_path, evidence),
        source_control_runbook_requirement(evidence),
        private_renderer_requirement(evidence),
        backup_storage_controls_requirement(evidence),
        restore_validation_controls_requirement(evidence),
        key_recovery_controls_requirement(evidence),
        governance_controls_requirement(evidence),
        private_summary_requirement(evidence),
    ]
    if load_errors:
        requirements.insert(
            0,
            requirement(
                requirement_id="backup_disaster_recovery_evidence_load",
                name="Backup/DR evidence file can be loaded",
                status="blocked",
                blockers=load_errors,
                evidence={"evidence_path": str(evidence_path), "values_redacted": True},
            ),
        )
    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    backup_disaster_recovery_ready = not blocked_items and bool_value(
        evidence,
        "backup_disaster_recovery_ready",
    )
    if not backup_disaster_recovery_ready and not any(
        item["requirement_id"] == "backup_disaster_recovery_ready_flag"
        for item in blocked_items
    ):
        ready_flag = requirement(
            requirement_id="backup_disaster_recovery_ready_flag",
            name="Backup/DR evidence is explicitly marked ready",
            status="ready" if bool_value(evidence, "backup_disaster_recovery_ready") else "blocked",
            blockers=[] if bool_value(evidence, "backup_disaster_recovery_ready") else [
                "backup_disaster_recovery_ready is not true"
            ],
            evidence={
                "backup_disaster_recovery_ready": bool_value(
                    evidence,
                    "backup_disaster_recovery_ready",
                ),
                "values_redacted": True,
            },
        )
        requirements.append(ready_flag)
        if ready_flag["status"] == "blocked":
            blocked_items.append(ready_flag)
    return {
        "artifact": "backup_disaster_recovery_evidence_validation_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safe_to_review": not any(
            item["requirement_id"] == "backup_disaster_recovery_no_phi_secret_or_values"
            and item["status"] == "blocked"
            for item in requirements
        ),
        "backup_disaster_recovery_ready": backup_disaster_recovery_ready,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "requirements": requirements,
        "evidence": {
            "evidence_path": sanitize_report_value(str(evidence_path), REPO_ROOT),
            "runbook": (
                "health-ai-medical-billing-medical-corporations-20260414_180528/"
                "docs/backup-disaster-recovery.md"
            ),
            "private_evidence_renderer": (
                "llm-distill/scripts/render_backup_disaster_recovery_private_evidence.py"
            ),
            "values_redacted": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()
    report = build_report(args.evidence)
    write_source_controlled_report_json(args.report, report, repo_root=REPO_ROOT)
    print(
        f"wrote backup/DR evidence report to {args.report} "
        f"ready={report['backup_disaster_recovery_ready']} "
        f"blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and report["blocked_item_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
