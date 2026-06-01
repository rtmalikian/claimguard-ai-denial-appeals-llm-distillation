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
READY_SUPERVISOR_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/mlx_runtime_supervisor_ready_report.json"
)


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


def _private_summary_payload(**overrides):
    payload = {
        "raphael_approval_attested": True,
        "runtime_supervised_attested": True,
        "distillation_release_attested": True,
        "rollback_reviewed": True,
        "student_default_enabled_reviewed": True,
        "approval_reference_configured": True,
        "supervisor_report_ready": True,
        "runtime_supervised": True,
        "runtime_owner_assigned": True,
        "distillation_release_ready": True,
        "rollback_to_nvidia_disabled_reviewed": True,
        "auto_launch_setting_reviewed": True,
        "scope_limited_to_denial_workflow_and_appeals": True,
        "no_phi_or_secret_values_attested": True,
        "values_redacted": True,
        "approval_reference_value_included": False,
        "raw_env_values_included": False,
        "raw_report_evidence_included": False,
        "raw_runtime_output_included": False,
        "phi_or_secret_values_included": False,
        "endpoint_values_included": False,
        "credential_values_included": False,
        "prompt_or_response_values_included": False,
        "production_document_content_included": False,
        "environment_variable_count": 7,
        "private_reference_count": 1,
        "supervisor_report_count": 1,
        "runtime_validation_check_count": 4,
        "rollback_review_count": 1,
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
    assert summary["supervisor_report_checked"] is False
    assert summary["supervisor_report_ready"] is False
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
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_requires_private_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )

    with pytest.raises(
        renderer.RenderError,
        match="private cutover summary path env var is required",
    ):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_requires_ready_supervisor_report(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )

    with pytest.raises(renderer.RenderError, match="supervisor evidence report is not ready"):
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


def test_approved_cutover_rejects_source_control_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(RENDERER_SCRIPT))

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_rejects_incomplete_private_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )
    summary_path = tmp_path / "student-cutover-summary.json"
    _write_private_summary(summary_path, runtime_owner_assigned=False)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="runtime_owner_assigned=true"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_rejects_private_summary_raw_value_flags(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )
    summary_path = tmp_path / "student-cutover-summary.json"
    _write_private_summary(summary_path, raw_env_values_included=True)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="raw_env_values_included=false"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_rejects_unsupported_private_summary_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )
    summary_path = tmp_path / "student-cutover-summary.json"
    _write_private_summary(summary_path, approval_reference="redacted")
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_rejects_private_summary_count_mismatch(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    monkeypatch.setenv(
        renderer.DEFAULT_APPROVAL_REFERENCE_ENV,
        "CG-CUTOVER-REF-20260531",
    )
    summary_path = tmp_path / "student-cutover-summary.json"
    _write_private_summary(summary_path, environment_variable_count=8)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="environment variable count mismatch"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                approved_cutover=True,
                raphael_approval_attested=True,
                runtime_supervised_attested=True,
                distillation_release_attested=True,
                rollback_reviewed=True,
                supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
            )
        )


def test_approved_cutover_writes_private_env_and_redacts_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    approval_reference = "CG-CUTOVER-REF-20260531"
    output_path = tmp_path / "student-cutover.env"
    summary_path = tmp_path / "student-cutover-summary.json"
    monkeypatch.setenv(renderer.DEFAULT_APPROVAL_REFERENCE_ENV, approval_reference)
    _write_private_summary(summary_path)
    _set_private_summary(monkeypatch, renderer, summary_path)

    summary = renderer.render_private_env(
        renderer.RenderConfig(
            output_path=output_path,
            approved_cutover=True,
            enable_auto_launch=True,
            raphael_approval_attested=True,
            runtime_supervised_attested=True,
            distillation_release_attested=True,
            rollback_reviewed=True,
            supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
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
    assert summary["supervisor_report_checked"] is True
    assert summary["supervisor_report_ready"] is True
    assert summary["private_cutover_summary_checked"] is True
    assert summary["private_cutover_summary_path_env_configured"] is True
    assert summary["private_cutover_summary_path_value_included"] is False
    assert summary["private_cutover_summary_environment_variable_count"] == 7
    assert summary["private_cutover_summary_private_reference_count"] == 1
    assert summary["private_cutover_summary_supervisor_report_count"] == 1
    assert summary["private_cutover_summary_runtime_validation_check_count"] == 4
    assert summary["private_cutover_summary_rollback_review_count"] == 1
    assert summary["private_cutover_summary_raw_values_included"] is False
    assert summary["values_redacted"] is True
    assert approval_reference in output_text
    assert approval_reference not in serialized
    assert str(summary_path) not in output_text
    assert str(summary_path) not in serialized
    assert "CLAIMGUARD_STUDENT_USE_BY_DEFAULT=true" in output_text
    assert "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=false" in output_text


def test_supervisor_report_path_must_stay_inside_source_control(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="inside source control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=tmp_path / "student-cutover.env",
                supervisor_report="../private-supervisor-report.json",
            )
        )


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_env(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "student-cutover.private.env",
            )
        )
