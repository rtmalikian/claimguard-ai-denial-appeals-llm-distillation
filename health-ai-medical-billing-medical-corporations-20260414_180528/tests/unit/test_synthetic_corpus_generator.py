import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
GENERATOR = SCRIPT_DIR / "generate_synthetic_denial_appeal_corpus.py"


def _load_generator() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "generate_synthetic_denial_appeal_corpus",
        GENERATOR,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generator_creates_varied_synthetic_pairs_with_format_profiles(tmp_path):
    generator = _load_generator()
    output_dir = tmp_path / "generated_synthetic_pairs"

    report = generator.generate_corpus(
        pair_count=12,
        output_dir=output_dir,
        enforce_requested_range=False,
    )

    manifest = json.loads(
        (output_dir / "manifest_synthetic_12.json").read_text(encoding="utf-8")
    )
    denial_files = sorted((output_dir / "letters").glob("*/*_denial.txt"))
    appeal_files = sorted((output_dir / "letters").glob("*/*_appeal.txt"))
    sample_denial = denial_files[0].read_text(encoding="utf-8")
    sample_appeal = appeal_files[0].read_text(encoding="utf-8")

    assert report["pair_count"] == 12
    assert report["letter_count"] == 24
    assert report["phi_scan"]["finding_count"] == 0
    assert len(manifest["records"]) == 24
    assert len(denial_files) == 12
    assert len(appeal_files) == 12
    assert "Training synthetic corpus pair" in sample_denial
    assert "Synthetic formatting profile" in sample_denial
    assert "Layout profile:" in sample_denial
    assert "Typography profile:" in sample_denial
    assert "Draft for human review." in sample_appeal
    assert "draft_for_human_review" in sample_appeal
    assert len(report["counts"]["denial_format"]) > 1
    assert len(report["counts"]["appeal_format"]) > 1
    assert len(report["counts"]["layout_profile"]) > 1
    assert len(report["counts"]["typography_profile"]) > 1
    assert len(report["counts"]["length_profile"]) > 1
    assert (output_dir / "README.md").exists()
