import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_model_improvement_private_env.py"
READY_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/model_improvement_ready_report.json"
)


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_model_improvement_private_env",
        RENDERER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _private_summary_payload(**overrides):
    payload = {
        "model_improvement_request_attested": True,
        "legal_approval_attested": True,
        "baa_confirmed_attested": True,
        "consent_notice_attested": True,
        "retention_reviewed": True,
        "revocation_reviewed": True,
        "per_request_attestations_reviewed": True,
        "evidence_ready_attested": True,
        "approval_reference_configured": True,
        "consent_notice_version_configured": True,
        "model_improvement_evidence_report_ready": True,
        "data_use_scope_reviewed": True,
        "approved_corpus_only_attested": True,
        "no_external_phi_deidentification_attested": True,
        "raw_phi_training_disabled_attested": True,
        "revocation_blocks_future_training_attested": True,
        "no_phi_or_secret_values_attested": True,
        "values_redacted": True,
        "approval_reference_value_included": False,
        "consent_notice_value_included": False,
        "raw_env_values_included": False,
        "raw_evidence_report_included": False,
        "raw_user_data_included": False,
        "raw_document_content_included": False,
        "phi_or_secret_values_included": False,
        "credential_values_included": False,
        "endpoint_values_included": False,
        "legal_document_values_included": False,
        "baa_document_values_included": False,
        "environment_variable_count": 6,
        "private_reference_count": 1,
        "private_consent_notice_count": 1,
        "evidence_report_count": 1,
        "retention_review_count": 1,
        "revocation_review_count": 1,
        "per_request_gate_count": 1,
    }
    payload.update(overrides)
    return payload


def _write_private_summary(path: Path, **overrides) -> None:
    path.write_text(
        json.dumps(
            _private_summary_payload(**overrides),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _set_private_summary(monkeypatch, renderer: ModuleType, summary_path: Path) -> None:
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "claimguard-model-improvement.private.env"

    summary = renderer.render_private_env(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["model_improvement_enabled"] is False
    assert summary["legal_approval_confirmed"] is False
    assert summary["baa_confirmed"] is False
    assert summary["consent_notice_version_configured"] is False
    assert summary["approval_reference_configured"] is False
    assert summary["evidence_report_checked"] is False
    assert summary["evidence_report_ready"] is False
    assert summary["raw_env_values_included"] is False
    assert summary["approval_reference_value_included"] is False
    assert summary["consent_notice_value_included"] is False
    assert "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE=" not in serialized
    assert not output_path.exists()


def test_approved_mode_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
            )
        )


def test_approved_mode_requires_private_reference_and_consent(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="approval reference env var"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_requires_private_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")

    with pytest.raises(
        renderer.RenderError,
        match="private model-improvement summary path env var is required",
    ):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_requires_ready_evidence_report(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")

    with pytest.raises(renderer.RenderError, match="evidence report is not ready"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
            )
        )


def test_approved_mode_rejects_source_control_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(RENDERER_SCRIPT))

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_rejects_incomplete_private_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")
    summary_path = tmp_path / "model-improvement-summary.json"
    _write_private_summary(summary_path, data_use_scope_reviewed=False)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="data_use_scope_reviewed=true"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_rejects_private_summary_raw_value_flags(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")
    summary_path = tmp_path / "model-improvement-summary.json"
    _write_private_summary(summary_path, raw_user_data_included=True)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="raw_user_data_included=false"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_rejects_unsupported_private_summary_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")
    summary_path = tmp_path / "model-improvement-summary.json"
    _write_private_summary(summary_path, approval_reference="redacted")
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_rejects_private_summary_count_mismatch(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "MODEL-IMPROVEMENT-REF-TEST",
    )
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, "CONSENT-VERSION-TEST")
    summary_path = tmp_path / "model-improvement-summary.json"
    _write_private_summary(summary_path, environment_variable_count=7)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="environment variable count mismatch"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                approved_model_improvement=True,
                model_improvement_request_attested=True,
                legal_approval_attested=True,
                baa_confirmed_attested=True,
                consent_notice_attested=True,
                retention_reviewed=True,
                revocation_reviewed=True,
                per_request_attestations_reviewed=True,
                evidence_ready_attested=True,
                evidence_report=READY_REPORT_FIXTURE,
            )
        )


def test_approved_mode_writes_private_env_and_redacts_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    approval_reference = "MODEL-IMPROVEMENT-REF-TEST"
    consent_notice = "CONSENT-VERSION-TEST"
    output_path = tmp_path / "model-improvement.env"
    summary_path = tmp_path / "model-improvement-summary.json"
    monkeypatch.setenv(renderer.DEFAULT_APPROVAL_REFERENCE_ENV, approval_reference)
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, consent_notice)
    _write_private_summary(summary_path)
    _set_private_summary(monkeypatch, renderer, summary_path)

    summary = renderer.render_private_env(
        renderer.RenderConfig(
            output_path=output_path,
            approved_model_improvement=True,
            model_improvement_request_attested=True,
            legal_approval_attested=True,
            baa_confirmed_attested=True,
            consent_notice_attested=True,
            retention_reviewed=True,
            revocation_reviewed=True,
            per_request_attestations_reviewed=True,
            evidence_ready_attested=True,
            evidence_report=READY_REPORT_FIXTURE,
        )
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    serialized = json.dumps(summary, sort_keys=True)

    assert output_mode == 0o600
    assert summary["model_improvement_enabled"] is True
    assert summary["legal_approval_confirmed"] is True
    assert summary["baa_confirmed"] is True
    assert summary["consent_notice_version_configured"] is True
    assert summary["approval_reference_configured"] is True
    assert summary["evidence_report_checked"] is True
    assert summary["evidence_report_ready"] is True
    assert summary["private_model_improvement_summary_checked"] is True
    assert summary["private_model_improvement_summary_path_env_configured"] is True
    assert summary["private_model_improvement_summary_path_value_included"] is False
    assert summary["private_model_improvement_summary_environment_variable_count"] == 6
    assert summary["private_model_improvement_summary_private_reference_count"] == 1
    assert summary["private_model_improvement_summary_consent_notice_count"] == 1
    assert summary["private_model_improvement_summary_evidence_report_count"] == 1
    assert summary["private_model_improvement_summary_retention_review_count"] == 1
    assert summary["private_model_improvement_summary_revocation_review_count"] == 1
    assert summary["private_model_improvement_summary_per_request_gate_count"] == 1
    assert summary["private_model_improvement_summary_raw_values_included"] is False
    assert summary["values_redacted"] is True
    assert approval_reference in output_text
    assert consent_notice in output_text
    assert approval_reference not in serialized
    assert consent_notice not in serialized
    assert str(summary_path) not in output_text
    assert str(summary_path) not in serialized
    assert "USER_DATA_MODEL_IMPROVEMENT_ENABLED=true" in output_text
    assert "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=true" in output_text
    assert "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=true" in output_text
    assert f"USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT={READY_REPORT_FIXTURE}" in output_text


def test_evidence_report_path_must_stay_inside_source_control(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="inside source control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "model-improvement.env",
                evidence_report="../private-model-improvement-report.json",
            )
        )


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "model-improvement.private.env",
            )
        )
