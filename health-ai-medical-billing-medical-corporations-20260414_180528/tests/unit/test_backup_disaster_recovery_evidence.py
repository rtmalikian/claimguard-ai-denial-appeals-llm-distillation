import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_SCRIPT = (
    REPO_ROOT / "llm-distill" / "scripts" / "validate_backup_disaster_recovery_evidence.py"
)
RENDERER_SCRIPT = (
    REPO_ROOT / "llm-distill" / "scripts" / "render_backup_disaster_recovery_private_evidence.py"
)
SCRIPT_DIR = VALIDATOR_SCRIPT.parent


def _load_module(script: Path, module_name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(module_name, script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ready_evidence() -> dict:
    return {
        "artifact": "claimguard_backup_disaster_recovery_evidence",
        "version": "1.0",
        "evidence_status": "backup_disaster_recovery_ready",
        "backup_disaster_recovery_ready": True,
        "no_phi_or_secret_values_attested": True,
        "no_backup_storage_values_attested": True,
        "no_database_row_values_attested": True,
        "no_encryption_key_values_attested": True,
        "private_backup_summary_path_env": "CLAIMGUARD_BACKUP_DR_PRIVATE_SUMMARY_PATH",
        "private_backup_summary_path_configured": True,
        "private_backup_summary_path_value_included": False,
        "private_backup_summary_checked": True,
        "private_backup_summary_private_reference_count": 4,
        "private_backup_summary_backup_artifact_count": 2,
        "private_backup_summary_restore_verification_count": 1,
        "private_backup_summary_key_recovery_artifact_count": 1,
        "private_backup_summary_retention_policy_count": 1,
        "private_backup_summary_raw_values_included": False,
        "backup_storage_controls": {
            "off_repository_backup_storage_configured": True,
            "backup_artifacts_encrypted_at_rest": True,
            "scheduler_least_privilege_verified": True,
            "backup_restore_access_reviewed": True,
            "retention_period_approved": True,
        },
        "restore_validation_controls": {
            "restore_verification_completed": True,
            "restore_verification_metadata_only": True,
            "disaster_recovery_smoke_completed": True,
            "recovery_objectives_approved": True,
            "rollback_restore_procedure_reviewed": True,
        },
        "key_recovery_controls": {
            "encryption_key_recovery_tested": True,
            "key_custody_reviewed": True,
            "no_key_values_in_evidence": True,
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
            "metadata_only_audit_reviewed": True,
            "incident_recording_without_phi_reviewed": True,
        },
    }


def _private_summary() -> dict:
    return {
        "backup_storage_outside_repository_verified": True,
        "backup_artifact_encryption_verified": True,
        "scheduler_least_privilege_verified": True,
        "restore_verification_completed": True,
        "restore_verification_metadata_only": True,
        "encryption_key_recovery_tested": True,
        "key_custody_reviewed": True,
        "disaster_recovery_smoke_completed": True,
        "retention_period_approved": True,
        "recovery_objectives_approved": True,
        "rollback_restore_procedure_reviewed": True,
        "metadata_only_audit_reviewed": True,
        "incident_recording_without_phi_reviewed": True,
        "no_phi_or_secret_values_included": True,
        "no_backup_paths_included": True,
        "no_database_rows_included": True,
        "no_encryption_key_values_included": True,
        "private_reference_count": 4,
        "backup_artifact_count": 2,
        "restore_verification_count": 1,
        "key_recovery_artifact_count": 1,
        "retention_policy_count": 1,
    }


def test_backup_dr_template_is_safe_to_review_but_not_ready():
    validator = _load_module(VALIDATOR_SCRIPT, "validate_backup_disaster_recovery_evidence")

    report = validator.build_report()
    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    runbook = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "backup_disaster_recovery_runbook"
    )
    renderer = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "backup_disaster_recovery_private_evidence_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["backup_disaster_recovery_ready"] is False
    assert "backup_disaster_recovery_no_phi_secret_or_values" not in blocked_ids
    assert "backup_disaster_recovery_runbook" not in blocked_ids
    assert "backup_disaster_recovery_private_evidence_renderer" not in blocked_ids
    assert "backup_disaster_recovery_storage_controls" in blocked_ids
    assert "backup_disaster_recovery_restore_validation" in blocked_ids
    assert "backup_disaster_recovery_key_recovery" in blocked_ids
    assert "backup_disaster_recovery_private_summary_metadata" in blocked_ids
    assert "backup_disaster_recovery_ready_flag" in blocked_ids
    assert runbook["evidence"]["runbook_missing_marker_count"] == 0
    assert runbook["evidence"]["runbook_values_included"] is False
    assert renderer["evidence"]["private_evidence_renderer_missing_marker_count"] == 0
    assert renderer["evidence"]["private_evidence_renderer_values_included"] is False


def test_backup_dr_validator_accepts_fully_attested_boolean_evidence(tmp_path):
    validator = _load_module(VALIDATOR_SCRIPT, "validate_backup_disaster_recovery_evidence")
    evidence_path = tmp_path / "backup_dr_ready.json"
    _write_json(evidence_path, _ready_evidence())

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["backup_disaster_recovery_ready"] is True
    assert report["blocked_item_count"] == 0


def test_backup_dr_private_renderer_refuses_source_control_output():
    renderer = _load_module(RENDERER_SCRIPT, "render_backup_disaster_recovery_private_evidence")
    output = REPO_ROOT / "llm-distill" / "evals" / "reports" / "private-backup-dr.json"
    config = renderer.RenderConfig(
        output=output,
        approved_mode=True,
        backup_storage_configured=True,
        encrypted_at_rest=True,
        scheduler_least_privilege=True,
        restore_verification_completed=True,
        restore_verification_metadata_only=True,
        key_recovery_tested=True,
        key_custody_reviewed=True,
        disaster_recovery_smoke_completed=True,
        retention_approved=True,
        recovery_objectives_approved=True,
        rollback_restore_reviewed=True,
        metadata_only_audit_reviewed=True,
        incident_recording_without_phi_reviewed=True,
        no_raw_values_attested=True,
    )

    payload = renderer.render_private_evidence(config, env={})

    assert payload["backup_disaster_recovery_ready"] is False
    assert "refusing_to_write_inside_source_control" in payload["blockers"]
    assert payload["values_redacted"] is True
    assert str(output) not in json.dumps(payload)


def test_backup_dr_private_renderer_outputs_ready_boolean_evidence(tmp_path):
    renderer = _load_module(RENDERER_SCRIPT, "render_backup_disaster_recovery_private_evidence")
    summary_path = tmp_path / "private-summary.json"
    output = tmp_path / "private-output" / "backup-dr-evidence.json"
    _write_json(summary_path, _private_summary())
    env = {
        "CLAIMGUARD_BACKUP_DR_PRIVATE_SUMMARY_PATH": str(summary_path),
        "CLAIMGUARD_BACKUP_DR_STORAGE_REFERENCE": "configured",
        "CLAIMGUARD_BACKUP_DR_RESTORE_VERIFICATION_REFERENCE": "configured",
        "CLAIMGUARD_BACKUP_DR_KEY_RECOVERY_REFERENCE": "configured",
        "CLAIMGUARD_BACKUP_DR_RETENTION_APPROVAL_REFERENCE": "configured",
    }
    config = renderer.RenderConfig(
        output=output,
        approved_mode=True,
        backup_storage_configured=True,
        encrypted_at_rest=True,
        scheduler_least_privilege=True,
        restore_verification_completed=True,
        restore_verification_metadata_only=True,
        key_recovery_tested=True,
        key_custody_reviewed=True,
        disaster_recovery_smoke_completed=True,
        retention_approved=True,
        recovery_objectives_approved=True,
        rollback_restore_reviewed=True,
        metadata_only_audit_reviewed=True,
        incident_recording_without_phi_reviewed=True,
        no_raw_values_attested=True,
    )

    payload = renderer.render_private_evidence(config, env=env)

    assert payload["backup_disaster_recovery_ready"] is True
    assert payload["blockers"] == []
    assert payload["private_reference_value_count"] == 4
    assert payload["private_reference_values_included"] is False
    assert payload["private_backup_summary_path_value_included"] is False
    assert payload["private_backup_summary_backup_artifact_count"] == 2
    assert str(summary_path) not in json.dumps(payload)
