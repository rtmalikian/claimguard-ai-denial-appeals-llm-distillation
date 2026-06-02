import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
HANDOFF_SCRIPT = REPO_ROOT / "llm-distill" / "scripts" / "validate_phi_plan_private_evidence_handoff.py"
SCRIPT_DIR = HANDOFF_SCRIPT.parent


def _load_handoff() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "validate_phi_plan_private_evidence_handoff",
        HANDOFF_SCRIPT,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_private_evidence_handoff_report_summarizes_current_private_blockers():
    handoff = _load_handoff()

    report = handoff.build_report()

    assert report["safe_to_review"] is True
    assert report["handoff_ready"] is True
    assert report["private_evidence_complete"] is False
    assert report["source_control_blocker_count"] == 0
    assert report["private_blocker_count"] == 9
    assert report["domain_count"] == 9
    assert report["operator_run_plan"]["ready"] is True
    assert report["operator_run_plan"]["step_count"] == 9
    assert report["operator_run_plan"]["manual_production_gate_runs_last"] is True
    assert report["operator_run_plan"]["raw_private_values_included"] is False
    assert report["operator_run_plan"]["raw_private_paths_included"] is False
    assert report["operator_run_plan"]["domain_order"][-1] == (
        "manual_production_gate_packet_evidence"
    )
    assert report["operator_run_plan"]["domain_order"][:3] == [
        "student_default_cutover_external_approval",
        "user_data_model_improvement_external_approval",
        "production_semantic_vector_backend",
    ]
    for step in report["operator_run_plan"]["steps"]:
        assert step["render_command_skeletons"]
        assert step["validate_command_skeletons"]
        assert step["values_redacted"] is True
        assert "outside-source-control" in step["private_input_placeholder"]
        assert "outside-source-control" in step["private_output_placeholder"]
    assert report["raw_approval_values_included"] is False
    assert report["raw_private_summary_paths_included"] is False
    assert report["raw_report_paths_included"] is False
    assert report["raw_phi_or_secret_values_included"] is False
    assert report["raw_document_content_included"] is False
    requirement_ids = {
        domain["requirement_id"] for domain in report["domain_statuses"]
    }
    assert requirement_ids == {
        "manual_production_gate_packet_evidence",
        "student_default_cutover_external_approval",
        "user_data_model_improvement_external_approval",
        "production_semantic_vector_backend",
        "production_corpus_expansion_beyond_synthetic",
        "production_prediction_fairness_monitoring",
        "backup_disaster_recovery_evidence",
        "dependency_security_evidence",
        "clearinghouse_submission_evidence",
    }
    serialized = json.dumps(report, sort_keys=True)
    assert "/Users/" not in serialized
    assert "/private/tmp/" not in serialized
    assert "synthetic-" not in serialized


def test_private_evidence_handoff_report_blocks_external_handoff(tmp_path):
    handoff = _load_handoff()
    external_handoff = tmp_path / "phi-plan-private-evidence-handoff.md"
    external_handoff.write_text(
        "# PHIplan Private Evidence Handoff\n\nboolean-only evidence\n",
        encoding="utf-8",
    )

    report = handoff.build_report(external_handoff)

    assert report["safe_to_review"] is True
    assert report["handoff_ready"] is False
    assert report["source_control_blocker_count"] > 0
    assert "handoff_document_outside_source_control" in report["source_control_blockers"]
    assert "handoff_document_required_markers_missing" in report["source_control_blockers"]
    assert report["handoff_document"]["handoff_path"] == "external_path_redacted"
