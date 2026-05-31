import importlib.util
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "validate_public_repo_docs.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_public_repo_docs", VALIDATOR_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_public_readme_links_technical_distillation_breakdown_with_stats_and_tools():
    validator = _load_validator()

    report = validator.validate_public_docs(REPO_ROOT)

    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["evidence"]["readme_links_technical_breakdown"] is True
    assert report["evidence"]["architect_attribution_present"] is True
    assert report["evidence"]["required_tool_marker_count"] >= 10
    assert report["evidence"]["expected_stat_count"] >= 20
    assert report["evidence"]["values_redacted"] is True
