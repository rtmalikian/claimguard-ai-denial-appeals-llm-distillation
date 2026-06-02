import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.dependency_security_config import (
    validate_dependency_security_startup_config,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "DEPENDENCY_SECURITY_EVIDENCE_REPORT": (
            "llm-distill/evals/reports/dependency_security_evidence_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "dependency_security_ready": True,
        "requirements": [
            {
                "requirement_id": "dependency_security_scan_controls",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def test_dependency_security_development_reports_blockers_without_fail_fast():
    report = validate_dependency_security_startup_config(
        settings_like=_settings(),
        evidence_report=_ready_evidence_report(
            dependency_security_ready=False,
            requirements=[
                {
                    "requirement_id": "dependency_security_scan_controls",
                    "status": "blocked",
                }
            ],
        ),
    )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "dependency_security_evidence_report_not_ready" in report["blockers"]
    assert (
        "dependency_security_evidence_report_has_blocked_requirements"
        in report["blockers"]
    )
    assert report["safe_context"]["raw_scanner_output_included"] is False


def test_dependency_security_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_dependency_security_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(dependency_security_ready=False),
        )

    assert str(exc_info.value) == (
        "Dependency security startup configuration is not production-ready."
    )


def test_dependency_security_production_fails_fast_when_unsafe():
    with pytest.raises(RuntimeError):
        validate_dependency_security_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_dependency_security_production_passes_when_report_ready():
    report = validate_dependency_security_startup_config(
        settings_like=_settings(APP_ENV="production"),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["evidence_report_ready"] is True
    assert report["evidence_report_safe_to_review"] is True
    assert report["blockers"] == []


def test_dependency_security_startup_can_load_configured_report(tmp_path):
    report_path = tmp_path / "dependency-security-report.json"
    report_path.write_text(json.dumps(_ready_evidence_report()), encoding="utf-8")

    report = validate_dependency_security_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            DEPENDENCY_SECURITY_EVIDENCE_REPORT=str(report_path),
        )
    )

    assert report["startup_ready"] is True
    assert report["evidence_report_checked"] is True
    assert str(report_path) not in json.dumps(report, sort_keys=True)


def test_dependency_security_missing_report_path_blocks_production():
    with pytest.raises(RuntimeError):
        validate_dependency_security_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                DEPENDENCY_SECURITY_EVIDENCE_REPORT="",
            )
        )


def test_dependency_security_startup_report_does_not_emit_raw_values(caplog):
    raw_registry_url = "https://registry.example.invalid/private"
    raw_reference = "synthetic-dependency-reference-should-not-emit"
    raw_scanner_output = "raw-vulnerability-detail-should-not-emit"
    report_with_values = _ready_evidence_report(
        scanner_output=raw_scanner_output,
        vulnerability_details=raw_scanner_output,
        private_registry_url=raw_registry_url,
        approval_reference=raw_reference,
    )

    with caplog.at_level(
        logging.INFO,
        logger="app.utils.dependency_security_config",
    ):
        report = validate_dependency_security_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                DEPENDENCY_SECURITY_EVIDENCE_REPORT=raw_registry_url,
            ),
            evidence_report=report_with_values,
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].dependency_security_startup_config,
        sort_keys=True,
    )

    assert raw_registry_url not in serialized
    assert raw_reference not in serialized
    assert raw_scanner_output not in serialized
    assert raw_registry_url not in log_serialized
    assert raw_reference not in log_serialized
    assert raw_scanner_output not in log_serialized
