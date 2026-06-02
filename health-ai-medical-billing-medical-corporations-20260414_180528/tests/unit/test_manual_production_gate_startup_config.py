import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.manual_production_gate_config import (
    validate_manual_production_gate_startup_config,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "PHI_PLAN_MANUAL_GATE_PACKET_REPORT": (
            "llm-distill/evals/reports/phi_plan_manual_gate_packet_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "production_gate_ready": True,
        "requirements": [
            {
                "requirement_id": "manual_gate_packet_format",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def test_manual_production_gate_development_reports_blockers_without_fail_fast():
    report = validate_manual_production_gate_startup_config(
        settings_like=_settings(),
        evidence_report=_ready_evidence_report(
            production_gate_ready=False,
            requirements=[
                {
                    "requirement_id": "manual_production_corpus_evidence",
                    "status": "blocked",
                }
            ],
        ),
    )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "manual_production_gate_packet_report_not_ready" in report["blockers"]
    assert (
        "manual_production_gate_packet_report_has_blocked_requirements"
        in report["blockers"]
    )
    assert report["safe_context"]["raw_document_content_included"] is False


def test_manual_production_gate_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_manual_production_gate_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(production_gate_ready=False),
        )

    assert str(exc_info.value) == "Manual production gate startup configuration is not ready."


def test_manual_production_gate_production_fails_fast_when_unsafe():
    with pytest.raises(RuntimeError):
        validate_manual_production_gate_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_manual_production_gate_production_fails_fast_with_blocked_items_schema():
    with pytest.raises(RuntimeError):
        validate_manual_production_gate_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report={
                "safe_to_review": True,
                "production_gate_ready": True,
                "blocked_items": [
                    {
                        "requirement_id": "manual_prediction_fairness_monitoring_evidence",
                        "status": "blocked",
                    }
                ],
            },
        )


def test_manual_production_gate_production_passes_when_report_ready():
    report = validate_manual_production_gate_startup_config(
        settings_like=_settings(APP_ENV="production"),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["evidence_report_ready"] is True
    assert report["evidence_report_safe_to_review"] is True
    assert report["blockers"] == []


def test_manual_production_gate_startup_can_load_configured_report(tmp_path):
    report_path = tmp_path / "manual-gate-report.json"
    report_path.write_text(json.dumps(_ready_evidence_report()), encoding="utf-8")

    report = validate_manual_production_gate_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            PHI_PLAN_MANUAL_GATE_PACKET_REPORT=str(report_path),
        )
    )

    assert report["startup_ready"] is True
    assert report["evidence_report_checked"] is True
    assert str(report_path) not in json.dumps(report, sort_keys=True)


def test_manual_production_gate_missing_report_path_blocks_production():
    with pytest.raises(RuntimeError):
        validate_manual_production_gate_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                PHI_PLAN_MANUAL_GATE_PACKET_REPORT="",
            )
        )


def test_manual_production_gate_startup_report_does_not_emit_raw_values(caplog):
    raw_private_summary_path = "/private/manual-gate/summary.json"
    raw_reference = "synthetic-manual-reference-should-not-emit"
    raw_manifest_id = "MANIFEST-RAW-SHOULD-NOT-EMIT"
    raw_report_evidence = "raw-dependent-report-evidence-should-not-emit"
    report_with_values = _ready_evidence_report(
        private_manual_gate_summary_path=raw_private_summary_path,
        approval_reference=raw_reference,
        manifest_record_ids=[raw_manifest_id],
        raw_report_evidence=raw_report_evidence,
    )

    with caplog.at_level(
        logging.INFO,
        logger="app.utils.manual_production_gate_config",
    ):
        report = validate_manual_production_gate_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                PHI_PLAN_MANUAL_GATE_PACKET_REPORT=raw_private_summary_path,
            ),
            evidence_report=report_with_values,
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].manual_production_gate_startup_config,
        sort_keys=True,
    )

    assert raw_private_summary_path not in serialized
    assert raw_reference not in serialized
    assert raw_manifest_id not in serialized
    assert raw_report_evidence not in serialized
    assert raw_private_summary_path not in log_serialized
    assert raw_reference not in log_serialized
    assert raw_manifest_id not in log_serialized
    assert raw_report_evidence not in log_serialized
