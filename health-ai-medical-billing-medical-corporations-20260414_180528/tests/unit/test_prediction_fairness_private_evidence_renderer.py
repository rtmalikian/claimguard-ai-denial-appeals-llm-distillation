import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_prediction_fairness_private_evidence.py"


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_prediction_fairness_private_evidence",
        RENDERER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _approved_config(renderer: ModuleType, output_path: Path):
    return renderer.RenderConfig(
        output_path=output_path,
        approved_monitoring=True,
        approved_outcome_dataset_attested=True,
        minimum_sample_size_attested=True,
        calibration_run_attested=True,
        threshold_review_attested=True,
        human_review_policy_attested=True,
        demographic_grouping_reviewed=True,
        continuous_monitoring_configured=True,
        disparity_thresholds_documented=True,
        alert_owner_configured=True,
        latest_monitoring_run_passed=True,
        legal_privacy_review_completed=True,
        rollback_reviewed=True,
        metadata_only_audit_verified=True,
        no_raw_values_attested=True,
    )


def _monitoring_summary_payload(**overrides):
    payload = {
        "approved_outcome_dataset_available": True,
        "minimum_sample_size_met": True,
        "calibration_run_completed": True,
        "threshold_review_completed": True,
        "human_review_policy_confirmed": True,
        "approved_demographic_grouping_reviewed": True,
        "continuous_monitoring_configured": True,
        "disparity_thresholds_documented": True,
        "alerting_and_review_owner_configured": True,
        "latest_monitoring_run_passed": True,
        "legal_privacy_review_completed": True,
        "rollback_or_threshold_reversion_reviewed": True,
        "audit_log_metadata_only_verified": True,
        "no_phi_or_secret_values_attested": True,
        "no_raw_demographic_values_attested": True,
        "no_production_outcome_rows_attested": True,
        "raw_demographic_values_included": False,
        "production_outcome_rows_included": False,
        "individual_identifiers_included": False,
        "approval_reference_values_included": False,
        "values_redacted": True,
        "evaluated_outcome_count": 240,
        "monitored_group_count": 6,
        "disparity_metric_count": 3,
        "alert_rule_count": 2,
    }
    payload.update(overrides)
    return payload


def _write_private_summary(path: Path, **overrides) -> None:
    path.write_text(
        json.dumps(_monitoring_summary_payload(**overrides), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _set_private_references(
    monkeypatch,
    renderer: ModuleType,
    summary_path: Path,
) -> dict[str, str]:
    values = {
        renderer.DEFAULT_OUTCOME_DATASET_REFERENCE_ENV: "OUTCOME-DATASET-REF-TEST",
        renderer.DEFAULT_THRESHOLD_REVIEW_REFERENCE_ENV: "THRESHOLD-REVIEW-REF-TEST",
        renderer.DEFAULT_DEMOGRAPHIC_GROUPING_REFERENCE_ENV: "GROUPING-REF-TEST",
        renderer.DEFAULT_MONITORING_CONFIG_REFERENCE_ENV: "MONITORING-CONFIG-REF-TEST",
        renderer.DEFAULT_ALERT_OWNER_REFERENCE_ENV: "ALERT-OWNER-REF-TEST",
        renderer.DEFAULT_LATEST_RUN_REFERENCE_ENV: "LATEST-RUN-REF-TEST",
        renderer.DEFAULT_LEGAL_PRIVACY_REFERENCE_ENV: "LEGAL-PRIVACY-REF-TEST",
        renderer.DEFAULT_MONITORING_SUMMARY_PATH_ENV: str(summary_path),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "prediction-fairness.private.json"

    summary = renderer.render_private_evidence(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["approved_monitoring_requested"] is False
    assert summary["approved_outcome_dataset_available"] is False
    assert summary["latest_monitoring_run_passed"] is False
    assert summary["legal_privacy_review_completed"] is False
    assert summary["raw_private_values_included"] is False
    assert summary["raw_demographic_values_included"] is False
    assert summary["production_outcome_rows_included"] is False
    assert "OUTCOME-DATASET-REF-TEST" not in serialized
    assert not output_path.exists()


def test_approved_mode_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    summary_path = tmp_path / "fairness-monitoring-summary.json"
    _write_private_summary(summary_path)
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=tmp_path / "prediction-fairness.private.json",
                approved_monitoring=True,
            )
        )


def test_approved_mode_requires_private_monitoring_summary_path(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="monitoring summary path"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_requires_private_references(monkeypatch, tmp_path):
    renderer = _load_renderer()
    summary_path = tmp_path / "fairness-monitoring-summary.json"
    _write_private_summary(summary_path)
    monkeypatch.setenv(renderer.DEFAULT_MONITORING_SUMMARY_PATH_ENV, str(summary_path))

    with pytest.raises(renderer.RenderError, match="outcome dataset reference"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_rejects_source_control_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(renderer.DEFAULT_MONITORING_SUMMARY_PATH_ENV, str(RENDERER_SCRIPT))

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_rejects_incomplete_private_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    summary_path = tmp_path / "fairness-monitoring-summary.json"
    _write_private_summary(summary_path, latest_monitoring_run_passed=False)
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(
        renderer.RenderError,
        match="latest_monitoring_run_passed=true",
    ):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_rejects_summary_with_raw_value_flags(monkeypatch, tmp_path):
    renderer = _load_renderer()
    summary_path = tmp_path / "fairness-monitoring-summary.json"
    _write_private_summary(summary_path, production_outcome_rows_included=True)
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(
        renderer.RenderError,
        match="production_outcome_rows_included=false",
    ):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_rejects_unsupported_private_summary_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    summary_path = tmp_path / "fairness-monitoring-summary.json"
    _write_private_summary(summary_path, raw_demographic_values=["redacted"])
    _set_private_references(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_writes_private_evidence_and_redacts_values(monkeypatch, tmp_path):
    renderer = _load_renderer()
    summary_path = tmp_path / "fairness-monitoring-summary.json"
    _write_private_summary(summary_path)
    private_values = _set_private_references(monkeypatch, renderer, summary_path)
    output_path = tmp_path / "prediction-fairness.private.json"

    summary = renderer.render_private_evidence(
        _approved_config(renderer, output_path)
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(output_text)
    serialized_summary = json.dumps(summary, sort_keys=True)

    assert output_mode == 0o600
    assert summary["approved_outcome_dataset_available"] is True
    assert summary["minimum_sample_size_met"] is True
    assert summary["threshold_review_completed"] is True
    assert summary["approved_demographic_grouping_reviewed"] is True
    assert summary["latest_monitoring_run_passed"] is True
    assert summary["legal_privacy_review_completed"] is True
    assert summary["private_reference_count"] == len(private_values) - 1
    assert summary["private_monitoring_summary_checked"] is True
    assert summary["private_monitoring_summary_path_env_configured"] is True
    assert summary["private_monitoring_summary_path_value_included"] is False
    assert summary["private_monitoring_summary_evaluated_outcome_count"] == 240
    assert summary["private_monitoring_summary_monitored_group_count"] == 6
    assert summary["private_monitoring_summary_disparity_metric_count"] == 3
    assert summary["private_monitoring_summary_alert_rule_count"] == 2
    assert summary["private_monitoring_summary_raw_values_included"] is False
    assert summary["values_redacted"] is True
    assert payload["evidence_status"] == "production_monitoring_ready"
    assert (
        payload["private_monitoring_summary_path_env"]
        == renderer.DEFAULT_MONITORING_SUMMARY_PATH_ENV
    )
    assert payload["private_monitoring_summary_path_value_included"] is False
    assert payload["private_monitoring_summary_checked"] is True
    assert payload["private_monitoring_summary_evaluated_outcome_count"] == 240
    assert payload["calibrated_threshold"]["approved_outcome_dataset_available"] is True
    assert payload["fairness_monitoring"]["latest_monitoring_run_passed"] is True
    assert payload["governance_controls"]["legal_privacy_review_completed"] is True
    assert str(summary_path) not in output_text
    assert str(summary_path) not in serialized_summary
    for key, private_value in private_values.items():
        if key == renderer.DEFAULT_MONITORING_SUMMARY_PATH_ENV:
            continue
        assert private_value not in output_text
        assert private_value not in serialized_summary


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "prediction-fairness.private.json",
            )
        )
