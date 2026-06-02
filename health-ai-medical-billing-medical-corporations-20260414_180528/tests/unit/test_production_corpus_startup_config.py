import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.production_corpus_config import (
    validate_production_corpus_startup_config,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "PRODUCTION_CORPUS_EVIDENCE_REPORT": (
            "llm-distill/evals/reports/production_corpus_evidence_report.json"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready_evidence_report(**overrides):
    values = {
        "safe_to_review": True,
        "production_corpus_ready": True,
        "requirements": [
            {
                "requirement_id": "production_corpus_manifest_pair_evidence",
                "status": "ready",
            }
        ],
    }
    values.update(overrides)
    return values


def test_production_corpus_development_reports_blockers_without_fail_fast():
    report = validate_production_corpus_startup_config(
        settings_like=_settings(),
        evidence_report=_ready_evidence_report(
            production_corpus_ready=False,
            requirements=[
                {
                    "requirement_id": "production_corpus_manifest_pair_evidence",
                    "status": "blocked",
                }
            ],
        ),
    )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "production_corpus_evidence_report_not_ready" in report["blockers"]
    assert (
        "production_corpus_evidence_report_has_blocked_requirements"
        in report["blockers"]
    )
    assert report["safe_context"]["raw_document_text_included"] is False


def test_production_corpus_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_production_corpus_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(production_corpus_ready=False),
        )

    assert str(exc_info.value) == "Production corpus startup configuration is not ready."


def test_production_corpus_production_fails_fast_when_unsafe():
    with pytest.raises(RuntimeError):
        validate_production_corpus_startup_config(
            settings_like=_settings(APP_ENV="production"),
            evidence_report=_ready_evidence_report(safe_to_review=False),
        )


def test_production_corpus_production_passes_when_report_ready():
    report = validate_production_corpus_startup_config(
        settings_like=_settings(APP_ENV="production"),
        evidence_report=_ready_evidence_report(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["evidence_report_ready"] is True
    assert report["evidence_report_safe_to_review"] is True
    assert report["blockers"] == []


def test_production_corpus_startup_can_load_configured_report(tmp_path):
    report_path = tmp_path / "production-corpus-report.json"
    report_path.write_text(json.dumps(_ready_evidence_report()), encoding="utf-8")

    report = validate_production_corpus_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            PRODUCTION_CORPUS_EVIDENCE_REPORT=str(report_path),
        )
    )

    assert report["startup_ready"] is True
    assert report["evidence_report_checked"] is True
    assert str(report_path) not in json.dumps(report, sort_keys=True)


def test_production_corpus_missing_report_path_blocks_production():
    with pytest.raises(RuntimeError):
        validate_production_corpus_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                PRODUCTION_CORPUS_EVIDENCE_REPORT="",
            )
        )


def test_production_corpus_startup_report_does_not_emit_raw_values(caplog):
    raw_source_path = "/private/corpus/patient-denial.txt"
    raw_reference = "synthetic-corpus-reference-should-not-emit"
    raw_document = "raw-denial-letter-text-should-not-emit"
    raw_checksum = "sha256:synthetic-checksum-should-not-emit"
    report_with_values = _ready_evidence_report(
        source_url_or_path=raw_source_path,
        raw_document_text=raw_document,
        checksum=raw_checksum,
        approval_reference=raw_reference,
    )

    with caplog.at_level(
        logging.INFO,
        logger="app.utils.production_corpus_config",
    ):
        report = validate_production_corpus_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                PRODUCTION_CORPUS_EVIDENCE_REPORT=raw_source_path,
            ),
            evidence_report=report_with_values,
        )

    serialized = json.dumps(report, sort_keys=True)
    log_serialized = json.dumps(
        caplog.records[-1].production_corpus_startup_config,
        sort_keys=True,
    )

    assert raw_source_path not in serialized
    assert raw_reference not in serialized
    assert raw_document not in serialized
    assert raw_checksum not in serialized
    assert raw_source_path not in log_serialized
    assert raw_reference not in log_serialized
    assert raw_document not in log_serialized
    assert raw_checksum not in log_serialized
