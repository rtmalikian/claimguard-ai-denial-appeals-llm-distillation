import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "validate_prediction_fairness_evidence.py"
SCRIPT_DIR = VALIDATOR_SCRIPT.parent


def _load_validator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_prediction_fairness_evidence",
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
        "artifact": "claimguard_prediction_fairness_monitoring_evidence",
        "version": "1.0",
        "evidence_status": "production_monitoring_ready",
        "prepared_at": "2026-05-31T00:00:00Z",
        "no_phi_or_secret_values_attested": True,
        "no_raw_demographic_values_attested": True,
        "no_production_outcome_rows_attested": True,
        "calibrated_threshold": {
            "source_control_calibration_checklist_documented": True,
            "calibration_checklist_path": (
                "llm-distill/docs/prediction-fairness-calibration-checklist.md"
            ),
            "approved_outcome_dataset_available": True,
            "minimum_sample_size_met": True,
            "calibration_run_completed": True,
            "threshold_review_completed": True,
            "human_review_policy_confirmed": True,
        },
        "fairness_monitoring": {
            "source_control_monitoring_validation_checklist_documented": True,
            "monitoring_validation_checklist_path": (
                "llm-distill/docs/prediction-fairness-monitoring-validation-checklist.md"
            ),
            "approved_demographic_grouping_reviewed": True,
            "continuous_monitoring_configured": True,
            "disparity_thresholds_documented": True,
            "alerting_and_review_owner_configured": True,
            "latest_monitoring_run_passed": True,
        },
        "governance_controls": {
            "legal_privacy_review_completed": True,
            "source_control_legal_privacy_checklist_documented": True,
            "legal_privacy_checklist_path": (
                "llm-distill/docs/prediction-fairness-legal-privacy-checklist.md"
            ),
            "source_control_monitoring_runbook_documented": True,
            "monitoring_runbook_path": "llm-distill/docs/prediction-fairness-monitoring-runbook.md",
            "model_card_updated": True,
            "rollback_or_threshold_reversion_reviewed": True,
            "audit_log_metadata_only_verified": True,
        },
    }


def test_template_is_safe_to_review_but_not_production_ready():
    validator = _load_validator()

    report = validator.build_report()
    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    governance_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "prediction_fairness_governance_controls"
    )
    runbook_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "prediction_fairness_monitoring_runbook"
    )
    calibration_checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "prediction_fairness_calibration_checklist"
    )
    monitoring_validation_checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"]
        == "prediction_fairness_monitoring_validation_checklist"
    )
    legal_privacy_checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "prediction_fairness_legal_privacy_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is False
    assert "prediction_fairness_calibrated_threshold" in blocked_ids
    assert "prediction_fairness_calibration_checklist" not in blocked_ids
    assert "prediction_fairness_continuous_monitoring" in blocked_ids
    assert "prediction_fairness_monitoring_validation_checklist" not in blocked_ids
    assert "prediction_fairness_legal_privacy_checklist" not in blocked_ids
    assert "prediction_fairness_governance_controls" in blocked_ids
    assert "source_control_legal_privacy_checklist_not_documented" not in governance_requirement["blockers"]
    assert "model_card_not_updated" not in governance_requirement["blockers"]
    assert "model_card_document_missing" not in governance_requirement["blockers"]
    assert governance_requirement["evidence"]["model_card_exists"] is True
    assert governance_requirement["evidence"]["model_card_missing_marker_count"] == 0
    assert governance_requirement["evidence"]["model_card_values_included"] is False
    assert runbook_requirement["status"] == "ready"
    assert runbook_requirement["evidence"]["source_control_monitoring_runbook_documented"] is True
    assert runbook_requirement["evidence"]["monitoring_runbook_exists"] is True
    assert runbook_requirement["evidence"]["monitoring_runbook_missing_marker_count"] == 0
    assert runbook_requirement["evidence"]["monitoring_runbook_values_included"] is False
    assert calibration_checklist_requirement["status"] == "ready"
    assert (
        calibration_checklist_requirement["evidence"][
            "source_control_calibration_checklist_documented"
        ]
        is True
    )
    assert (
        calibration_checklist_requirement["evidence"][
            "calibration_checklist_exists"
        ]
        is True
    )
    assert (
        calibration_checklist_requirement["evidence"][
            "calibration_checklist_missing_marker_count"
        ]
        == 0
    )
    assert (
        calibration_checklist_requirement["evidence"][
            "calibration_checklist_values_included"
        ]
        is False
    )
    assert monitoring_validation_checklist_requirement["status"] == "ready"
    assert (
        monitoring_validation_checklist_requirement["evidence"][
            "source_control_monitoring_validation_checklist_documented"
        ]
        is True
    )
    assert (
        monitoring_validation_checklist_requirement["evidence"][
            "monitoring_validation_checklist_exists"
        ]
        is True
    )
    assert (
        monitoring_validation_checklist_requirement["evidence"][
            "monitoring_validation_checklist_missing_marker_count"
        ]
        == 0
    )
    assert (
        monitoring_validation_checklist_requirement["evidence"][
            "monitoring_validation_checklist_values_included"
        ]
        is False
    )
    assert legal_privacy_checklist_requirement["status"] == "ready"
    assert (
        legal_privacy_checklist_requirement["evidence"][
            "source_control_legal_privacy_checklist_documented"
        ]
        is True
    )
    assert (
        legal_privacy_checklist_requirement["evidence"][
            "legal_privacy_checklist_exists"
        ]
        is True
    )
    assert (
        legal_privacy_checklist_requirement["evidence"][
            "legal_privacy_checklist_missing_marker_count"
        ]
        == 0
    )
    assert (
        legal_privacy_checklist_requirement["evidence"][
            "legal_privacy_checklist_values_included"
        ]
        is False
    )


def test_ready_evidence_passes_when_all_external_controls_are_attested(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_ready.json"
    _write_json(evidence_path, _ready_evidence())

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is True
    assert report["blocked_item_count"] == 0


def test_raw_demographic_values_are_blocked_without_echoing_values(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_values.json"
    evidence = _ready_evidence()
    evidence["raw_demographic_values_by_group"] = ["synthetic_group_a"]
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    no_values_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "prediction_fairness_no_phi_secret_or_values"
    )

    assert report["safe_to_review"] is False
    assert report["prediction_fairness_monitoring_ready"] is False
    assert no_values_requirement["evidence"]["forbidden_value_key_count"] == 1
    assert "raw_demographic_values_by_group" in serialized
    assert "synthetic_group_a" not in serialized


def test_model_card_document_markers_are_required_when_attested(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_missing_model_card_markers.json"
    model_card_path = tmp_path / "prediction-fairness-model-card.md"
    model_card_path.write_text(
        "Current status: not production-ready.\n",
        encoding="utf-8",
    )
    evidence = _ready_evidence()
    evidence["governance_controls"]["model_card_path"] = str(model_card_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    governance_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "prediction_fairness_governance_controls"
    )

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is False
    assert "model_card_required_markers_missing" in governance_requirement["blockers"]
    assert governance_requirement["evidence"]["model_card_exists"] is True
    assert governance_requirement["evidence"]["model_card_missing_marker_count"] > 0
    assert "Approved real-world outcome data required." not in json.dumps(
        governance_requirement,
        sort_keys=True,
    )


def test_monitoring_runbook_markers_are_required_when_documented(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_missing_runbook_markers.json"
    runbook_path = tmp_path / "prediction-fairness-monitoring-runbook.md"
    runbook_path.write_text(
        "Current status: not production-ready.\n",
        encoding="utf-8",
    )
    evidence = _ready_evidence()
    evidence["governance_controls"]["monitoring_runbook_path"] = str(runbook_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    runbook_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "prediction_fairness_monitoring_runbook"
    )

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is False
    assert "monitoring_runbook_required_markers_missing" in runbook_requirement["blockers"]
    assert runbook_requirement["evidence"]["monitoring_runbook_exists"] is True
    assert runbook_requirement["evidence"]["monitoring_runbook_missing_marker_count"] > 0
    assert "Approved outcome dataset required." not in json.dumps(
        runbook_requirement,
        sort_keys=True,
    )


def test_calibration_checklist_markers_are_required_when_documented(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_missing_calibration_checklist_markers.json"
    checklist_path = tmp_path / "prediction-fairness-calibration-checklist.md"
    checklist_path.write_text(
        "Current status: not calibrated for production.\n",
        encoding="utf-8",
    )
    evidence = _ready_evidence()
    evidence["calibrated_threshold"]["calibration_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "prediction_fairness_calibration_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is False
    assert (
        "calibration_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["calibration_checklist_exists"] is True
    assert (
        checklist_requirement["evidence"][
            "calibration_checklist_missing_marker_count"
        ]
        > 0
    )
    assert "approved outcome dataset required" not in json.dumps(
        checklist_requirement,
        sort_keys=True,
    )


def test_monitoring_validation_checklist_markers_are_required_when_documented(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_missing_monitoring_validation_checklist_markers.json"
    checklist_path = tmp_path / "prediction-fairness-monitoring-validation-checklist.md"
    checklist_path.write_text(
        "Current status: not validated for production.\n",
        encoding="utf-8",
    )
    evidence = _ready_evidence()
    evidence["fairness_monitoring"]["monitoring_validation_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"]
        == "prediction_fairness_monitoring_validation_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is False
    assert (
        "monitoring_validation_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert (
        checklist_requirement["evidence"][
            "monitoring_validation_checklist_exists"
        ]
        is True
    )
    assert (
        checklist_requirement["evidence"][
            "monitoring_validation_checklist_missing_marker_count"
        ]
        > 0
    )
    assert "approved demographic grouping review required" not in json.dumps(
        checklist_requirement,
        sort_keys=True,
    )


def test_legal_privacy_checklist_markers_are_required_when_documented(tmp_path):
    validator = _load_validator()
    evidence_path = tmp_path / "fairness_missing_legal_privacy_checklist_markers.json"
    checklist_path = tmp_path / "prediction-fairness-legal-privacy-checklist.md"
    checklist_path.write_text(
        "Current status: legal/privacy review not complete for production fairness monitoring.\n",
        encoding="utf-8",
    )
    evidence = _ready_evidence()
    evidence["governance_controls"]["legal_privacy_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "prediction_fairness_legal_privacy_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["prediction_fairness_monitoring_ready"] is False
    assert (
        "legal_privacy_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert (
        checklist_requirement["evidence"]["legal_privacy_checklist_exists"]
        is True
    )
    assert (
        checklist_requirement["evidence"][
            "legal_privacy_checklist_missing_marker_count"
        ]
        > 0
    )
    assert "approved outcome dataset required" not in json.dumps(
        checklist_requirement,
        sort_keys=True,
    )
