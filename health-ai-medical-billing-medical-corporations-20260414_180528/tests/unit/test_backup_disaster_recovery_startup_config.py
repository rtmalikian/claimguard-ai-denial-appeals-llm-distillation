import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.backup_disaster_recovery_config import (
    validate_backup_disaster_recovery_startup_config,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT": (
            "llm-distill/evals/reports/backup_disaster_recovery_evidence_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "backup_disaster_recovery_ready": True,
        "requirements": [
            {
                "requirement_id": "backup_disaster_recovery_storage_controls",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def test_backup_dr_development_reports_blockers_without_fail_fast():
    report = validate_backup_disaster_recovery_startup_config(
        settings_like=_settings(),
        evidence_report=_ready_evidence_report(
            backup_disaster_recovery_ready=False,
            requirements=[
                {
                    "requirement_id": "backup_disaster_recovery_storage_controls",
                    "status": "blocked",
                }
            ],
        ),
    )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "backup_disaster_recovery_evidence_report_not_ready" in report["blockers"]
    assert (
        "backup_disaster_recovery_evidence_report_has_blocked_requirements"
        in report["blockers"]
    )
    assert report["safe_context"]["raw_backup_path_included"] is False


def test_backup_dr_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_backup_disaster_recovery_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(
                backup_disaster_recovery_ready=False
            ),
        )

    assert str(exc_info.value) == (
        "Backup and disaster-recovery startup configuration is not production-ready."
    )


def test_backup_dr_production_fails_fast_when_unsafe():
    with pytest.raises(RuntimeError):
        validate_backup_disaster_recovery_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_backup_dr_production_passes_when_report_ready():
    report = validate_backup_disaster_recovery_startup_config(
        settings_like=_settings(APP_ENV="production"),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["evidence_report_ready"] is True
    assert report["evidence_report_safe_to_review"] is True
    assert report["blockers"] == []


def test_backup_dr_startup_can_load_configured_report(tmp_path):
    report_path = tmp_path / "backup-dr-report.json"
    report_path.write_text(json.dumps(_ready_evidence_report()), encoding="utf-8")

    report = validate_backup_disaster_recovery_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT=str(report_path),
        )
    )

    assert report["startup_ready"] is True
    assert report["evidence_report_checked"] is True
    assert str(report_path) not in json.dumps(report, sort_keys=True)


def test_backup_dr_missing_report_path_blocks_production():
    with pytest.raises(RuntimeError):
        validate_backup_disaster_recovery_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT="",
            )
        )


def test_backup_dr_startup_report_does_not_emit_raw_values(caplog):
    raw_backup_path = "/private/backups/claim-data.sql.gz"
    raw_reference = "synthetic-backup-reference-should-not-emit"
    raw_key_value = "synthetic-encryption-key-value-should-not-emit"
    raw_restore_output = "raw-database-row-should-not-emit"
    report_with_values = _ready_evidence_report(
        backup_path=raw_backup_path,
        restore_output=raw_restore_output,
        encryption_key_value=raw_key_value,
        approval_reference=raw_reference,
    )

    with caplog.at_level(
        logging.INFO,
        logger="app.utils.backup_disaster_recovery_config",
    ):
        report = validate_backup_disaster_recovery_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT=raw_backup_path,
            ),
            evidence_report=report_with_values,
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].backup_disaster_recovery_startup_config,
        sort_keys=True,
    )

    assert raw_backup_path not in serialized
    assert raw_reference not in serialized
    assert raw_key_value not in serialized
    assert raw_restore_output not in serialized
    assert raw_backup_path not in log_serialized
    assert raw_reference not in log_serialized
    assert raw_key_value not in log_serialized
    assert raw_restore_output not in log_serialized
