import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "validate_model_improvement_evidence.py"
SCRIPT_DIR = VALIDATOR_SCRIPT.parent


def _load_validator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_model_improvement_evidence",
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


def _ready_evidence() -> dict:
    return {
        "artifact": "claimguard_model_improvement_evidence",
        "version": "1.0",
        "evidence_status": "operator_attested_ready",
        "prepared_at": "",
        "no_phi_or_secret_values_attested": True,
        "no_approval_reference_values_attested": True,
        "no_user_data_content_attested": True,
        "legal_controls": {
            "source_control_approval_runbook_documented": True,
            "source_control_approval_runbook_path": str(
                REPO_ROOT / "llm-distill" / "docs" / "model-improvement-approval-runbook.md"
            ),
            "source_control_private_env_renderer_documented": True,
            "source_control_private_env_renderer_path": str(
                REPO_ROOT / "llm-distill" / "scripts" / "render_model_improvement_private_env.py"
            ),
            "model_improvement_requested": True,
            "legal_approval_attested": True,
            "baa_confirmed": True,
            "consent_notice_version_configured": True,
            "approval_reference_configured": True,
            "data_use_scope_documented": True,
            "retention_policy_reviewed": True,
            "revocation_path_reviewed": True,
        },
        "runtime_controls": {
            "model_improvement_disabled_by_default": True,
            "per_request_attestations_required": True,
            "approved_corpus_import_does_not_auto_opt_in": True,
            "audit_logging_reviewed": True,
            "frontend_readiness_blockers_visible": True,
        },
        "safety_boundaries": {
            "external_phi_deidentification_disabled_by_default": True,
            "raw_phi_training_disabled": True,
            "production_user_data_excluded_until_approval": True,
            "training_jobs_require_ready_evidence_packet": True,
            "revocation_blocks_future_training_use": True,
        },
        "review_boundaries": {
            "stores_approval_reference_values": False,
            "stores_user_data_content": False,
            "stores_raw_legal_or_baa_documents": False,
            "stores_credentials_or_tokens": False,
        },
    }


def test_template_is_safe_to_review_but_not_ready():
    validator = _load_validator()

    report = validator.build_report()
    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    legal_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "model_improvement_legal_controls"
    )

    assert report["safe_to_review"] is True
    assert report["model_improvement_ready"] is False
    assert "model_improvement_legal_controls" in blocked_ids
    assert "model_improvement_approval_runbook" not in blocked_ids
    assert "model_improvement_private_env_renderer" not in blocked_ids
    assert "model_improvement_runtime_controls" not in blocked_ids
    assert "model_improvement_safety_boundaries" not in blocked_ids
    runbook_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "model_improvement_approval_runbook"
    )
    assert runbook_requirement["status"] == "ready"
    assert runbook_requirement["evidence"]["source_control_approval_runbook_documented"] is True
    assert runbook_requirement["evidence"]["runbook_exists"] is True
    assert runbook_requirement["evidence"]["runbook_inside_source_control"] is True
    assert runbook_requirement["evidence"]["missing_marker_count"] == 0
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    renderer_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "model_improvement_private_env_renderer"
    )
    assert renderer_requirement["status"] == "ready"
    assert (
        renderer_requirement["evidence"][
            "source_control_private_env_renderer_documented"
        ]
        is True
    )
    assert renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert (
        renderer_requirement["evidence"][
            "private_env_renderer_inside_source_control"
        ]
        is True
    )
    assert renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert (
        renderer_requirement["evidence"]["approval_reference_value_included"]
        is False
    )
    assert renderer_requirement["evidence"]["consent_notice_value_included"] is False
    assert "source_control_approval_runbook_not_documented" not in legal_requirement["blockers"]
    assert (
        "source_control_private_env_renderer_not_documented"
        not in legal_requirement["blockers"]
    )
    assert legal_requirement["evidence"]["source_control_approval_runbook_documented"] is True
    assert (
        legal_requirement["evidence"][
            "source_control_private_env_renderer_documented"
        ]
        is True
    )
    assert "data_use_scope_not_documented" not in legal_requirement["blockers"]
    assert "retention_policy_not_reviewed" not in legal_requirement["blockers"]
    assert "revocation_path_not_reviewed" not in legal_requirement["blockers"]


def test_ready_model_improvement_evidence_passes(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, _ready_evidence())

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["model_improvement_ready"] is True
    assert report["blocked_item_count"] == 0


def test_missing_consent_notice_blocks_readiness(tmp_path):
    validator = _load_validator()
    evidence = _ready_evidence()
    evidence["legal_controls"]["consent_notice_version_configured"] = False
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    legal_requirement = next(
        item for item in report["blocked_items"] if item["requirement_id"] == "model_improvement_legal_controls"
    )

    assert report["model_improvement_ready"] is False
    assert "consent_notice_version_not_configured" in legal_requirement["blockers"]


def test_raw_phi_training_boundary_is_required(tmp_path):
    validator = _load_validator()
    evidence = _ready_evidence()
    evidence["safety_boundaries"]["raw_phi_training_disabled"] = False
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    boundary_requirement = next(
        item for item in report["blocked_items"] if item["requirement_id"] == "model_improvement_safety_boundaries"
    )

    assert report["model_improvement_ready"] is False
    assert "raw_phi_training_not_disabled" in boundary_requirement["blockers"]


def test_runtime_audit_logging_review_is_required(tmp_path):
    validator = _load_validator()
    evidence = _ready_evidence()
    evidence["runtime_controls"]["audit_logging_reviewed"] = False
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    runtime_requirement = next(
        item for item in report["blocked_items"] if item["requirement_id"] == "model_improvement_runtime_controls"
    )

    assert report["model_improvement_ready"] is False
    assert "audit_logging_not_reviewed" in runtime_requirement["blockers"]


def test_raw_approval_or_user_data_values_block_without_emitting_values(tmp_path):
    validator = _load_validator()
    evidence = deepcopy(_ready_evidence())
    evidence["approval_reference_value"] = "MODEL-APPROVAL-KEEP-OUT"
    evidence["user_data_sample"] = "Synthetic user training note keep out"
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["model_improvement_ready"] is False
    assert "MODEL-APPROVAL-KEEP-OUT" not in serialized
    assert "Synthetic user training note keep out" not in serialized
    assert "forbidden_value_key_count" in serialized


def test_incomplete_model_improvement_runbook_blocks_without_emitting_text(
    tmp_path,
    monkeypatch,
):
    validator = _load_validator()
    evidence = deepcopy(_ready_evidence())
    incomplete_runbook = tmp_path / "model-improvement-approval-runbook.md"
    raw_runbook_text = "ClaimGuard AI is architected by Raphael Malikian"
    incomplete_runbook.write_text(raw_runbook_text, encoding="utf-8")
    evidence["legal_controls"]["source_control_approval_runbook_path"] = str(incomplete_runbook)
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)
    original_path_is_within = validator.path_is_within

    def path_is_within_tmp_runbook(path: Path, parent: Path) -> bool:
        if path.resolve() == incomplete_runbook.resolve():
            return True
        return original_path_is_within(path, parent)

    monkeypatch.setattr(validator, "path_is_within", path_is_within_tmp_runbook)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    runbook_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "model_improvement_approval_runbook"
    )

    assert report["safe_to_review"] is True
    assert report["model_improvement_ready"] is False
    assert "source_control_approval_runbook_required_markers_missing" in runbook_requirement["blockers"]
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert raw_runbook_text not in serialized


def test_model_improvement_runbook_must_stay_inside_source_control(tmp_path):
    validator = _load_validator()
    evidence = deepcopy(_ready_evidence())
    outside_runbook = tmp_path / "model-improvement-approval-runbook.md"
    raw_runbook_text = "\n".join(validator.RUNBOOK_REQUIRED_MARKERS)
    outside_runbook.write_text(raw_runbook_text, encoding="utf-8")
    evidence["legal_controls"]["source_control_approval_runbook_path"] = str(
        outside_runbook
    )
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    runbook_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "model_improvement_approval_runbook"
    )

    assert report["safe_to_review"] is True
    assert report["model_improvement_ready"] is False
    assert runbook_requirement["blockers"] == [
        "source_control_approval_runbook_must_be_inside_repo"
    ]
    assert runbook_requirement["evidence"]["runbook_exists"] is True
    assert runbook_requirement["evidence"]["runbook_inside_source_control"] is False
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert raw_runbook_text not in serialized


def test_private_env_renderer_documentation_is_required(tmp_path):
    validator = _load_validator()
    evidence = deepcopy(_ready_evidence())
    evidence["legal_controls"]["source_control_private_env_renderer_documented"] = False
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    legal_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "model_improvement_legal_controls"
    )
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "model_improvement_private_env_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["model_improvement_ready"] is False
    assert legal_requirement["blockers"] == [
        "source_control_private_env_renderer_not_documented"
    ]
    assert renderer_requirement["blockers"] == [
        "source_control_private_env_renderer_not_documented"
    ]


def test_model_improvement_private_env_renderer_must_stay_inside_source_control(
    tmp_path,
):
    validator = _load_validator()
    evidence = deepcopy(_ready_evidence())
    outside_renderer = tmp_path / "render_model_improvement_private_env.py"
    raw_renderer_text = "\n".join(validator.PRIVATE_ENV_RENDERER_REQUIRED_MARKERS)
    outside_renderer.write_text(raw_renderer_text, encoding="utf-8")
    evidence["legal_controls"]["source_control_private_env_renderer_path"] = str(
        outside_renderer
    )
    evidence_path = tmp_path / "model_improvement_evidence.json"
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "model_improvement_private_env_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["model_improvement_ready"] is False
    assert renderer_requirement["blockers"] == [
        "source_control_private_env_renderer_must_be_inside_repo"
    ]
    assert renderer_requirement["evidence"]["private_env_renderer_exists"] is True
    assert (
        renderer_requirement["evidence"][
            "private_env_renderer_inside_source_control"
        ]
        is False
    )
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert raw_renderer_text not in serialized
