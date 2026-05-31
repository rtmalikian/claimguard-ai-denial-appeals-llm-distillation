import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.prediction_fairness_config import (
    validate_prediction_fairness_startup_config,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "PREDICTION_FAIRNESS_EVIDENCE_REPORT": (
            "llm-distill/evals/reports/prediction_fairness_evidence_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "prediction_fairness_monitoring_ready": True,
        "requirements": [
            {
                "requirement_id": "prediction_fairness_calibrated_threshold",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def test_prediction_fairness_blocked_report_warns_without_fail_fast_in_development(
    caplog,
):
    blocked_report = _ready_evidence_report(
        prediction_fairness_monitoring_ready=False,
        requirements=[
            {
                "requirement_id": "prediction_fairness_calibrated_threshold",
                "status": "blocked",
            }
        ],
    )

    with caplog.at_level(logging.WARNING, logger="app.utils.prediction_fairness_config"):
        report = validate_prediction_fairness_startup_config(
            settings_like=_settings(),
            evidence_report=blocked_report,
        )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "prediction_fairness_evidence_report_not_ready" in report["blockers"]
    assert (
        "prediction_fairness_evidence_report_has_blocked_requirements"
        in report["blockers"]
    )
    assert report["safe_context"]["raw_demographic_values_included"] is False
    assert caplog.records[-1].prediction_fairness_startup_config["startup_ready"] is False


def test_prediction_fairness_blocked_report_fails_fast_in_production():
    with pytest.raises(RuntimeError) as exc_info:
        validate_prediction_fairness_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(
                prediction_fairness_monitoring_ready=False
            ),
        )

    assert str(exc_info.value) == (
        "Prediction fairness startup configuration is not production-ready."
    )


def test_prediction_fairness_ready_report_passes_in_production():
    report = validate_prediction_fairness_startup_config(
        settings_like=_settings(APP_ENV="production"),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["evidence_report_ready"] is True
    assert report["evidence_report_safe_to_review"] is True
    assert report["blockers"] == []


def test_prediction_fairness_unsafe_report_blocks_production_startup():
    with pytest.raises(RuntimeError):
        validate_prediction_fairness_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_prediction_fairness_missing_report_path_blocks_production_startup():
    with pytest.raises(RuntimeError):
        validate_prediction_fairness_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                PREDICTION_FAIRNESS_EVIDENCE_REPORT="",
            ),
        )


def test_prediction_fairness_startup_can_load_configured_report(tmp_path):
    report_path = tmp_path / "fairness-report.json"
    report_path.write_text(json.dumps(_ready_evidence_report()), encoding="utf-8")

    report = validate_prediction_fairness_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            PREDICTION_FAIRNESS_EVIDENCE_REPORT=str(report_path),
        )
    )

    assert report["startup_ready"] is True
    assert report["evidence_report_checked"] is True
    assert str(report_path) not in json.dumps(report, sort_keys=True)


def test_prediction_fairness_startup_report_does_not_emit_raw_values(caplog):
    raw_group = "synthetic-demographic-group-should-not-emit"
    raw_path = "/tmp/synthetic-fairness-report-path-should-not-emit.json"
    report_with_values = _ready_evidence_report(
        raw_group_value=raw_group,
        production_outcome_rows=[{"group": raw_group, "denial_prediction": 0.9}],
    )

    with caplog.at_level(logging.INFO, logger="app.utils.prediction_fairness_config"):
        report = validate_prediction_fairness_startup_config(
            settings_like=_settings(PREDICTION_FAIRNESS_EVIDENCE_REPORT=raw_path),
            evidence_report=report_with_values,
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].prediction_fairness_startup_config,
        sort_keys=True,
    )

    assert raw_group not in serialized
    assert raw_path not in serialized
    assert raw_group not in log_serialized
    assert raw_path not in log_serialized
