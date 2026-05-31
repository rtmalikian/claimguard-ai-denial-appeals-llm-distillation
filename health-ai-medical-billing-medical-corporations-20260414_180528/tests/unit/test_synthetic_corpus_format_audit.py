import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
GENERATOR = SCRIPT_DIR / "generate_synthetic_denial_appeal_corpus.py"
AUDITOR = SCRIPT_DIR / "audit_synthetic_denial_appeal_corpus.py"
RENDERER = SCRIPT_DIR / "render_synthetic_corpus_visual_layouts.py"


def _load_script(path: Path, name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _generate_fixture(tmp_path: Path, pair_count: int = 12) -> Path:
    generator = _load_script(GENERATOR, "generate_synthetic_denial_appeal_corpus")
    renderer = _load_script(RENDERER, "render_synthetic_corpus_visual_layouts")
    output_dir = tmp_path / "generated_synthetic_pairs"
    generator.generate_corpus(
        pair_count=pair_count,
        output_dir=output_dir,
        enforce_requested_range=False,
    )
    renderer.render_visual_layouts(
        corpus_dir=output_dir,
        manifest_path=output_dir / f"manifest_synthetic_{pair_count}.json",
        visual_manifest_path=output_dir / f"visual_manifest_synthetic_{pair_count}.json",
        report_path=output_dir / "visual_render_report.json",
    )
    return output_dir


def test_synthetic_corpus_format_audit_accepts_generated_fixture(tmp_path):
    auditor = _load_script(AUDITOR, "audit_synthetic_denial_appeal_corpus")
    output_dir = _generate_fixture(tmp_path)

    report = auditor.audit_corpus(
        corpus_dir=output_dir,
        generation_report_path=output_dir / "generation_report.json",
        manifest_path=output_dir / "manifest_synthetic_12.json",
        visual_render_report_path=output_dir / "visual_render_report.json",
        min_pairs=12,
        max_pairs=12,
    )

    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["evidence"]["pair_count"] == 12
    assert report["evidence"]["letter_count"] == 24
    assert report["evidence"]["unique_text_count"] == 24
    assert report["evidence"]["content_contract"]["profile_mismatch_count"] == 0
    assert report["evidence"]["content_contract"]["missing_marker_count"] == 0
    assert report["evidence"]["documentation"]["ready"] is True
    assert report["evidence"]["visual_rendering"]["ready"] is True
    assert report["evidence"]["visual_rendering"]["rendered_html_count"] == 24
    assert report["evidence"]["visual_rendering"]["font_family_count"] == 8
    assert len(report["evidence"]["counts"]["layout_profile"]) == 12
    assert len(report["evidence"]["counts"]["typography_profile"]) == 8
    assert len(report["evidence"]["counts"]["length_profile"]) == 6
    profile_matrix = report["evidence"]["profile_matrix_coverage"]
    assert profile_matrix["document_role"]["denial_letter"]["layout_profile"]["variant_count"] == 12
    assert profile_matrix["document_role"]["appeal_letter"]["typography_profile"]["variant_count"] == 8
    assert profile_matrix["document_role"]["denial_letter"]["length_profile"]["variant_count"] == 6
    assert profile_matrix["split"]["train"]["layout_profile"]["ready"] is True
    assert profile_matrix["split"]["valid"]["layout_profile"]["ready"] is True
    assert profile_matrix["split"]["test"]["typography_profile"]["ready"] is True
    appeal_quality = report["evidence"]["appeal_quality_contract"]
    assert appeal_quality["ready"] is True
    assert appeal_quality["checked_appeal_count"] == 12
    assert appeal_quality["missing_source_grounding_count"] == 0
    assert appeal_quality["missing_deadline_verification_count"] == 0
    assert appeal_quality["missing_phi_minimization_count"] == 0
    assert appeal_quality["missing_route_alignment_count"] == 0
    assert appeal_quality["unsupported_deadline_or_citation_claim_count"] == 0
    assert report["evidence"]["word_count"]["range"] >= 50
    assert report["evidence"]["phi_scan"]["finding_count"] == 0


def test_synthetic_corpus_format_audit_blocks_missing_appeal_draft_marker(tmp_path):
    auditor = _load_script(AUDITOR, "audit_synthetic_denial_appeal_corpus")
    output_dir = _generate_fixture(tmp_path, pair_count=3)
    appeal_path = next((output_dir / "letters").glob("*/*_appeal.txt"))
    appeal_text = appeal_path.read_text(encoding="utf-8").replace(
        "draft_for_human_review",
        "draft_pending_review",
    )
    appeal_path.write_text(appeal_text, encoding="utf-8")

    report = auditor.audit_corpus(
        corpus_dir=output_dir,
        generation_report_path=output_dir / "generation_report.json",
        manifest_path=output_dir / "manifest_synthetic_3.json",
        visual_render_report_path=output_dir / "visual_render_report.json",
        min_pairs=3,
        max_pairs=3,
    )

    assert report["ready"] is False
    assert report["evidence"]["content_contract"]["missing_marker_count"] >= 1
    assert any("draft_status_marker" in blocker for blocker in report["blockers"])


def test_synthetic_corpus_format_audit_blocks_duplicate_letter_text(tmp_path):
    auditor = _load_script(AUDITOR, "audit_synthetic_denial_appeal_corpus")
    output_dir = _generate_fixture(tmp_path, pair_count=3)
    denial_files = sorted((output_dir / "letters").glob("*/*_denial.txt"))
    duplicate_text = denial_files[0].read_text(encoding="utf-8")
    denial_files[1].write_text(duplicate_text, encoding="utf-8")

    report = auditor.audit_corpus(
        corpus_dir=output_dir,
        generation_report_path=output_dir / "generation_report.json",
        manifest_path=output_dir / "manifest_synthetic_3.json",
        visual_render_report_path=output_dir / "visual_render_report.json",
        min_pairs=3,
        max_pairs=3,
    )

    assert report["ready"] is False
    assert report["evidence"]["duplicate_text_group_count"] == 1
    assert any("unique text" in blocker for blocker in report["blockers"])


def test_synthetic_corpus_format_audit_blocks_missing_appeal_quality_gate(tmp_path):
    auditor = _load_script(AUDITOR, "audit_synthetic_denial_appeal_corpus")
    output_dir = _generate_fixture(tmp_path, pair_count=3)
    appeal_path = next((output_dir / "letters").glob("*/*_appeal.txt"))
    appeal_text = appeal_path.read_text(encoding="utf-8").replace(
        "minimum necessary PHI scope",
        "review scope",
    )
    appeal_path.write_text(appeal_text, encoding="utf-8")

    report = auditor.audit_corpus(
        corpus_dir=output_dir,
        generation_report_path=output_dir / "generation_report.json",
        manifest_path=output_dir / "manifest_synthetic_3.json",
        visual_render_report_path=output_dir / "visual_render_report.json",
        min_pairs=3,
        max_pairs=3,
    )

    assert report["ready"] is False
    assert report["evidence"]["appeal_quality_contract"]["ready"] is False
    assert report["evidence"]["appeal_quality_contract"]["missing_phi_minimization_count"] == 1
    assert any("appeal quality contract" in blocker for blocker in report["blockers"])


def test_synthetic_corpus_format_audit_report_is_json_serializable(tmp_path):
    auditor = _load_script(AUDITOR, "audit_synthetic_denial_appeal_corpus")
    output_dir = _generate_fixture(tmp_path, pair_count=3)
    report = auditor.audit_corpus(
        corpus_dir=output_dir,
        generation_report_path=output_dir / "generation_report.json",
        manifest_path=output_dir / "manifest_synthetic_3.json",
        visual_render_report_path=output_dir / "visual_render_report.json",
        min_pairs=3,
        max_pairs=3,
    )

    assert json.loads(json.dumps(report))["artifact"] == (
        "synthetic_denial_appeal_corpus_format_audit"
    )


def test_synthetic_corpus_format_audit_blocks_missing_visual_render_report(tmp_path):
    auditor = _load_script(AUDITOR, "audit_synthetic_denial_appeal_corpus")
    output_dir = _generate_fixture(tmp_path, pair_count=3)
    (output_dir / "visual_render_report.json").unlink()

    report = auditor.audit_corpus(
        corpus_dir=output_dir,
        generation_report_path=output_dir / "generation_report.json",
        manifest_path=output_dir / "manifest_synthetic_3.json",
        visual_render_report_path=output_dir / "visual_render_report.json",
        min_pairs=3,
        max_pairs=3,
    )

    assert report["ready"] is False
    assert any("visual_render_report.json" in blocker for blocker in report["blockers"])
