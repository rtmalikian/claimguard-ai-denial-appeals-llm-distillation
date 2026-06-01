#!/usr/bin/env python3
"""Validate prediction fairness monitoring evidence without storing values."""

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
DEFAULT_EVIDENCE = (
    DISTILL_DIR
    / "data"
    / "prediction_fairness_evidence"
    / "fairness_monitoring_evidence.template.json"
)
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "prediction_fairness_evidence_report.json"
EXPECTED_ARTIFACT = "claimguard_prediction_fairness_monitoring_evidence"
DEFAULT_MODEL_CARD = DISTILL_DIR / "docs" / "prediction-fairness-model-card.md"
DEFAULT_RUNBOOK = DISTILL_DIR / "docs" / "prediction-fairness-monitoring-runbook.md"
DEFAULT_CALIBRATION_CHECKLIST = (
    DISTILL_DIR / "docs" / "prediction-fairness-calibration-checklist.md"
)
DEFAULT_MONITORING_VALIDATION_CHECKLIST = (
    DISTILL_DIR / "docs" / "prediction-fairness-monitoring-validation-checklist.md"
)
DEFAULT_LEGAL_PRIVACY_CHECKLIST = (
    DISTILL_DIR / "docs" / "prediction-fairness-legal-privacy-checklist.md"
)
DEFAULT_PRIVATE_EVIDENCE_RENDERER = (
    DISTILL_DIR / "scripts" / "render_prediction_fairness_private_evidence.py"
)
MODEL_CARD_REQUIRED_MARKERS = [
    "Current status: not production-ready.",
    "Human-review routing threshold only.",
    "No auto-denial threshold.",
    "Approved real-world outcome data required.",
    "Calibration required before production threshold changes.",
    "Continuous fairness monitoring required before production use.",
    "no raw demographic values",
    "Reports must not include raw demographic values",
]
RUNBOOK_REQUIRED_MARKERS = [
    "Current status: not production-ready.",
    "Approved outcome dataset required.",
    "Minimum sample size required.",
    "Calibration run required before threshold changes.",
    "Continuous monitoring configuration required.",
    "Disparity thresholds and alert owner required.",
    "Latest monitoring run required.",
    "Legal/privacy review required.",
    "Rollback or threshold reversion required.",
    "no raw demographic values",
    "production outcome rows must stay outside source control",
    "boolean-only evidence",
]
CALIBRATION_CHECKLIST_REQUIRED_MARKERS = [
    "Current status: not calibrated for production.",
    "approved outcome dataset required",
    "minimum sample size required",
    "calibration run required before threshold changes",
    "threshold review required for human-review routing",
    "human-review routing only",
    "no auto-denial threshold",
    "approved demographic grouping review required",
    "legal/privacy review required",
    "rollback or threshold reversion required",
    "boolean-only evidence",
    "production outcome rows must stay outside source control",
    "no raw demographic values",
    "prediction_fairness_monitoring_ready=false",
]
MONITORING_VALIDATION_CHECKLIST_REQUIRED_MARKERS = [
    "Current status: not validated for production.",
    "approved demographic grouping review required",
    "continuous monitoring configuration required",
    "disparity thresholds documented",
    "alerting and review owner required",
    "latest monitoring run required",
    "legal/privacy review required",
    "rollback or threshold reversion required",
    "boolean-only evidence",
    "production outcome rows must stay outside source control",
    "no raw demographic values",
    "prediction_fairness_monitoring_ready=false",
]
LEGAL_PRIVACY_CHECKLIST_REQUIRED_MARKERS = [
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: legal/privacy review not complete for production fairness monitoring.",
    "legal/privacy review required",
    "approved outcome dataset required",
    "approved demographic grouping review required",
    "minimum sample size required",
    "human-review routing only",
    "no auto-denial threshold",
    "production outcome rows must stay outside source control",
    "raw demographic values must stay outside source control",
    "approval references must stay outside source control",
    "rollback or threshold reversion required",
    "boolean-only evidence",
    "no raw demographic values",
    "no production outcome rows",
    "no individual identifiers",
    "no approval reference values",
    "no legal document text",
    "no BAA document text",
    "no consent document text",
    "prediction_fairness_monitoring_ready=false",
]
PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS = [
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "PREDICTION_FAIRNESS_OUTCOME_DATASET_REFERENCE",
    "PREDICTION_FAIRNESS_THRESHOLD_REVIEW_REFERENCE",
    "PREDICTION_FAIRNESS_DEMOGRAPHIC_GROUPING_REFERENCE",
    "PREDICTION_FAIRNESS_MONITORING_CONFIG_REFERENCE",
    "PREDICTION_FAIRNESS_ALERT_OWNER_REFERENCE",
    "PREDICTION_FAIRNESS_LATEST_RUN_REFERENCE",
    "PREDICTION_FAIRNESS_LEGAL_PRIVACY_REFERENCE",
    "PREDICTION_FAIRNESS_PRIVATE_MONITORING_SUMMARY_PATH",
    "_validate_private_monitoring_summary",
    "approved_outcome_dataset_available",
    "latest_monitoring_run_passed",
    "private_monitoring_summary_checked",
    "private_monitoring_summary_private_reference_count",
    "private_monitoring_summary_path_value_included",
    "private_monitoring_summary_evaluated_outcome_count",
    "private_monitoring_summary_monitored_group_count",
    "private_monitoring_summary_disparity_metric_count",
    "private_monitoring_summary_alert_rule_count",
    "private_monitoring_summary_raw_values_included",
    "private monitoring summary private reference count mismatch",
    "unsupported fields",
    "raw_private_values_included",
    "raw_demographic_values_included",
    "production_outcome_rows_included",
    "0600",
    "values_redacted",
]
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "address",
    "approval_reference",
    "claim_id",
    "credential",
    "birth_date",
    "date_of_birth",
    "demographic_value",
    "document_content",
    "email",
    "identifier",
    "individual",
    "member",
    "name",
    "outcome_row",
    "password",
    "phone",
    "raw_claim",
    "raw_demographic",
    "raw_document",
    "record_content",
    "secret",
    "token",
    "user_data",
}
ALLOWED_BOOLEAN_FLAG_KEYS = {
    "no_phi_or_secret_values_attested",
    "no_production_outcome_rows_attested",
    "no_raw_demographic_values_attested",
    "audit_log_metadata_only_verified",
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
                key_lower not in ALLOWED_BOOLEAN_FLAG_KEYS
                and any(fragment in key_lower for fragment in FORBIDDEN_VALUE_KEY_FRAGMENTS)
                and not isinstance(child, bool)
                and child not in (None, "", [])
            ):
                findings.append(
                    f"{child_path}: raw demographic, outcome, identifier, secret, or document value key is not allowed"
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
    for section_name in [
        "calibrated_threshold",
        "fairness_monitoring",
        "governance_controls",
    ]:
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="prediction_fairness_evidence_format",
        name="Prediction fairness monitoring evidence has the required structure",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "artifact": evidence.get("artifact") if isinstance(evidence, dict) else None,
            "version_configured": bool(evidence.get("version")) if isinstance(evidence, dict) else False,
            "evidence_status": evidence.get("evidence_status") if isinstance(evidence, dict) else None,
        },
    )


def no_values_requirement(evidence_path: Path, evidence: Any) -> dict[str, Any]:
    evidence_text = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else ""
    phi_findings = scan_text(evidence_path, evidence_text) if evidence_text else []
    forbidden_key_findings = find_forbidden_value_keys(evidence)
    if not isinstance(evidence, dict):
        evidence = {}
    no_phi_attested = bool_value(evidence, "no_phi_or_secret_values_attested")
    no_raw_demographic_attested = bool_value(evidence, "no_raw_demographic_values_attested")
    no_outcome_rows_attested = bool_value(evidence, "no_production_outcome_rows_attested")

    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(
            f"prediction fairness evidence contains PHI/PII-like metadata findings: {finding_types}"
        )
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    if not no_phi_attested:
        blockers.append("no_phi_or_secret_values_attested is not true")
    if not no_raw_demographic_attested:
        blockers.append("no_raw_demographic_values_attested is not true")
    if not no_outcome_rows_attested:
        blockers.append("no_production_outcome_rows_attested is not true")

    return requirement(
        requirement_id="prediction_fairness_no_phi_secret_or_values",
        name="Prediction fairness evidence contains no PHI, secrets, raw demographic values, or outcome rows",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "evidence_path": str(evidence_path),
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            "no_phi_or_secret_values_attested": no_phi_attested,
            "no_raw_demographic_values_attested": no_raw_demographic_attested,
            "no_production_outcome_rows_attested": no_outcome_rows_attested,
            "values_redacted": True,
        },
    )


def calibrated_threshold_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("calibrated_threshold", {})
    required_flags = {
        "approved_outcome_dataset_available": "approved_outcome_dataset_missing",
        "minimum_sample_size_met": "minimum_sample_size_not_met",
        "calibration_run_completed": "calibration_run_not_completed",
        "threshold_review_completed": "threshold_review_not_completed",
        "human_review_policy_confirmed": "human_review_policy_not_confirmed",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="prediction_fairness_calibrated_threshold",
        name="Production denial-risk threshold is calibrated and reviewed on approved outcome data",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def calibration_checklist_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("calibrated_threshold", {})
    documented = bool_value(section, "source_control_calibration_checklist_documented")
    checklist_path = resolve_repo_path(
        section.get("calibration_checklist_path"),
        DEFAULT_CALIBRATION_CHECKLIST,
    )
    checklist_exists = checklist_path.exists()
    checklist_marker_count = 0
    missing_checklist_markers: list[str] = []
    blockers: list[str] = []
    if not documented:
        blockers.append("source_control_calibration_checklist_not_documented")
    if documented:
        if not checklist_exists:
            blockers.append("calibration_checklist_document_missing")
        else:
            checklist_text = checklist_path.read_text(encoding="utf-8")
            missing_checklist_markers = [
                marker
                for marker in CALIBRATION_CHECKLIST_REQUIRED_MARKERS
                if marker.lower() not in checklist_text.lower()
            ]
            checklist_marker_count = (
                len(CALIBRATION_CHECKLIST_REQUIRED_MARKERS)
                - len(missing_checklist_markers)
            )
            if missing_checklist_markers:
                blockers.append("calibration_checklist_required_markers_missing")
    return requirement(
        requirement_id="prediction_fairness_calibration_checklist",
        name="Source-controlled prediction fairness calibration checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_calibration_checklist_documented": documented,
            "calibration_checklist_path": str(checklist_path),
            "calibration_checklist_exists": checklist_exists,
            "calibration_checklist_required_marker_count": len(
                CALIBRATION_CHECKLIST_REQUIRED_MARKERS
            ),
            "calibration_checklist_present_marker_count": checklist_marker_count,
            "calibration_checklist_missing_marker_count": len(
                missing_checklist_markers
            ),
            "calibration_checklist_values_included": False,
        },
    )


def continuous_monitoring_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("fairness_monitoring", {})
    required_flags = {
        "approved_demographic_grouping_reviewed": "approved_demographic_grouping_not_reviewed",
        "continuous_monitoring_configured": "continuous_monitoring_not_configured",
        "disparity_thresholds_documented": "disparity_thresholds_not_documented",
        "alerting_and_review_owner_configured": "alerting_and_review_owner_not_configured",
        "latest_monitoring_run_passed": "latest_monitoring_run_not_passed",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="prediction_fairness_continuous_monitoring",
        name="Continuous production fairness monitoring is configured, owned, and passing",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def monitoring_validation_checklist_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("fairness_monitoring", {})
    documented = bool_value(
        section,
        "source_control_monitoring_validation_checklist_documented",
    )
    checklist_path = resolve_repo_path(
        section.get("monitoring_validation_checklist_path"),
        DEFAULT_MONITORING_VALIDATION_CHECKLIST,
    )
    checklist_exists = checklist_path.exists()
    checklist_marker_count = 0
    missing_checklist_markers: list[str] = []
    blockers: list[str] = []
    if not documented:
        blockers.append("source_control_monitoring_validation_checklist_not_documented")
    if documented:
        if not checklist_exists:
            blockers.append("monitoring_validation_checklist_document_missing")
        else:
            checklist_text = checklist_path.read_text(encoding="utf-8")
            missing_checklist_markers = [
                marker
                for marker in MONITORING_VALIDATION_CHECKLIST_REQUIRED_MARKERS
                if marker.lower() not in checklist_text.lower()
            ]
            checklist_marker_count = (
                len(MONITORING_VALIDATION_CHECKLIST_REQUIRED_MARKERS)
                - len(missing_checklist_markers)
            )
            if missing_checklist_markers:
                blockers.append("monitoring_validation_checklist_required_markers_missing")
    return requirement(
        requirement_id="prediction_fairness_monitoring_validation_checklist",
        name="Source-controlled prediction fairness monitoring validation checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_monitoring_validation_checklist_documented": documented,
            "monitoring_validation_checklist_path": str(checklist_path),
            "monitoring_validation_checklist_exists": checklist_exists,
            "monitoring_validation_checklist_required_marker_count": len(
                MONITORING_VALIDATION_CHECKLIST_REQUIRED_MARKERS
            ),
            "monitoring_validation_checklist_present_marker_count": checklist_marker_count,
            "monitoring_validation_checklist_missing_marker_count": len(
                missing_checklist_markers
            ),
            "monitoring_validation_checklist_values_included": False,
        },
    )


def monitoring_runbook_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    documented = bool_value(section, "source_control_monitoring_runbook_documented")
    runbook_path = resolve_repo_path(section.get("monitoring_runbook_path"), DEFAULT_RUNBOOK)
    runbook_exists = runbook_path.exists()
    runbook_marker_count = 0
    missing_runbook_markers: list[str] = []
    blockers: list[str] = []
    if not documented:
        blockers.append("source_control_monitoring_runbook_not_documented")
    if documented:
        if not runbook_exists:
            blockers.append("monitoring_runbook_document_missing")
        else:
            runbook_text = runbook_path.read_text(encoding="utf-8")
            missing_runbook_markers = [
                marker
                for marker in RUNBOOK_REQUIRED_MARKERS
                if marker.lower() not in runbook_text.lower()
            ]
            runbook_marker_count = (
                len(RUNBOOK_REQUIRED_MARKERS) - len(missing_runbook_markers)
            )
            if missing_runbook_markers:
                blockers.append("monitoring_runbook_required_markers_missing")
    return requirement(
        requirement_id="prediction_fairness_monitoring_runbook",
        name="Source-controlled prediction fairness monitoring runbook is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_monitoring_runbook_documented": documented,
            "monitoring_runbook_path": str(runbook_path),
            "monitoring_runbook_exists": runbook_exists,
            "monitoring_runbook_required_marker_count": len(RUNBOOK_REQUIRED_MARKERS),
            "monitoring_runbook_present_marker_count": runbook_marker_count,
            "monitoring_runbook_missing_marker_count": len(missing_runbook_markers),
            "monitoring_runbook_values_included": False,
        },
    )


def private_evidence_renderer_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    documented = bool_value(section, "source_control_private_evidence_renderer_documented")
    renderer_path = resolve_repo_path(
        str_value(section, "private_evidence_renderer_path"),
        DEFAULT_PRIVATE_EVIDENCE_RENDERER,
    )
    renderer_exists = renderer_path.exists()
    marker_count = 0
    missing_markers: list[str] = []
    blockers: list[str] = []
    if not documented:
        blockers.append("source_control_private_evidence_renderer_not_documented")
    if documented:
        if not renderer_exists:
            blockers.append("private_evidence_renderer_missing")
        else:
            renderer_text = renderer_path.read_text(encoding="utf-8")
            missing_markers = [
                marker
                for marker in PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS
                if marker not in renderer_text
            ]
            marker_count = (
                len(PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS)
                - len(missing_markers)
            )
            if missing_markers:
                blockers.append("private_evidence_renderer_required_markers_missing")
    return requirement(
        requirement_id="prediction_fairness_private_evidence_renderer",
        name="Source-controlled prediction fairness private evidence renderer is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_private_evidence_renderer_documented": documented,
            "private_evidence_renderer_path": str(renderer_path),
            "private_evidence_renderer_exists": renderer_exists,
            "private_evidence_renderer_required_marker_count": len(
                PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS
            ),
            "private_evidence_renderer_present_marker_count": marker_count,
            "private_evidence_renderer_missing_marker_count": len(missing_markers),
            "raw_renderer_text_included": False,
            "raw_private_values_included": False,
            "private_output_required": True,
            "values_redacted": True,
        },
    )


def legal_privacy_checklist_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    documented = bool_value(
        section,
        "source_control_legal_privacy_checklist_documented",
    )
    checklist_path = resolve_repo_path(
        section.get("legal_privacy_checklist_path"),
        DEFAULT_LEGAL_PRIVACY_CHECKLIST,
    )
    checklist_exists = checklist_path.exists()
    checklist_marker_count = 0
    missing_checklist_markers: list[str] = []
    blockers: list[str] = []
    if not documented:
        blockers.append("source_control_legal_privacy_checklist_not_documented")
    if documented:
        if not checklist_exists:
            blockers.append("legal_privacy_checklist_document_missing")
        else:
            checklist_text = checklist_path.read_text(encoding="utf-8")
            missing_checklist_markers = [
                marker
                for marker in LEGAL_PRIVACY_CHECKLIST_REQUIRED_MARKERS
                if marker.lower() not in checklist_text.lower()
            ]
            checklist_marker_count = (
                len(LEGAL_PRIVACY_CHECKLIST_REQUIRED_MARKERS)
                - len(missing_checklist_markers)
            )
            if missing_checklist_markers:
                blockers.append("legal_privacy_checklist_required_markers_missing")
    return requirement(
        requirement_id="prediction_fairness_legal_privacy_checklist",
        name="Source-controlled prediction fairness legal/privacy checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_legal_privacy_checklist_documented": documented,
            "legal_privacy_checklist_path": str(checklist_path),
            "legal_privacy_checklist_exists": checklist_exists,
            "legal_privacy_checklist_required_marker_count": len(
                LEGAL_PRIVACY_CHECKLIST_REQUIRED_MARKERS
            ),
            "legal_privacy_checklist_present_marker_count": checklist_marker_count,
            "legal_privacy_checklist_missing_marker_count": len(
                missing_checklist_markers
            ),
            "legal_privacy_checklist_values_included": False,
        },
    )


def governance_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    required_flags = {
        "legal_privacy_review_completed": "legal_privacy_review_not_completed",
        "source_control_legal_privacy_checklist_documented": (
            "source_control_legal_privacy_checklist_not_documented"
        ),
        "source_control_private_evidence_renderer_documented": (
            "source_control_private_evidence_renderer_not_documented"
        ),
        "model_card_updated": "model_card_not_updated",
        "rollback_or_threshold_reversion_reviewed": "rollback_or_threshold_reversion_not_reviewed",
        "audit_log_metadata_only_verified": "audit_log_metadata_only_not_verified",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    model_card_path = resolve_repo_path(section.get("model_card_path"), DEFAULT_MODEL_CARD)
    model_card_exists = model_card_path.exists()
    model_card_marker_count = 0
    missing_model_card_markers: list[str] = []
    if bool_value(section, "model_card_updated"):
        if not model_card_exists:
            blockers.append("model_card_document_missing")
        else:
            model_card_text = model_card_path.read_text(encoding="utf-8")
            missing_model_card_markers = [
                marker
                for marker in MODEL_CARD_REQUIRED_MARKERS
                if marker.lower() not in model_card_text.lower()
            ]
            model_card_marker_count = (
                len(MODEL_CARD_REQUIRED_MARKERS) - len(missing_model_card_markers)
            )
            if missing_model_card_markers:
                blockers.append("model_card_required_markers_missing")
    return requirement(
        requirement_id="prediction_fairness_governance_controls",
        name="Fairness monitoring governance, rollback, and metadata-only audit controls are complete",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            **{key: bool_value(section, key) for key in required_flags},
            "model_card_path": str(model_card_path),
            "model_card_exists": model_card_exists,
            "model_card_required_marker_count": len(MODEL_CARD_REQUIRED_MARKERS),
            "model_card_present_marker_count": model_card_marker_count,
            "model_card_missing_marker_count": len(missing_model_card_markers),
            "model_card_values_included": False,
        },
    )


def build_report(evidence_path: Path = DEFAULT_EVIDENCE) -> dict[str, Any]:
    evidence, errors = load_json(evidence_path)
    if errors:
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}

    requirements = [
        evidence_format_requirement(evidence),
        no_values_requirement(evidence_path, evidence),
        calibrated_threshold_requirement(evidence),
        calibration_checklist_requirement(evidence),
        continuous_monitoring_requirement(evidence),
        monitoring_validation_checklist_requirement(evidence),
        monitoring_runbook_requirement(evidence),
        legal_privacy_checklist_requirement(evidence),
        private_evidence_renderer_requirement(evidence),
        governance_controls_requirement(evidence),
    ]
    if errors:
        requirements[0]["blockers"].extend(errors)
        requirements[0]["status"] = "blocked"

    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    ready_item_count = sum(1 for item in requirements if item["status"] == "ready")
    safe_to_review = all(item["status"] == "ready" for item in requirements[:2])
    prediction_fairness_monitoring_ready = not blocked_items

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Validate production prediction-threshold calibration and continuous fairness "
            "monitoring evidence without storing PHI, secrets, raw demographic values, "
            "approval references, or production outcome rows."
        ),
        "evidence_path": str(evidence_path),
        "requirements": requirements,
        "ready_item_count": ready_item_count,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "safe_to_review": safe_to_review,
        "prediction_fairness_monitoring_ready": prediction_fairness_monitoring_ready,
        "notes": [
            "This validator reads a local JSON evidence packet only and does not call external outcome, legal, privacy, alerting, or model-card systems.",
            "Raw demographic values, production outcome rows, PHI, secrets, approval references, and individual identifiers must remain outside source control.",
            "A template evidence file is expected to be safe_to_review=true but prediction_fairness_monitoring_ready=false until approved outcome data, calibration, monitoring, and governance reviews are complete.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.evidence)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.report} "
        f"prediction_fairness_monitoring_ready={report['prediction_fairness_monitoring_ready']} "
        f"safe_to_review={report['safe_to_review']} blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and not report["prediction_fairness_monitoring_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
