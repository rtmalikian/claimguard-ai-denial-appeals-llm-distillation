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


def _set_private_references(monkeypatch, renderer: ModuleType) -> dict[str, str]:
    values = {
        renderer.DEFAULT_OUTCOME_DATASET_REFERENCE_ENV: "OUTCOME-DATASET-REF-TEST",
        renderer.DEFAULT_THRESHOLD_REVIEW_REFERENCE_ENV: "THRESHOLD-REVIEW-REF-TEST",
        renderer.DEFAULT_DEMOGRAPHIC_GROUPING_REFERENCE_ENV: "GROUPING-REF-TEST",
        renderer.DEFAULT_MONITORING_CONFIG_REFERENCE_ENV: "MONITORING-CONFIG-REF-TEST",
        renderer.DEFAULT_ALERT_OWNER_REFERENCE_ENV: "ALERT-OWNER-REF-TEST",
        renderer.DEFAULT_LATEST_RUN_REFERENCE_ENV: "LATEST-RUN-REF-TEST",
        renderer.DEFAULT_LEGAL_PRIVACY_REFERENCE_ENV: "LEGAL-PRIVACY-REF-TEST",
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
    _set_private_references(monkeypatch, renderer)

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=tmp_path / "prediction-fairness.private.json",
                approved_monitoring=True,
            )
        )


def test_approved_mode_requires_private_references(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="outcome dataset reference"):
        renderer.render_private_evidence(
            _approved_config(
                renderer,
                tmp_path / "prediction-fairness.private.json",
            )
        )


def test_approved_mode_writes_private_evidence_and_redacts_values(monkeypatch, tmp_path):
    renderer = _load_renderer()
    private_values = _set_private_references(monkeypatch, renderer)
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
    assert summary["private_reference_count"] == len(private_values)
    assert summary["values_redacted"] is True
    assert payload["evidence_status"] == "production_monitoring_ready"
    assert payload["calibrated_threshold"]["approved_outcome_dataset_available"] is True
    assert payload["fairness_monitoring"]["latest_monitoring_run_passed"] is True
    assert payload["governance_controls"]["legal_privacy_review_completed"] is True
    for private_value in private_values.values():
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
