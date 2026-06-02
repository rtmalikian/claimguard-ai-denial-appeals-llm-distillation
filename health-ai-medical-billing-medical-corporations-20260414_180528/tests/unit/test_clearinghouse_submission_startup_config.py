import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.clearinghouse_submission_config import (
    validate_clearinghouse_submission_startup_config,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED": False,
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL": True,
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT": (
            "llm-distill/evals/reports/clearinghouse_submission_evidence_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "clearinghouse_submission_ready": True,
        "requirements": [
            {
                "requirement_id": "clearinghouse_submission_connectivity_controls",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def test_clearinghouse_submission_disabled_is_startup_ready_without_report_check(caplog):
    with caplog.at_level(
        logging.INFO,
        logger="app.utils.clearinghouse_submission_config",
    ):
        report = validate_clearinghouse_submission_startup_config(
            settings_like=_settings()
        )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["submission_enabled"] is False
    assert report["rollback_to_manual"] is True
    assert report["evidence_report_checked"] is False
    assert report["blockers"] == []
    assert report["safe_context"]["raw_edi_payload_included"] is False
    assert caplog.records[-1].clearinghouse_submission_startup_config["startup_ready"] is True


def test_clearinghouse_submission_enabled_in_development_reports_blockers_without_fail_fast():
    report = validate_clearinghouse_submission_startup_config(
        settings_like=_settings(CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True),
        evidence_report=_ready_evidence_report(
            clearinghouse_submission_ready=False,
            requirements=[
                {
                    "requirement_id": "clearinghouse_submission_connectivity_controls",
                    "status": "blocked",
                }
            ],
        ),
    )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "clearinghouse_submission_rollback_to_manual_enabled" in report["blockers"]
    assert "clearinghouse_submission_evidence_report_not_ready" in report["blockers"]
    assert (
        "clearinghouse_submission_evidence_report_has_blocked_requirements"
        in report["blockers"]
    )


def test_clearinghouse_submission_enabled_in_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_clearinghouse_submission_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True,
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL=False,
            ),
            evidence_report=_ready_evidence_report(clearinghouse_submission_ready=False),
        )

    assert str(exc_info.value) == (
        "Clearinghouse submission startup configuration is not production-ready."
    )


def test_clearinghouse_submission_enabled_in_production_requires_rollback_disabled():
    with pytest.raises(RuntimeError):
        validate_clearinghouse_submission_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True,
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL=True,
            ),
            evidence_report=_ready_evidence_report(),
        )


def test_clearinghouse_submission_enabled_in_production_passes_when_all_gates_are_ready():
    report = validate_clearinghouse_submission_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True,
            CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL=False,
        ),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["submission_enabled"] is True
    assert report["rollback_to_manual"] is False
    assert report["evidence_report_ready"] is True
    assert report["evidence_report_safe_to_review"] is True
    assert report["blockers"] == []


def test_clearinghouse_submission_startup_blocks_unsafe_evidence_report():
    with pytest.raises(RuntimeError):
        validate_clearinghouse_submission_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True,
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL=False,
            ),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_clearinghouse_submission_startup_can_load_configured_report(tmp_path):
    report_path = tmp_path / "clearinghouse-report.json"
    report_path.write_text(json.dumps(_ready_evidence_report()), encoding="utf-8")

    report = validate_clearinghouse_submission_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True,
            CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL=False,
            CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT=str(report_path),
        )
    )

    assert report["startup_ready"] is True
    assert report["evidence_report_checked"] is True
    assert str(report_path) not in json.dumps(report, sort_keys=True)


def test_clearinghouse_submission_startup_report_does_not_emit_raw_values(caplog):
    raw_endpoint = "https://clearinghouse.example.invalid/private"
    raw_reference = "synthetic-clearinghouse-reference-should-not-emit"
    report_with_values = _ready_evidence_report(
        private_endpoint_url=raw_endpoint,
        approval_reference=raw_reference,
        production_claim_payload="raw-edi-payload-should-not-emit",
    )

    with caplog.at_level(
        logging.INFO,
        logger="app.utils.clearinghouse_submission_config",
    ):
        report = validate_clearinghouse_submission_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ENABLED=True,
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_ROLLBACK_TO_MANUAL=False,
                CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT=raw_endpoint,
            ),
            evidence_report=report_with_values,
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].clearinghouse_submission_startup_config,
        sort_keys=True,
    )

    assert raw_endpoint not in serialized
    assert raw_reference not in serialized
    assert "raw-edi-payload-should-not-emit" not in serialized
    assert raw_endpoint not in log_serialized
    assert raw_reference not in log_serialized
    assert "raw-edi-payload-should-not-emit" not in log_serialized
