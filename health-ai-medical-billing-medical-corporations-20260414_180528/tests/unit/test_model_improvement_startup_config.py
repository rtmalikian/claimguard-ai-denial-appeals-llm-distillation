import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.model_improvement import validate_model_improvement_startup_config


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "USER_DATA_MODEL_IMPROVEMENT_ENABLED": False,
        "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED": False,
        "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED": False,
        "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": "",
        "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": "",
        "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT": (
            "llm-distill/evals/reports/model_improvement_evidence_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "model_improvement_ready": True,
        "requirements": [
            {
                "requirement_id": "model_improvement_legal_controls",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def _approved_settings(**overrides):
    values = {
        "APP_ENV": "production",
        "USER_DATA_MODEL_IMPROVEMENT_ENABLED": True,
        "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED": True,
        "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED": True,
        "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION": "synthetic-notice-v1",
        "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE": "synthetic-reference",
    }
    values.update(overrides)
    return _settings(**values)


def test_model_improvement_disabled_is_startup_ready_without_report_check(caplog):
    with caplog.at_level(logging.INFO, logger="app.utils.model_improvement"):
        report = validate_model_improvement_startup_config(settings_like=_settings())

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["enabled"] is False
    assert report["evidence_report_checked"] is False
    assert report["blockers"] == []
    assert report["safe_context"]["raw_user_data_included"] is False
    assert caplog.records[-1].model_improvement_startup_config["startup_ready"] is True


def test_model_improvement_enabled_in_development_reports_blockers_without_fail_fast():
    report = validate_model_improvement_startup_config(
        settings_like=_settings(USER_DATA_MODEL_IMPROVEMENT_ENABLED=True),
        evidence_report=_ready_evidence_report(
            model_improvement_ready=False,
            requirements=[
                {
                    "requirement_id": "model_improvement_legal_controls",
                    "status": "blocked",
                }
            ],
        ),
    )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "legal_approval_missing" in report["blockers"]
    assert "baa_confirmation_missing" in report["blockers"]
    assert "consent_notice_version_missing" in report["blockers"]
    assert "approval_reference_missing" in report["blockers"]
    assert "model_improvement_evidence_report_not_ready" in report["blockers"]
    assert (
        "model_improvement_evidence_report_has_blocked_requirements"
        in report["blockers"]
    )


def test_model_improvement_enabled_in_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_model_improvement_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                USER_DATA_MODEL_IMPROVEMENT_ENABLED=True,
            ),
            evidence_report=_ready_evidence_report(model_improvement_ready=False),
        )

    assert str(exc_info.value) == (
        "User-data model improvement startup configuration is not production-ready."
    )


def test_model_improvement_enabled_in_production_passes_when_all_gates_are_ready():
    report = validate_model_improvement_startup_config(
        settings_like=_approved_settings(),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["legal_approval_confirmed"] is True
    assert report["baa_confirmed"] is True
    assert report["consent_notice_version_configured"] is True
    assert report["approval_reference_configured"] is True
    assert report["evidence_report_ready"] is True
    assert report["blockers"] == []


def test_model_improvement_startup_blocks_unsafe_evidence_report():
    with pytest.raises(RuntimeError):
        validate_model_improvement_startup_config(
            settings_like=_approved_settings(),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_model_improvement_startup_report_does_not_emit_raw_values(caplog):
    raw_reference = "synthetic-reference-value-should-not-emit"
    raw_notice = "synthetic-consent-version-should-not-emit"

    with caplog.at_level(logging.INFO, logger="app.utils.model_improvement"):
        report = validate_model_improvement_startup_config(
            settings_like=_approved_settings(
                USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION=raw_notice,
                USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE=raw_reference,
            ),
            evidence_report=_ready_evidence_report(),
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].model_improvement_startup_config,
        sort_keys=True,
    )

    assert report["consent_notice_version_configured"] is True
    assert report["approval_reference_configured"] is True
    assert raw_reference not in serialized
    assert raw_notice not in serialized
    assert raw_reference not in log_serialized
    assert raw_notice not in log_serialized
