import importlib.util
import json
import plistlib
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_mlx_runtime_supervisor_private_evidence.py"


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_mlx_runtime_supervisor_private_evidence",
        RENDERER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _approved_config(renderer: ModuleType, output_path: Path):
    return renderer.RenderConfig(
        output_path=output_path,
        approved_supervisor=True,
        runtime_owner_attested=True,
        private_launchd_copy_attested=True,
        restart_policy_reviewed=True,
        health_check_reviewed=True,
        manual_start_command_reviewed=True,
        rollback_to_nvidia_reviewed=True,
        environment_file_excluded_attested=True,
        mlx_runtime_preflight_ready=True,
        student_status_endpoint_checked=True,
        student_runtime_health_ok=True,
        supervisor_loaded_in_user_session=True,
        supervisor_restart_test_passed=True,
        no_raw_values_attested=True,
    )


def _write_private_plist(path: Path) -> None:
    payload = {
        "Label": "com.claimguard.mlx-student",
        "ProgramArguments": [
            "/private/claimguard/.venv-mlx/bin/mlx_lm.server",
            "--model",
            "Qwen/Qwen3-4B-MLX-4bit",
            "--adapter-path",
            "/private/claimguard/llm-distill/models/adapters/claimguard-qwen3-4b-lora-reviewed",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--max-tokens",
            "1800",
        ],
        "WorkingDirectory": "/private/claimguard",
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": "/tmp/claimguard-mlx-student.out.log",
        "StandardErrorPath": "/tmp/claimguard-mlx-student.err.log",
        "EnvironmentVariables": {
            "CLAIMGUARD_RUNTIME_PROFILE": "student_denial_workflow_local_only",
        },
    }
    path.write_bytes(plistlib.dumps(payload))


def _set_private_references(
    monkeypatch,
    renderer: ModuleType,
    plist_path: Path,
) -> dict[str, str]:
    values = {
        renderer.DEFAULT_PRIVATE_PLIST_PATH_ENV: str(plist_path),
        renderer.DEFAULT_OWNER_REFERENCE_ENV: "RUNTIME-OWNER-REF-TEST",
        renderer.DEFAULT_PREFLIGHT_REFERENCE_ENV: "PREFLIGHT-REF-TEST",
        renderer.DEFAULT_HEALTH_REFERENCE_ENV: "HEALTH-REF-TEST",
        renderer.DEFAULT_RESTART_REFERENCE_ENV: "RESTART-REF-TEST",
        renderer.DEFAULT_ROLLBACK_REFERENCE_ENV: "ROLLBACK-REF-TEST",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "mlx-supervisor.private.json"

    summary = renderer.render_private_evidence(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["approved_supervisor_requested"] is False
    assert summary["runtime_owner_configured"] is False
    assert summary["student_runtime_health_ok"] is False
    assert summary["supervisor_restart_test_passed"] is False
    assert summary["raw_private_values_included"] is False
    assert summary["raw_runtime_output_included"] is False
    assert summary["private_plist_path_value_included"] is False
    assert "RUNTIME-OWNER-REF-TEST" not in serialized
    assert not output_path.exists()


def test_approved_mode_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    plist_path = tmp_path / "private-launchd.plist"
    _write_private_plist(plist_path)
    _set_private_references(monkeypatch, renderer, plist_path)

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=tmp_path / "mlx-supervisor.private.json",
                approved_supervisor=True,
            )
        )


def test_approved_mode_requires_private_plist_path(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="private plist path"):
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "mlx-supervisor.private.json")
        )


def test_approved_mode_rejects_source_control_private_plist(monkeypatch, tmp_path):
    renderer = _load_renderer()
    source_control_plist = (
        REPO_ROOT
        / "llm-distill"
        / "data"
        / "runtime_supervision"
        / "claimguard.mlx-student.launchd.template.plist"
    )
    _set_private_references(monkeypatch, renderer, source_control_plist)

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_evidence(
            _approved_config(renderer, tmp_path / "mlx-supervisor.private.json")
        )


def test_approved_mode_writes_private_evidence_and_redacts_values(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    plist_path = tmp_path / "private-launchd.plist"
    _write_private_plist(plist_path)
    private_values = _set_private_references(monkeypatch, renderer, plist_path)
    output_path = tmp_path / "mlx-supervisor.private.json"

    summary = renderer.render_private_evidence(
        _approved_config(renderer, output_path)
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(output_text)
    serialized_summary = json.dumps(summary, sort_keys=True)

    assert output_mode == 0o600
    assert summary["runtime_owner_configured"] is True
    assert summary["private_launchd_copy_attested"] is True
    assert summary["mlx_runtime_preflight_ready"] is True
    assert summary["student_runtime_health_ok"] is True
    assert summary["supervisor_loaded_in_user_session"] is True
    assert summary["supervisor_restart_test_passed"] is True
    assert summary["private_reference_count"] == len(private_values) - 1
    assert summary["private_plist_path_value_included"] is False
    assert summary["values_redacted"] is True
    assert str(plist_path) not in serialized_summary
    assert payload["evidence_status"] == (
        "supervisor_ready_private_runtime_validation_complete"
    )
    assert payload["launchd_template"]["plist_path"] == str(plist_path)
    assert payload["operator_controls"]["runtime_owner_configured"] is True
    assert payload["runtime_validation"]["student_runtime_health_ok"] is True
    for key, private_value in private_values.items():
        if key == renderer.DEFAULT_PRIVATE_PLIST_PATH_ENV:
            continue
        assert private_value not in output_text
        assert private_value not in serialized_summary


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_evidence(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "mlx-supervisor.private.json",
            )
        )
