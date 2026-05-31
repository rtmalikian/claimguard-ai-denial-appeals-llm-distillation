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


def test_approved_mode_rejects_insufficient_manifest_record_ids(monkeypatch, tmp_path):
    renderer = _load_renderer()
    _set_private_values(monkeypatch, renderer)
    monkeypatch.setenv(renderer.DEFAULT_MANIFEST_RECORD_IDS_ENV, "PRIVATE-DENIAL-REC-1")

    with pytest.raises(renderer.RenderError, match="missing for approved pairs"):
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
    assert summary["private_reference_count"] == 3
    assert summary["manifest_record_id_count"] == 2
    assert summary["manifest_record_ids_included_in_summary"] is False
    assert summary["approval_reference_value_included"] is False
    assert summary["values_redacted"] is True
    assert payload["packet_status"] == "private_manual_production_gate_ready"
    assert payload["source_control_private_packet_renderer_documented"] is True
    assert report["safe_to_review"] is True
    assert report["production_gate_ready"] is True
    for key, private_value in private_values.items():
        if key == renderer.DEFAULT_MANIFEST_RECORD_IDS_ENV:
            continue
        assert private_value not in output_text
        assert private_value not in serialized_summary
    assert "PRIVATE-DENIAL-REC-1" not in serialized_summary
    assert "PRIVATE-APPEAL-REC-1" not in serialized_summary


def test_renderer_refuses_source_control_output():
    renderer = _load_renderer()

    with pytest.raises(renderer.RenderError, match="source_control"):
        renderer.render_private_packet(
            renderer.RenderConfig(
                output_path=REPO_ROOT / "manual-gate.private.json",
            )
        )
