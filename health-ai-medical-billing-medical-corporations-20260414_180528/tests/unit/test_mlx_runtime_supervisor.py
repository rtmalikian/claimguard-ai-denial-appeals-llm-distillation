import importlib.util
import json
import plistlib
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_mlx_runtime_supervisor.py"
RENDERER_SCRIPT = SCRIPT_DIR / "render_mlx_launchd_private_copy.py"


def _load_validator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_mlx_runtime_supervisor",
        VALIDATOR_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_renderer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_mlx_launchd_private_copy",
        RENDERER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_plist(
    path: Path,
    *,
    host: str = "127.0.0.1",
    environment_variables: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": "com.claimguard.mlx-student",
        "ProgramArguments": [
            "/private/claimguard/.venv-mlx/bin/mlx_lm.server",
            "--model",
            "Qwen/Qwen3-4B-MLX-4bit",
            "--adapter-path",
            "/private/claimguard/llm-distill/models/adapters/claimguard-qwen3-4b-lora-reviewed",
            "--host",
            host,
            "--port",
            "8080",
            "--max-tokens",
            "1800",
            "--chat-template-args",
            '{"enable_thinking": false}',
        ],
        "WorkingDirectory": "/private/claimguard",
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": "/tmp/claimguard-mlx-student.out.log",
        "StandardErrorPath": "/tmp/claimguard-mlx-student.err.log",
        "EnvironmentVariables": environment_variables
        if environment_variables is not None
        else {
            "CLAIMGUARD_RUNTIME_PROFILE": "student_denial_workflow_local_only",
        },
    }
    path.write_bytes(plistlib.dumps(payload))


def _ready_evidence(plist_path: Path, runbook_path: Path | None = None) -> dict:
    if runbook_path is None:
        runbook_path = (
            REPO_ROOT
            / "llm-distill"
            / "docs"
            / "mlx-runtime-supervisor-runbook.md"
        )
    return {
        "artifact": "claimguard_mlx_runtime_supervisor_evidence",
        "version": "1.0",
        "evidence_status": "ready_for_private_operator_install",
        "prepared_at": "2026-05-30T18:39:10-07:00",
        "no_phi_or_secret_values_attested": True,
        "launchd_template": {
            "plist_path": str(plist_path),
            "uses_shell": False,
            "runs_mlx_lm_server": True,
            "uses_adapter_path": True,
            "binds_loopback_only": True,
            "base_url_matches_mlx_base_url": True,
            "keepalive_enabled": True,
            "working_directory_configured": True,
            "log_paths_configured": True,
            "contains_secrets": False,
        },
        "operator_controls": {
            "runtime_owner_configured": True,
            "launchd_private_copy_renderer_available": True,
            "launchd_private_copy_renderer_path": (
                "llm-distill/scripts/render_mlx_launchd_private_copy.py"
            ),
            "source_control_private_evidence_renderer_documented": True,
            "private_evidence_renderer_path": (
                "llm-distill/scripts/render_mlx_runtime_supervisor_private_evidence.py"
            ),
            "source_control_runbook_documented": True,
            "source_control_runbook_path": str(runbook_path),
            "source_control_owner_handoff_checklist_documented": True,
            "source_control_owner_handoff_checklist_path": "llm-distill/docs/mlx-runtime-owner-handoff-checklist.md",
            "restart_policy_reviewed": True,
            "health_check_reviewed": True,
            "manual_start_command_reviewed": True,
            "rollback_to_nvidia_reviewed": True,
            "environment_file_excluded_from_source_control": True,
        },
        "runtime_validation": {
            "source_control_validation_checklist_documented": True,
            "source_control_validation_checklist_path": "llm-distill/docs/mlx-runtime-validation-checklist.md",
            "mlx_runtime_preflight_ready": True,
            "student_status_endpoint_checked": True,
            "student_runtime_health_ok": True,
            "supervisor_loaded_in_user_session": True,
            "supervisor_restart_test_passed": True,
        },
        "private_plist_validation": {
            "private_plist_metadata_checked": True,
            "private_plist_program_arguments_checked": True,
            "private_plist_environment_checked": True,
            "private_plist_program_argument_count": 13,
            "private_plist_environment_key_count": 1,
            "private_plist_required_environment_key_count": 1,
            "private_plist_runs_mlx_lm_server": True,
            "private_plist_uses_adapter_path": True,
            "private_plist_uses_loopback": True,
            "private_plist_port_configured": True,
            "private_plist_working_directory_configured": True,
            "private_plist_keepalive_configured": True,
            "private_plist_log_paths_configured": True,
            "private_plist_runtime_profile_ok": True,
            "private_plist_secret_like_env_keys_present": False,
            "private_plist_unapproved_env_keys_present": False,
            "private_plist_path_value_included": False,
            "private_plist_raw_values_included": False,
            "values_redacted": True,
        },
        "private_summary_validation": {
            "private_supervisor_summary_checked": True,
            "private_supervisor_summary_path_env_configured": True,
            "private_supervisor_summary_path_value_included": False,
            "private_supervisor_summary_private_reference_count": 5,
            "private_supervisor_summary_private_plist_count": 1,
            "private_supervisor_summary_launchd_program_argument_count": 13,
            "private_supervisor_summary_launchd_environment_variable_count": 1,
            "private_supervisor_summary_required_environment_variable_count": 1,
            "private_supervisor_summary_operator_control_count": 7,
            "private_supervisor_summary_runtime_validation_count": 5,
            "private_supervisor_summary_raw_values_included": False,
        },
    }


def test_supervisor_template_is_safe_to_review_but_not_ready():
    validator = _load_validator()
    template_path = (
        REPO_ROOT
        / "llm-distill"
        / "data"
        / "runtime_supervision"
        / "supervisor_evidence.template.json"
    )

    report = validator.build_report(template_path)

    blocked_ids = {item["requirement_id"] for item in report["blocked_items"]}
    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert "mlx_runtime_supervisor_no_phi_or_secret_values" not in blocked_ids
    assert "mlx_runtime_supervisor_launchd_template" not in blocked_ids
    assert "mlx_runtime_supervisor_private_copy_renderer" not in blocked_ids
    assert "mlx_runtime_supervisor_private_evidence_renderer" not in blocked_ids
    assert "mlx_runtime_supervisor_operator_runbook" not in blocked_ids
    assert "mlx_runtime_supervisor_owner_handoff_checklist" not in blocked_ids
    assert "mlx_runtime_supervisor_runtime_validation_checklist" not in blocked_ids
    assert "mlx_runtime_supervisor_private_runtime_metadata" in blocked_ids
    assert "mlx_runtime_supervisor_operator_controls" in blocked_ids
    assert "mlx_runtime_supervisor_runtime_validation" in blocked_ids
    operator_requirement = next(
        item for item in report["blocked_items"] if item["requirement_id"] == "mlx_runtime_supervisor_operator_controls"
    )
    assert operator_requirement["blockers"] == ["runtime_owner_not_configured"]
    assert "restart_policy_not_reviewed" not in operator_requirement["blockers"]
    assert "health_check_not_reviewed" not in operator_requirement["blockers"]
    assert "manual_start_command_not_reviewed" not in operator_requirement["blockers"]
    assert operator_requirement["evidence"]["restart_policy_reviewed"] is True
    assert operator_requirement["evidence"]["health_check_reviewed"] is True
    assert operator_requirement["evidence"]["manual_start_command_reviewed"] is True
    assert (
        operator_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    assert operator_requirement["evidence"]["source_control_runbook_documented"] is True
    assert (
        operator_requirement["evidence"][
            "source_control_owner_handoff_checklist_documented"
        ]
        is True
    )
    runbook_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "mlx_runtime_supervisor_operator_runbook"
    )
    assert runbook_requirement["status"] == "ready"
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False
    assert runbook_requirement["evidence"]["missing_marker_count"] == 0
    owner_checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "mlx_runtime_supervisor_owner_handoff_checklist"
    )
    assert owner_checklist_requirement["status"] == "ready"
    assert (
        owner_checklist_requirement["evidence"][
            "source_control_owner_handoff_checklist_documented"
        ]
        is True
    )
    assert owner_checklist_requirement["evidence"]["owner_handoff_checklist_exists"] is True
    assert owner_checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert owner_checklist_requirement["evidence"]["missing_marker_count"] == 0
    launchd_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "mlx_runtime_supervisor_launchd_template"
    )
    assert launchd_requirement["status"] == "ready"
    assert launchd_requirement["evidence"]["raw_environment_values_included"] is False
    assert launchd_requirement["evidence"]["environment_variable_count"] == 1
    renderer_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "mlx_runtime_supervisor_private_copy_renderer"
    )
    assert renderer_requirement["status"] == "ready"
    assert renderer_requirement["evidence"]["renderer_exists"] is True
    assert renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    private_evidence_renderer_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "mlx_runtime_supervisor_private_evidence_renderer"
    )
    assert private_evidence_renderer_requirement["status"] == "ready"
    assert (
        private_evidence_renderer_requirement["evidence"][
            "source_control_private_evidence_renderer_documented"
        ]
        is True
    )
    assert (
        private_evidence_renderer_requirement["evidence"][
            "private_evidence_renderer_exists"
        ]
        is True
    )
    assert private_evidence_renderer_requirement["evidence"]["missing_marker_count"] == 0
    assert (
        private_evidence_renderer_requirement["evidence"]["raw_renderer_text_included"]
        is False
    )
    checklist_requirement = next(
        item
        for item in report["requirements"]
        if item["requirement_id"] == "mlx_runtime_supervisor_runtime_validation_checklist"
    )
    assert checklist_requirement["status"] == "ready"
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert checklist_requirement["evidence"]["missing_marker_count"] == 0
    private_metadata_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_private_runtime_metadata"
    )
    assert (
        "private_plist_metadata_not_checked"
        in private_metadata_requirement["blockers"]
    )
    assert (
        "private_supervisor_summary_not_checked"
        in private_metadata_requirement["blockers"]
    )
    assert (
        "private_supervisor_summary_private_reference_count_missing"
        in private_metadata_requirement["blockers"]
    )
    assert (
        private_metadata_requirement["evidence"]["private_plist_raw_values_included"]
        is False
    )


def test_ready_supervisor_evidence_passes_all_requirements(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_evidence.json"
    _write_plist(plist_path)
    _write_json(evidence_path, _ready_evidence(plist_path))

    report = validator.build_report(evidence_path)

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is True
    assert report["blocked_item_count"] == 0


def test_ready_supervisor_requires_private_runtime_metadata(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_missing_private_metadata.json"
    evidence = _ready_evidence(plist_path)
    for key in [
        "private_plist_metadata_checked",
        "private_plist_program_arguments_checked",
        "private_plist_environment_checked",
        "private_plist_runs_mlx_lm_server",
        "private_plist_uses_adapter_path",
        "private_plist_uses_loopback",
        "private_plist_port_configured",
        "private_plist_working_directory_configured",
        "private_plist_keepalive_configured",
        "private_plist_log_paths_configured",
        "private_plist_runtime_profile_ok",
    ]:
        evidence["private_plist_validation"][key] = False
    for key in [
        "private_plist_program_argument_count",
        "private_plist_environment_key_count",
        "private_plist_required_environment_key_count",
    ]:
        evidence["private_plist_validation"][key] = 0
    for key in [
        "private_supervisor_summary_checked",
        "private_supervisor_summary_path_env_configured",
    ]:
        evidence["private_summary_validation"][key] = False
    for key in [
        "private_supervisor_summary_private_reference_count",
        "private_supervisor_summary_private_plist_count",
        "private_supervisor_summary_launchd_program_argument_count",
        "private_supervisor_summary_launchd_environment_variable_count",
        "private_supervisor_summary_required_environment_variable_count",
        "private_supervisor_summary_operator_control_count",
        "private_supervisor_summary_runtime_validation_count",
    ]:
        evidence["private_summary_validation"][key] = 0
    _write_plist(plist_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    private_metadata_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_private_runtime_metadata"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert (
        "private_plist_metadata_not_checked"
        in private_metadata_requirement["blockers"]
    )
    assert (
        "private_supervisor_summary_private_reference_count_missing"
        in private_metadata_requirement["blockers"]
    )
    assert (
        "private_supervisor_summary_private_plist_count_must_be_one"
        in private_metadata_requirement["blockers"]
    )


def test_private_runtime_metadata_value_flags_are_blocked(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_private_value_flags.json"
    evidence = _ready_evidence(plist_path)
    evidence["private_plist_validation"]["private_plist_path_value_included"] = True
    evidence["private_summary_validation"][
        "private_supervisor_summary_raw_values_included"
    ] = True
    _write_plist(plist_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    private_metadata_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_private_runtime_metadata"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert "private_plist_path_value_included" in private_metadata_requirement["blockers"]
    assert (
        "private_supervisor_summary_raw_values_included"
        in private_metadata_requirement["blockers"]
    )
    assert (
        private_metadata_requirement["evidence"]["private_plist_path_value_included"]
        is True
    )


def test_source_control_runbook_markers_are_required(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    runbook_path = tmp_path / "mlx-runtime-supervisor-runbook.md"
    evidence_path = tmp_path / "supervisor_evidence.json"
    _write_plist(plist_path)
    runbook_path.write_text(
        "ClaimGuard AI is architected by Raphael Malikian.\n",
        encoding="utf-8",
    )
    _write_json(evidence_path, _ready_evidence(plist_path, runbook_path))

    report = validator.build_report(evidence_path)
    runbook_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_operator_runbook"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert "source_control_runbook_required_markers_missing" in runbook_requirement["blockers"]
    assert runbook_requirement["evidence"]["raw_runbook_text_included"] is False


def test_runtime_validation_checklist_markers_are_required(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    checklist_path = tmp_path / "mlx-runtime-validation-checklist.md"
    evidence_path = tmp_path / "supervisor_evidence.json"
    _write_plist(plist_path)
    checklist_path.write_text(
        "Current status: not runtime-validated.\n",
        encoding="utf-8",
    )
    evidence = _ready_evidence(plist_path)
    evidence["runtime_validation"]["source_control_validation_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_runtime_validation_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert (
        "source_control_validation_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False


def test_runtime_owner_handoff_checklist_markers_are_required(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    checklist_path = tmp_path / "mlx-runtime-owner-handoff-checklist.md"
    evidence_path = tmp_path / "supervisor_evidence.json"
    _write_plist(plist_path)
    checklist_text = "Current status: runtime owner not assigned for production.\n"
    checklist_path.write_text(checklist_text, encoding="utf-8")
    evidence = _ready_evidence(plist_path)
    evidence["operator_controls"]["source_control_owner_handoff_checklist_path"] = str(
        checklist_path
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    checklist_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_owner_handoff_checklist"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert (
        "source_control_owner_handoff_checklist_required_markers_missing"
        in checklist_requirement["blockers"]
    )
    assert checklist_requirement["evidence"]["raw_checklist_text_included"] is False
    assert checklist_text.strip() not in serialized


def test_manual_start_command_review_is_required_for_operator_controls(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_evidence.json"
    evidence = _ready_evidence(plist_path)
    evidence["operator_controls"]["manual_start_command_reviewed"] = False
    _write_plist(plist_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    operator_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_operator_controls"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert operator_requirement["blockers"] == ["manual_start_command_not_reviewed"]


def test_supervisor_evidence_blocks_non_loopback_host(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_evidence.json"
    _write_plist(plist_path, host="0.0.0.0")
    _write_json(evidence_path, _ready_evidence(plist_path))

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["supervisor_ready"] is False
    assert "launchd_template_host_must_be_loopback" in serialized


def test_supervisor_evidence_blocks_unapproved_launchd_environment_without_values(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_evidence.json"
    blocked_value = "student-runtime-value-do-not-write"
    _write_plist(
        plist_path,
        environment_variables={
            "CLAIMGUARD_RUNTIME_PROFILE": "unsafe_profile",
            "NVIDIA_API_KEY": blocked_value,
        },
    )
    _write_json(evidence_path, _ready_evidence(plist_path))

    report = validator.build_report(evidence_path)
    launchd_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_launchd_template"
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["supervisor_ready"] is False
    assert "launchd_template_required_environment_values_not_conservative" in launchd_requirement["blockers"]
    assert "launchd_template_has_unapproved_environment_variables" in launchd_requirement["blockers"]
    assert "launchd_template_has_secret_or_proxy_environment_names" in launchd_requirement["blockers"]
    assert launchd_requirement["evidence"]["wrong_required_environment_variables"] == [
        "CLAIMGUARD_RUNTIME_PROFILE"
    ]
    assert launchd_requirement["evidence"]["unexpected_environment_variables"] == [
        "NVIDIA_API_KEY"
    ]
    assert launchd_requirement["evidence"]["forbidden_environment_variables"] == [
        "NVIDIA_API_KEY"
    ]
    assert launchd_requirement["evidence"]["raw_environment_values_included"] is False
    assert blocked_value not in serialized
    assert "unsafe_profile" not in serialized


def test_supervisor_evidence_blocks_raw_secret_values_without_emitting_them(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_evidence.json"
    blocked_value = "student-runtime-value-do-not-write"
    evidence = _ready_evidence(plist_path)
    evidence["runtime_secret"] = blocked_value
    _write_plist(plist_path)
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["safe_to_review"] is False
    assert report["supervisor_ready"] is False
    assert "raw approval, secret, or document value key is not allowed" in serialized
    assert blocked_value not in serialized


def test_private_launchd_renderer_writes_redacted_safe_plist(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "claimguard.mlx-student.private.plist"
    deployment_root = tmp_path / "private-claimguard"

    summary = renderer.render_private_copy(
        renderer.RenderConfig(
            template_path=(
                REPO_ROOT
                / "llm-distill"
                / "data"
                / "runtime_supervision"
                / "claimguard.mlx-student.launchd.template.plist"
            ),
            output_path=output_path,
            deployment_root=deployment_root,
            host="127.0.0.1",
            port=8080,
            model="Qwen/Qwen3-4B-MLX-4bit",
            max_tokens=1800,
        )
    )
    plist = plistlib.loads(output_path.read_bytes())
    arguments = plist["ProgramArguments"]

    assert summary["rendered"] is True
    assert summary["output_path_in_source_control"] is False
    assert summary["raw_paths_in_summary"] is False
    assert summary["raw_environment_values_included"] is False
    assert summary["values_redacted"] is True
    assert output_path.stat().st_mode & 0o777 == 0o600
    assert "/ABSOLUTE/PATH/TO" not in json.dumps(plist)
    assert arguments[0].endswith("mlx_lm.server")
    assert arguments[arguments.index("--host") + 1] == "127.0.0.1"
    assert plist["EnvironmentVariables"] == {
        "CLAIMGUARD_RUNTIME_PROFILE": "student_denial_workflow_local_only"
    }


def test_private_launchd_renderer_refuses_source_control_output(tmp_path):
    renderer = _load_renderer()
    repo_output = REPO_ROOT / "llm-distill" / "data" / "runtime_supervision" / "unsafe.plist"

    try:
        try:
            renderer.render_private_copy(
                renderer.RenderConfig(
                    template_path=(
                        REPO_ROOT
                        / "llm-distill"
                        / "data"
                        / "runtime_supervision"
                        / "claimguard.mlx-student.launchd.template.plist"
                    ),
                    output_path=repo_output,
                    deployment_root=tmp_path / "private-claimguard",
                    host="127.0.0.1",
                    port=8080,
                    model="Qwen/Qwen3-4B-MLX-4bit",
                    max_tokens=1800,
                )
            )
        except renderer.RenderError as exc:
            assert str(exc) == "refusing_to_write_inside_source_control"
        else:
            raise AssertionError("renderer accepted a source-control output path")
    finally:
        if repo_output.exists():
            repo_output.unlink()


def test_private_evidence_renderer_markers_are_required_without_emitting_text(tmp_path):
    validator = _load_validator()
    plist_path = tmp_path / "claimguard.mlx-student.plist"
    evidence_path = tmp_path / "supervisor_evidence.json"
    incomplete_renderer = tmp_path / "render_mlx_runtime_supervisor_private_evidence.py"
    raw_renderer_text = "RenderConfig"
    _write_plist(plist_path)
    incomplete_renderer.write_text(raw_renderer_text, encoding="utf-8")
    evidence = _ready_evidence(plist_path)
    evidence["operator_controls"]["private_evidence_renderer_path"] = str(
        incomplete_renderer
    )
    _write_json(evidence_path, evidence)

    report = validator.build_report(evidence_path)
    serialized = json.dumps(report, sort_keys=True)
    renderer_requirement = next(
        item
        for item in report["blocked_items"]
        if item["requirement_id"] == "mlx_runtime_supervisor_private_evidence_renderer"
    )

    assert report["safe_to_review"] is True
    assert report["supervisor_ready"] is False
    assert (
        "source_control_private_evidence_renderer_required_markers_missing"
        in renderer_requirement["blockers"]
    )
    assert renderer_requirement["evidence"]["raw_renderer_text_included"] is False
    assert raw_renderer_text not in serialized
