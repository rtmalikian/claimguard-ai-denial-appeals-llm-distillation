import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "validate_dependency_security_evidence.py"
RENDERER_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "render_dependency_security_private_evidence.py"
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
        "artifact": "claimguard_dependency_security_evidence",
        "version": "1.0",
        "evidence_status": "dependency_security_ready",
        "dependency_security_ready": True,
        "no_phi_or_secret_values_attested": True,
        "no_raw_scan_output_attested": True,
        "no_vulnerability_detail_values_attested": True,
        "no_approval_reference_values_attested": True,
        "private_dependency_security_summary_path_env": (
            "CLAIMGUARD_DEPENDENCY_SECURITY_PRIVATE_SUMMARY_PATH"
        ),
        "private_dependency_security_summary_path_configured": True,
        "private_dependency_security_summary_path_value_included": False,
        "private_dependency_security_summary_checked": True,
        "private_dependency_security_summary_private_reference_count": 4,
        "private_dependency_security_summary_python_package_count": 42,
        "private_dependency_security_summary_frontend_package_count": 120,
        "private_dependency_security_summary_container_image_count": 2,
        "private_dependency_security_summary_remediated_or_approved_finding_count": 3,
        "private_dependency_security_summary_raw_values_included": False,
        "scan_controls": {
            "python_dependency_scan_completed": True,
            "frontend_dependency_scan_completed": True,
            "container_image_scan_completed": True,
            "lockfiles_reviewed": True,
            "scan_tools_documented": True,
        },
        "remediation_controls": {
            "critical_high_findings_remediated_or_approved": True,
            "known_vulnerable_packages_reviewed": True,
            "compensating_controls_documented": True,
            "rebuild_and_retest_completed": True,
            "upgrade_plan_documented": True,
        },
        "governance_controls": {
            "source_control_runbook_documented": True,
            "runbook_path": "llm-distill/docs/dependency-security-runbook.md",
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_dependency_security_private_evidence.py"
            ),
            "approval_or_risk_acceptance_private": True,
            "metadata_only_audit_reviewed": True,
        },
    }


def _private_summary() -> dict:
    return {
        "python_dependency_scan_completed": True,
        "frontend_dependency_scan_completed": True,
        "container_image_scan_completed": True,
        "lockfiles_reviewed": True,
        "scan_tools_documented": True,
        "critical_high_findings_remediated_or_approved": True,
        "known_vulnerable_packages_reviewed": True,
        "compensating_controls_documented": True,
        "rebuild_and_retest_completed": True,
        "upgrade_plan_documented": True,
        "approval_or_risk_acceptance_private": True,
        "metadata_only_audit_reviewed": True,
        "no_phi_or_secret_values_included": True,
        "no_raw_scan_output_included": True,
        "no_vulnerability_detail_values_included": True,
        "no_approval_reference_values_included": True,
        "private_reference_count": 4,
        "python_package_count": 42,
        "frontend_package_count": 120,
        "container_image_count": 2,
        "remediated_or_approved_finding_count": 3,
    }


def test_dependency_security_template_is_safe_to_review_and_ready():
    validator = _load_module(VALIDATOR_SCRIPT, "validate_dependency_security_evidence")

    report = validator.build_report()
    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    runbook = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "dependency_security_runbook"
    )
    renderer = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "dependency_security_private_evidence_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["dependency_security_ready"] is True
    assert report["blocked_item_count"] == 0
    assert "dependency_security_no_phi_secret_or_values" not in blocked_ids
    assert "dependency_security_runbook" not in blocked_ids
    assert "dependency_security_private_evidence_renderer" not in blocked_ids
    assert "dependency_security_scan_controls" not in blocked_ids
    assert "dependency_security_remediation_controls" not in blocked_ids
    assert "dependency_security_governance_controls" not in blocked_ids
    assert "dependency_security_private_summary_metadata" not in blocked_ids
    assert runbook["evidence"]["runbook_missing_marker_count"] == 0
    assert runbook["evidence"]["runbook_values_included"] is False
    assert renderer["evidence"]["private_evidence_renderer_missing_marker_count"] == 0
    assert renderer["evidence"]["private_evidence_renderer_values_included"] is False


def test_dependency_security_validator_accepts_fully_attested_boolean_evidence(tmp_path):
    validator = _load_module(VALIDATOR_SCRIPT, "validate_dependency_security_evidence")
    evidence_path = tmp_path / "dependency_security_ready.json"
    _write_json(evidence_path, _ready_evidence())

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["dependency_security_ready"] is True
    assert report["blocked_item_count"] == 0


def test_dependency_security_private_renderer_refuses_source_control_output():
    renderer = _load_module(RENDERER_SCRIPT, "render_dependency_security_private_evidence")
    output = REPO_ROOT / "llm-distill" / "evals" / "reports" / "private-dependency.json"
    config = renderer.RenderConfig(
        output=output,
        approved_mode=True,
        python_scan_completed=True,
        frontend_scan_completed=True,
        container_scan_completed=True,
        lockfiles_reviewed=True,
        scan_tools_documented=True,
        critical_high_findings_remediated_or_approved=True,
        known_vulnerable_packages_reviewed=True,
        compensating_controls_documented=True,
        rebuild_and_retest_completed=True,
        upgrade_plan_documented=True,
        approval_or_risk_acceptance_private=True,
        metadata_only_audit_reviewed=True,
        no_raw_values_attested=True,
    )

    payload = renderer.render_private_evidence(config, env={})

    assert payload["dependency_security_ready"] is False
    assert "refusing_to_write_inside_source_control" in payload["blockers"]
    assert payload["values_redacted"] is True
    assert str(output) not in json.dumps(payload)


def test_dependency_security_private_renderer_outputs_ready_boolean_evidence(tmp_path):
    renderer = _load_module(RENDERER_SCRIPT, "render_dependency_security_private_evidence")
    summary_path = tmp_path / "private-summary.json"
    output = tmp_path / "private-output" / "dependency-security-evidence.json"
    _write_json(summary_path, _private_summary())
    env = {
        "CLAIMGUARD_DEPENDENCY_SECURITY_PRIVATE_SUMMARY_PATH": str(summary_path),
        "CLAIMGUARD_DEPENDENCY_SECURITY_PYTHON_SCAN_REFERENCE": "configured",
        "CLAIMGUARD_DEPENDENCY_SECURITY_FRONTEND_SCAN_REFERENCE": "configured",
        "CLAIMGUARD_DEPENDENCY_SECURITY_CONTAINER_SCAN_REFERENCE": "configured",
        "CLAIMGUARD_DEPENDENCY_SECURITY_REMEDIATION_REFERENCE": "configured",
    }
    config = renderer.RenderConfig(
        output=output,
        approved_mode=True,
        python_scan_completed=True,
        frontend_scan_completed=True,
        container_scan_completed=True,
        lockfiles_reviewed=True,
        scan_tools_documented=True,
        critical_high_findings_remediated_or_approved=True,
        known_vulnerable_packages_reviewed=True,
        compensating_controls_documented=True,
        rebuild_and_retest_completed=True,
        upgrade_plan_documented=True,
        approval_or_risk_acceptance_private=True,
        metadata_only_audit_reviewed=True,
        no_raw_values_attested=True,
    )

    payload = renderer.render_private_evidence(config, env=env)

    assert payload["dependency_security_ready"] is True
    assert payload["blockers"] == []
    assert payload["private_reference_value_count"] == 4
    assert payload["private_reference_values_included"] is False
    assert payload["private_dependency_security_summary_path_value_included"] is False
    assert payload["private_dependency_security_summary_python_package_count"] == 42
    assert str(summary_path) not in json.dumps(payload)
