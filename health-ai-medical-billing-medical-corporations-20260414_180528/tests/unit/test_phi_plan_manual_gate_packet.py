import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_phi_plan_manual_gate_packet.py"


def _load_validator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_phi_plan_manual_gate_packet",
        VALIDATOR_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_marker_file(path: Path, markers: list[str], unique_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([*markers, unique_text]), encoding="utf-8")


def _requirement(report: dict, requirement_id: str) -> dict:
    return next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == requirement_id
    )


def _allow_tmp_source_control_path(
    monkeypatch,
    validator: ModuleType,
    path: Path,
) -> None:
    original_path_is_within = validator.path_is_within
    allowed_path = path.resolve()

    def path_is_within(candidate: Path, parent: Path) -> bool:
        if candidate.resolve() == allowed_path:
            return True
        return original_path_is_within(candidate, parent)

    monkeypatch.setattr(validator, "path_is_within", path_is_within)


def _manual_gate_checklist_text(validator: ModuleType) -> str:
    return "\n".join(validator.MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS) + "\n"


def _ready_packet() -> dict:
    return {
        "artifact": "claimguard_phi_plan_manual_gate_packet",
        "version": "1.0",
        "packet_status": "ready_for_runtime_configuration",
        "prepared_at": "2026-05-30T17:15:48-07:00",
        "no_phi_or_secret_values_attested": True,
        "source_control_manual_gate_checklist_documented": True,
        "manual_gate_checklist_path": "llm-distill/docs/phi-plan-manual-production-gate-checklist.md",
        "source_control_private_packet_renderer_documented": True,
        "private_packet_renderer_path": (
            "llm-distill/scripts/render_phi_plan_manual_gate_private_packet.py"
        ),
        "private_manual_gate_summary_path_env": "PHI_PLAN_MANUAL_GATE_PRIVATE_SUMMARY_PATH",
        "private_manual_gate_summary_path_configured": True,
        "private_manual_gate_summary_path_value_included": False,
        "private_manual_gate_summary_checked": True,
        "private_manual_gate_summary_approved_non_synthetic_pair_count": 1,
        "private_manual_gate_summary_approved_source_type_count": 1,
        "private_manual_gate_summary_manifest_record_id_count": 2,
        "private_manual_gate_summary_dependent_report_count": 9,
        "private_manual_gate_summary_private_reference_count": 6,
        "private_manual_gate_summary_raw_values_included": False,
        "approval_reference_value_included": False,
        "private_reference_values_included": False,
        "manifest_record_ids_included_in_summary": False,
        "raw_document_content_included": False,
        "raw_report_evidence_included": False,
        "student_default_cutover": {
            "requested": True,
            "raphael_approval_attested": True,
            "approval_reference_configured": True,
            "supervisor_evidence_report_ready": True,
            "supervised_runtime_owner_configured": True,
            "source_control_runbook_documented": True,
            "source_control_private_env_renderer_documented": True,
            "private_env_renderer_path": "llm-distill/scripts/render_student_cutover_private_env.py",
            "source_control_runtime_supervisor_private_evidence_renderer_documented": True,
            "runtime_supervisor_private_evidence_renderer_path": (
                "llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py"
            ),
            "source_control_runtime_validation_checklist_documented": True,
            "source_control_runtime_owner_handoff_checklist_documented": True,
            "supervised_runtime_runbook_reviewed": True,
            "rollback_to_nvidia_reviewed": True,
            "scope_limited_to_denial_workflow_and_appeals": True,
        },
        "user_data_model_improvement": {
            "requested": True,
            "source_control_approval_runbook_documented": True,
            "source_control_private_env_renderer_documented": True,
            "private_env_renderer_path": "llm-distill/scripts/render_model_improvement_private_env.py",
            "legal_approval_attested": True,
            "baa_confirmed": True,
            "consent_notice_version_configured": True,
            "approval_reference_configured": True,
            "model_improvement_evidence_report_ready": True,
            "data_use_scope_documented": True,
            "per_request_attestations_required": True,
        },
        "production_corpus": {
            "approved_non_synthetic_pair_count": 1,
            "approved_source_types": ["real_deidentified_pair"],
            "manifest_record_ids": ["DOC-REAL-DENIAL", "DOC-REAL-APPEAL"],
            "production_corpus_evidence_report_ready": True,
            "source_control_review_runbook_documented": True,
            "source_control_collection_license_checklist_documented": True,
            "source_control_pair_source_checklist_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_production_corpus_private_evidence.py"
            ),
            "privacy_review_attested": True,
            "license_review_attested": True,
            "residual_risk_review_attested": True,
            "training_scope_reviewed": True,
        },
        "retrieval_vector_backend": {
            "vector_backend_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_reindex_checklist_documented": True,
            "source_control_runtime_smoke_checklist_documented": True,
            "source_control_private_env_renderer_documented": True,
            "private_env_renderer_path": "llm-distill/scripts/render_retrieval_vector_private_env.py",
            "semantic_backend_configured": True,
            "production_vector_backend_configured": True,
            "retrieval_chunks_reindexed": True,
            "governance_controls_reviewed": True,
            "runtime_validation_reviewed": True,
        },
        "prediction_fairness_monitoring": {
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
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_prediction_fairness_private_evidence.py"
            ),
            "model_card_updated": True,
            "model_card_required_markers_verified": True,
            "rollback_or_threshold_reversion_reviewed": True,
            "audit_log_metadata_only_verified": True,
        },
        "backup_disaster_recovery": {
            "backup_disaster_recovery_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_backup_disaster_recovery_private_evidence.py"
            ),
            "encrypted_backup_storage_configured": True,
            "restore_validation_completed": True,
            "encryption_key_recovery_reviewed": True,
            "retention_policy_approved": True,
            "disaster_recovery_smoke_passed": True,
            "metadata_only_restore_verified": True,
        },
        "dependency_security": {
            "dependency_security_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_dependency_security_private_evidence.py"
            ),
            "python_dependency_scan_completed": True,
            "frontend_dependency_scan_completed": True,
            "container_dependency_scan_completed": True,
            "critical_high_findings_remediated_or_approved": True,
            "rebuild_retest_completed": True,
            "upgrade_plan_reviewed": True,
            "raw_scanner_output_excluded": True,
        },
        "clearinghouse_submission": {
            "clearinghouse_submission_evidence_report_ready": True,
            "source_control_runbook_documented": True,
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_clearinghouse_submission_private_evidence.py"
            ),
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
        },
        "file_ingestion_surface_audit": {
            "file_ingestion_surface_report_ready": True,
            "expected_upload_surface_count": 3,
            "registered_upload_surface_count": 3,
            "unregistered_upload_surface_count": 0,
            "metadata_only_surface_inspection_attested": True,
            "safe_audit_marker_coverage_attested": True,
        },
    }


def test_template_packet_is_safe_to_review_but_not_ready():
    validator = _load_validator()
    template_path = (
        REPO_ROOT
        / "llm-distill"
        / "data"
        / "production_gate_evidence"
        / "manual_gate_packet.template.json"
    )

    report = validator.build_report(template_path)

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is False
    checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "manual_gate_packet_completion_checklist"
    )
    assert checklist_requirement["status"] == "ready"
    assert (
        checklist_requirement["evidence"][
            "source_control_manual_gate_checklist_documented"
        ]
        is True
    )
    assert checklist_requirement["evidence"]["manual_gate_checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "manual_gate_checklist_inside_source_control"
        ]
        is True
    )
    assert (
        checklist_requirement["evidence"]["manual_gate_checklist_missing_marker_count"]
        == 0
    )
    assert checklist_requirement["evidence"]["manual_gate_checklist_values_included"] is False
    assert "manual_gate_packet_no_phi_or_secret_values" not in blocked_ids
    assert "manual_gate_packet_completion_checklist" not in blocked_ids
    assert "manual_gate_private_packet_renderer" not in blocked_ids
    assert "manual_gate_private_summary_metadata" in blocked_ids
    assert "manual_student_cutover_private_env_renderer" not in blocked_ids
    assert "manual_student_default_cutover_evidence" in blocked_ids
    assert "manual_user_data_model_improvement_evidence" in blocked_ids
    assert "manual_production_corpus_evidence" in blocked_ids
    assert "manual_retrieval_vector_backend_evidence" in blocked_ids
    assert "manual_prediction_fairness_monitoring_evidence" in blocked_ids
    assert "manual_backup_disaster_recovery_evidence" in blocked_ids
    assert "manual_dependency_security_evidence" in blocked_ids
    assert "manual_clearinghouse_submission_evidence" in blocked_ids
    assert "manual_file_ingestion_surface_evidence" not in blocked_ids
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )
    assert "rollback_to_nvidia_not_reviewed" not in student_requirement["blockers"]
    assert "source_control_runbook_not_documented" not in student_requirement["blockers"]
    assert (
        "student_cutover_private_env_renderer_not_documented"
        not in student_requirement["blockers"]
    )
    assert (
        "runtime_supervisor_private_evidence_renderer_not_documented"
        not in student_requirement["blockers"]
    )
    assert "source_control_runtime_validation_checklist_not_documented" not in student_requirement["blockers"]
    assert (
        "source_control_runtime_owner_handoff_checklist_not_documented"
        not in student_requirement["blockers"]
    )
    assert student_requirement["evidence"]["rollback_to_nvidia_reviewed"] is True
    assert student_requirement["evidence"]["source_control_runbook_documented"] is True
    assert (
        student_requirement["evidence"][
            "source_control_private_env_renderer_documented"
        ]
        is True
    )
    assert (
        student_requirement["evidence"][
            "source_control_runtime_supervisor_private_evidence_renderer_documented"
        ]
        is True
    )
    assert (
        student_requirement["evidence"]["source_control_runtime_validation_checklist_documented"]
        is True
    )
    assert (
        student_requirement["evidence"][
            "source_control_runtime_owner_handoff_checklist_documented"
        ]
        is True
    )
    private_packet_renderer_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "manual_gate_private_packet_renderer"
    )
    assert private_packet_renderer_requirement["status"] == "ready"
    assert (
        private_packet_renderer_requirement["evidence"][
            "source_control_private_packet_renderer_documented"
        ]
        is True
    )
    assert (
        private_packet_renderer_requirement["evidence"][
            "private_packet_renderer_inside_source_control"
        ]
        is True
    )
    assert (
        private_packet_renderer_requirement["evidence"][
            "private_packet_renderer_exists"
        ]
        is True
    )
    assert private_packet_renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert (
        private_packet_renderer_requirement["evidence"]["raw_renderer_text_included"]
        is False
    )
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_private_summary_metadata"
    )
    assert (
        "private_manual_gate_summary_not_checked"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manual_gate_summary_path_not_configured"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manual_gate_summary_approved_non_synthetic_pair_count_missing"
        in private_summary_requirement["blockers"]
    )
    assert (
        private_summary_requirement["evidence"][
            "private_manual_gate_summary_path_value_included"
        ]
        is False
    )
    assert private_summary_requirement["evidence"]["values_redacted"] is True
    private_renderer_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "manual_student_cutover_private_env_renderer"
    )
    assert private_renderer_requirement["status"] == "ready"
    assert private_renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert (
        private_renderer_requirement["evidence"][
            "private_env_renderer_inside_source_control"
        ]
        is True
    )
    assert private_renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert private_renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert (
        private_renderer_requirement["evidence"]["approval_reference_value_included"]
        is False
    )
    model_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_user_data_model_improvement_evidence"
    )
    assert "data_use_scope_not_documented" not in model_requirement["blockers"]
    assert "model_improvement_source_control_approval_runbook_not_documented" not in model_requirement["blockers"]
    assert (
        "model_improvement_private_env_renderer_not_documented"
        not in model_requirement["blockers"]
    )
    assert model_requirement["evidence"]["data_use_scope_documented"] is True
    assert model_requirement["evidence"]["source_control_approval_runbook_documented"] is True
    assert (
        model_requirement["evidence"][
            "source_control_private_env_renderer_documented"
        ]
        is True
    )
    file_ingestion_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "manual_file_ingestion_surface_evidence"
    )
    assert file_ingestion_requirement["status"] == "ready"
    assert file_ingestion_requirement["evidence"]["registered_upload_surface_count"] == 3
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_retrieval_vector_backend_evidence"
    )
    assert "retrieval_governance_controls_not_reviewed" not in vector_requirement["blockers"]
    assert "retrieval_vector_source_control_runbook_not_documented" not in vector_requirement["blockers"]
    assert "retrieval_reindex_checklist_not_documented" not in vector_requirement["blockers"]
    assert "retrieval_runtime_smoke_checklist_not_documented" not in vector_requirement["blockers"]
    assert "retrieval_private_env_renderer_not_documented" not in vector_requirement["blockers"]
    assert vector_requirement["evidence"]["governance_controls_reviewed"] is True
    assert vector_requirement["evidence"]["source_control_runbook_documented"] is True
    assert (
        vector_requirement["evidence"]["source_control_reindex_checklist_documented"]
        is True
    )
    assert (
        vector_requirement["evidence"][
            "source_control_runtime_smoke_checklist_documented"
        ]
        is True
    )
    assert (
        vector_requirement["evidence"]["source_control_private_env_renderer_documented"]
        is True
    )
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_corpus_evidence"
    )
    for blocker in [
        "privacy_review_not_attested",
        "license_review_not_attested",
        "residual_risk_review_not_attested",
        "training_scope_not_reviewed",
        "production_corpus_source_control_review_runbook_not_documented",
        "production_corpus_collection_license_checklist_not_documented",
        "production_corpus_pair_source_checklist_not_documented",
        "production_corpus_private_evidence_renderer_not_documented",
    ]:
        assert blocker not in corpus_requirement["blockers"]
    for key in [
        "source_control_review_runbook_documented",
        "source_control_collection_license_checklist_documented",
        "source_control_pair_source_checklist_documented",
        "source_control_private_evidence_renderer_documented",
        "privacy_review_attested",
        "license_review_attested",
        "residual_risk_review_attested",
        "training_scope_reviewed",
    ]:
        assert corpus_requirement["evidence"][key] is True
    assert "approved_non_synthetic_pair_count_must_be_at_least_1" in corpus_requirement["blockers"]
    assert "production_corpus_evidence_report_not_ready" in corpus_requirement["blockers"]
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )
    assert "prediction_fairness_evidence_report_not_ready" in fairness_requirement["blockers"]
    assert (
        "prediction_fairness_source_control_monitoring_runbook_not_documented"
        not in fairness_requirement["blockers"]
    )
    assert (
        "prediction_fairness_source_control_monitoring_validation_checklist_not_documented"
        not in fairness_requirement["blockers"]
    )
    assert (
        "prediction_fairness_source_control_legal_privacy_checklist_not_documented"
        not in fairness_requirement["blockers"]
    )
    assert (
        "prediction_fairness_private_evidence_renderer_not_documented"
        not in fairness_requirement["blockers"]
    )
    assert "model_card_not_updated" not in fairness_requirement["blockers"]
    assert "model_card_required_markers_not_verified" not in fairness_requirement["blockers"]
    assert fairness_requirement["evidence"]["model_card_updated"] is True
    assert fairness_requirement["evidence"]["model_card_required_markers_verified"] is True
    assert "rollback_or_threshold_reversion_not_reviewed" not in fairness_requirement["blockers"]
    assert "audit_log_metadata_only_not_verified" not in fairness_requirement["blockers"]
    assert (
        "prediction_fairness_source_control_calibration_checklist_not_documented"
        not in fairness_requirement["blockers"]
    )
    assert fairness_requirement["evidence"]["rollback_or_threshold_reversion_reviewed"] is True
    assert fairness_requirement["evidence"]["audit_log_metadata_only_verified"] is True
    assert fairness_requirement["evidence"]["source_control_monitoring_runbook_documented"] is True
    assert (
        fairness_requirement["evidence"][
            "source_control_monitoring_validation_checklist_documented"
        ]
        is True
    )
    assert (
        fairness_requirement["evidence"][
            "source_control_legal_privacy_checklist_documented"
        ]
        is True
    )
    assert (
        fairness_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    assert (
        fairness_requirement["evidence"][
            "source_control_calibration_checklist_documented"
        ]
        is True
    )
    backup_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_backup_disaster_recovery_evidence"
    )
    assert "backup_disaster_recovery_evidence_report_not_ready" in backup_requirement["blockers"]
    assert "backup_disaster_recovery_source_control_runbook_not_documented" not in backup_requirement["blockers"]
    assert "backup_disaster_recovery_private_evidence_renderer_not_documented" not in backup_requirement["blockers"]
    assert backup_requirement["evidence"]["source_control_runbook_documented"] is True
    assert (
        backup_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    dependency_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_dependency_security_evidence"
    )
    assert "dependency_security_evidence_report_not_ready" in dependency_requirement["blockers"]
    assert "dependency_security_source_control_runbook_not_documented" not in dependency_requirement["blockers"]
    assert "dependency_security_private_evidence_renderer_not_documented" not in dependency_requirement["blockers"]
    assert dependency_requirement["evidence"]["source_control_runbook_documented"] is True
    assert (
        dependency_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    assert dependency_requirement["evidence"]["raw_scanner_output_excluded"] is True
    clearinghouse_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_clearinghouse_submission_evidence"
    )
    assert "clearinghouse_submission_evidence_report_not_ready" in clearinghouse_requirement["blockers"]
    assert (
        "clearinghouse_submission_source_control_runbook_not_documented"
        not in clearinghouse_requirement["blockers"]
    )
    assert (
        "clearinghouse_submission_private_evidence_renderer_not_documented"
        not in clearinghouse_requirement["blockers"]
    )
    assert clearinghouse_requirement["evidence"]["source_control_runbook_documented"] is True
    assert (
        clearinghouse_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    assert clearinghouse_requirement["evidence"]["rollback_to_manual_reviewed"] is True
    assert clearinghouse_requirement["evidence"]["metadata_only_audit_logging_verified"] is True


def test_ready_packet_passes_all_manual_gate_requirements(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    _write_json(packet_path, _ready_packet())

    report = validator.build_report(packet_path)

    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is True
    assert report["blocked_item_count"] == 0


def test_ready_packet_requires_private_manual_gate_summary_metadata(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["private_manual_gate_summary_checked"] = False
    packet["private_manual_gate_summary_path_configured"] = False
    packet["private_manual_gate_summary_approved_non_synthetic_pair_count"] = 0
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_private_summary_metadata"
    )

    assert report["production_gate_ready"] is False
    assert (
        "private_manual_gate_summary_not_checked"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manual_gate_summary_path_not_configured"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manual_gate_summary_approved_non_synthetic_pair_count_missing"
        in private_summary_requirement["blockers"]
    )


def test_private_manual_gate_summary_value_flags_are_blocked(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["private_manual_gate_summary_path_value_included"] = True
    packet["private_manual_gate_summary_raw_values_included"] = True
    packet["raw_report_evidence_included"] = True
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_private_summary_metadata"
    )

    assert report["production_gate_ready"] is False
    assert (
        "private_manual_gate_summary_path_value_included"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manual_gate_summary_raw_values_included"
        in private_summary_requirement["blockers"]
    )
    assert "raw_report_evidence_included" in private_summary_requirement["blockers"]
    assert (
        private_summary_requirement["evidence"][
            "private_manual_gate_summary_path_value_included"
        ]
        is True
    )


def test_private_manual_gate_summary_count_parity_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["private_manual_gate_summary_manifest_record_id_count"] = 3
    packet["private_manual_gate_summary_private_reference_count"] = 2
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    private_summary_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_private_summary_metadata"
    )

    assert report["production_gate_ready"] is False
    assert (
        "private_manual_gate_summary_manifest_record_count_mismatch"
        in private_summary_requirement["blockers"]
    )
    assert (
        "private_manual_gate_summary_private_reference_count_mismatch"
        in private_summary_requirement["blockers"]
    )


def test_manual_gate_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["source_control_manual_gate_checklist_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_packet_completion_checklist"
    )

    assert report["production_gate_ready"] is False
    assert checklist_requirement["blockers"] == [
        "source_control_manual_gate_checklist_not_documented"
    ]


def test_manual_gate_checklist_markers_are_required_without_raw_marker_output(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    checklist_path = tmp_path / "manual-checklist.md"
    missing_marker = validator.MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS[-1]
    checklist_text = _manual_gate_checklist_text(validator).replace(missing_marker, "")
    checklist_path.write_text(checklist_text, encoding="utf-8")
    packet = _ready_packet()
    packet["manual_gate_checklist_path"] = str(checklist_path)
    _write_json(packet_path, packet)
    _allow_tmp_source_control_path(monkeypatch, validator, checklist_path)

    report = validator.build_report(packet_path)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_packet_completion_checklist"
    )
    serialized_requirement = json.dumps(checklist_requirement, sort_keys=True)

    assert report["production_gate_ready"] is False
    assert checklist_requirement["blockers"] == [
        "manual_gate_checklist_required_markers_missing"
    ]
    assert checklist_requirement["evidence"]["manual_gate_checklist_missing_marker_count"] == 1
    assert checklist_requirement["evidence"]["manual_gate_checklist_values_included"] is False
    assert missing_marker not in serialized_requirement


def test_manual_gate_private_packet_renderer_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["source_control_private_packet_renderer_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_private_packet_renderer"
    )

    assert report["production_gate_ready"] is False
    assert renderer_requirement["blockers"] == [
        "manual_gate_private_packet_renderer_not_documented"
    ]


def test_manual_gate_private_packet_renderer_markers_are_required_without_raw_output(
    monkeypatch,
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    incomplete_renderer = tmp_path / "render_phi_plan_manual_gate_private_packet.py"
    raw_renderer_text = "RenderConfig"
    incomplete_renderer.write_text(raw_renderer_text, encoding="utf-8")
    packet = _ready_packet()
    packet["private_packet_renderer_path"] = str(incomplete_renderer)
    _write_json(packet_path, packet)
    _allow_tmp_source_control_path(monkeypatch, validator, incomplete_renderer)

    report = validator.build_report(packet_path)
    serialized_report = json.dumps(report, sort_keys=True)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_gate_private_packet_renderer"
    )

    assert report["production_gate_ready"] is False
    assert renderer_requirement["blockers"] == [
        "manual_gate_private_packet_renderer_markers_missing"
    ]
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert raw_renderer_text not in serialized_report


def test_manual_gate_checklist_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    checklist_path = tmp_path / "phi-plan-manual-production-gate-checklist.md"
    unique_text = "outside manual gate checklist marker should not leak"
    _write_marker_file(
        checklist_path,
        validator.MANUAL_GATE_CHECKLIST_REQUIRED_MARKERS,
        unique_text,
    )
    packet = _ready_packet()
    packet["manual_gate_checklist_path"] = str(checklist_path)
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = _requirement(
        report,
        "manual_gate_packet_completion_checklist",
    )

    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is False
    assert (
        "source_control_manual_gate_checklist_must_be_inside_repo"
        in checklist_requirement["blockers"]
    )
    assert (
        "manual_gate_checklist_required_markers_missing"
        not in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["manual_gate_checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "manual_gate_checklist_inside_source_control"
        ]
        is False
    )
    assert (
        checklist_requirement["evidence"]["manual_gate_checklist_present_marker_count"]
        == 0
    )
    assert checklist_requirement["evidence"]["manual_gate_checklist_values_included"] is False
    assert unique_text not in serialized


def test_manual_gate_private_packet_renderer_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    renderer_path = tmp_path / "render_phi_plan_manual_gate_private_packet.py"
    unique_text = "outside manual gate private packet renderer marker should not leak"
    _write_marker_file(
        renderer_path,
        validator.MANUAL_GATE_PRIVATE_PACKET_RENDERER_REQUIRED_MARKERS,
        unique_text,
    )
    packet = _ready_packet()
    packet["private_packet_renderer_path"] = str(renderer_path)
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = _requirement(
        report,
        "manual_gate_private_packet_renderer",
    )

    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is False
    assert (
        "source_control_private_packet_renderer_must_be_inside_repo"
        in renderer_requirement["blockers"]
    )
    assert (
        "manual_gate_private_packet_renderer_markers_missing"
        not in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["private_packet_renderer_exists"] is True
    assert (
        renderer_requirement["evidence"][
            "private_packet_renderer_inside_source_control"
        ]
        is False
    )
    assert renderer_requirement["evidence"]["present_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert unique_text not in serialized


def test_student_cutover_private_env_renderer_must_stay_inside_source_control(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    renderer_path = tmp_path / "render_student_cutover_private_env.py"
    unique_text = "outside student cutover private env renderer marker should not leak"
    _write_marker_file(
        renderer_path,
        validator.STUDENT_CUTOVER_PRIVATE_ENV_RENDERER_REQUIRED_MARKERS,
        unique_text,
    )
    packet = _ready_packet()
    packet["student_default_cutover"]["private_env_renderer_path"] = str(
        renderer_path
    )
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = _requirement(
        report,
        "manual_student_cutover_private_env_renderer",
    )

    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is False
    assert (
        "student_cutover_private_env_renderer_must_be_inside_repo"
        in renderer_requirement["blockers"]
    )
    assert (
        "student_cutover_private_env_renderer_markers_missing"
        not in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert (
        renderer_requirement["evidence"][
            "private_env_renderer_inside_source_control"
        ]
        is False
    )
    assert renderer_requirement["evidence"]["present_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert unique_text not in serialized


def test_model_improvement_report_flag_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["user_data_model_improvement"]["model_improvement_evidence_report_ready"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    model_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_user_data_model_improvement_evidence"
    )

    assert report["production_gate_ready"] is False
    assert "model_improvement_evidence_report_not_ready" in model_requirement["blockers"]


def test_model_improvement_source_control_approval_runbook_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["user_data_model_improvement"]["source_control_approval_runbook_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    model_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_user_data_model_improvement_evidence"
    )

    assert report["production_gate_ready"] is False
    assert model_requirement["blockers"] == [
        "model_improvement_source_control_approval_runbook_not_documented"
    ]


def test_model_improvement_private_env_renderer_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["user_data_model_improvement"][
        "source_control_private_env_renderer_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    model_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_user_data_model_improvement_evidence"
    )

    assert report["production_gate_ready"] is False
    assert model_requirement["blockers"] == [
        "model_improvement_private_env_renderer_not_documented"
    ]


def test_production_corpus_report_flag_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["production_corpus"]["production_corpus_evidence_report_ready"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_corpus_evidence"
    )

    assert report["production_gate_ready"] is False
    assert "production_corpus_evidence_report_not_ready" in corpus_requirement["blockers"]


def test_production_corpus_source_control_review_runbook_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["production_corpus"]["source_control_review_runbook_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_corpus_evidence"
    )

    assert report["production_gate_ready"] is False
    assert corpus_requirement["blockers"] == [
        "production_corpus_source_control_review_runbook_not_documented"
    ]


def test_production_corpus_collection_license_checklist_documentation_is_required(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["production_corpus"][
        "source_control_collection_license_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_corpus_evidence"
    )

    assert report["production_gate_ready"] is False
    assert corpus_requirement["blockers"] == [
        "production_corpus_collection_license_checklist_not_documented"
    ]


def test_production_corpus_pair_source_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["production_corpus"]["source_control_pair_source_checklist_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_corpus_evidence"
    )

    assert report["production_gate_ready"] is False
    assert corpus_requirement["blockers"] == [
        "production_corpus_pair_source_checklist_not_documented"
    ]


def test_production_corpus_private_evidence_renderer_documentation_is_required(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["production_corpus"][
        "source_control_private_evidence_renderer_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_corpus_evidence"
    )

    assert report["production_gate_ready"] is False
    assert corpus_requirement["blockers"] == [
        "production_corpus_private_evidence_renderer_not_documented"
    ]


def test_retrieval_vector_backend_report_flag_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["retrieval_vector_backend"]["vector_backend_evidence_report_ready"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_retrieval_vector_backend_evidence"
    )

    assert report["production_gate_ready"] is False
    assert "retrieval_vector_backend_evidence_report_not_ready" in vector_requirement["blockers"]


def test_retrieval_vector_backend_source_control_runbook_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["retrieval_vector_backend"]["source_control_runbook_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_retrieval_vector_backend_evidence"
    )

    assert report["production_gate_ready"] is False
    assert vector_requirement["blockers"] == [
        "retrieval_vector_source_control_runbook_not_documented"
    ]


def test_retrieval_vector_backend_reindex_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["retrieval_vector_backend"][
        "source_control_reindex_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_retrieval_vector_backend_evidence"
    )

    assert report["production_gate_ready"] is False
    assert vector_requirement["blockers"] == [
        "retrieval_reindex_checklist_not_documented"
    ]


def test_retrieval_vector_backend_runtime_smoke_checklist_documentation_is_required(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["retrieval_vector_backend"][
        "source_control_runtime_smoke_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_retrieval_vector_backend_evidence"
    )

    assert report["production_gate_ready"] is False
    assert vector_requirement["blockers"] == [
        "retrieval_runtime_smoke_checklist_not_documented"
    ]


def test_retrieval_vector_backend_private_env_renderer_documentation_is_required(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["retrieval_vector_backend"][
        "source_control_private_env_renderer_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_retrieval_vector_backend_evidence"
    )

    assert report["production_gate_ready"] is False
    assert vector_requirement["blockers"] == [
        "retrieval_private_env_renderer_not_documented"
    ]


def test_prediction_fairness_report_flag_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"][
        "prediction_fairness_evidence_report_ready"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert "prediction_fairness_evidence_report_not_ready" in fairness_requirement["blockers"]


def test_prediction_fairness_latest_monitoring_run_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"]["latest_monitoring_run_passed"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == ["latest_monitoring_run_not_passed"]


def test_prediction_fairness_model_card_marker_verification_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"]["model_card_required_markers_verified"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == ["model_card_required_markers_not_verified"]


def test_prediction_fairness_source_control_runbook_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"]["source_control_monitoring_runbook_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == [
        "prediction_fairness_source_control_monitoring_runbook_not_documented"
    ]


def test_prediction_fairness_monitoring_validation_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"][
        "source_control_monitoring_validation_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == [
        "prediction_fairness_source_control_monitoring_validation_checklist_not_documented"
    ]


def test_prediction_fairness_legal_privacy_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"][
        "source_control_legal_privacy_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == [
        "prediction_fairness_source_control_legal_privacy_checklist_not_documented"
    ]


def test_prediction_fairness_private_evidence_renderer_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"][
        "source_control_private_evidence_renderer_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == [
        "prediction_fairness_private_evidence_renderer_not_documented"
    ]


def test_prediction_fairness_calibration_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["prediction_fairness_monitoring"][
        "source_control_calibration_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_prediction_fairness_monitoring_evidence"
    )

    assert report["production_gate_ready"] is False
    assert fairness_requirement["blockers"] == [
        "prediction_fairness_source_control_calibration_checklist_not_documented"
    ]


def test_student_cutover_rollback_review_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["student_default_cutover"]["rollback_to_nvidia_reviewed"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )

    assert report["production_gate_ready"] is False
    assert student_requirement["blockers"] == ["rollback_to_nvidia_not_reviewed"]


def test_student_cutover_source_control_runbook_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["student_default_cutover"]["source_control_runbook_documented"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )

    assert report["production_gate_ready"] is False
    assert student_requirement["blockers"] == ["source_control_runbook_not_documented"]


def test_student_cutover_private_env_renderer_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["student_default_cutover"][
        "source_control_private_env_renderer_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_cutover_private_env_renderer"
    )

    assert report["production_gate_ready"] is False
    assert student_requirement["blockers"] == [
        "student_cutover_private_env_renderer_not_documented"
    ]
    assert renderer_requirement["blockers"] == [
        "student_cutover_private_env_renderer_not_documented"
    ]


def test_runtime_supervisor_private_evidence_renderer_documentation_is_required(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["student_default_cutover"][
        "source_control_runtime_supervisor_private_evidence_renderer_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )

    assert report["production_gate_ready"] is False
    assert student_requirement["blockers"] == [
        "runtime_supervisor_private_evidence_renderer_not_documented"
    ]


def test_student_cutover_runtime_validation_checklist_documentation_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["student_default_cutover"][
        "source_control_runtime_validation_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )

    assert report["production_gate_ready"] is False
    assert student_requirement["blockers"] == [
        "source_control_runtime_validation_checklist_not_documented"
    ]


def test_student_cutover_runtime_owner_handoff_checklist_documentation_is_required(
    tmp_path,
):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["student_default_cutover"][
        "source_control_runtime_owner_handoff_checklist_documented"
    ] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_student_default_cutover_evidence"
    )

    assert report["production_gate_ready"] is False
    assert student_requirement["blockers"] == [
        "source_control_runtime_owner_handoff_checklist_not_documented"
    ]


def test_file_ingestion_surface_report_flag_is_required(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["file_ingestion_surface_audit"]["file_ingestion_surface_report_ready"] = False
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    ingestion_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_file_ingestion_surface_evidence"
    )

    assert report["production_gate_ready"] is False
    assert "file_ingestion_surface_report_not_ready" in ingestion_requirement["blockers"]


def test_unregistered_file_ingestion_surface_count_is_blocked(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    packet["file_ingestion_surface_audit"]["registered_upload_surface_count"] = 1
    packet["file_ingestion_surface_audit"]["unregistered_upload_surface_count"] = 1
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    ingestion_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_file_ingestion_surface_evidence"
    )

    assert report["production_gate_ready"] is False
    assert "registered_upload_surface_count_below_expected" in ingestion_requirement["blockers"]
    assert "unregistered_upload_surface_count_must_be_zero" in ingestion_requirement["blockers"]


def test_raw_reference_value_is_blocked_and_not_emitted(tmp_path):
    validator = _load_validator()
    packet_path = tmp_path / "packet.json"
    packet = _ready_packet()
    raw_reference = "approval-value-should-not-be-written"
    packet["student_default_cutover"]["approval_reference"] = raw_reference
    _write_json(packet_path, packet)

    report = validator.build_report(packet_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["production_gate_ready"] is False
    assert "raw approval, secret, or document value key is not allowed" in serialized
    assert raw_reference not in serialized
