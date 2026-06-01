import importlib.util
import json
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SANITIZER_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "report_output_sanitizer.py"


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
