import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
RENDERER_SCRIPT = SCRIPT_DIR / "render_phi_plan_manual_gate_private_packet.py"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_phi_plan_manual_gate_packet.py"
READY_SUPERVISOR_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/mlx_runtime_supervisor_ready_report.json"
)
READY_MODEL_IMPROVEMENT_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/model_improvement_ready_report.json"
)
READY_PRODUCTION_CORPUS_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/production_corpus_ready_report.json"
)
READY_RETRIEVAL_VECTOR_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/retrieval_vector_backend_ready_report.json"
)
READY_PREDICTION_FAIRNESS_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/prediction_fairness_ready_report.json"
)
READY_FILE_INGESTION_SURFACE_REPORT_FIXTURE = (
    "health-ai-medical-billing-medical-corporations-20260414_180528/"
    "tests/fixtures/file_ingestion_surface_ready_report.json"
)


def _load_script(script_path: Path, module_name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_renderer() -> ModuleType:
    return _load_script(
        RENDERER_SCRIPT,
        "render_phi_plan_manual_gate_private_packet",
    )


def _load_validator() -> ModuleType:
    return _load_script(
        VALIDATOR_SCRIPT,
        "validate_phi_plan_manual_gate_packet_for_renderer_test",
    )


def _approved_config(renderer: ModuleType, output_path: Path):
    return renderer.RenderConfig(
        output_path=output_path,
        approved_production_gate=True,
        approved_non_synthetic_pair_count=1,
        approved_source_types=("real_deidentified_pair",),
        student_cutover_attested=True,
        student_runtime_attested=True,
        model_improvement_attested=True,
        production_corpus_attested=True,
        retrieval_vector_attested=True,
        prediction_fairness_attested=True,
        file_ingestion_surface_attested=True,
        dependent_reports_ready_attested=True,
        no_raw_values_attested=True,
        supervisor_report=READY_SUPERVISOR_REPORT_FIXTURE,
        model_improvement_report=READY_MODEL_IMPROVEMENT_REPORT_FIXTURE,
        production_corpus_report=READY_PRODUCTION_CORPUS_REPORT_FIXTURE,
        retrieval_vector_report=READY_RETRIEVAL_VECTOR_REPORT_FIXTURE,
        prediction_fairness_report=READY_PREDICTION_FAIRNESS_REPORT_FIXTURE,
        file_ingestion_surface_report=READY_FILE_INGESTION_SURFACE_REPORT_FIXTURE,
    )


def _manual_gate_summary_payload(**overrides):
    payload = {
        "student_cutover_attested": True,
        "student_runtime_attested": True,
        "model_improvement_attested": True,
        "production_corpus_attested": True,
        "retrieval_vector_attested": True,
        "prediction_fairness_attested": True,
        "file_ingestion_surface_attested": True,
        "dependent_reports_ready_attested": True,
        "manual_review_completed": True,
        "release_review_completed": True,
        "all_dependent_reports_ready": True,
        "manifest_records_reviewed": True,
        "approved_non_synthetic_pairs_reviewed": True,
        "no_phi_or_secret_values_attested": True,
        "no_raw_values_attested": True,
        "values_redacted": True,
        "approval_reference_values_included": False,
        "private_reference_values_included": False,
        "summary_manifest_record_ids_included": False,
        "raw_document_content_included": False,
        "raw_report_evidence_included": False,
        "phi_or_secret_values_included": False,
        "source_text_included": False,
        "vector_values_included": False,
        "endpoint_values_included": False,
        "credential_values_included": False,
        "raw_demographic_values_included": False,
        "raw_outcome_rows_included": False,
        "approved_non_synthetic_pair_count": 1,
        "approved_source_type_count": 1,
        "manifest_record_id_count": 2,
        "dependent_report_count": 6,
        "private_reference_count": 3,
    }
    payload.update(overrides)
    return payload


def _write_private_summary(path: Path, **overrides) -> None:
    path.write_text(
        json.dumps(
            _manual_gate_summary_payload(**overrides),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _set_private_values(monkeypatch, renderer: ModuleType) -> dict[str, str]:
    values = {
        renderer.DEFAULT_MANIFEST_RECORD_IDS_ENV: json.dumps(
            ["PRIVATE-DENIAL-REC-1", "PRIVATE-APPEAL-REC-1"]
        ),
        renderer.DEFAULT_MANUAL_REVIEW_REFERENCE_ENV: "MANUAL-GATE-REF-TEST",
        renderer.DEFAULT_DEPENDENT_EVIDENCE_REFERENCE_ENV: "DEPENDENT-EVIDENCE-REF-TEST",
        renderer.DEFAULT_RELEASE_REFERENCE_ENV: "RELEASE-REF-TEST",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def _set_private_summary(monkeypatch, renderer: ModuleType, summary_path: Path) -> None:
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(summary_path))


def test_conservative_dry_run_redacts_values(tmp_path):
    renderer = _load_renderer()
    output_path = tmp_path / "manual-gate.private.json"

    summary = renderer.render_private_packet(
        renderer.RenderConfig(output_path=output_path, dry_run=True)
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["dry_run"] is True
    assert summary["rendered"] is False
    assert summary["approved_production_gate_requested"] is False
    assert summary["production_gate_ready"] is False
    assert summary["dependent_evidence_reports_checked"] is False
    assert summary["dependent_evidence_reports_ready"] is False
    assert summary["approved_non_synthetic_pair_count"] == 0
    assert summary["manifest_record_id_count"] == 0
    assert summary["raw_packet_values_included"] is False
    assert summary["raw_document_content_included"] is False
    assert summary["raw_report_evidence_included"] is False
    assert summary["values_redacted"] is True
    assert "MANUAL-GATE-REF-TEST" not in serialized
    assert not output_path.exists()


def test_approved_mode_requires_explicit_attestations(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)

    with pytest.raises(renderer.RenderError, match="explicit attestations"):
        renderer.render_private_packet(
            renderer.RenderConfig(
                output_path=tmp_path / "manual-gate.private.json",
                approved_production_gate=True,
            )
        )


def test_approved_mode_requires_private_manifest_record_ids(monkeypatch, tmp_path):
    renderer = _load_renderer()
    config = _approved_config(renderer, tmp_path / "manual-gate.private.json")
    for env_name, value in [
        (config.manual_review_reference_env, "MANUAL-GATE-REF-TEST"),
        (config.dependent_evidence_reference_env, "DEPENDENT-EVIDENCE-REF-TEST"),
        (config.release_reference_env, "RELEASE-REF-TEST"),
    ]:
        monkeypatch.setenv(env_name, value)

    with pytest.raises(renderer.RenderError, match="manifest record ids"):
        renderer.render_private_packet(config)


def test_approved_mode_requires_private_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)

    with pytest.raises(
        renderer.RenderError,
        match="private manual gate summary path env var is required",
    ):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_requires_ready_dependent_reports(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)

    with pytest.raises(renderer.RenderError, match="manual gate dependent report is not ready"):
        renderer.render_private_packet(
            renderer.RenderConfig(
                output_path=tmp_path / "manual-gate.private.json",
                approved_production_gate=True,
                approved_non_synthetic_pair_count=1,
                approved_source_types=("real_deidentified_pair",),
                student_cutover_attested=True,
                student_runtime_attested=True,
                model_improvement_attested=True,
                production_corpus_attested=True,
                retrieval_vector_attested=True,
                prediction_fairness_attested=True,
                file_ingestion_surface_attested=True,
                dependent_reports_ready_attested=True,
                no_raw_values_attested=True,
            )
        )


def test_approved_mode_rejects_insufficient_manifest_record_ids(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    monkeypatch.setenv(renderer.DEFAULT_MANIFEST_RECORD_IDS_ENV, "PRIVATE-DENIAL-REC-1")

    with pytest.raises(renderer.RenderError, match="missing for approved pairs"):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_rejects_source_control_summary_path(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    monkeypatch.setenv(renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV, str(RENDERER_SCRIPT))

    with pytest.raises(renderer.RenderError, match="outside source control"):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_rejects_incomplete_private_summary(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "manual-gate-summary.json"
    _write_private_summary(summary_path, all_dependent_reports_ready=False)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(
        renderer.RenderError,
        match="all_dependent_reports_ready=true",
    ):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_rejects_private_summary_raw_value_flags(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "manual-gate-summary.json"
    _write_private_summary(summary_path, raw_report_evidence_included=True)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="raw_report_evidence_included=false"):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_rejects_unsupported_private_summary_fields(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "manual-gate-summary.json"
    _write_private_summary(summary_path, raw_approval_reference="redacted")
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="unsupported fields"):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_rejects_private_summary_count_mismatch(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    summary_path = tmp_path / "manual-gate-summary.json"
    _write_private_summary(summary_path, manifest_record_id_count=3)
    _set_private_summary(monkeypatch, renderer, summary_path)

    with pytest.raises(renderer.RenderError, match="manifest record count mismatch"):
        renderer.render_private_packet(
            _approved_config(renderer, tmp_path / "manual-gate.private.json")
        )


def test_approved_mode_writes_private_packet_and_redacts_summary(
    monkeypatch,
    tmp_path,
):
    renderer = _load_renderer()
    validator = _load_validator()
    private_values = _set_private_values(monkeypatch, renderer)
    output_path = tmp_path / "manual-gate.private.json"
    summary_path = tmp_path / "manual-gate-summary.json"
    _write_private_summary(summary_path)
    _set_private_summary(monkeypatch, renderer, summary_path)

    summary = renderer.render_private_packet(
        _approved_config(renderer, output_path)
    )

    output_mode = stat.S_IMODE(output_path.stat().st_mode)
    output_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(output_text)
    serialized_summary = json.dumps(summary, sort_keys=True)
    report = validator.build_report(output_path)

    assert output_mode == 0o600
    assert summary["production_gate_ready"] is True
    assert summary["dependent_evidence_reports_checked"] is True
    assert summary["dependent_evidence_reports_ready"] is True
    assert summary["private_reference_count"] == 3
    assert summary["manifest_record_id_count"] == 2
    assert summary["private_manual_gate_summary_checked"] is True
    assert summary["private_manual_gate_summary_path_env_configured"] is True
    assert summary["private_manual_gate_summary_path_configured"] is True
    assert summary["private_manual_gate_summary_path_value_included"] is False
    assert summary["private_manual_gate_summary_approved_non_synthetic_pair_count"] == 1
    assert summary["private_manual_gate_summary_approved_source_type_count"] == 1
    assert summary["private_manual_gate_summary_manifest_record_id_count"] == 2
    assert summary["private_manual_gate_summary_dependent_report_count"] == 6
    assert summary["private_manual_gate_summary_private_reference_count"] == 3
    assert summary["private_manual_gate_summary_raw_values_included"] is False
    assert summary["manifest_record_ids_included_in_summary"] is False
    assert summary["approval_reference_value_included"] is False
    assert summary["values_redacted"] is True
    assert payload["packet_status"] == "private_manual_production_gate_ready"
    assert payload["source_control_private_packet_renderer_documented"] is True
    assert (
        payload["private_manual_gate_summary_path_env"]
        == renderer.DEFAULT_PRIVATE_SUMMARY_PATH_ENV
    )
    assert payload["private_manual_gate_summary_path_value_included"] is False
    assert payload["private_manual_gate_summary_checked"] is True
    assert payload["private_manual_gate_summary_path_configured"] is True
    assert payload["private_manual_gate_summary_approved_non_synthetic_pair_count"] == 1
    assert payload["private_manual_gate_summary_approved_source_type_count"] == 1
    assert payload["private_manual_gate_summary_manifest_record_id_count"] == 2
    assert payload["private_manual_gate_summary_dependent_report_count"] == 6
    assert payload["private_manual_gate_summary_private_reference_count"] == 3
    assert payload["private_manual_gate_summary_raw_values_included"] is False
    assert payload["approval_reference_value_included"] is False
    assert payload["private_reference_values_included"] is False
    assert payload["manifest_record_ids_included_in_summary"] is False
    assert payload["raw_document_content_included"] is False
    assert payload["raw_report_evidence_included"] is False
    assert str(summary_path) not in output_text
    assert str(summary_path) not in serialized_summary
    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is True
    for key, private_value in private_values.items():
        if key == renderer.DEFAULT_MANIFEST_RECORD_IDS_ENV:
            continue
        assert private_value not in output_text
        assert private_value not in serialized_summary
    assert "PRIVATE-DENIAL-REC-1" not in serialized_summary
    assert "PRIVATE-APPEAL-REC-1" not in serialized_summary


def test_dependent_report_path_must_stay_inside_source_control(tmp_path):
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="inside source control"):
        renderer.render_private_packet(
            renderer.RenderConfig(
                output_path=tmp_path / "manual-gate.private.json",
                supervisor_report="../private-supervisor-report.json",
            )
        )


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_packet(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "manual-gate.private.json",
            )
        )
