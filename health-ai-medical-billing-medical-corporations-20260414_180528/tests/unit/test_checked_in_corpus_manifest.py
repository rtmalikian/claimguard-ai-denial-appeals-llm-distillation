import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "llm-distill" / "scripts"
MANIFEST_PATH = REPO_ROOT / "llm-distill" / "data" / "corpus" / "manifest.json"


def _load_script(script_name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(script_name, SCRIPT_DIR / f"{script_name}.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_checked_in_corpus_manifest_exports_training_pairs_without_public_notes(tmp_path):
    exporter = _load_script("export_corpus_sft_data")
    phi_scan = _load_script("run_phi_scan")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = payload["records"]
    training_records = [record for record in records if record["training_eligible"] is True]
    public_records = [
        record for record in records if record["source_type"] == "public_government_source"
    ]

    assert payload["version"] == "1.3"
    assert len(records) == 13
    assert len(training_records) == 6
    assert len(public_records) == 7
    assert {record["pair_id"] for record in training_records} == {
        "PAIR-SYN-CORPUS-TRAIN",
        "PAIR-SYN-CORPUS-VALID",
        "PAIR-SYN-CORPUS-TEST",
    }
    assert {record["split"] for record in training_records} == {"train", "valid", "test"}
    assert {record["document_role"] for record in public_records} == {"rule_source"}
    assert {record["split"] for record in public_records} == {"none"}
    assert all(record["training_eligible"] is False for record in public_records)
    assert all(record["phi_status"] == "no_phi" for record in records)
    assert all(record["license_status"] == "public_government_source" for record in public_records)

    manifest_findings = phi_scan.scan_text(MANIFEST_PATH, MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest_findings == []
    for record in records:
        source_path = REPO_ROOT / record["source_url_or_path"]
        text = source_path.read_text(encoding="utf-8")
        checksum = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert checksum == record["checksum"]
        assert phi_scan.scan_text(source_path, text) == []

    output_dir = tmp_path / "mlx_sft_corpus"
    exported_manifest = exporter.export_corpus_sft(
        manifest_path=MANIFEST_PATH,
        output_dir=output_dir,
        model="test-model",
        adapter_path=tmp_path / "adapter",
    )

    assert exported_manifest["training_allowed"] is True
    assert exported_manifest["pair_count"] == 3
    assert exported_manifest["ignored_records"]["not_training_eligible"] == 7
    assert exported_manifest["coverage_counts"]["source_type"] == {
        "synthetic_deidentified_pair": 3
    }
    assert exported_manifest["split_counts"] == {"train": 1, "valid": 1, "test": 1}
    assert exported_manifest["micro_skill_coverage_complete"] is True
    assert exported_manifest["data_safety"]["phi_status"] == "no_phi"
    for split in ["train", "valid", "test"]:
        split_path = output_dir / f"{split}.jsonl"
        assert split_path.exists()
        assert phi_scan.scan_text(split_path, split_path.read_text(encoding="utf-8")) == []
