#!/usr/bin/env python3
"""Render a private PHIplan manual gate packet without printing values."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = (
    REPO_ROOT
    / "llm-distill"
    / "data"
    / "production_gate_evidence"
    / "manual_gate_packet.template.json"
)
DEFAULT_OUTPUT = Path("/private/tmp/claimguard-phi-plan-manual-gate.private.packet.json")
DEFAULT_MANIFEST_RECORD_IDS_ENV = "PHI_PLAN_MANUAL_GATE_MANIFEST_RECORD_IDS"
DEFAULT_MANUAL_REVIEW_REFERENCE_ENV = "PHI_PLAN_MANUAL_GATE_REVIEW_REFERENCE"
DEFAULT_DEPENDENT_EVIDENCE_REFERENCE_ENV = (
    "PHI_PLAN_MANUAL_GATE_DEPENDENT_EVIDENCE_REFERENCE"
)
DEFAULT_RELEASE_REFERENCE_ENV = "PHI_PLAN_MANUAL_GATE_RELEASE_REFERENCE"
DEFAULT_BACKUP_DR_REFERENCE_ENV = "PHI_PLAN_MANUAL_GATE_BACKUP_DR_REFERENCE"
DEFAULT_DEPENDENCY_SECURITY_REFERENCE_ENV = (
    "PHI_PLAN_MANUAL_GATE_DEPENDENCY_SECURITY_REFERENCE"
)
DEFAULT_CLEARINGHOUSE_REFERENCE_ENV = "PHI_PLAN_MANUAL_GATE_CLEARINGHOUSE_REFERENCE"
DEFAULT_PRIVATE_SUMMARY_PATH_ENV = "PHI_PLAN_MANUAL_GATE_PRIVATE_SUMMARY_PATH"
DEFAULT_PRIVATE_PACKET_RENDERER_PATH = (
    "llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py"
)
DEFAULT_SUPERVISOR_REPORT = "llm-distill/evals/reports/mlx_runtime_supervisor_report.json"
DEFAULT_MODEL_IMPROVEMENT_REPORT = (
    "llm-distill/evals/reports/model_improvement_evidence_report.json"
)
DEFAULT_PRODUCTION_CORPUS_REPORT = (
    "llm-distill/evals/reports/production_corpus_evidence_report.json"
)
DEFAULT_RETRIEVAL_VECTOR_REPORT = (
    "llm-distill/evals/reports/retrieval_vector_backend_report.json"
)
DEFAULT_PREDICTION_FAIRNESS_REPORT = (
    "llm-distill/evals/reports/prediction_fairness_evidence_report.json"
)
DEFAULT_BACKUP_DISASTER_RECOVERY_REPORT = (
    "llm-distill/evals/reports/backup_disaster_recovery_evidence_report.json"
)
DEFAULT_DEPENDENCY_SECURITY_REPORT = (
    "llm-distill/evals/reports/dependency_security_evidence_report.json"
)
DEFAULT_CLEARINGHOUSE_SUBMISSION_REPORT = (
    "llm-distill/evals/reports/clearinghouse_submission_evidence_report.json"
)
DEFAULT_FILE_INGESTION_SURFACE_REPORT = (
    "llm-distill/evals/reports/file_ingestion_surface_audit_report.json"
)
ACCEPTED_PRODUCTION_SOURCE_TYPES = {
    "real_deidentified_pair",
    "real_world_deidentified_pair",
    "public_government_deidentified_pair",
    "public_government_denial_appeal_pair",
    "approved_public_denial_appeal_pair",
}
REQUIRED_ATTESTATIONS = {
    "student_cutover_attested": "student cutover attestation is required",
    "student_runtime_attested": "student runtime attestation is required",
    "model_improvement_attested": "model-improvement attestation is required",
    "production_corpus_attested": "production corpus attestation is required",
    "retrieval_vector_attested": "retrieval vector attestation is required",
    "prediction_fairness_attested": "prediction fairness attestation is required",
    "backup_disaster_recovery_attested": "backup/disaster-recovery attestation is required",
    "dependency_security_attested": "dependency security attestation is required",
    "clearinghouse_submission_attested": "clearinghouse submission attestation is required",
    "file_ingestion_surface_attested": "file-ingestion surface attestation is required",
    "dependent_reports_ready_attested": "dependent report readiness attestation is required",
    "no_raw_values_attested": "no raw values attestation is required",
}
ALLOWED_ENV_KEYS = {
    DEFAULT_MANIFEST_RECORD_IDS_ENV,
    DEFAULT_MANUAL_REVIEW_REFERENCE_ENV,
    DEFAULT_DEPENDENT_EVIDENCE_REFERENCE_ENV,
    DEFAULT_RELEASE_REFERENCE_ENV,
    DEFAULT_BACKUP_DR_REFERENCE_ENV,
    DEFAULT_DEPENDENCY_SECURITY_REFERENCE_ENV,
    DEFAULT_CLEARINGHOUSE_REFERENCE_ENV,
    DEFAULT_PRIVATE_SUMMARY_PATH_ENV,
}
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "raw",
    "secret",
    "token",
}
SAFE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,255}$")
SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+-]{2,127}$")
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS = {
    "student_cutover_attested",
    "student_runtime_attested",
    "model_improvement_attested",
    "production_corpus_attested",
    "retrieval_vector_attested",
    "prediction_fairness_attested",
    "backup_disaster_recovery_attested",
    "dependency_security_attested",
    "clearinghouse_submission_attested",
    "file_ingestion_surface_attested",
    "dependent_reports_ready_attested",
    "manual_review_completed",
    "release_review_completed",
    "all_dependent_reports_ready",
    "manifest_records_reviewed",
    "approved_non_synthetic_pairs_reviewed",
    "no_phi_or_secret_values_attested",
    "no_raw_values_attested",
    "values_redacted",
}
REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS = {
    "approval_reference_values_included",
    "private_reference_values_included",
    "summary_manifest_record_ids_included",
    "raw_document_content_included",
    "raw_report_evidence_included",
    "phi_or_secret_values_included",
    "source_text_included",
    "vector_values_included",
    "endpoint_values_included",
    "credential_values_included",
    "raw_demographic_values_included",
    "raw_outcome_rows_included",
}
REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS = {
    "approved_non_synthetic_pair_count",
    "approved_source_type_count",
    "manifest_record_id_count",
    "dependent_report_count",
    "private_reference_count",
}
ALLOWED_PRIVATE_SUMMARY_KEYS = (
    REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS
    | REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS
    | REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS
)


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderConfig:
    output_path: Path
    template_path: Path = DEFAULT_TEMPLATE
    approved_production_gate: bool = False
    approved_non_synthetic_pair_count: int = 0
    approved_source_types: tuple[str, ...] = ()
    manifest_record_ids_env: str = DEFAULT_MANIFEST_RECORD_IDS_ENV
    manual_review_reference_env: str = DEFAULT_MANUAL_REVIEW_REFERENCE_ENV
    dependent_evidence_reference_env: str = DEFAULT_DEPENDENT_EVIDENCE_REFERENCE_ENV
    release_reference_env: str = DEFAULT_RELEASE_REFERENCE_ENV
    backup_dr_reference_env: str = DEFAULT_BACKUP_DR_REFERENCE_ENV
    dependency_security_reference_env: str = DEFAULT_DEPENDENCY_SECURITY_REFERENCE_ENV
    clearinghouse_reference_env: str = DEFAULT_CLEARINGHOUSE_REFERENCE_ENV
    private_summary_path_env: str = DEFAULT_PRIVATE_SUMMARY_PATH_ENV
    supervisor_report: str = DEFAULT_SUPERVISOR_REPORT
    model_improvement_report: str = DEFAULT_MODEL_IMPROVEMENT_REPORT
    production_corpus_report: str = DEFAULT_PRODUCTION_CORPUS_REPORT
    retrieval_vector_report: str = DEFAULT_RETRIEVAL_VECTOR_REPORT
    prediction_fairness_report: str = DEFAULT_PREDICTION_FAIRNESS_REPORT
    backup_disaster_recovery_report: str = DEFAULT_BACKUP_DISASTER_RECOVERY_REPORT
    dependency_security_report: str = DEFAULT_DEPENDENCY_SECURITY_REPORT
    clearinghouse_submission_report: str = DEFAULT_CLEARINGHOUSE_SUBMISSION_REPORT
    file_ingestion_surface_report: str = DEFAULT_FILE_INGESTION_SURFACE_REPORT
    student_cutover_attested: bool = False
    student_runtime_attested: bool = False
    model_improvement_attested: bool = False
    production_corpus_attested: bool = False
    retrieval_vector_attested: bool = False
    prediction_fairness_attested: bool = False
    backup_disaster_recovery_attested: bool = False
    dependency_security_attested: bool = False
    clearinghouse_submission_attested: bool = False
    file_ingestion_surface_attested: bool = False
    dependent_reports_ready_attested: bool = False
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
        raise RenderError(f"{label} env var is required for approved gate")
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


def _load_private_references(config: RenderConfig) -> list[str]:
    reference_specs = [
        (config.manual_review_reference_env, "manual gate review reference"),
        (
            config.dependent_evidence_reference_env,
            "dependent evidence packet reference",
        ),
        (config.release_reference_env, "release review reference"),
        (
            config.backup_dr_reference_env,
            "backup/disaster-recovery evidence reference",
        ),
        (
            config.dependency_security_reference_env,
            "dependency security evidence reference",
        ),
        (
            config.clearinghouse_reference_env,
            "clearinghouse submission evidence reference",
        ),
    ]
    return [
        _load_private_reference(env_name, label)
        for env_name, label in reference_specs
    ]


def _validate_record_id(value: str) -> None:
    if not SAFE_RECORD_ID_RE.match(value):
        raise RenderError("manifest record id contains unsupported characters")


def _load_manifest_record_ids(config: RenderConfig) -> list[str]:
    _validate_env_key(config.manifest_record_ids_env)
    raw_value = os.environ.get(config.manifest_record_ids_env, "").strip()
    if not raw_value:
        raise RenderError("manifest record ids env var is required for approved gate")
    if "\n" in raw_value or "\r" in raw_value or "\t" in raw_value or "#" in raw_value:
        raise RenderError("manifest record ids contain unsupported characters")
    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise RenderError("manifest record ids must be valid JSON or comma-separated") from exc
        if not isinstance(parsed, list):
            raise RenderError("manifest record ids JSON must be a list")
        record_ids = [str(item).strip() for item in parsed]
    else:
        record_ids = [item.strip() for item in raw_value.split(",")]
    if not record_ids or any(not item for item in record_ids):
        raise RenderError("manifest record ids must be non-empty")
    for record_id in record_ids:
        _validate_record_id(record_id)
    return record_ids


def _load_private_summary_path(env_name: str) -> Path:
    _validate_env_key(env_name)
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        raise RenderError("private manual gate summary path env var is required")
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        raise RenderError("private manual gate summary path contains unsupported characters")
    summary_path = Path(raw_path).expanduser().resolve()
    if path_is_within(summary_path, REPO_ROOT):
        raise RenderError("private manual gate summary path must be outside source control")
    if not summary_path.exists():
        raise RenderError("private manual gate summary path does not exist")
    if not summary_path.is_file():
        raise RenderError("private manual gate summary path must be a file")
    return summary_path


def _load_private_summary_payload(summary_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise RenderError("private manual gate summary must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise RenderError("private manual gate summary must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RenderError("private manual gate summary must be a JSON object")
    return payload


def _validate_approved_attestations(config: RenderConfig) -> None:
    missing = [
        message
        for flag, message in REQUIRED_ATTESTATIONS.items()
        if getattr(config, flag) is not True
    ]
    if missing:
        raise RenderError("approved production gate requires explicit attestations")
    if config.approved_non_synthetic_pair_count < 1:
        raise RenderError("approved non-synthetic pair count must be at least 1")
    unknown_source_types = sorted(
        set(config.approved_source_types) - ACCEPTED_PRODUCTION_SOURCE_TYPES
    )
    if not config.approved_source_types:
        raise RenderError("at least one approved source type is required")
    if unknown_source_types:
        raise RenderError("approved source type is not accepted")


def _load_template(template_path: Path) -> dict[str, Any]:
    resolved = template_path.resolve()
    if not resolved.exists():
        raise RenderError("manual gate packet template is missing")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RenderError("manual gate packet template is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise RenderError("manual gate packet template must be a JSON object")
    if payload.get("artifact") != "claimguard_phi_plan_manual_gate_packet":
        raise RenderError("manual gate packet template artifact is invalid")
    return payload


def _validate_report_path(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise RenderError("manual gate dependent report path is required")
    if "\n" in cleaned or "\r" in cleaned or "\t" in cleaned or "#" in cleaned:
        raise RenderError("manual gate dependent report path contains unsupported characters")
    if Path(cleaned).is_absolute():
        raise RenderError("manual gate dependent report path must be repository-relative")
    report_path = (REPO_ROOT / cleaned).resolve()
    if not path_is_within(report_path, REPO_ROOT):
        raise RenderError("manual gate dependent report path must stay inside source control")
    return cleaned


def _load_dependent_report(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        raise RenderError("manual gate dependent report is unavailable")
    if not report_path.is_file():
        raise RenderError("manual gate dependent report path must be a file")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError("manual gate dependent report is unreadable") from exc
    if not isinstance(payload, dict):
        raise RenderError("manual gate dependent report must be a JSON object")
    return payload


def _dependent_report_specs(config: RenderConfig) -> tuple[tuple[str, str, str, bool], ...]:
    return (
        ("supervisor", config.supervisor_report, "supervisor_ready", True),
        (
            "model improvement",
            config.model_improvement_report,
            "model_improvement_ready",
            True,
        ),
        (
            "production corpus",
            config.production_corpus_report,
            "production_corpus_ready",
            True,
        ),
        (
            "retrieval vector",
            config.retrieval_vector_report,
            "vector_backend_ready",
            True,
        ),
        (
            "prediction fairness",
            config.prediction_fairness_report,
            "prediction_fairness_monitoring_ready",
            True,
        ),
        (
            "backup/disaster recovery",
            config.backup_disaster_recovery_report,
            "backup_disaster_recovery_ready",
            True,
        ),
        (
            "dependency security",
            config.dependency_security_report,
            "dependency_security_ready",
            True,
        ),
        (
            "clearinghouse submission",
            config.clearinghouse_submission_report,
            "clearinghouse_submission_ready",
            True,
        ),
        (
            "file ingestion surface",
            config.file_ingestion_surface_report,
            "ready",
            False,
        ),
    )


def _validate_dependent_report_ready(
    label: str,
    report_path_text: str,
    ready_key: str,
    require_safe_to_review: bool,
) -> None:
    report_path = (REPO_ROOT / report_path_text).resolve()
    report = _load_dependent_report(report_path)
    blocked_items = report.get("blocked_items")
    blocked_item_count = report.get("blocked_item_count")
    blocked_reasons = report.get("blocked_reasons")
    summary = report.get("summary")
    if require_safe_to_review and report.get("safe_to_review") is not True:
        raise RenderError(f"{label} manual gate dependent report is not safe to review")
    if report.get(ready_key) is not True:
        raise RenderError(f"{label} manual gate dependent report is not ready")
    if blocked_item_count not in (0, None):
        raise RenderError(f"{label} manual gate dependent report has blocked requirements")
    if isinstance(blocked_items, list) and blocked_items:
        raise RenderError(f"{label} manual gate dependent report has blocked requirements")
    if isinstance(blocked_reasons, list) and blocked_reasons:
        raise RenderError(f"{label} manual gate dependent report has blocked requirements")
    if isinstance(summary, dict) and summary.get("unregistered_count") not in (0, None):
        raise RenderError(f"{label} manual gate dependent report has blocked requirements")


def _validate_dependent_report_paths(config: RenderConfig) -> tuple[tuple[str, str, str, bool], ...]:
    return tuple(
        (label, _validate_report_path(report_path), ready_key, require_safe_to_review)
        for label, report_path, ready_key, require_safe_to_review in _dependent_report_specs(config)
    )


def _validate_dependent_reports_ready(config: RenderConfig) -> None:
    for label, report_path, ready_key, require_safe_to_review in _validate_dependent_report_paths(config):
        _validate_dependent_report_ready(
            label,
            report_path,
            ready_key,
            require_safe_to_review,
        )


def _validate_private_manual_gate_summary(
    summary_path: Path,
    config: RenderConfig,
    private_reference_count: int,
    manifest_record_id_count: int,
) -> dict[str, int]:
    payload = _load_private_summary_payload(summary_path)
    unsupported_keys = sorted(set(payload) - ALLOWED_PRIVATE_SUMMARY_KEYS)
    if unsupported_keys:
        raise RenderError("private manual gate summary contains unsupported fields")

    for key in sorted(REQUIRED_PRIVATE_SUMMARY_TRUE_FLAGS):
        if payload.get(key) is not True:
            raise RenderError(f"private manual gate summary requires {key}=true")
    for key in sorted(REQUIRED_PRIVATE_SUMMARY_FALSE_FLAGS):
        if payload.get(key) is not False:
            raise RenderError(f"private manual gate summary requires {key}=false")
    counts: dict[str, int] = {}
    for key in sorted(REQUIRED_PRIVATE_SUMMARY_POSITIVE_COUNTS):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderError(f"private manual gate summary requires positive {key}")
        counts[key] = int(value)

    expected_dependent_report_count = len(_dependent_report_specs(config))
    if counts["approved_non_synthetic_pair_count"] < config.approved_non_synthetic_pair_count:
        raise RenderError("private manual gate summary pair count is below approved request")
    if counts["approved_source_type_count"] != len(config.approved_source_types):
        raise RenderError("private manual gate summary source-type count mismatch")
    if counts["manifest_record_id_count"] != manifest_record_id_count:
        raise RenderError("private manual gate summary manifest record count mismatch")
    if counts["manifest_record_id_count"] < config.approved_non_synthetic_pair_count * 2:
        raise RenderError("private manual gate summary manifest record count is incomplete")
    if counts["dependent_report_count"] != expected_dependent_report_count:
        raise RenderError("private manual gate summary dependent report count mismatch")
    if counts["private_reference_count"] != private_reference_count:
        raise RenderError("private manual gate summary private reference count mismatch")
    return counts


def _mark_source_control_renderer(packet: dict[str, Any]) -> None:
    packet["source_control_private_packet_renderer_documented"] = True
    packet["private_packet_renderer_path"] = DEFAULT_PRIVATE_PACKET_RENDERER_PATH


def _blocked_packet(template: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
    packet = json.loads(json.dumps(template))
    packet["packet_status"] = "private_renderer_default_production_gate_ready_false"
    packet["prepared_at"] = datetime.now(timezone.utc).isoformat()
    packet["no_phi_or_secret_values_attested"] = True
    _mark_source_control_renderer(packet)
    return packet, 0, 0


def _approved_packet(
    template: dict[str, Any],
    config: RenderConfig,
) -> tuple[dict[str, Any], int, int, dict[str, int]]:
    _validate_approved_attestations(config)
    _validate_dependent_reports_ready(config)
    private_reference_count = len(_load_private_references(config))
    manifest_record_ids = _load_manifest_record_ids(config)
    minimum_record_count = config.approved_non_synthetic_pair_count * 2
    if len(manifest_record_ids) < minimum_record_count:
        raise RenderError("manifest record ids are missing for approved pairs")
    private_summary_counts = _validate_private_manual_gate_summary(
        _load_private_summary_path(config.private_summary_path_env),
        config,
        private_reference_count,
        len(manifest_record_ids),
    )

    packet = json.loads(json.dumps(template))
    packet["packet_status"] = "private_manual_production_gate_ready"
    packet["prepared_at"] = datetime.now(timezone.utc).isoformat()
    packet["no_phi_or_secret_values_attested"] = True
    packet["private_manual_gate_summary_path_env"] = config.private_summary_path_env
    packet["private_manual_gate_summary_path_configured"] = True
    packet["private_manual_gate_summary_path_value_included"] = False
    packet["private_manual_gate_summary_checked"] = True
    packet["private_manual_gate_summary_approved_non_synthetic_pair_count"] = (
        private_summary_counts["approved_non_synthetic_pair_count"]
    )
    packet["private_manual_gate_summary_approved_source_type_count"] = (
        private_summary_counts["approved_source_type_count"]
    )
    packet["private_manual_gate_summary_manifest_record_id_count"] = (
        private_summary_counts["manifest_record_id_count"]
    )
    packet["private_manual_gate_summary_dependent_report_count"] = (
        private_summary_counts["dependent_report_count"]
    )
    packet["private_manual_gate_summary_private_reference_count"] = (
        private_summary_counts["private_reference_count"]
    )
    packet["private_manual_gate_summary_raw_values_included"] = False
    packet["approval_reference_value_included"] = False
    packet["private_reference_values_included"] = False
    packet["manifest_record_ids_included_in_summary"] = False
    packet["raw_document_content_included"] = False
    packet["raw_report_evidence_included"] = False
    _mark_source_control_renderer(packet)

    student = packet["student_default_cutover"]
    student.update(
        {
            "requested": True,
            "raphael_approval_attested": True,
            "approval_reference_configured": True,
            "supervisor_evidence_report_ready": True,
            "supervised_runtime_owner_configured": True,
            "source_control_runbook_documented": True,
            "source_control_private_env_renderer_documented": True,
            "source_control_runtime_supervisor_private_evidence_renderer_documented": True,
            "source_control_runtime_validation_checklist_documented": True,
            "source_control_runtime_owner_handoff_checklist_documented": True,
            "supervised_runtime_runbook_reviewed": True,
            "rollback_to_nvidia_reviewed": True,
            "scope_limited_to_denial_workflow_and_appeals": True,
        }
    )

    model = packet["user_data_model_improvement"]
    model.update(
        {
            "requested": True,
            "source_control_approval_runbook_documented": True,
            "source_control_private_env_renderer_documented": True,
            "legal_approval_attested": True,
            "baa_confirmed": True,
            "consent_notice_version_configured": True,
            "approval_reference_configured": True,
            "model_improvement_evidence_report_ready": True,
            "data_use_scope_documented": True,
            "per_request_attestations_required": True,
        }
    )

    corpus = packet["production_corpus"]
    corpus.update(
        {
            "approved_non_synthetic_pair_count": config.approved_non_synthetic_pair_count,
            "approved_source_types": list(config.approved_source_types),
            "manifest_record_ids": manifest_record_ids,
            "production_corpus_evidence_report_ready": True,
            "source_control_review_runbook_documented": True,
            "source_control_collection_license_checklist_documented": True,
            "source_control_pair_source_checklist_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "privacy_review_attested": True,
            "license_review_attested": True,
            "residual_risk_review_attested": True,
            "training_scope_reviewed": True,
        }
    )

    retrieval = packet["retrieval_vector_backend"]
    retrieval.update(
        {
            "vector_backend_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_reindex_checklist_documented": True,
            "source_control_runtime_smoke_checklist_documented": True,
            "source_control_private_env_renderer_documented": True,
            "semantic_backend_configured": True,
            "production_vector_backend_configured": True,
            "retrieval_chunks_reindexed": True,
            "governance_controls_reviewed": True,
            "runtime_validation_reviewed": True,
        }
    )

    fairness = packet["prediction_fairness_monitoring"]
    fairness.update(
        {
            "prediction_fairness_evidence_report_ready": True,
            "approved_outcome_dataset_available": True,
            "minimum_sample_size_met": True,
            "threshold_review_completed": True,
            "source_control_calibration_checklist_documented": True,
            "approved_demographic_grouping_reviewed": True,
            "continuous_monitoring_configured": True,
            "disparity_thresholds_documented": True,
            "alerting_and_review_owner_configured": True,
            "latest_monitoring_run_passed": True,
            "legal_privacy_review_completed": True,
            "source_control_legal_privacy_checklist_documented": True,
            "source_control_monitoring_runbook_documented": True,
            "source_control_monitoring_validation_checklist_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "model_card_updated": True,
            "model_card_required_markers_verified": True,
            "rollback_or_threshold_reversion_reviewed": True,
            "audit_log_metadata_only_verified": True,
        }
    )

    backup_dr = packet["backup_disaster_recovery"]
    backup_dr.update(
        {
            "backup_disaster_recovery_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "encrypted_backup_storage_configured": True,
            "restore_validation_completed": True,
            "encryption_key_recovery_reviewed": True,
            "retention_policy_approved": True,
            "disaster_recovery_smoke_passed": True,
            "metadata_only_restore_verified": True,
        }
    )

    dependency = packet["dependency_security"]
    dependency.update(
        {
            "dependency_security_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "python_dependency_scan_completed": True,
            "frontend_dependency_scan_completed": True,
            "container_dependency_scan_completed": True,
            "critical_high_findings_remediated_or_approved": True,
            "rebuild_retest_completed": True,
            "upgrade_plan_reviewed": True,
            "raw_scanner_output_excluded": True,
        }
    )

    clearinghouse = packet["clearinghouse_submission"]
    clearinghouse.update(
        {
            "clearinghouse_submission_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "payer_or_clearinghouse_enrollment_attested": True,
            "test_mode_credentials_configured": True,
            "encrypted_transit_validated": True,
            "edi_837_submission_contract_test_passed": True,
            "acknowledgement_handling_validated": True,
            "rejection_retry_duplicate_controls_reviewed": True,
            "rollback_to_manual_reviewed": True,
            "metadata_only_audit_logging_verified": True,
            "access_controls_reviewed": True,
            "retention_policy_reviewed": True,
        }
    )

    file_ingestion = packet["file_ingestion_surface_audit"]
    file_ingestion.update(
        {
            "file_ingestion_surface_report_ready": True,
            "metadata_only_surface_inspection_attested": True,
            "safe_audit_marker_coverage_attested": True,
        }
    )
    return packet, private_reference_count, len(manifest_record_ids), private_summary_counts


def _json_file_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_private_packet(config: RenderConfig) -> dict[str, Any]:
    output_path = config.output_path.resolve()
    if path_is_within(output_path, REPO_ROOT):
        raise RenderError("refusing_to_write_inside_source_control")

    _validate_dependent_report_paths(config)
    template = _load_template(config.template_path)
    private_summary_counts = {
        "approved_non_synthetic_pair_count": 0,
        "approved_source_type_count": 0,
        "manifest_record_id_count": 0,
        "dependent_report_count": 0,
        "private_reference_count": 0,
    }
    if config.approved_production_gate:
        (
            packet,
            private_reference_count,
            manifest_record_id_count,
            private_summary_counts,
        ) = _approved_packet(
            template,
            config,
        )
    else:
        packet, private_reference_count, manifest_record_id_count = _blocked_packet(
            template
        )

    summary = {
        "dry_run": config.dry_run,
        "rendered": not config.dry_run,
        "approved_production_gate_requested": config.approved_production_gate,
        "production_gate_ready": config.approved_production_gate,
        "student_cutover_attested": config.student_cutover_attested,
        "student_runtime_attested": config.student_runtime_attested,
        "model_improvement_attested": config.model_improvement_attested,
        "production_corpus_attested": config.production_corpus_attested,
        "retrieval_vector_attested": config.retrieval_vector_attested,
        "prediction_fairness_attested": config.prediction_fairness_attested,
        "backup_disaster_recovery_attested": config.backup_disaster_recovery_attested,
        "dependency_security_attested": config.dependency_security_attested,
        "clearinghouse_submission_attested": config.clearinghouse_submission_attested,
        "file_ingestion_surface_attested": config.file_ingestion_surface_attested,
        "dependent_reports_ready_attested": config.dependent_reports_ready_attested,
        "dependent_evidence_reports_configured": True,
        "dependent_evidence_reports_checked": config.approved_production_gate,
        "dependent_evidence_reports_ready": config.approved_production_gate,
        "approved_non_synthetic_pair_count": (
            config.approved_non_synthetic_pair_count
            if config.approved_production_gate
            else 0
        ),
        "approved_source_type_count": (
            len(config.approved_source_types)
            if config.approved_production_gate
            else 0
        ),
        "manifest_record_id_count": manifest_record_id_count,
        "private_reference_count": private_reference_count,
        "private_manual_gate_summary_checked": config.approved_production_gate,
        "private_manual_gate_summary_path_env_configured": (
            bool(config.private_summary_path_env)
            if config.approved_production_gate
            else False
        ),
        "private_manual_gate_summary_path_configured": (
            bool(config.private_summary_path_env)
            if config.approved_production_gate
            else False
        ),
        "private_manual_gate_summary_path_value_included": False,
        "private_manual_gate_summary_approved_non_synthetic_pair_count": (
            private_summary_counts["approved_non_synthetic_pair_count"]
        ),
        "private_manual_gate_summary_approved_source_type_count": (
            private_summary_counts["approved_source_type_count"]
        ),
        "private_manual_gate_summary_manifest_record_id_count": (
            private_summary_counts["manifest_record_id_count"]
        ),
        "private_manual_gate_summary_dependent_report_count": (
            private_summary_counts["dependent_report_count"]
        ),
        "private_manual_gate_summary_private_reference_count": (
            private_summary_counts["private_reference_count"]
        ),
        "private_manual_gate_summary_raw_values_included": False,
        "manual_gate_private_packet_renderer_documented": True,
        "output_path_in_source_control": False,
        "approval_reference_value_included": False,
        "private_reference_values_included": False,
        "manifest_record_ids_included_in_summary": False,
        "raw_packet_values_included": False,
        "raw_document_content_included": False,
        "raw_report_evidence_included": False,
        "values_redacted": True,
        "file_mode": "0600" if not config.dry_run else None,
    }
    if not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_json_file_text(packet))
        output_path.chmod(0o600)
    return summary


def build_config(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        output_path=args.output,
        template_path=args.template,
        approved_production_gate=args.approved_production_gate,
        approved_non_synthetic_pair_count=args.approved_non_synthetic_pair_count,
        approved_source_types=tuple(args.approved_source_type or ()),
        manifest_record_ids_env=args.manifest_record_ids_env,
        manual_review_reference_env=args.manual_review_reference_env,
        dependent_evidence_reference_env=args.dependent_evidence_reference_env,
        release_reference_env=args.release_reference_env,
        backup_dr_reference_env=args.backup_dr_reference_env,
        dependency_security_reference_env=args.dependency_security_reference_env,
        clearinghouse_reference_env=args.clearinghouse_reference_env,
        private_summary_path_env=args.private_summary_path_env,
        supervisor_report=args.supervisor_report,
        model_improvement_report=args.model_improvement_report,
        production_corpus_report=args.production_corpus_report,
        retrieval_vector_report=args.retrieval_vector_report,
        prediction_fairness_report=args.prediction_fairness_report,
        backup_disaster_recovery_report=args.backup_disaster_recovery_report,
        dependency_security_report=args.dependency_security_report,
        clearinghouse_submission_report=args.clearinghouse_submission_report,
        file_ingestion_surface_report=args.file_ingestion_surface_report,
        student_cutover_attested=args.student_cutover_attested,
        student_runtime_attested=args.student_runtime_attested,
        model_improvement_attested=args.model_improvement_attested,
        production_corpus_attested=args.production_corpus_attested,
        retrieval_vector_attested=args.retrieval_vector_attested,
        prediction_fairness_attested=args.prediction_fairness_attested,
        backup_disaster_recovery_attested=args.backup_disaster_recovery_attested,
        dependency_security_attested=args.dependency_security_attested,
        clearinghouse_submission_attested=args.clearinghouse_submission_attested,
        file_ingestion_surface_attested=args.file_ingestion_surface_attested,
        dependent_reports_ready_attested=args.dependent_reports_ready_attested,
        no_raw_values_attested=args.no_raw_values_attested,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--approved-production-gate", action="store_true")
    parser.add_argument("--approved-non-synthetic-pair-count", type=int, default=0)
    parser.add_argument(
        "--approved-source-type",
        action="append",
        choices=sorted(ACCEPTED_PRODUCTION_SOURCE_TYPES),
    )
    parser.add_argument("--manifest-record-ids-env", default=DEFAULT_MANIFEST_RECORD_IDS_ENV)
    parser.add_argument(
        "--manual-review-reference-env",
        default=DEFAULT_MANUAL_REVIEW_REFERENCE_ENV,
    )
    parser.add_argument(
        "--dependent-evidence-reference-env",
        default=DEFAULT_DEPENDENT_EVIDENCE_REFERENCE_ENV,
    )
    parser.add_argument("--release-reference-env", default=DEFAULT_RELEASE_REFERENCE_ENV)
    parser.add_argument("--backup-dr-reference-env", default=DEFAULT_BACKUP_DR_REFERENCE_ENV)
    parser.add_argument(
        "--dependency-security-reference-env",
        default=DEFAULT_DEPENDENCY_SECURITY_REFERENCE_ENV,
    )
    parser.add_argument(
        "--clearinghouse-reference-env",
        default=DEFAULT_CLEARINGHOUSE_REFERENCE_ENV,
    )
    parser.add_argument("--private-summary-path-env", default=DEFAULT_PRIVATE_SUMMARY_PATH_ENV)
    parser.add_argument("--supervisor-report", default=DEFAULT_SUPERVISOR_REPORT)
    parser.add_argument("--model-improvement-report", default=DEFAULT_MODEL_IMPROVEMENT_REPORT)
    parser.add_argument("--production-corpus-report", default=DEFAULT_PRODUCTION_CORPUS_REPORT)
    parser.add_argument("--retrieval-vector-report", default=DEFAULT_RETRIEVAL_VECTOR_REPORT)
    parser.add_argument("--prediction-fairness-report", default=DEFAULT_PREDICTION_FAIRNESS_REPORT)
    parser.add_argument(
        "--backup-disaster-recovery-report",
        default=DEFAULT_BACKUP_DISASTER_RECOVERY_REPORT,
    )
    parser.add_argument(
        "--dependency-security-report",
        default=DEFAULT_DEPENDENCY_SECURITY_REPORT,
    )
    parser.add_argument(
        "--clearinghouse-submission-report",
        default=DEFAULT_CLEARINGHOUSE_SUBMISSION_REPORT,
    )
    parser.add_argument(
        "--file-ingestion-surface-report",
        default=DEFAULT_FILE_INGESTION_SURFACE_REPORT,
    )
    parser.add_argument("--student-cutover-attested", action="store_true")
    parser.add_argument("--student-runtime-attested", action="store_true")
    parser.add_argument("--model-improvement-attested", action="store_true")
    parser.add_argument("--production-corpus-attested", action="store_true")
    parser.add_argument("--retrieval-vector-attested", action="store_true")
    parser.add_argument("--prediction-fairness-attested", action="store_true")
    parser.add_argument("--backup-disaster-recovery-attested", action="store_true")
    parser.add_argument("--dependency-security-attested", action="store_true")
    parser.add_argument("--clearinghouse-submission-attested", action="store_true")
    parser.add_argument("--file-ingestion-surface-attested", action="store_true")
    parser.add_argument("--dependent-reports-ready-attested", action="store_true")
    parser.add_argument("--no-raw-values-attested", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = render_private_packet(build_config(args))
    except RenderError as exc:
        print(json.dumps({"error": str(exc), "values_redacted": True}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
