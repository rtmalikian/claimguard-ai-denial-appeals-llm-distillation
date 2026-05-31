import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_student_cutover_private_env.py"


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_student_cutover_private_env",
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
    output_path = tmp_path / "claimguard-student-cutover.private.env"

    summary = renderer.render_private_env(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["student_use_by_default"] is False
    assert summary["cutover_approved"] is False
    assert summary["approval_reference_configured"] is False
    assert summary["rollback_to_nvidia"] is True
    assert summary["raw_env_values_included"] is False
    assert summary["approval_reference_value_included"] is False
    assert "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE=" not in serialized
    assert not output_path.exists()


def test_approved_cutover_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
            )
        )


def test_approved_cutover_requires_private_approval_reference(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="approval reference env var"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
            )
        )


def test_approved_cutover_writes_private_env_and_redacts_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    approval_reference = "CG-CUTOVER-REF-20260531"
    output_path = tmp_path / "student-cutover.env"
    monkeypatch.setenv(renderer.DEFAULT_APPROVAL_REFERENCE_ENV, approval_reference)

    summary = renderer.render_private_env(
        renderer.RenderConfig(
            output_path=output_path,
            approved_cutover=True,
            enable_auto_launch=True,
            raphael_approval_attested=True,
            runtime_supervised_attested=True,
            distillation_release_attested=True,
            rollback_reviewed=True,
        )
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    serialized = json.dumps(summary, sort_keys=True)

    assert output_mode == 0o600
    assert summary["student_use_by_default"] is True
    assert summary["student_auto_launch_requested"] is True
    assert summary["cutover_approved"] is True
    assert summary["approval_reference_configured"] is True
    assert summary["runtime_supervised"] is True
    assert summary["rollback_to_nvidia"] is False
    assert summary["values_redacted"] is True
    assert approval_reference in output_text
    assert approval_reference not in serialized
    assert "CLAIMGUARD_STUDENT_USE_BY_DEFAULT=true" in output_text
    assert "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=false" in output_text


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "student-cutover.private.env",
            )
        )
