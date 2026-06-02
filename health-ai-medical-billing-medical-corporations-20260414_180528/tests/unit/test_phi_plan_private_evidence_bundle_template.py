import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLE_SCRIPT = (
    REPO_ROOT
    / "llm-distill"
    / "scripts"
    / "validate_phi_plan_private_evidence_bundle_template.py"
)
SCRIPT_DIR = BUNDLE_SCRIPT.parent


def _load_bundle_template() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_phi_plan_private_evidence_bundle_template",
        BUNDLE_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_private_evidence_bundle_template_is_source_control_ready():
    validator = _load_bundle_template()

    report = validator.build_report()

    assert report["safe_to_review"] is True
    assert report["template_ready"] is True
    assert report["source_control_ready"] is True
    assert report["domain_count"] == 9
    assert report["required_domain_count"] == 9
    assert report["private_input_env_count"] == 9
    assert report["missing_domains"] == []
    assert report["extra_domains"] == []
    assert report["invalid_domains"] == []
    assert report["raw_approval_values_included"] is False
    assert report["raw_document_content_included"] is False
    assert report["raw_phi_included"] is False
    assert report["raw_private_paths_included"] is False
    assert report["raw_secret_included"] is False
    serialized = json.dumps(report, sort_keys=True)
    assert "/Users/" not in serialized
    assert "/private/tmp/" not in serialized


def test_private_evidence_bundle_template_blocks_missing_domain(tmp_path):
    validator = _load_bundle_template()
    template = json.loads(validator.DEFAULT_TEMPLATE.read_text(encoding="utf-8"))
    template["domains"] = template["domains"][:-1]
    template["domain_count"] = len(template["domains"])
    template_path = tmp_path / "private_evidence_bundle.template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    report = validator.build_report(template_path)

    assert report["template_ready"] is False
    assert "private_evidence_bundle_template_domains_missing" in report["blockers"]
    assert "manual_production_gate_packet_evidence" in report["missing_domains"]
    assert report["template_path"] == "external_path_redacted"


def test_private_evidence_bundle_template_blocks_raw_private_path(tmp_path):
    validator = _load_bundle_template()
    template = json.loads(validator.DEFAULT_TEMPLATE.read_text(encoding="utf-8"))
    template["domains"][0]["private_input_env"] = (
        "/private/tmp/synthetic-private-evidence-path-should-not-emit.json"
    )
    template_path = tmp_path / "private_evidence_bundle.template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    report = validator.build_report(template_path)
    serialized = json.dumps(report, sort_keys=True)

    assert report["template_ready"] is False
    assert "private_evidence_bundle_template_raw_private_paths_included" in report[
        "blockers"
    ]
    assert "private_evidence_bundle_template_domain_metadata_invalid" in report[
        "blockers"
    ]
    assert report["raw_private_paths_included"] is True
    assert "/private/tmp/synthetic-private-evidence-path-should-not-emit.json" not in serialized
