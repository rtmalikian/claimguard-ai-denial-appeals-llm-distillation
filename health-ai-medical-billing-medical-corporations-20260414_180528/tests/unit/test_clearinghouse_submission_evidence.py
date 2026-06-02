import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "validate_clearinghouse_submission_evidence.py"
RENDERER_SCRIPT = (
    REPO_ROOT / "llm-distill" / "scripts" / "render_clearinghouse_submission_private_evidence.py"
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
        "artifact": "claimguard_clearinghouse_submission_evidence",
        "version": "1.0",
        "evidence_status": "clearinghouse_submission_ready",
        "clearinghouse_submission_ready": True,
        "no_phi_or_secret_values_attested": True,
        "no_raw_edi_payloads_attested": True,
        "no_payer_portal_credential_values_attested": True,
        "no_approval_reference_values_attested": True,
        "private_clearinghouse_submission_summary_path_env": (
            "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_PRIVATE_SUMMARY_PATH"
        ),
        "private_clearinghouse_submission_summary_path_configured": True,
        "private_clearinghouse_submission_summary_path_value_included": False,
        "private_clearinghouse_submission_summary_checked": True,
        "private_clearinghouse_submission_summary_private_reference_count": 5,
        "private_clearinghouse_submission_summary_payer_count": 2,
        "private_clearinghouse_submission_summary_test_transaction_count": 4,
        "private_clearinghouse_submission_summary_acknowledgement_test_count": 4,
        "private_clearinghouse_submission_summary_raw_values_included": False,
        "connectivity_controls": {
            "payer_or_clearinghouse_enrollment_confirmed": True,
            "test_mode_credentials_configured_privately": True,
            "encrypted_transit_validated": True,
            "production_endpoint_configured_privately": True,
            "source_control_credentials_absent": True,
        },
        "submission_controls": {
            "edi_837_submission_contract_validated": True,
            "control_number_management_reviewed": True,
            "acknowledgement_999_277ca_handling_validated": True,
            "rejection_retry_and_duplicate_controls_reviewed": True,
            "rollback_to_non_submission_mode_reviewed": True,
        },
        "audit_retention_controls": {
            "metadata_only_audit_logging_reviewed": True,
            "access_controls_reviewed": True,
            "retention_policy_reviewed": True,
            "no_raw_edi_or_phi_logs_attested": True,
        },
        "governance_controls": {
            "source_control_runbook_documented": True,
            "runbook_path": "llm-distill/docs/clearinghouse-submission-runbook.md",
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_clearinghouse_submission_private_evidence.py"
            ),
            "approval_or_risk_acceptance_private": True,
            "metadata_only_audit_reviewed": True,
        },
    }


def _private_summary() -> dict:
    return {
        "payer_or_clearinghouse_enrollment_confirmed": True,
        "test_mode_credentials_configured_privately": True,
        "encrypted_transit_validated": True,
        "production_endpoint_configured_privately": True,
        "source_control_credentials_absent": True,
        "edi_837_submission_contract_validated": True,
        "control_number_management_reviewed": True,
        "acknowledgement_999_277ca_handling_validated": True,
        "rejection_retry_and_duplicate_controls_reviewed": True,
        "rollback_to_non_submission_mode_reviewed": True,
        "metadata_only_audit_logging_reviewed": True,
        "access_controls_reviewed": True,
        "retention_policy_reviewed": True,
        "no_raw_edi_or_phi_logs_attested": True,
        "approval_or_risk_acceptance_private": True,
        "no_phi_or_secret_values_included": True,
        "no_raw_edi_payloads_included": True,
        "no_payer_portal_credential_values_included": True,
        "no_approval_reference_values_included": True,
        "private_reference_count": 5,
        "payer_count": 2,
        "test_transaction_count": 4,
        "acknowledgement_test_count": 4,
    }


def _ready_config(renderer: ModuleType, output: Path):
    return renderer.RenderConfig(
        output=output,
        approved_mode=True,
        payer_or_clearinghouse_enrollment_confirmed=True,
        test_mode_credentials_configured_privately=True,
        encrypted_transit_validated=True,
        production_endpoint_configured_privately=True,
        source_control_credentials_absent=True,
        edi_837_submission_contract_validated=True,
        control_number_management_reviewed=True,
        acknowledgement_999_277ca_handling_validated=True,
        rejection_retry_and_duplicate_controls_reviewed=True,
        rollback_to_non_submission_mode_reviewed=True,
        metadata_only_audit_logging_reviewed=True,
        access_controls_reviewed=True,
        retention_policy_reviewed=True,
        no_raw_edi_or_phi_logs_attested=True,
        approval_or_risk_acceptance_private=True,
        no_raw_values_attested=True,
    )


def test_clearinghouse_submission_template_is_safe_to_review_but_not_ready():
    validator = _load_module(
        VALIDATOR_SCRIPT,
        "validate_clearinghouse_submission_evidence",
    )

    report = validator.build_report()
    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    runbook = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "clearinghouse_submission_runbook"
    )
    renderer = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "clearinghouse_submission_private_evidence_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["clearinghouse_submission_ready"] is False
    assert "clearinghouse_submission_no_phi_secret_or_values" not in blocked_ids
    assert "clearinghouse_submission_runbook" not in blocked_ids
    assert "clearinghouse_submission_private_evidence_renderer" not in blocked_ids
    assert "clearinghouse_submission_connectivity_controls" in blocked_ids
    assert "clearinghouse_submission_transaction_controls" in blocked_ids
    assert "clearinghouse_submission_audit_retention_controls" in blocked_ids
    assert "clearinghouse_submission_private_summary_metadata" in blocked_ids
    assert "clearinghouse_submission_ready_flag" in blocked_ids
    assert runbook["evidence"]["runbook_missing_marker_count"] == 0
    assert runbook["evidence"]["runbook_values_included"] is False
    assert renderer["evidence"]["private_evidence_renderer_missing_marker_count"] == 0
    assert renderer["evidence"]["private_evidence_renderer_values_included"] is False


def test_clearinghouse_submission_validator_accepts_fully_attested_boolean_evidence(tmp_path):
    validator = _load_module(
        VALIDATOR_SCRIPT,
        "validate_clearinghouse_submission_evidence",
    )
    evidence_path = tmp_path / "clearinghouse_submission_ready.json"
    _write_json(evidence_path, _ready_evidence())

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["clearinghouse_submission_ready"] is True
    assert report["blocked_item_count"] == 0


def test_clearinghouse_submission_private_renderer_refuses_source_control_output():
    renderer = _load_module(
        RENDERER_SCRIPT,
        "render_clearinghouse_submission_private_evidence",
    )
    output = REPO_ROOT / "llm-distill" / "evals" / "reports" / "private-clearinghouse.json"
    config = _ready_config(renderer, output)

    payload = renderer.render_private_evidence(config, env={})

    assert payload["clearinghouse_submission_ready"] is False
    assert "refusing_to_write_inside_source_control" in payload["blockers"]
    assert payload["values_redacted"] is True
    assert str(output) not in json.dumps(payload)


def test_clearinghouse_submission_private_renderer_outputs_ready_boolean_evidence(tmp_path):
    renderer = _load_module(
        RENDERER_SCRIPT,
        "render_clearinghouse_submission_private_evidence",
    )
    summary_path = tmp_path / "private-summary.json"
    output = tmp_path / "private-output" / "clearinghouse-submission-evidence.json"
    _write_json(summary_path, _private_summary())
    env = {
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_PRIVATE_SUMMARY_PATH": str(summary_path),
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENROLLMENT_REFERENCE": "configured",
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_CONNECTIVITY_REFERENCE": "configured",
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_TEST_TRANSACTION_REFERENCE": "configured",
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ACKNOWLEDGEMENT_REFERENCE": "configured",
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_GOVERNANCE_REFERENCE": "configured",
    }
    config = _ready_config(renderer, output)

    payload = renderer.render_private_evidence(config, env=env)

    assert payload["clearinghouse_submission_ready"] is True
    assert payload["blockers"] == []
    assert payload["private_reference_value_count"] == 5
    assert payload["private_reference_values_included"] is False
    assert payload["private_clearinghouse_submission_summary_path_value_included"] is False
    assert payload["private_clearinghouse_submission_summary_payer_count"] == 2
    assert str(summary_path) not in json.dumps(payload)
