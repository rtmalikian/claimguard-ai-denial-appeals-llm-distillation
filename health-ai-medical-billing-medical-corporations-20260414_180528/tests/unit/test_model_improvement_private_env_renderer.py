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
            )
        )


def test_approved_mode_writes_private_env_and_redacts_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    approval_reference = "MODEL-IMPROVEMENT-REF-TEST"
    consent_notice = "CONSENT-VERSION-TEST"
    output_path = tmp_path / "model-improvement.env"
    monkeypatch.setenv(renderer.DEFAULT_APPROVAL_REFERENCE_ENV, approval_reference)
    monkeypatch.setenv(renderer.DEFAULT_CONSENT_NOTICE_ENV, consent_notice)

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
    assert summary["values_redacted"] is True
    assert approval_reference in output_text
    assert consent_notice in output_text
    assert approval_reference not in serialized
    assert consent_notice not in serialized
    assert "USER_DATA_MODEL_IMPROVEMENT_ENABLED=true" in output_text
    assert "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED=true" in output_text
    assert "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED=true" in output_text


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "model-improvement.private.env",
            )
        )
