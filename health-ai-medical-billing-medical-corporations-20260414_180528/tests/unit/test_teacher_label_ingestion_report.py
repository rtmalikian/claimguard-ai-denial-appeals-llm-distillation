import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
INGEST_SCRIPT = SCRIPT_DIR / "ingest_teacher_labels.py"


def _load_ingester() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("ingest_teacher_labels", INGEST_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_teacher_label_ingestion_report_sanitizes_source_controlled_paths(tmp_path, monkeypatch):
    ingester = _load_ingester()
    fake_repo = tmp_path / "repo"
    output_path = (
        fake_repo
        / "llm-distill"
        / "data"
        / "distillation"
        / "teacher_label_ingestion_report.json"
    )
    payload = {
        "seed_input": str(
            fake_repo
            / "llm-distill"
            / "data"
            / "distillation"
            / "seed_synthetic_supervised.jsonl"
        ),
        "teacher_responses": str(
            fake_repo
            / "llm-distill"
            / "data"
            / "distillation"
            / "teacher_responses_from_review.jsonl"
        ),
        "reviewed_output": str(
            fake_repo
            / "llm-distill"
            / "data"
            / "distillation"
            / "reviewed_supervised.jsonl"
        ),
        "training_gate": {"training_allowed": True},
    }
    monkeypatch.setattr(ingester, "REPO_ROOT", fake_repo)

    ingester.write_report(output_path, payload)

    report_text = output_path.read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert str(fake_repo) not in report_text
    assert report["seed_input"] == "llm-distill/data/distillation/seed_synthetic_supervised.jsonl"
    assert (
        report["teacher_responses"]
        == "llm-distill/data/distillation/teacher_responses_from_review.jsonl"
    )
