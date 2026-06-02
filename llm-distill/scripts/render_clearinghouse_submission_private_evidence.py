#!/usr/bin/env python3
"""Render private clearinghouse submission evidence without exposing values."""

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
PRIVATE_SUMMARY_ENV = "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_PRIVATE_SUMMARY_PATH"
PRIVATE_REFERENCE_ENVS = (
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENROLLMENT_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_CONNECTIVITY_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_TEST_TRANSACTION_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ACKNOWLEDGEMENT_REFERENCE",
    "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_GOVERNANCE_REFERENCE",
)
ALLOWED_SUMMARY_FIELDS = {
    "payer_or_clearinghouse_enrollment_confirmed",
    "test_mode_credentials_configured_privately",
    "encrypted_transit_validated",
    "production_endpoint_configured_privately",
    "source_control_credentials_absent",
    "edi_837_submission_contract_validated",
    "control_number_management_reviewed",
    "acknowledgement_999_277ca_handling_validated",
    "rejection_retry_and_duplicate_controls_reviewed",
    "rollback_to_non_submission_mode_reviewed",
    "metadata_only_audit_logging_reviewed",
    "access_controls_reviewed",
    "retention_policy_reviewed",
    "no_raw_edi_or_phi_logs_attested",
    "approval_or_risk_acceptance_private",
    "metadata_only_audit_reviewed",
    "no_phi_or_secret_values_included",
    "no_raw_edi_payloads_included",
    "no_payer_portal_credential_values_included",
    "no_approval_reference_values_included",
    "private_reference_count",
    "payer_count",
    "test_transaction_count",
    "acknowledgement_test_count",
}
REQUIRED_READY_SUMMARY_FLAGS = (
    "payer_or_clearinghouse_enrollment_confirmed",
    "test_mode_credentials_configured_privately",
    "encrypted_transit_validated",
    "production_endpoint_configured_privately",
    "source_control_credentials_absent",
    "edi_837_submission_contract_validated",
    "control_number_management_reviewed",
    "acknowledgement_999_277ca_handling_validated",
    "rejection_retry_and_duplicate_controls_reviewed",
    "rollback_to_non_submission_mode_reviewed",
    "metadata_only_audit_logging_reviewed",
    "access_controls_reviewed",
    "retention_policy_reviewed",
    "no_raw_edi_or_phi_logs_attested",
    "approval_or_risk_acceptance_private",
    "no_phi_or_secret_values_included",
    "no_raw_edi_payloads_included",
    "no_payer_portal_credential_values_included",
    "no_approval_reference_values_included",
)
REQUIRED_POSITIVE_SUMMARY_COUNTS = (
    "private_reference_count",
    "payer_count",
    "test_transaction_count",
    "acknowledgement_test_count",
)


@dataclass(frozen=True)
class RenderConfig:
    output: Path
    approved_mode: bool
    payer_or_clearinghouse_enrollment_confirmed: bool
    test_mode_credentials_configured_privately: bool
    encrypted_transit_validated: bool
    production_endpoint_configured_privately: bool
    source_control_credentials_absent: bool
    edi_837_submission_contract_validated: bool
    control_number_management_reviewed: bool
    acknowledgement_999_277ca_handling_validated: bool
    rejection_retry_and_duplicate_controls_reviewed: bool
    rollback_to_non_submission_mode_reviewed: bool
    metadata_only_audit_logging_reviewed: bool
    access_controls_reviewed: bool
    retention_policy_reviewed: bool
    no_raw_edi_or_phi_logs_attested: bool
    approval_or_risk_acceptance_private: bool
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
        return {}, ["private clearinghouse submission summary path is not configured"]
    summary_path = Path(path_value).expanduser()
    if path_is_inside_source_control(summary_path):
        return {}, ["private clearinghouse submission summary path must not be inside source control"]
    if not summary_path.exists():
        return {}, ["private clearinghouse submission summary file is missing"]
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, ["private clearinghouse submission summary JSON is invalid"]
    if not isinstance(payload, dict):
        return {}, ["private clearinghouse submission summary must be a JSON object"]
    return payload, []


def _positive_int(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _validate_private_clearinghouse_submission_summary(
    payload: dict[str, Any],
    *,
    approved_mode: bool,
    expected_reference_count: int,
) -> list[str]:
    blockers: list[str] = []
    unsupported = sorted(set(payload) - ALLOWED_SUMMARY_FIELDS)
    if unsupported:
        blockers.append("unsupported fields in private clearinghouse submission summary")
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
        blockers.append("private clearinghouse submission summary private reference count mismatch")
    if payload.get("no_raw_edi_payloads_included") is not True:
        blockers.append("raw EDI payloads are included or unverified")
    if payload.get("no_payer_portal_credential_values_included") is not True:
        blockers.append("payer portal credential values are included or unverified")
    if payload.get("no_approval_reference_values_included") is not True:
        blockers.append("approval reference values are included or unverified")
    return blockers


def _require_approved_mode_flags(config: RenderConfig) -> list[str]:
    if not config.approved_mode:
        return []
    required = {
        "payer_or_clearinghouse_enrollment_confirmed": (
            config.payer_or_clearinghouse_enrollment_confirmed
        ),
        "test_mode_credentials_configured_privately": (
            config.test_mode_credentials_configured_privately
        ),
        "encrypted_transit_validated": config.encrypted_transit_validated,
        "production_endpoint_configured_privately": (
            config.production_endpoint_configured_privately
        ),
        "source_control_credentials_absent": config.source_control_credentials_absent,
        "edi_837_submission_contract_validated": (
            config.edi_837_submission_contract_validated
        ),
        "control_number_management_reviewed": config.control_number_management_reviewed,
        "acknowledgement_999_277ca_handling_validated": (
            config.acknowledgement_999_277ca_handling_validated
        ),
        "rejection_retry_and_duplicate_controls_reviewed": (
            config.rejection_retry_and_duplicate_controls_reviewed
        ),
        "rollback_to_non_submission_mode_reviewed": (
            config.rollback_to_non_submission_mode_reviewed
        ),
        "metadata_only_audit_logging_reviewed": config.metadata_only_audit_logging_reviewed,
        "access_controls_reviewed": config.access_controls_reviewed,
        "retention_policy_reviewed": config.retention_policy_reviewed,
        "no_raw_edi_or_phi_logs_attested": config.no_raw_edi_or_phi_logs_attested,
        "approval_or_risk_acceptance_private": config.approval_or_risk_acceptance_private,
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
        _validate_private_clearinghouse_submission_summary(
            summary_payload,
            approved_mode=config.approved_mode,
            expected_reference_count=len(configured_reference_envs),
        )
    )
    if config.approved_mode and len(configured_reference_envs) != len(PRIVATE_REFERENCE_ENVS):
        blockers.append("all private clearinghouse submission reference environment variables are required")

    ready = config.approved_mode and not blockers
    return {
        "artifact": "claimguard_clearinghouse_submission_evidence",
        "version": "1.0",
        "evidence_status": "clearinghouse_submission_ready" if ready else "draft_not_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clearinghouse_submission_ready": ready,
        "approved_mode_requested": config.approved_mode,
        "blockers": blockers,
        "no_phi_or_secret_values_attested": config.no_raw_values_attested,
        "no_raw_edi_payloads_attested": config.no_raw_values_attested,
        "no_payer_portal_credential_values_attested": config.no_raw_values_attested,
        "no_approval_reference_values_attested": config.no_raw_values_attested,
        "private_reference_env_vars": list(PRIVATE_REFERENCE_ENVS),
        "private_reference_value_count": len(configured_reference_envs),
        "private_reference_values_included": False,
        "private_clearinghouse_submission_summary_path_env": PRIVATE_SUMMARY_ENV,
        "private_clearinghouse_submission_summary_path_configured": bool(summary_path_value.strip()),
        "private_clearinghouse_submission_summary_path_value_included": False,
        "private_clearinghouse_submission_summary_checked": not summary_errors,
        "private_clearinghouse_submission_summary_private_reference_count": summary_payload.get(
            "private_reference_count",
            0,
        ),
        "private_clearinghouse_submission_summary_payer_count": summary_payload.get(
            "payer_count",
            0,
        ),
        "private_clearinghouse_submission_summary_test_transaction_count": summary_payload.get(
            "test_transaction_count",
            0,
        ),
        "private_clearinghouse_submission_summary_acknowledgement_test_count": (
            summary_payload.get("acknowledgement_test_count", 0)
        ),
        "private_clearinghouse_submission_summary_raw_values_included": False,
        "connectivity_controls": {
            "payer_or_clearinghouse_enrollment_confirmed": (
                config.payer_or_clearinghouse_enrollment_confirmed
            ),
            "test_mode_credentials_configured_privately": (
                config.test_mode_credentials_configured_privately
            ),
            "encrypted_transit_validated": config.encrypted_transit_validated,
            "production_endpoint_configured_privately": (
                config.production_endpoint_configured_privately
            ),
            "source_control_credentials_absent": config.source_control_credentials_absent,
        },
        "submission_controls": {
            "edi_837_submission_contract_validated": config.edi_837_submission_contract_validated,
            "control_number_management_reviewed": config.control_number_management_reviewed,
            "acknowledgement_999_277ca_handling_validated": (
                config.acknowledgement_999_277ca_handling_validated
            ),
            "rejection_retry_and_duplicate_controls_reviewed": (
                config.rejection_retry_and_duplicate_controls_reviewed
            ),
            "rollback_to_non_submission_mode_reviewed": (
                config.rollback_to_non_submission_mode_reviewed
            ),
        },
        "audit_retention_controls": {
            "metadata_only_audit_logging_reviewed": config.metadata_only_audit_logging_reviewed,
            "access_controls_reviewed": config.access_controls_reviewed,
            "retention_policy_reviewed": config.retention_policy_reviewed,
            "no_raw_edi_or_phi_logs_attested": config.no_raw_edi_or_phi_logs_attested,
        },
        "governance_controls": {
            "approval_or_risk_acceptance_private": config.approval_or_risk_acceptance_private,
            "metadata_only_audit_reviewed": config.metadata_only_audit_logging_reviewed,
            "source_control_runbook_documented": True,
            "runbook_path": "llm-distill/docs/clearinghouse-submission-runbook.md",
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_clearinghouse_submission_private_evidence.py"
            ),
        },
        "values_redacted": True,
    }


def write_private_evidence(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # 0600 keeps private clearinghouse evidence readable only by the operator.
    output.chmod(stat.S_IRUSR | stat.S_IWUSR)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-mode", action="store_true")
    for flag in (
        "payer-or-clearinghouse-enrollment-confirmed",
        "test-mode-credentials-configured-privately",
        "encrypted-transit-validated",
        "production-endpoint-configured-privately",
        "source-control-credentials-absent",
        "edi-837-submission-contract-validated",
        "control-number-management-reviewed",
        "acknowledgement-999-277ca-handling-validated",
        "rejection-retry-and-duplicate-controls-reviewed",
        "rollback-to-non-submission-mode-reviewed",
        "metadata-only-audit-logging-reviewed",
        "access-controls-reviewed",
        "retention-policy-reviewed",
        "no-raw-edi-or-phi-logs-attested",
        "approval-or-risk-acceptance-private",
        "no-raw-values-attested",
    ):
        parser.add_argument(f"--{flag}", action="store_true")
    args = parser.parse_args()
    config = RenderConfig(
        output=args.output,
        approved_mode=args.approved_mode,
        payer_or_clearinghouse_enrollment_confirmed=(
            args.payer_or_clearinghouse_enrollment_confirmed
        ),
        test_mode_credentials_configured_privately=(
            args.test_mode_credentials_configured_privately
        ),
        encrypted_transit_validated=args.encrypted_transit_validated,
        production_endpoint_configured_privately=args.production_endpoint_configured_privately,
        source_control_credentials_absent=args.source_control_credentials_absent,
        edi_837_submission_contract_validated=args.edi_837_submission_contract_validated,
        control_number_management_reviewed=args.control_number_management_reviewed,
        acknowledgement_999_277ca_handling_validated=(
            args.acknowledgement_999_277ca_handling_validated
        ),
        rejection_retry_and_duplicate_controls_reviewed=(
            args.rejection_retry_and_duplicate_controls_reviewed
        ),
        rollback_to_non_submission_mode_reviewed=args.rollback_to_non_submission_mode_reviewed,
        metadata_only_audit_logging_reviewed=args.metadata_only_audit_logging_reviewed,
        access_controls_reviewed=args.access_controls_reviewed,
        retention_policy_reviewed=args.retention_policy_reviewed,
        no_raw_edi_or_phi_logs_attested=args.no_raw_edi_or_phi_logs_attested,
        approval_or_risk_acceptance_private=args.approval_or_risk_acceptance_private,
        no_raw_values_attested=args.no_raw_values_attested,
    )
    payload = render_private_evidence(config)
    if payload["blockers"]:
        print(json.dumps({"ready": False, "blockers": payload["blockers"]}, indent=2))
        return 2
    write_private_evidence(args.output, payload)
    print(
        json.dumps(
            {
                "ready": payload["clearinghouse_submission_ready"],
                "private_reference_value_count": payload["private_reference_value_count"],
                "values_redacted": payload["values_redacted"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
