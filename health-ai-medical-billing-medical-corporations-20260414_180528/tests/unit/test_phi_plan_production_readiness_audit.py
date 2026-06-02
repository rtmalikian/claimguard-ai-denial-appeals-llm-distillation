import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "run_phi_plan_production_readiness_audit.py"
SCRIPT_DIR = AUDIT_SCRIPT.parent


def _load_audit() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "run_phi_plan_production_readiness_audit",
        AUDIT_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_compose(path: Path, api_environment: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    environment_lines = "\n".join(
        f"      {key}: {value}" for key, value in api_environment.items()
    )
    path.write_text(
        "\n".join(
            [
                "services:",
                "  api:",
                "    environment:",
                environment_lines,
                "    depends_on:",
                "      db:",
                "        condition: service_healthy",
                "  frontend:",
                "    image: synthetic-frontend",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_security_control_sources(app_dir: Path) -> dict[str, Path]:
    auth_middleware = app_dir / "app" / "middleware" / "auth.py"
    core_auth = app_dir / "app" / "core" / "auth.py"
    core_security = app_dir / "app" / "core" / "security.py"
    audit_utils = app_dir / "app" / "utils" / "audit.py"
    auth_middleware.parent.mkdir(parents=True, exist_ok=True)
    core_auth.parent.mkdir(parents=True, exist_ok=True)
    core_security.parent.mkdir(parents=True, exist_ok=True)
    audit_utils.parent.mkdir(parents=True, exist_ok=True)
    auth_middleware.write_text(
        "\n".join(
            [
                "class JWTAuthMiddleware: pass",
                "PUBLIC_API_PATHS = set()",
                "decode_token",
                "request.state.user",
                "invalid_token_claims",
                "json_error_response",
                "",
            ]
        ),
        encoding="utf-8",
    )
    core_auth.write_text(
        "\n".join(
            [
                "ADMIN_ROLES = ('admin',)",
                "READ_ROLES = ('admin', 'billing_staff', 'viewer')",
                "WRITE_ROLES = ('admin', 'billing_staff')",
                "def authenticate_user(): pass",
                "def create_user_access_token(): pass",
                "def require_roles(): pass",
                "",
            ]
        ),
        encoding="utf-8",
    )
    core_security.write_text(
        "\n".join(
            [
                "class EncryptionService: pass",
                "ENCRYPTION_KEYS must contain at least one valid Fernet key in production",
                "Placeholder encryption keys are forbidden in production",
                "MultiFernet",
                "def create_access_token(): pass",
                "def decode_token(): pass",
                "",
            ]
        ),
        encoding="utf-8",
    )
    audit_utils.write_text(
        "\n".join(
            [
                "SENSITIVE_AUDIT_DETAIL_KEYS = set()",
                "def sanitize_audit_details(): pass",
                "scan_text_for_phi",
                "def log_audit(): pass",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "auth_middleware_module_path": auth_middleware,
        "core_auth_module_path": core_auth,
        "core_security_module_path": core_security,
        "audit_utils_module_path": audit_utils,
    }


def _settings(**overrides):
    defaults = {
        "LLM_PROVIDER": "nvidia_nim",
        "CLAIMGUARD_STUDENT_USE_BY_DEFAULT": False,
        "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED": False,
        "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE": "",
        "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED": False,
        "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA": False,
        "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH": False,
        "USER_DATA_MODEL_IMPROVEMENT_ENABLED": False,
        "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED": False,
        "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED": False,
        "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": "",
        "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": "",
        "RETRIEVAL_EMBEDDING_BACKEND": "hash",
        "RETRIEVAL_EMBEDDING_MODEL": "claimguard-hash-embedding-v1",
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED": False,
        "RETRIEVAL_VECTOR_BACKEND": "encrypted_local_metadata",
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": False,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _manifest_record(*, pair_id: str, role: str, source_type: str = "synthetic_deidentified_pair"):
    return {
        "source_id": f"SRC-{pair_id}-{role}",
        "document_id": f"DOC-{pair_id}-{role}",
        "pair_id": pair_id,
        "source_type": source_type,
        "document_role": role,
        "source_url_or_path": f"synthetic://{pair_id}/{role}",
        "checksum": f"sha256:{pair_id}-{role}",
        "phi_status": "deidentified",
        "deidentification_status": "training_eligible",
        "license_status": "approved",
        "review_status": "training_approved",
        "residual_risk_score": 0.0,
        "training_eligible": True,
        "split": "train",
        "micro_skill_ids": ["MS01"],
    }


def _synthetic_900_report(training_succeeded=None):
    return {
        "ready": False,
        "training_attempted": False,
        "training_succeeded": training_succeeded,
        "blocked_reasons": ["mlx_lm.lora cannot access a Metal device in this session"],
        "checks": {
            "data": {"ready": True},
            "manifest": {"ready": True},
            "adapter_output": {"exists_after_run": False},
        },
    }


def _manual_gate_packet_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "manual_gate_private_summary_metadata"},
            {"requirement_id": "manual_student_default_cutover_evidence"},
            {"requirement_id": "manual_user_data_model_improvement_evidence"},
            {"requirement_id": "manual_production_corpus_evidence"},
            {"requirement_id": "manual_retrieval_vector_backend_evidence"},
            {"requirement_id": "manual_prediction_fairness_monitoring_evidence"},
            {"requirement_id": "manual_backup_disaster_recovery_evidence"},
            {"requirement_id": "manual_dependency_security_evidence"},
            {"requirement_id": "manual_clearinghouse_submission_evidence"},
        ]
    )
    return {
        "safe_to_review": True,
        "production_gate_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _runtime_supervisor_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "mlx_runtime_supervisor_operator_controls"},
            {"requirement_id": "mlx_runtime_supervisor_private_runtime_metadata"},
            {"requirement_id": "mlx_runtime_supervisor_runtime_validation"},
        ]
    )
    return {
        "safe_to_review": True,
        "supervisor_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _vector_backend_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "retrieval_vector_backend_configuration"},
            {"requirement_id": "retrieval_vector_backend_index_state"},
            {"requirement_id": "retrieval_vector_backend_runtime_validation"},
        ]
    )
    return {
        "safe_to_review": True,
        "vector_backend_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _production_corpus_evidence_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "production_corpus_manual_review_attestations"},
            {"requirement_id": "production_corpus_manifest_pair_evidence"},
        ]
    )
    return {
        "safe_to_review": True,
        "production_corpus_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _model_improvement_evidence_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "model_improvement_legal_controls"},
            {"requirement_id": "model_improvement_runtime_controls"},
        ]
    )
    return {
        "safe_to_review": True,
        "model_improvement_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _prediction_fairness_evidence_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "prediction_fairness_calibrated_threshold"},
            {"requirement_id": "prediction_fairness_continuous_monitoring"},
            {"requirement_id": "prediction_fairness_governance_controls"},
        ]
    )
    return {
        "safe_to_review": True,
        "prediction_fairness_monitoring_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _backup_disaster_recovery_evidence_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "backup_disaster_recovery_storage_controls"},
            {"requirement_id": "backup_disaster_recovery_restore_validation"},
            {"requirement_id": "backup_disaster_recovery_key_recovery"},
            {"requirement_id": "backup_disaster_recovery_private_summary_metadata"},
        ]
    )
    return {
        "safe_to_review": True,
        "backup_disaster_recovery_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _dependency_security_evidence_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "dependency_security_scan_controls"},
            {"requirement_id": "dependency_security_remediation_controls"},
            {"requirement_id": "dependency_security_governance_controls"},
            {"requirement_id": "dependency_security_private_summary_metadata"},
        ]
    )
    return {
        "safe_to_review": True,
        "dependency_security_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _clearinghouse_submission_evidence_report(ready: bool) -> dict:
    blockers = (
        []
        if ready
        else [
            {"requirement_id": "clearinghouse_submission_connectivity_controls"},
            {"requirement_id": "clearinghouse_submission_transaction_controls"},
            {"requirement_id": "clearinghouse_submission_audit_retention_controls"},
            {"requirement_id": "clearinghouse_submission_private_summary_metadata"},
        ]
    )
    return {
        "safe_to_review": True,
        "clearinghouse_submission_ready": ready,
        "blocked_item_count": len(blockers),
        "blocked_items": blockers,
    }


def _file_ingestion_surface_report(ready: bool) -> dict:
    return {
        "ready": ready,
        "blocked_reasons": [] if ready else ["unregistered file-ingestion endpoint: /demo/upload"],
        "summary": {
            "discovered_count": 2,
            "expected_count": 2,
            "registered_count": 2 if ready else 1,
            "unregistered_count": 0 if ready else 1,
        },
    }


def test_production_audit_keeps_safe_state_but_blocks_current_unapproved_defaults(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(pair_id="PAIR-SYN-1", role="denial_letter"),
                _manifest_record(pair_id="PAIR-SYN-1", role="appeal_letter"),
            ]
        },
    )
    _write_json(synthetic_run, _synthetic_900_report())
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(False))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(False))
    _write_json(vector_backend_report, _vector_backend_report(False))
    _write_json(production_corpus_report, _production_corpus_evidence_report(False))
    _write_json(model_improvement_report, _model_improvement_evidence_report(False))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(False))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(False))
    _write_json(dependency_security_report, _dependency_security_evidence_report(False))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(False))

    report = audit.build_report(
        settings_like=_settings(),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
    )

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    warning_ids = {item["requirement_id"] for item in report["warning_items"]}
    assert report["safe_current_state"] is True
    assert report["production_ready"] is False
    completion = report["completion_audit"]
    assert completion["artifact"] == "phi_plan_completion_audit_matrix"
    assert completion["completion_proven"] is False
    assert (
        completion["completion_status"]
        == "not_complete_private_or_external_evidence_required"
    )
    assert completion["production_ready"] is False
    assert completion["safe_current_state"] is True
    assert completion["blocked_requirement_count"] == report["blocked_item_count"]
    assert completion["warning_requirement_ids"] == [
        "synthetic_900_adapter_training_status"
    ]
    assert completion["private_or_external_blocker_ids"] == [
        "backup_disaster_recovery_evidence",
        "clearinghouse_submission_evidence",
        "dependency_security_evidence",
        "manual_production_gate_packet_evidence",
        "production_corpus_expansion_beyond_synthetic",
        "production_prediction_fairness_monitoring",
        "production_semantic_vector_backend",
        "student_default_cutover_external_approval",
        "user_data_model_improvement_external_approval",
    ]
    assert completion["source_control_ready_requirement_ids"] == [
        "current_runtime_default_safe",
        "external_phi_service_guard",
        "file_ingestion_surface_audit_ready",
        "monitoring_gate_metrics_ready",
        "monitoring_readiness_endpoint_ready",
        "production_compose_startup_guard_env",
        "security_control_surface_ready",
    ]
    assert completion["raw_approval_values_included"] is False
    assert completion["raw_evidence_values_included"] is False
    assert completion["raw_report_paths_included"] is False
    assert completion["raw_phi_or_secret_values_included"] is False
    assert "manual_production_gate_packet_evidence" in blocked_ids
    assert "student_default_cutover_external_approval" in blocked_ids
    assert "file_ingestion_surface_audit_ready" not in blocked_ids
    assert "user_data_model_improvement_external_approval" in blocked_ids
    assert "production_semantic_vector_backend" in blocked_ids
    assert "production_corpus_expansion_beyond_synthetic" in blocked_ids
    assert "production_prediction_fairness_monitoring" in blocked_ids
    assert "backup_disaster_recovery_evidence" in blocked_ids
    assert "dependency_security_evidence" in blocked_ids
    assert "clearinghouse_submission_evidence" in blocked_ids
    assert "production_compose_startup_guard_env" not in blocked_ids
    assert "security_control_surface_ready" not in blocked_ids
    security_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "security_control_surface_ready"
    )
    assert security_requirement["status"] == "ready"
    assert security_requirement["evidence"]["production_encryption_key_required"] is True
    assert security_requirement["evidence"]["production_placeholder_key_rejected"] is True
    assert security_requirement["evidence"]["production_valid_key_persistent"] is True
    assert (
        security_requirement["evidence"]["audit_sanitizer_redacts_sensitive_values"]
        is True
    )
    assert security_requirement["evidence"]["raw_sentinel_values_included"] is False
    assert security_requirement["evidence"]["raw_auth_token_included"] is False
    compose_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "production_compose_startup_guard_env"
    )
    assert compose_requirement["status"] == "ready"
    assert compose_requirement["evidence"]["raw_env_values_included"] is False
    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "student_default_cutover_external_approval"
    )
    assert "student_runtime_supervisor_report_not_ready" in student_requirement["blockers"]
    assert student_requirement["evidence"]["runtime_supervisor_blocked_requirement_ids"] == [
        "mlx_runtime_supervisor_operator_controls",
        "mlx_runtime_supervisor_private_runtime_metadata",
        "mlx_runtime_supervisor_runtime_validation",
    ]
    vector_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_semantic_vector_backend"
    )
    assert "retrieval_vector_backend_report_not_ready" in vector_requirement["blockers"]
    assert "embedding_model_not_approved_for_production" in vector_requirement["blockers"]
    assert "hash_fallback_not_disabled_for_production" in vector_requirement["blockers"]
    assert vector_requirement["evidence"]["vector_backend_blocked_requirement_ids"] == [
        "retrieval_vector_backend_configuration",
        "retrieval_vector_backend_index_state",
        "retrieval_vector_backend_runtime_validation",
    ]
    corpus_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_corpus_expansion_beyond_synthetic"
    )
    assert "production_corpus_evidence_report_not_ready" in corpus_requirement["blockers"]
    assert corpus_requirement["evidence"]["production_corpus_blocked_requirement_ids"] == [
        "production_corpus_manifest_pair_evidence",
        "production_corpus_manual_review_attestations",
    ]
    model_improvement_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "user_data_model_improvement_external_approval"
    )
    assert "model_improvement_evidence_report_not_ready" in model_improvement_requirement["blockers"]
    assert model_improvement_requirement["evidence"]["model_improvement_blocked_requirement_ids"] == [
        "model_improvement_legal_controls",
        "model_improvement_runtime_controls",
    ]
    fairness_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "production_prediction_fairness_monitoring"
    )
    assert "prediction_fairness_evidence_report_not_ready" in fairness_requirement["blockers"]
    assert fairness_requirement["evidence"]["prediction_fairness_blocked_requirement_ids"] == [
        "prediction_fairness_calibrated_threshold",
        "prediction_fairness_continuous_monitoring",
        "prediction_fairness_governance_controls",
    ]
    backup_dr_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "backup_disaster_recovery_evidence"
    )
    assert "backup_disaster_recovery_evidence_report_not_ready" in backup_dr_requirement["blockers"]
    assert backup_dr_requirement["evidence"]["backup_disaster_recovery_blocked_requirement_ids"] == [
        "backup_disaster_recovery_key_recovery",
        "backup_disaster_recovery_private_summary_metadata",
        "backup_disaster_recovery_restore_validation",
        "backup_disaster_recovery_storage_controls",
    ]
    dependency_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "dependency_security_evidence"
    )
    assert "dependency_security_evidence_report_not_ready" in dependency_requirement["blockers"]
    assert dependency_requirement["evidence"]["dependency_security_blocked_requirement_ids"] == [
        "dependency_security_governance_controls",
        "dependency_security_private_summary_metadata",
        "dependency_security_remediation_controls",
        "dependency_security_scan_controls",
    ]
    clearinghouse_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "clearinghouse_submission_evidence"
    )
    assert (
        "clearinghouse_submission_evidence_report_not_ready"
        in clearinghouse_requirement["blockers"]
    )
    assert clearinghouse_requirement["evidence"]["clearinghouse_submission_blocked_requirement_ids"] == [
        "clearinghouse_submission_audit_retention_controls",
        "clearinghouse_submission_connectivity_controls",
        "clearinghouse_submission_private_summary_metadata",
        "clearinghouse_submission_transaction_controls",
    ]
    manual_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "manual_production_gate_packet_evidence"
    )
    assert manual_requirement["evidence"]["blocked_requirement_ids"] == [
        "manual_backup_disaster_recovery_evidence",
        "manual_clearinghouse_submission_evidence",
        "manual_dependency_security_evidence",
        "manual_gate_private_summary_metadata",
        "manual_prediction_fairness_monitoring_evidence",
        "manual_production_corpus_evidence",
        "manual_retrieval_vector_backend_evidence",
        "manual_student_default_cutover_evidence",
        "manual_user_data_model_improvement_evidence",
    ]
    manual_action = next(
        action
        for action in report["next_required_actions"]
        if "manual_gate_packet.template.json" in action
    )
    for expected_phrase in [
        "student cutover",
        "user-data model improvement",
        "production corpus",
        "retrieval-vector backend",
        "prediction fairness monitoring",
        "backup/disaster-recovery",
        "dependency-security",
        "clearinghouse submission",
        "file-ingestion surface",
        "private summary paths",
        "production document content",
    ]:
        assert expected_phrase in manual_action
    assert "synthetic_900_adapter_training_status" in warning_ids
    file_ingestion_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "file_ingestion_surface_audit_ready"
    )
    assert file_ingestion_requirement["status"] == "ready"
    assert file_ingestion_requirement["evidence"]["summary"]["registered_count"] == 2


def test_production_audit_can_be_ready_with_external_gates_and_real_pair(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="student-approval-ref",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="model-improvement-ref",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
    )

    assert report["safe_current_state"] is True
    assert report["production_ready"] is True
    assert report["blocked_item_count"] == 0
    completion = report["completion_audit"]
    assert completion["completion_proven"] is True
    assert completion["completion_status"] == "complete"
    assert completion["non_completion_reason"] is None
    assert completion["blocked_requirement_ids"] == []
    assert completion["private_or_external_blocker_ids"] == []
    assert completion["production_ready"] is True


def test_production_audit_does_not_emit_secret_reference_values(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    student_reference = "student-approval-reference-do-not-write"
    model_reference = "model-improvement-reference-do-not-write"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE=student_reference,
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE=model_reference,
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert student_reference not in serialized
    assert model_reference not in serialized
    assert '"approval_reference_configured": true' in serialized


def test_production_audit_emits_repo_relative_paths_and_redacts_external_paths(
    monkeypatch,
    tmp_path,
):
    audit = _load_audit()
    repo_root = tmp_path / "repo"
    report_dir = repo_root / "llm-distill" / "evals" / "reports"
    data_dir = repo_root / "llm-distill" / "data"
    app_dir = repo_root / "health-ai-medical-billing-medical-corporations-20260414_180528"
    distillation_report = report_dir / "distillation.json"
    corpus_manifest = data_dir / "corpus" / "manifest.json"
    synthetic_run = report_dir / "synthetic_900_run.json"
    manual_gate_packet_report = report_dir / "manual_gate_packet_report.json"
    runtime_supervisor_report = report_dir / "runtime_supervisor_report.json"
    vector_backend_report = report_dir / "vector_backend_report.json"
    production_corpus_report = report_dir / "production_corpus_report.json"
    model_improvement_report = report_dir / "model_improvement_report.json"
    file_ingestion_surface_report = report_dir / "file_ingestion_surface_report.json"
    prediction_fairness_report = report_dir / "prediction_fairness_report.json"
    backup_disaster_recovery_report = report_dir / "backup_disaster_recovery_report.json"
    dependency_security_report = report_dir / "dependency_security_report.json"
    clearinghouse_submission_report = report_dir / "clearinghouse_submission_report.json"
    production_compose = app_dir / "docker-compose.production.yml"
    monitoring_module = app_dir / "app" / "api" / "v1" / "monitoring.py"
    security_source_paths = _write_security_control_sources(app_dir)
    outside_missing_report = tmp_path / "outside" / "private-report.json"

    monkeypatch.setattr(audit, "REPO_ROOT", repo_root)
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(pair_id="PAIR-SYN-1", role="denial_letter"),
                _manifest_record(pair_id="PAIR-SYN-1", role="appeal_letter"),
            ]
        },
    )
    _write_json(synthetic_run, _synthetic_900_report())
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(False))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(False))
    _write_json(vector_backend_report, _vector_backend_report(False))
    _write_json(production_corpus_report, _production_corpus_evidence_report(False))
    _write_json(model_improvement_report, _model_improvement_evidence_report(False))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(False))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(False))
    _write_json(dependency_security_report, _dependency_security_evidence_report(False))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(False))
    _write_compose(
        production_compose,
        {
            name: "${" + name + (":-" + default if default else "") + "}"
            for name, default in audit.REQUIRED_PRODUCTION_COMPOSE_GUARD_DEFAULTS.items()
        },
    )
    monitoring_module.parent.mkdir(parents=True, exist_ok=True)
    monitoring_module.write_text(
        "\n".join(
            [
                *(f"{name} = '{name}'" for name in sorted(audit.REQUIRED_MONITORING_GATE_METRICS)),
                '@router.get("/phi-plan-readiness")',
                "_safe_phi_plan_readiness_payload",
                "blocked_requirement_ids",
                "ready_requirement_ids",
                "raw_report_paths_included",
                "raw_evidence_included",
                "raw_approval_or_reference_values_included",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit.build_report(
        settings_like=_settings(),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
        production_compose_path=production_compose,
        monitoring_module_path=monitoring_module,
        **security_source_paths,
    )
    serialized = json.dumps(report, sort_keys=True)
    _, missing_errors = audit.load_json(outside_missing_report)

    assert str(repo_root) not in serialized
    assert "llm-distill/evals/reports/distillation.json" in serialized
    assert "llm-distill/data/corpus/manifest.json" in serialized
    assert "health-ai-medical-billing-medical-corporations-20260414_180528/docker-compose.production.yml" in serialized
    assert missing_errors == ["missing file: external_path_redacted"]
    assert str(outside_missing_report) not in json.dumps(missing_errors)


def test_production_audit_cli_sanitizes_source_controlled_report_output(
    monkeypatch,
    tmp_path,
):
    audit = _load_audit()
    repo_root = tmp_path / "repo"
    report_dir = repo_root / "llm-distill" / "evals" / "reports"
    data_dir = repo_root / "llm-distill" / "data"
    app_dir = repo_root / "health-ai-medical-billing-medical-corporations-20260414_180528"
    output_report = report_dir / "phi_plan_production_readiness_report.json"
    distillation_report = report_dir / "distillation.json"
    corpus_manifest = data_dir / "corpus" / "manifest.json"
    synthetic_run = report_dir / "synthetic_900_run.json"
    manual_gate_packet_report = report_dir / "manual_gate_packet_report.json"
    runtime_supervisor_report = report_dir / "runtime_supervisor_report.json"
    vector_backend_report = report_dir / "vector_backend_report.json"
    production_corpus_report = report_dir / "production_corpus_report.json"
    model_improvement_report = report_dir / "model_improvement_report.json"
    file_ingestion_surface_report = report_dir / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "outside" / "prediction_fairness_report.json"
    backup_disaster_recovery_report = report_dir / "backup_disaster_recovery_report.json"
    dependency_security_report = report_dir / "dependency_security_report.json"
    clearinghouse_submission_report = report_dir / "clearinghouse_submission_report.json"
    production_compose = app_dir / "docker-compose.production.yml"
    monitoring_module = app_dir / "app" / "api" / "v1" / "monitoring.py"
    security_source_paths = _write_security_control_sources(app_dir)

    monkeypatch.setattr(audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(audit, "load_runtime_settings", lambda: _settings())
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(pair_id="PAIR-SYN-1", role="denial_letter"),
                _manifest_record(pair_id="PAIR-SYN-1", role="appeal_letter"),
            ]
        },
    )
    _write_json(synthetic_run, _synthetic_900_report())
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(False))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(False))
    _write_json(vector_backend_report, _vector_backend_report(False))
    _write_json(production_corpus_report, _production_corpus_evidence_report(False))
    _write_json(model_improvement_report, _model_improvement_evidence_report(False))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(False))
    _write_json(dependency_security_report, _dependency_security_evidence_report(False))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(False))
    _write_compose(
        production_compose,
        {
            name: "${" + name + (":-" + default if default else "") + "}"
            for name, default in audit.REQUIRED_PRODUCTION_COMPOSE_GUARD_DEFAULTS.items()
        },
    )
    monitoring_module.parent.mkdir(parents=True, exist_ok=True)
    monitoring_module.write_text(
        "\n".join(
            [
                *(f"{name} = '{name}'" for name in sorted(audit.REQUIRED_MONITORING_GATE_METRICS)),
                '@router.get("/phi-plan-readiness")',
                "_safe_phi_plan_readiness_payload",
                "blocked_requirement_ids",
                "ready_requirement_ids",
                "raw_report_paths_included",
                "raw_evidence_included",
                "raw_approval_or_reference_values_included",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phi_plan_production_readiness_audit.py",
            "--report",
            str(output_report),
            "--corpus-manifest",
            str(corpus_manifest),
            "--distillation-report",
            str(distillation_report),
            "--synthetic-900-run-report",
            str(synthetic_run),
            "--manual-gate-packet-report",
            str(manual_gate_packet_report),
            "--runtime-supervisor-report",
            str(runtime_supervisor_report),
            "--vector-backend-report",
            str(vector_backend_report),
            "--production-corpus-report",
            str(production_corpus_report),
            "--model-improvement-report",
            str(model_improvement_report),
            "--file-ingestion-surface-report",
            str(file_ingestion_surface_report),
            "--prediction-fairness-report",
            str(prediction_fairness_report),
            "--backup-disaster-recovery-report",
            str(backup_disaster_recovery_report),
            "--dependency-security-report",
            str(dependency_security_report),
            "--clearinghouse-submission-report",
            str(clearinghouse_submission_report),
            "--production-compose",
            str(production_compose),
            "--monitoring-module",
            str(monitoring_module),
            "--auth-middleware-module",
            str(security_source_paths["auth_middleware_module_path"]),
            "--core-auth-module",
            str(security_source_paths["core_auth_module_path"]),
            "--core-security-module",
            str(security_source_paths["core_security_module_path"]),
            "--audit-utils-module",
            str(security_source_paths["audit_utils_module_path"]),
        ],
    )

    assert audit.main() == 0

    text = output_report.read_text(encoding="utf-8")
    report = json.loads(text)
    assert text.endswith("\n")
    assert str(repo_root) not in text
    assert str(prediction_fairness_report) not in text
    assert "llm-distill/evals/reports/distillation.json" in text
    assert "external_path_redacted" in text
    assert report["safe_current_state"] is True
    assert report["production_ready"] is False


def test_production_audit_blocks_unready_file_ingestion_surface_report(tmp_path):
    audit = _load_audit()
    report_path = tmp_path / "file_ingestion_surface_report.json"
    _write_json(report_path, _file_ingestion_surface_report(False))

    requirement = audit.file_ingestion_surface_requirement(report_path)

    assert requirement["status"] == "blocked"
    assert "file_ingestion_surface_audit_not_ready" in requirement["blockers"]
    assert any(
        "unregistered file-ingestion endpoint" in blocker
        for blocker in requirement["blockers"]
    )


def test_production_audit_blocks_missing_monitoring_gate_metrics(tmp_path):
    audit = _load_audit()
    monitoring_module = tmp_path / "monitoring.py"
    monitoring_module.write_text(
        "\n".join(
            [
                "def build_prometheus_metrics(db):",
                "    return 'claimguard_prometheus_no_phi_context 1\\n'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    requirement = audit.monitoring_gate_metrics_requirement(monitoring_module)

    assert requirement["status"] == "blocked"
    assert "monitoring_gate_metrics_missing_from_source" in requirement["blockers"]
    assert "claimguard_student_default_enabled" in requirement["evidence"]["missing_source_metrics"]
    assert requirement["evidence"]["runtime_check_performed"] is False
    assert requirement["evidence"]["raw_metric_output_included"] is False


def test_production_audit_blocks_missing_monitoring_readiness_endpoint(tmp_path):
    audit = _load_audit()
    monitoring_module = tmp_path / "monitoring.py"
    monitoring_module.write_text(
        "\n".join(
            [
                "def build_prometheus_metrics(db):",
                "    return 'claimguard_prometheus_no_phi_context 1\\n'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    requirement = audit.monitoring_readiness_endpoint_requirement(monitoring_module)

    assert requirement["status"] == "blocked"
    assert "monitoring_readiness_endpoint_missing_from_source" in requirement["blockers"]
    assert '@router.get("/phi-plan-readiness")' in requirement["evidence"]["missing_source_markers"]
    assert requirement["evidence"]["runtime_check_performed"] is False
    assert requirement["evidence"]["raw_evidence_included"] is False
    assert requirement["evidence"]["raw_report_paths_included"] is False


def test_production_audit_blocks_missing_security_control_markers(tmp_path):
    audit = _load_audit()
    security_source_paths = _write_security_control_sources(tmp_path / "app")
    security_source_paths["core_security_module_path"].write_text(
        "class EncryptionService: pass\n",
        encoding="utf-8",
    )

    requirement = audit.security_control_surface_requirement(**security_source_paths)

    assert requirement["status"] == "blocked"
    assert "security_control_source_markers_missing" in requirement["blockers"]
    assert "MultiFernet" in requirement["evidence"]["missing_source_markers"]["core_security"]
    assert (
        "Placeholder encryption keys are forbidden in production"
        in requirement["evidence"]["missing_source_markers"]["core_security"]
    )
    assert requirement["evidence"]["runtime_check_performed"] is False
    assert requirement["evidence"]["raw_sentinel_values_included"] is False
    assert requirement["evidence"]["raw_secret_included"] is False


def test_production_audit_safe_state_depends_on_file_ingestion_gate(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(False))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="student-approval-ref",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="model-improvement-ref",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
    )

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_current_state"] is False
    assert report["production_ready"] is False
    assert blocked_ids == {"file_ingestion_surface_audit_ready"}


def test_production_audit_safe_state_depends_on_monitoring_gate_metrics(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    monitoring_module = tmp_path / "monitoring.py"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))
    monitoring_module.write_text(
        "\n".join(
            [
                "claimguard_prometheus_no_phi_context = 'claimguard_prometheus_no_phi_context'",
                '@router.get("/phi-plan-readiness")',
                "_safe_phi_plan_readiness_payload",
                "blocked_requirement_ids",
                "ready_requirement_ids",
                "raw_report_paths_included",
                "raw_evidence_included",
                "raw_approval_or_reference_values_included",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="student-approval-ref",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="model-improvement-ref",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
        monitoring_module_path=monitoring_module,
    )

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_current_state"] is False
    assert report["production_ready"] is False
    assert blocked_ids == {"monitoring_gate_metrics_ready"}


def test_production_audit_safe_state_depends_on_monitoring_readiness_endpoint(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    monitoring_module = tmp_path / "monitoring.py"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))
    monitoring_module.write_text(
        "\n".join(
            f"{metric_name} = '{metric_name}'"
            for metric_name in sorted(audit.REQUIRED_MONITORING_GATE_METRICS)
        ),
        encoding="utf-8",
    )

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="student-approval-ref",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="model-improvement-ref",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
        monitoring_module_path=monitoring_module,
    )

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_current_state"] is False
    assert report["production_ready"] is False
    assert blocked_ids == {"monitoring_readiness_endpoint_ready"}


def test_production_audit_safe_state_depends_on_security_control_surface(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    security_source_paths = _write_security_control_sources(tmp_path / "app")
    security_source_paths["auth_middleware_module_path"].write_text(
        "\n".join(
            [
                "class JWTAuthMiddleware: pass",
                "PUBLIC_API_PATHS = set()",
                "decode_token",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="student-approval-ref",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="model-improvement-ref",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
        **security_source_paths,
    )

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_current_state"] is False
    assert report["production_ready"] is False
    assert blocked_ids == {"security_control_surface_ready"}


def test_production_audit_safe_state_blocks_unapproved_student_auto_launch(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(pair_id="PAIR-SYN-1", role="denial_letter"),
                _manifest_record(pair_id="PAIR-SYN-1", role="appeal_letter"),
            ]
        },
    )
    _write_json(synthetic_run, _synthetic_900_report())
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(False))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(False))
    _write_json(vector_backend_report, _vector_backend_report(False))
    _write_json(production_corpus_report, _production_corpus_evidence_report(False))
    _write_json(model_improvement_report, _model_improvement_evidence_report(False))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(False))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(False))
    _write_json(dependency_security_report, _dependency_security_evidence_report(False))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(False))

    report = audit.build_report(
        settings_like=_settings(CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=True),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
    )

    student_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "student_default_cutover_external_approval"
    )
    assert report["safe_current_state"] is False
    assert student_requirement["evidence"]["student_auto_launch_requested"] is True
    assert "student_runtime_supervisor_report_not_ready" in student_requirement["blockers"]


def test_production_audit_safe_state_depends_on_compose_guard_env(tmp_path):
    audit = _load_audit()
    distillation_report = tmp_path / "distillation.json"
    corpus_manifest = tmp_path / "manifest.json"
    synthetic_run = tmp_path / "synthetic_900_run.json"
    manual_gate_packet_report = tmp_path / "manual_gate_packet_report.json"
    runtime_supervisor_report = tmp_path / "runtime_supervisor_report.json"
    vector_backend_report = tmp_path / "vector_backend_report.json"
    production_corpus_report = tmp_path / "production_corpus_report.json"
    model_improvement_report = tmp_path / "model_improvement_report.json"
    file_ingestion_surface_report = tmp_path / "file_ingestion_surface_report.json"
    prediction_fairness_report = tmp_path / "prediction_fairness_report.json"
    backup_disaster_recovery_report = tmp_path / "backup_disaster_recovery_report.json"
    dependency_security_report = tmp_path / "dependency_security_report.json"
    clearinghouse_submission_report = tmp_path / "clearinghouse_submission_report.json"
    production_compose = tmp_path / "docker-compose.production.yml"
    _write_json(distillation_report, {"release_ready": True})
    _write_json(
        corpus_manifest,
        {
            "records": [
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="denial_letter",
                    source_type="real_deidentified_pair",
                ),
                _manifest_record(
                    pair_id="PAIR-REAL-1",
                    role="appeal_letter",
                    source_type="real_deidentified_pair",
                ),
            ]
        },
    )
    _write_json(synthetic_run, {"training_attempted": True, "training_succeeded": True, "checks": {}})
    _write_json(manual_gate_packet_report, _manual_gate_packet_report(True))
    _write_json(runtime_supervisor_report, _runtime_supervisor_report(True))
    _write_json(vector_backend_report, _vector_backend_report(True))
    _write_json(production_corpus_report, _production_corpus_evidence_report(True))
    _write_json(model_improvement_report, _model_improvement_evidence_report(True))
    _write_json(file_ingestion_surface_report, _file_ingestion_surface_report(True))
    _write_json(prediction_fairness_report, _prediction_fairness_evidence_report(True))
    _write_json(backup_disaster_recovery_report, _backup_disaster_recovery_evidence_report(True))
    _write_json(dependency_security_report, _dependency_security_evidence_report(True))
    _write_json(clearinghouse_submission_report, _clearinghouse_submission_evidence_report(True))
    _write_compose(
        production_compose,
        {
            "CLAIMGUARD_STUDENT_USE_BY_DEFAULT": "${CLAIMGUARD_STUDENT_USE_BY_DEFAULT:-true}",
            "CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT": "${CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT:-false}",
        },
    )

    report = audit.build_report(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="student-approval-ref",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=True,
            USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=True,
            USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION="notice-v1",
            USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE="model-improvement-ref",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        corpus_manifest_path=corpus_manifest,
        distillation_report_path=distillation_report,
        synthetic_900_run_report_path=synthetic_run,
        manual_gate_packet_report_path=manual_gate_packet_report,
        runtime_supervisor_report_path=runtime_supervisor_report,
        vector_backend_report_path=vector_backend_report,
        production_corpus_report_path=production_corpus_report,
        model_improvement_report_path=model_improvement_report,
        file_ingestion_surface_report_path=file_ingestion_surface_report,
        prediction_fairness_report_path=prediction_fairness_report,
        backup_disaster_recovery_report_path=backup_disaster_recovery_report,
        dependency_security_report_path=dependency_security_report,
        clearinghouse_submission_report_path=clearinghouse_submission_report,
        production_compose_path=production_compose,
    )

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    compose_requirement = report["blocked_items"][0]
    assert report["safe_current_state"] is False
    assert report["production_ready"] is False
    assert blocked_ids == {"production_compose_startup_guard_env"}
    assert "production_compose_missing_startup_guard_env_vars" in compose_requirement["blockers"]
    assert "production_compose_has_unconsumed_guard_aliases" in compose_requirement["blockers"]
    assert "production_compose_guard_env_defaults_not_conservative" in compose_requirement["blockers"]
    assert compose_requirement["evidence"]["raw_env_values_included"] is False
    assert "CLAIMGUARD_ALLOW_MODEL_IMPROVEMENT" in compose_requirement["evidence"]["forbidden_guard_env_vars"]
    assert "CLAIMGUARD_STUDENT_USE_BY_DEFAULT" in compose_requirement["evidence"]["non_conservative_default_guard_env_vars"]


def test_vector_backend_requirement_redacts_url_or_credential_shaped_backend():
    audit = _load_audit()
    raw_backend = "postgresql://runtimeuser@localhost:5432/vector"

    requirement = audit.vector_backend_requirement(
        _settings(
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND=raw_backend,
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
        ),
        vector_backend_report_path=None,
    )
    serialized = json.dumps(requirement, sort_keys=True)

    assert requirement["status"] == "blocked"
    assert "vector_backend_setting_must_not_store_url_or_credentials" in requirement["blockers"]
    assert requirement["evidence"]["vector_backend"] == "redacted_url_or_credentials"
    assert requirement["evidence"]["vector_backend_has_url_or_credentials"] is True
    assert raw_backend not in serialized
    assert "runtimeuser" not in serialized
