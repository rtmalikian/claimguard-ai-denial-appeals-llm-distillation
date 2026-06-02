import importlib.util
import json
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SANITIZER_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "report_output_sanitizer.py"
PHI_PLAN_EVIDENCE_VALIDATOR_SCRIPTS = (
    REPO_ROOT / "llm-distill" / "scripts" / "validate_mlx_runtime_supervisor.py",
    REPO_ROOT / "llm-distill" / "scripts" / "validate_model_improvement_evidence.py",
    REPO_ROOT / "llm-distill" / "scripts" / "validate_phi_plan_manual_gate_packet.py",
    REPO_ROOT / "llm-distill" / "scripts" / "validate_prediction_fairness_evidence.py",
    REPO_ROOT / "llm-distill" / "scripts" / "validate_production_corpus_evidence.py",
    REPO_ROOT / "llm-distill" / "scripts" / "validate_retrieval_vector_backend.py",
)
TEACHER_REVIEW_PIPELINE_REPORT_SCRIPTS = (
    REPO_ROOT / "llm-distill" / "scripts" / "run_reviewed_distillation_pipeline.py",
    REPO_ROOT / "llm-distill" / "scripts" / "run_teacher_label_batch.py",
    REPO_ROOT / "llm-distill" / "scripts" / "run_teacher_review_packet.py",
)
PUBLIC_REPORT_WRITER_SCRIPTS = (
    REPO_ROOT / "llm-distill" / "scripts" / "audit_file_ingestion_surfaces.py",
    REPO_ROOT / "llm-distill" / "scripts" / "audit_public_source_notes.py",
    REPO_ROOT / "llm-distill" / "scripts" / "audit_synthetic_denial_appeal_corpus.py",
    REPO_ROOT
    / "llm-distill"
    / "scripts"
    / "audit_synthetic_document_analysis_extraction.py",
    REPO_ROOT / "llm-distill" / "scripts" / "bootstrap_mlx_runtime.py",
    REPO_ROOT / "llm-distill" / "scripts" / "export_corpus_sft_data.py",
    REPO_ROOT / "llm-distill" / "scripts" / "generate_synthetic_denial_appeal_corpus.py",
    REPO_ROOT / "llm-distill" / "scripts" / "ingest_teacher_labels.py",
    REPO_ROOT / "llm-distill" / "scripts" / "prepare_mlx_sft_data.py",
    REPO_ROOT / "llm-distill" / "scripts" / "render_synthetic_corpus_visual_layouts.py",
    REPO_ROOT / "llm-distill" / "scripts" / "run_mlx_finetune.py",
)


def _load_sanitizer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "report_output_sanitizer",
        SANITIZER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sanitizer_emits_repo_relative_paths_and_redacts_external_paths(tmp_path):
    sanitizer = _load_sanitizer()
    repo_root = tmp_path / "repo"
    payload = {
        "report_path": str(
            repo_root / "llm-distill" / "evals" / "reports" / "report.json"
        ),
        "embedded_repo_path": (
            "validated "
            + str(repo_root / "llm-distill" / "docs" / "operator-runbook.md")
        ),
        "external_path": str(tmp_path / "private" / "summary.json"),
        "traceback_tail": "File "
        + str(tmp_path / "outside" / ".venv" / "bin" / "tool"),
        "nested": [
            {
                "error": (
                    "missing evidence file: "
                    + str(tmp_path / "var" / "private-evidence.json")
                )
            }
        ],
    }

    sanitized = sanitizer.sanitize_report_value(payload, repo_root)
    serialized = json.dumps(sanitized, sort_keys=True)

    assert sanitized["report_path"] == "llm-distill/evals/reports/report.json"
    assert "llm-distill/docs/operator-runbook.md" in sanitized["embedded_repo_path"]
    assert sanitized["external_path"] == "external_path_redacted"
    assert sanitized["traceback_tail"] == "File external_path_redacted"
    assert (
        sanitized["nested"][0]["error"]
        == "missing evidence file: external_path_redacted"
    )
    assert str(repo_root) not in serialized
    assert str(tmp_path) not in serialized


def test_write_sanitized_report_json_writes_clean_sorted_payload(tmp_path):
    sanitizer = _load_sanitizer()
    repo_root = tmp_path / "repo"
    output = tmp_path / "report.json"
    payload = {
        "z_path": str(repo_root / "llm-distill" / "evals" / "reports" / "z.json"),
        "a_path": str(tmp_path / "outside" / "private.json"),
    }

    sanitizer.write_sanitized_report_json(output, payload, repo_root)

    text = output.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a_path"') < text.index('"z_path"')
    assert "llm-distill/evals/reports/z.json" in text
    assert "external_path_redacted" in text
    assert str(repo_root) not in text
    assert str(tmp_path) not in text


def test_write_source_controlled_report_json_sanitizes_repo_outputs(tmp_path):
    sanitizer = _load_sanitizer()
    repo_root = tmp_path / "repo"
    output = repo_root / "llm-distill" / "evals" / "reports" / "report.json"
    payload = {
        "repo_path": str(output),
        "external_path": str(tmp_path / "scratch" / "private-report.json"),
    }

    sanitizer.write_source_controlled_report_json(output, payload, repo_root)

    text = output.read_text(encoding="utf-8")
    report = json.loads(text)
    assert report["repo_path"] == "llm-distill/evals/reports/report.json"
    assert report["external_path"] == "external_path_redacted"
    assert str(repo_root) not in text
    assert str(tmp_path / "scratch") not in text


def test_write_source_controlled_report_json_preserves_scratch_outputs(tmp_path):
    sanitizer = _load_sanitizer()
    repo_root = tmp_path / "repo"
    output = tmp_path / "scratch" / "report.json"
    payload = {
        "repo_path": str(repo_root / "llm-distill" / "evals" / "reports" / "report.json"),
        "external_path": str(output),
    }

    sanitizer.write_source_controlled_report_json(output, payload, repo_root)

    text = output.read_text(encoding="utf-8")
    report = json.loads(text)
    assert report["repo_path"] == str(
        repo_root / "llm-distill" / "evals" / "reports" / "report.json"
    )
    assert report["external_path"] == str(output)


def test_phi_plan_evidence_validators_use_source_controlled_report_writer():
    for script_path in PHI_PLAN_EVIDENCE_VALIDATOR_SCRIPTS:
        text = script_path.read_text(encoding="utf-8")

        assert (
            "from report_output_sanitizer import "
            "write_source_controlled_report_json"
        ) in text
        assert "write_source_controlled_report_json(args.report, safe_report, REPO_ROOT)" in text
        assert "args.report.write_text(json.dumps(safe_report" not in text


def test_teacher_review_pipeline_reports_use_source_controlled_writer():
    for script_path in TEACHER_REVIEW_PIPELINE_REPORT_SCRIPTS:
        text = script_path.read_text(encoding="utf-8")

        assert "write_source_controlled_report_json" in text
        assert "write_sanitized_report_json" not in text


def test_public_report_writers_use_source_controlled_writer():
    for script_path in PUBLIC_REPORT_WRITER_SCRIPTS:
        text = script_path.read_text(encoding="utf-8")

        assert "write_source_controlled_report_json" in text
        assert "write_sanitized_report_json" not in text
