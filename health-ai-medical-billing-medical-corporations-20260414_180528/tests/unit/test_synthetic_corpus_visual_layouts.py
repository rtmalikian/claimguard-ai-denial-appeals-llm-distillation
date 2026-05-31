import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
GENERATOR = SCRIPT_DIR / "generate_synthetic_denial_appeal_corpus.py"
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


def test_visual_renderer_creates_html_font_and_layout_companions(tmp_path):
    generator = _load_script(GENERATOR, "generate_synthetic_denial_appeal_corpus")
    renderer = _load_script(RENDERER, "render_synthetic_corpus_visual_layouts")
    output_dir = tmp_path / "generated_synthetic_pairs"
    generator.generate_corpus(
        pair_count=12,
        output_dir=output_dir,
        enforce_requested_range=False,
    )

    report = renderer.render_visual_layouts(
        corpus_dir=output_dir,
        manifest_path=output_dir / "manifest_synthetic_12.json",
        visual_manifest_path=output_dir / "visual_manifest_synthetic_12.json",
        report_path=output_dir / "visual_render_report.json",
    )

    html_files = sorted((output_dir / "rendered_html").glob("*/*.html"))
    sample_html = html_files[0].read_text(encoding="utf-8")
    visual_manifest = json.loads(
        (output_dir / "visual_manifest_synthetic_12.json").read_text(encoding="utf-8")
    )

    assert report["ready"] is True
    assert report["evidence"]["letter_count"] == 24
    assert report["evidence"]["rendered_html_count"] == 24
    assert report["evidence"]["variant_counts"]["font_family"] == 8
    assert report["evidence"]["variant_counts"]["layout_profile"] == 12
    assert report["evidence"]["phi_scan"]["finding_count"] == 0
    assert len(html_files) == 24
    assert len(visual_manifest["records"]) == 24
    assert "font-family:" in sample_html
    assert "data-layout-profile=" in sample_html
    assert "Synthetic visual profile" in sample_html
