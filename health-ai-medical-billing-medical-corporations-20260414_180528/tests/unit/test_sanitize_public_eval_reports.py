import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
SANITIZER_SCRIPT = SCRIPT_DIR / "sanitize_public_eval_reports.py"


def _load_sanitizer() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "sanitize_public_eval_reports",
        SANITIZER_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sanitize_report_file_updates_nested_report_payload(monkeypatch, tmp_path):
    sanitizer = _load_sanitizer()
    repo_root = tmp_path / "repo"
    monkeypatch.setattr(sanitizer, "REPO_ROOT", repo_root)
    report_path = tmp_path / "report.json"
    payload = {
        "path": str(repo_root / "llm-distill" / "evals" / "reports" / "audit.json"),
        "nested": {
            "stderr_tail": "File " + str(tmp_path / "outside" / "tool.py")
        },
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    changed = sanitizer.sanitize_report_file(report_path)
    sanitized = json.loads(report_path.read_text(encoding="utf-8"))

    assert changed is True
    assert sanitized["path"] == "llm-distill/evals/reports/audit.json"
    assert sanitized["nested"]["stderr_tail"] == "File external_path_redacted"
    assert str(repo_root) not in json.dumps(sanitized)
    assert str(tmp_path) not in json.dumps(sanitized)


def test_sanitize_report_file_check_mode_does_not_write(monkeypatch, tmp_path):
    sanitizer = _load_sanitizer()
    repo_root = tmp_path / "repo"
    monkeypatch.setattr(sanitizer, "REPO_ROOT", repo_root)
    report_path = tmp_path / "report.json"
    payload = {"path": str(repo_root / "llm-distill" / "report.json")}
    original = json.dumps(payload, indent=2)
    report_path.write_text(original, encoding="utf-8")

    changed = sanitizer.sanitize_report_file(report_path, check=True)

    assert changed is True
    assert report_path.read_text(encoding="utf-8") == original
