#!/usr/bin/env python3
"""Validate PHIplan manual production-gate evidence without storing values."""

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
DEFAULT_PACKET = DISTILL_DIR / "data" / "production_gate_evidence" / "manual_gate_packet.template.json"
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "phi_plan_manual_gate_packet_report.json"
DEFAULT_MANUAL_GATE_CHECKLIST = (
    DISTILL_DIR / "docs" / "phi-plan-manual-production-gate-checklist.md"
)
MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS = [
    "Current status: manual production gate not ready.",
    "student default cutover approval required",
    "user-data model improvement legal/BAA/consent approval required",
    "approved non-synthetic denial/appeal pair required",
    "production semantic vector backend required",
    "production threshold/fairness monitoring evidence required",
    "file-ingestion surface audit must stay ready",
    "boolean-only evidence",
    "approval references must stay outside source control",
    "no PHI or production document content",
    "production_gate_ready=false",
]
ACCEPTED_PRODUCTION_SOURCE_TYPES = {
    "real_deidentified_pair",
    "real_world_deidentified_pair",
    "public_government_deidentified_pair",
    "public_government_denial_appeal_pair",
    "approved_public_denial_appeal_pair",
}
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
    "consent_notice_version_configured",
}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing packet: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def bool_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is True


def count_value(section: dict[str, Any], key: str) -> int:
    value = section.get(key)
    if isinstance(value, int):
        return value
    return 0


def list_value(section: dict[str, Any], key: str) -> list[Any]:
    value = section.get(key)
    return value if isinstance(value, list) else []


def resolve_repo_path(raw_path: Any, default_path: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return default_path
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


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


def packet_format_requirement(packet: Any) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(packet, dict):
        blockers.append("packet must be a JSON object")
        packet = {}
    if packet.get("artifact") != "claimguard_phi_plan_manual_gate_packet":
        blockers.append("artifact must be claimguard_phi_plan_manual_gate_packet")
    for section_name in [
        "student_default_cutover",
        "user_data_model_improvement",
        "production_corpus",
        "retrieval_vector_backend",
        "prediction_fairness_monitoring",
        "file_ingestion_surface_audit",
    ]:
        if not isinstance(packet.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="manual_gate_packet_format",
        name="Manual production-gate packet has the required structure",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "artifact": packet.get("artifact") if isinstance(packet, dict) else None,
            "version_configured": bool(packet.get("version")) if isinstance(packet, dict) else False,
            "packet_status": packet.get("packet_status") if isinstance(packet, dict) else None,
        },
    )


def no_phi_or_secret_values_requirement(packet_path: Path, packet: Any) -> dict[str, Any]:
    text = packet_path.read_text(encoding="utf-8") if packet_path.exists() else ""
    phi_findings = scan_text(packet_path, text) if text else []
    forbidden_key_findings = find_forbidden_value_keys(packet)
    attested = bool_value(packet, "no_phi_or_secret_values_attested") if isinstance(packet, dict) else False
    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(f"packet contains PHI/PII-like metadata findings: {finding_types}")
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    if not attested:
        blockers.append("no_phi_or_secret_values_attested is not true")

    return requirement(
        requirement_id="manual_gate_packet_no_phi_or_secret_values",
        name="Manual gate packet contains no PHI, secrets, or raw approval values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "packet_path": str(packet_path),
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            "no_phi_or_secret_values_attested": attested,
            "values_redacted": True,
        },
    )


def manual_gate_checklist_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    documented = bool_value(packet, "source_control_manual_gate_checklist_documented")
    checklist_path = resolve_repo_path(
        packet.get("manual_gate_checklist_path"),
        DEFAULT_MANUAL_GATE_CHECKLIST,
    )
    checklist_exists = checklist_path.exists()
    checklist_marker_count = 0
    missing_checklist_markers: list[str] = []
    blockers: list[str] = []
    if not documented:
        blockers.append("source_control_manual_gate_checklist_not_documented")
    if documented:
        if not checklist_exists:
            blockers.append("manual_gate_checklist_document_missing")
        else:
            checklist_text = checklist_path.read_text(encoding="utf-8")
            missing_checklist_markers = [
                marker
                for marker in MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS
                if marker.lower() not in checklist_text.lower()
            ]
            checklist_marker_count = (
                len(MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS)
                - len(missing_checklist_markers)
            )
            if missing_checklist_markers:
                blockers.append("manual_gate_checklist_required_markers_missing")
    return requirement(
        requirement_id="manual_gate_packet_completion_checklist",
        name="Source-controlled PHIplan manual production-gate checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_manual_gate_checklist_documented": documented,
            "manual_gate_checklist_path": str(checklist_path),
            "manual_gate_checklist_exists": checklist_exists,
            "manual_gate_checklist_required_marker_count": len(
                MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS
            ),
            "manual_gate_checklist_present_marker_count": checklist_marker_count,
            "manual_gate_checklist_missing_marker_count": len(
                missing_checklist_markers
            ),
            "manual_gate_checklist_values_included": False,
        },
    )


def student_cutover_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    section = packet.get("student_default_cutover", {})
    blockers: list[str] = []
    required_flags = {
        "requested": "student_default_cutover_not_requested",
        "raphael_approval_attested": "raphael_cutover_approval_not_attested",
        "approval_reference_configured": "student_cutover_approval_reference_not_configured",
        "supervisor_evidence_report_ready": "supervisor_evidence_report_not_ready",
        "supervised_runtime_owner_configured": "supervised_runtime_owner_not_configured",
        "source_control_runbook_documented": "source_control_runbook_not_documented",
        "source_control_runtime_validation_checklist_documented": "source_control_runtime_validation_checklist_not_documented",
        "source_control_runtime_owner_handoff_checklist_documented": "source_control_runtime_owner_handoff_checklist_not_documented",
        "supervised_runtime_runbook_reviewed": "supervised_runtime_runbook_not_reviewed",
        "rollback_to_nvidia_reviewed": "rollback_to_nvidia_not_reviewed",
        "scope_limited_to_denial_workflow_and_appeals": "student_scope_not_limited_to_denial_workflow_and_appeals",
    }
    for key, blocker in required_flags.items():
        if not bool_value(section, key):
            blockers.append(blocker)
    return requirement(
        requirement_id="manual_student_default_cutover_evidence",
        name="Manual packet attests student default cutover approval and supervised runtime ownership",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            key: bool_value(section, key)
            for key in required_flags
        },
    )


def model_improvement_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    section = packet.get("user_data_model_improvement", {})
    blockers: list[str] = []
    required_flags = {
        "requested": "model_improvement_not_requested",
        "source_control_approval_runbook_documented": "model_improvement_source_control_approval_runbook_not_documented",
        "legal_approval_attested": "legal_approval_not_attested",
        "baa_confirmed": "baa_not_confirmed",
        "consent_notice_version_configured": "consent_notice_version_not_configured",
        "approval_reference_configured": "model_improvement_approval_reference_not_configured",
        "model_improvement_evidence_report_ready": "model_improvement_evidence_report_not_ready",
        "data_use_scope_documented": "data_use_scope_not_documented",
        "per_request_attestations_required": "per_request_attestations_not_required",
    }
    for key, blocker in required_flags.items():
        if not bool_value(section, key):
            blockers.append(blocker)
    return requirement(
        requirement_id="manual_user_data_model_improvement_evidence",
        name="Manual packet attests user-data model-improvement legal, BAA, and consent gates",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            key: bool_value(section, key)
            for key in required_flags
        },
    )


def production_corpus_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    section = packet.get("production_corpus", {})
    approved_source_types = [str(item) for item in list_value(section, "approved_source_types")]
    manifest_record_ids = [str(item) for item in list_value(section, "manifest_record_ids")]
    pair_count = count_value(section, "approved_non_synthetic_pair_count")
    blockers: list[str] = []
    if pair_count < 1:
        blockers.append("approved_non_synthetic_pair_count_must_be_at_least_1")
    if not approved_source_types:
        blockers.append("approved_source_types_missing")
    unknown_types = sorted(set(approved_source_types) - ACCEPTED_PRODUCTION_SOURCE_TYPES)
    if unknown_types:
        blockers.append(f"approved_source_types_not_accepted: {unknown_types}")
    if len(manifest_record_ids) < pair_count * 2:
        blockers.append("manifest_record_ids_missing_for_denial_appeal_pairs")
    if not bool_value(section, "production_corpus_evidence_report_ready"):
        blockers.append("production_corpus_evidence_report_not_ready")
    for key, blocker in {
        "source_control_review_runbook_documented": "production_corpus_source_control_review_runbook_not_documented",
        "source_control_collection_license_checklist_documented": "production_corpus_collection_license_checklist_not_documented",
        "source_control_pair_source_checklist_documented": "production_corpus_pair_source_checklist_not_documented",
        "privacy_review_attested": "privacy_review_not_attested",
        "license_review_attested": "license_review_not_attested",
        "residual_risk_review_attested": "residual_risk_review_not_attested",
        "training_scope_reviewed": "training_scope_not_reviewed",
    }.items():
        if not bool_value(section, key):
            blockers.append(blocker)
    return requirement(
        requirement_id="manual_production_corpus_evidence",
        name="Manual packet attests approved non-synthetic paired corpus evidence",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "approved_non_synthetic_pair_count": pair_count,
            "approved_source_types": approved_source_types,
            "manifest_record_id_count": len(manifest_record_ids),
            "production_corpus_evidence_report_ready": bool_value(section, "production_corpus_evidence_report_ready"),
            "source_control_review_runbook_documented": bool_value(section, "source_control_review_runbook_documented"),
            "source_control_collection_license_checklist_documented": bool_value(section, "source_control_collection_license_checklist_documented"),
            "source_control_pair_source_checklist_documented": bool_value(section, "source_control_pair_source_checklist_documented"),
            "privacy_review_attested": bool_value(section, "privacy_review_attested"),
            "license_review_attested": bool_value(section, "license_review_attested"),
            "residual_risk_review_attested": bool_value(section, "residual_risk_review_attested"),
            "training_scope_reviewed": bool_value(section, "training_scope_reviewed"),
        },
    )


def retrieval_vector_backend_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    section = packet.get("retrieval_vector_backend", {})
    required_flags = {
        "vector_backend_evidence_report_ready": "retrieval_vector_backend_evidence_report_not_ready",
        "source_control_runbook_documented": "retrieval_vector_source_control_runbook_not_documented",
        "source_control_reindex_checklist_documented": "retrieval_reindex_checklist_not_documented",
        "source_control_runtime_smoke_checklist_documented": "retrieval_runtime_smoke_checklist_not_documented",
        "semantic_backend_configured": "semantic_backend_not_attested",
        "production_vector_backend_configured": "production_vector_backend_not_attested",
        "retrieval_chunks_reindexed": "retrieval_chunks_not_reindexed",
        "governance_controls_reviewed": "retrieval_governance_controls_not_reviewed",
        "runtime_validation_reviewed": "retrieval_runtime_validation_not_reviewed",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="manual_retrieval_vector_backend_evidence",
        name="Manual packet attests retrieval vector backend evidence and production readiness",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def prediction_fairness_monitoring_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    section = packet.get("prediction_fairness_monitoring", {})
    required_flags = {
        "prediction_fairness_evidence_report_ready": "prediction_fairness_evidence_report_not_ready",
        "approved_outcome_dataset_available": "approved_outcome_dataset_not_attested",
        "minimum_sample_size_met": "minimum_sample_size_not_attested",
        "threshold_review_completed": "threshold_review_not_attested",
        "source_control_calibration_checklist_documented": "prediction_fairness_source_control_calibration_checklist_not_documented",
        "approved_demographic_grouping_reviewed": "approved_demographic_grouping_not_reviewed",
        "continuous_monitoring_configured": "continuous_monitoring_not_attested",
        "disparity_thresholds_documented": "disparity_thresholds_not_documented",
        "alerting_and_review_owner_configured": "alerting_and_review_owner_not_configured",
        "latest_monitoring_run_passed": "latest_monitoring_run_not_passed",
        "legal_privacy_review_completed": "legal_privacy_review_not_attested",
        "source_control_legal_privacy_checklist_documented": "prediction_fairness_source_control_legal_privacy_checklist_not_documented",
        "source_control_monitoring_runbook_documented": "prediction_fairness_source_control_monitoring_runbook_not_documented",
        "source_control_monitoring_validation_checklist_documented": "prediction_fairness_source_control_monitoring_validation_checklist_not_documented",
        "model_card_updated": "model_card_not_updated",
        "model_card_required_markers_verified": "model_card_required_markers_not_verified",
        "rollback_or_threshold_reversion_reviewed": "rollback_or_threshold_reversion_not_reviewed",
        "audit_log_metadata_only_verified": "audit_log_metadata_only_not_verified",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="manual_prediction_fairness_monitoring_evidence",
        name="Manual packet attests production threshold calibration and continuous fairness monitoring evidence",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def file_ingestion_surface_requirement(packet: dict[str, Any]) -> dict[str, Any]:
    section = packet.get("file_ingestion_surface_audit", {})
    expected_count = count_value(section, "expected_upload_surface_count")
    registered_count = count_value(section, "registered_upload_surface_count")
    unregistered_count = count_value(section, "unregistered_upload_surface_count")
    blockers: list[str] = []
    if not bool_value(section, "file_ingestion_surface_report_ready"):
        blockers.append("file_ingestion_surface_report_not_ready")
    if expected_count < 1:
        blockers.append("expected_upload_surface_count_missing")
    if registered_count < expected_count:
        blockers.append("registered_upload_surface_count_below_expected")
    if unregistered_count != 0:
        blockers.append("unregistered_upload_surface_count_must_be_zero")
    for key, blocker in {
        "metadata_only_surface_inspection_attested": "metadata_only_surface_inspection_not_attested",
        "safe_audit_marker_coverage_attested": "safe_audit_marker_coverage_not_attested",
    }.items():
        if not bool_value(section, key):
            blockers.append(blocker)
    return requirement(
        requirement_id="manual_file_ingestion_surface_evidence",
        name="Manual packet attests automated file-ingestion PHI surface audit coverage",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "file_ingestion_surface_report_ready": bool_value(
                section, "file_ingestion_surface_report_ready"
            ),
            "expected_upload_surface_count": expected_count,
            "registered_upload_surface_count": registered_count,
            "unregistered_upload_surface_count": unregistered_count,
            "metadata_only_surface_inspection_attested": bool_value(
                section, "metadata_only_surface_inspection_attested"
            ),
            "safe_audit_marker_coverage_attested": bool_value(
                section, "safe_audit_marker_coverage_attested"
            ),
        },
    )


def build_report(packet_path: Path) -> dict[str, Any]:
    packet, load_errors = load_json(packet_path)
    if packet is None:
        packet = {}
    requirements = [
        packet_format_requirement(packet),
        no_phi_or_secret_values_requirement(packet_path, packet),
        manual_gate_checklist_requirement(packet if isinstance(packet, dict) else {}),
        student_cutover_requirement(packet if isinstance(packet, dict) else {}),
        model_improvement_requirement(packet if isinstance(packet, dict) else {}),
        production_corpus_requirement(packet if isinstance(packet, dict) else {}),
        retrieval_vector_backend_requirement(packet if isinstance(packet, dict) else {}),
        prediction_fairness_monitoring_requirement(packet if isinstance(packet, dict) else {}),
        file_ingestion_surface_requirement(packet if isinstance(packet, dict) else {}),
    ]
    if load_errors:
        requirements.insert(
            0,
            requirement(
                requirement_id="manual_gate_packet_load",
                name="Manual production-gate packet can be loaded",
                status="blocked",
                blockers=load_errors,
                evidence={"packet_path": str(packet_path)},
            ),
        )
    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    ready_items = [item for item in requirements if item["status"] == "ready"]
    safe_to_review = not any(
        item["requirement_id"] in {
            "manual_gate_packet_load",
            "manual_gate_packet_format",
            "manual_gate_packet_no_phi_or_secret_values",
        }
        and item["status"] == "blocked"
        for item in requirements
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Validate the manual PHIplan production-gate packet without storing "
            "approval reference values, PHI, secrets, or production document content."
        ),
        "packet_path": str(packet_path),
        "safe_to_review": safe_to_review,
        "production_gate_ready": not blocked_items,
        "blocked_item_count": len(blocked_items),
        "ready_item_count": len(ready_items),
        "blocked_items": blocked_items,
        "requirements": requirements,
        "notes": [
            "This validator reads a local JSON packet only and does not call external services.",
            "Approval references and consent values must remain in approved runtime configuration; this packet records only boolean readiness evidence.",
            "A template packet is expected to be safe_to_review=true but production_gate_ready=false until Raphael, legal/BAA, corpus, retrieval-vector, fairness-monitoring, and runtime-supervisor gates are complete.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.packet)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.report} production_gate_ready={report['production_gate_ready']} "
        f"safe_to_review={report['safe_to_review']} blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and report["blocked_item_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
