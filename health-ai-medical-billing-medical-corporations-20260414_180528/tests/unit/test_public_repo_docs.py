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
    assert report["evidence"]["readme_screenshot_count"] == 3
    assert report["evidence"]["public_generated_artifact_count"] == 4
    assert report["evidence"]["required_tool_marker_count"] >= 10
    assert report["evidence"]["required_completion_audit_marker_count"] >= 7
    assert report["evidence"]["expected_stat_count"] >= 30
    assert (
        report["evidence"]["completion_status"]
        == "not_complete_private_or_external_evidence_required"
    )
    assert report["evidence"]["values_redacted"] is True
