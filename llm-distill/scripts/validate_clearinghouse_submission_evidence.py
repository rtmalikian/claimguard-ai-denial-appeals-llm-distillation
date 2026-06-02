#!/usr/bin/env python3
"""Validate clearinghouse submission evidence without storing values."""

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

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import sanitize_report_value, write_source_controlled_report_json  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402

DEFAULT_EVIDENCE = (
    DISTILL_DIR
    / "data"
    / "clearinghouse_submission_evidence"
    / "clearinghouse_submission_evidence.template.json"
)
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "clearinghouse_submission_evidence_report.json"
DEFAULT_RUNBOOK = DISTILL_DIR / "docs" / "clearinghouse-submission-runbook.md"
DEFAULT_PRIVATE_EVIDENCE_RENDERER = (
    DISTILL_DIR / "scripts" / "render_clearinghouse_submission_private_evidence.py"
)
EXPECTED_ARTIFACT = "claimguard_clearinghouse_submission_evidence"
RUNBOOK_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "clearinghouse_submission_ready=false",
    "Payer or clearinghouse enrollment",
    "Test-mode credentials are configured privately",
    "Encrypted transit has been validated",
    "EDI 837 submission contract behavior",
    "Control-number management",
    "999 and 277CA acknowledgement",
    "Do not store raw EDI payloads",
    "PHIplan production-readiness blocked",
)
PRIVATE_RENDERER_REQUIRED_MARKERS = (
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_PRIVATE_SUMMARY_PATH",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENROLLMENT_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_CONNECTIVITY_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_TEST_TRANSACTION_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ACKNOWLEDGEMENT_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_GOVERNANCE_REFERENCE",
    "_validate_private_clearinghouse_submission_summary",
    "private_clearinghouse_submission_summary_checked",
    "private_clearinghouse_submission_summary_path_value_included",
    "private_clearinghouse_submission_summary_private_reference_count",
    "private_clearinghouse_submission_summary_payer_count",
    "private_clearinghouse_submission_summary_test_transaction_count",
    "private_clearinghouse_submission_summary_acknowledgement_test_count",
    "private_clearinghouse_submission_summary_raw_values_included",
    "private clearinghouse submission summary private reference count mismatch",
    "unsupported fields",
    "clearinghouse_submission_ready",
    "0600",
    "values_redacted",
)
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "api_key",
    "approval_reference",
    "claim_control_number",
    "clearinghouse_credential",
    "credential",
    "document_content",
    "edi_payload",
    "endpoint_url",
    "payer_control_number",
    "payer_portal",
    "password",
    "production_claim",
    "raw_edi",
    "raw_submission",
    "secret",
    "subscriber_id",
    "token",
    "user_data",
}
ALLOWED_BOOLEAN_FLAG_KEYS = {
    "no_phi_or_secret_values_attested",
    "no_raw_edi_payloads_attested",
    "no_payer_portal_credential_values_attested",
    "no_approval_reference_values_attested",
    "private_clearinghouse_submission_summary_path_value_included",
    "private_clearinghouse_submission_summary_raw_values_included",
    "private_reference_values_included",
}


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
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": [],
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
                    f"{child_path}: raw clearinghouse, payer, EDI, approval, secret, or production value key is not allowed"
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
        "connectivity_controls",
        "submission_controls",
        "audit_retention_controls",
        "governance_controls",
    ):
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="clearinghouse_submission_evidence_format",
        name="Clearinghouse submission evidence has the required structure",
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
        blockers.append(
            f"clearinghouse evidence contains PHI/PII-like metadata findings: {finding_types}"
        )
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    required_attestations = {
        "no_phi_or_secret_values_attested": bool_value(evidence, "no_phi_or_secret_values_attested"),
        "no_raw_edi_payloads_attested": bool_value(evidence, "no_raw_edi_payloads_attested"),
        "no_payer_portal_credential_values_attested": bool_value(
            evidence,
            "no_payer_portal_credential_values_attested",
        ),
        "no_approval_reference_values_attested": bool_value(
            evidence,
            "no_approval_reference_values_attested",
        ),
        "private_clearinghouse_submission_summary_path_value_included_false": false_value(
            evidence,
            "private_clearinghouse_submission_summary_path_value_included",
        ),
        "private_clearinghouse_submission_summary_raw_values_included_false": false_value(
            evidence,
            "private_clearinghouse_submission_summary_raw_values_included",
        ),
    }
    for key, passed in required_attestations.items():
        if not passed:
            blockers.append(f"{key} is not satisfied")
    return requirement(
        requirement_id="clearinghouse_submission_no_phi_secret_or_values",
        name="Clearinghouse submission evidence contains no PHI, secrets, raw EDI payloads, credentials, or approval references",
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


def boolean_section_requirement(
    *,
    evidence: dict[str, Any],
    section_name: str,
    requirement_id: str,
    name: str,
    required: dict[str, str],
) -> dict[str, Any]:
    section = evidence.get(section_name, {})
    blockers = [blocker for key, blocker in required.items() if not bool_value(section, key)]
    return requirement(
        requirement_id=requirement_id,
        name=name,
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required} | {"values_redacted": True},
    )


def connectivity_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    return boolean_section_requirement(
        evidence=evidence,
        section_name="connectivity_controls",
        requirement_id="clearinghouse_submission_connectivity_controls",
        name="Clearinghouse enrollment, private credentials, encrypted transit, and endpoint controls are ready",
        required={
            "payer_or_clearinghouse_enrollment_confirmed": "payer_or_clearinghouse_enrollment_not_confirmed",
            "test_mode_credentials_configured_privately": "test_mode_credentials_not_configured_privately",
            "encrypted_transit_validated": "encrypted_transit_not_validated",
            "production_endpoint_configured_privately": "production_endpoint_not_configured_privately",
            "source_control_credentials_absent": "source_control_credentials_absence_not_confirmed",
        },
    )


def submission_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    return boolean_section_requirement(
        evidence=evidence,
        section_name="submission_controls",
        requirement_id="clearinghouse_submission_transaction_controls",
        name="EDI 837 submission, control number, acknowledgement, retry, duplicate, and rollback controls are ready",
        required={
            "edi_837_submission_contract_validated": "edi_837_submission_contract_not_validated",
            "control_number_management_reviewed": "control_number_management_not_reviewed",
            "acknowledgement_999_277ca_handling_validated": "acknowledgement_handling_not_validated",
            "rejection_retry_and_duplicate_controls_reviewed": "rejection_retry_duplicate_controls_not_reviewed",
            "rollback_to_non_submission_mode_reviewed": "rollback_to_non_submission_mode_not_reviewed",
        },
    )


def audit_retention_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    return boolean_section_requirement(
        evidence=evidence,
        section_name="audit_retention_controls",
        requirement_id="clearinghouse_submission_audit_retention_controls",
        name="Clearinghouse submission audit, access, retention, and no-raw-log controls are ready",
        required={
            "metadata_only_audit_logging_reviewed": "metadata_only_audit_logging_not_reviewed",
            "access_controls_reviewed": "access_controls_not_reviewed",
            "retention_policy_reviewed": "retention_policy_not_reviewed",
            "no_raw_edi_or_phi_logs_attested": "no_raw_edi_or_phi_logs_not_attested",
        },
    )


def private_summary_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    required_positive_counts = {
        "private_clearinghouse_submission_summary_private_reference_count": (
            "private_clearinghouse_submission_summary_private_reference_count_missing"
        ),
        "private_clearinghouse_submission_summary_payer_count": (
            "private_clearinghouse_submission_summary_payer_count_missing"
        ),
        "private_clearinghouse_submission_summary_test_transaction_count": (
            "private_clearinghouse_submission_summary_test_transaction_count_missing"
        ),
        "private_clearinghouse_submission_summary_acknowledgement_test_count": (
            "private_clearinghouse_submission_summary_acknowledgement_test_count_missing"
        ),
    }
    blockers: list[str] = []
    if not bool_value(evidence, "private_clearinghouse_submission_summary_path_configured"):
        blockers.append("private_clearinghouse_submission_summary_path_not_configured")
    if not bool_value(evidence, "private_clearinghouse_submission_summary_checked"):
        blockers.append("private_clearinghouse_submission_summary_not_checked")
    if not false_value(evidence, "private_clearinghouse_submission_summary_path_value_included"):
        blockers.append("private_clearinghouse_submission_summary_path_value_included")
    if not false_value(evidence, "private_clearinghouse_submission_summary_raw_values_included"):
        blockers.append("private_clearinghouse_submission_summary_raw_values_included")
    for key, blocker in required_positive_counts.items():
        if not positive_int_value(evidence, key):
            blockers.append(blocker)
    return requirement(
        requirement_id="clearinghouse_submission_private_summary_metadata",
        name="Private clearinghouse submission summary metadata is present without raw values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "private_clearinghouse_submission_summary_path_env": evidence.get(
                "private_clearinghouse_submission_summary_path_env"
            ),
            "private_clearinghouse_submission_summary_path_configured": bool_value(
                evidence,
                "private_clearinghouse_submission_summary_path_configured",
            ),
            "private_clearinghouse_submission_summary_path_value_included": bool_value(
                evidence,
                "private_clearinghouse_submission_summary_path_value_included",
            ),
            "private_clearinghouse_submission_summary_checked": bool_value(
                evidence,
                "private_clearinghouse_submission_summary_checked",
            ),
            **{key: evidence.get(key) for key in required_positive_counts},
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
        requirement_id="clearinghouse_submission_runbook",
        name="Source-controlled clearinghouse submission runbook has required safety markers",
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
        requirement_id="clearinghouse_submission_private_evidence_renderer",
        name="Private clearinghouse submission evidence renderer exists with no-source-control and redaction markers",
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
        "approval_or_risk_acceptance_private": "approval_or_risk_acceptance_not_private_or_missing",
        "metadata_only_audit_reviewed": "metadata_only_audit_not_reviewed",
    }
    blockers = [blocker for key, blocker in required.items() if not bool_value(section, key)]
    return requirement(
        requirement_id="clearinghouse_submission_governance_controls",
        name="Clearinghouse submission approval and metadata-only audit governance controls are ready",
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
        connectivity_controls_requirement(evidence),
        submission_controls_requirement(evidence),
        audit_retention_controls_requirement(evidence),
        governance_controls_requirement(evidence),
        private_summary_requirement(evidence),
    ]
    if load_errors:
        requirements.insert(
            0,
            requirement(
                requirement_id="clearinghouse_submission_evidence_load",
                name="Clearinghouse submission evidence file can be loaded",
                status="blocked",
                blockers=load_errors,
                evidence={"evidence_path": str(evidence_path), "values_redacted": True},
            ),
        )
    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    clearinghouse_submission_ready = not blocked_items and bool_value(
        evidence,
        "clearinghouse_submission_ready",
    )
    ready_flag = requirement(
        requirement_id="clearinghouse_submission_ready_flag",
        name="Clearinghouse submission evidence is explicitly marked ready",
        status="ready" if bool_value(evidence, "clearinghouse_submission_ready") else "blocked",
        blockers=[] if bool_value(evidence, "clearinghouse_submission_ready") else [
            "clearinghouse_submission_ready is not true"
        ],
        evidence={
            "clearinghouse_submission_ready": bool_value(evidence, "clearinghouse_submission_ready"),
            "values_redacted": True,
        },
    )
    requirements.append(ready_flag)
    if ready_flag["status"] == "blocked":
        blocked_items.append(ready_flag)
    return {
        "artifact": "clearinghouse_submission_evidence_validation_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safe_to_review": not any(
            item["requirement_id"] == "clearinghouse_submission_no_phi_secret_or_values"
            and item["status"] == "blocked"
            for item in requirements
        ),
        "clearinghouse_submission_ready": clearinghouse_submission_ready,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "requirements": requirements,
        "evidence": {
            "evidence_path": sanitize_report_value(str(evidence_path), REPO_ROOT),
            "runbook": "llm-distill/docs/clearinghouse-submission-runbook.md",
            "private_evidence_renderer": (
                "llm-distill/scripts/render_clearinghouse_submission_private_evidence.py"
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
        f"wrote clearinghouse submission evidence report to {args.report} "
        f"ready={report['clearinghouse_submission_ready']} "
        f"blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and report["blocked_item_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
